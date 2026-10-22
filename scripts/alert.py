#!/usr/bin/env python3
"""
MCX Margin Surveillance & Capital Call Alert Engine.

Surveys clearing house margin publications for NATURALGAS across ALL active expiries.
Evaluates:
  1. Unscheduled Volatility Shocks: |ΔSPAN Initial Margin| >= THRESHOLD (default 2.0 pp)
  2. Tender Delivery Window Entry: prev_tender == 0.0 and today_tender > 0.0
  3. Total Margin & Rupee Capital Impact per Lot (1,250 mmBtu)

Routine tender steps (+5% on days 2, 3, 4, 5) without SPAN shocks are suppressed
to eliminate false panic alarms, while compound events (volatility shock + tender ramp)
are fully attributed.
"""

import os
import smtplib
import sqlite3
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

THRESHOLD = 2.0  # percentage points for unscheduled SPAN IM shock
DB_PATH = Path("data/margins.db")
PRICE_DB_PATH = Path("data/prices.db")
ALERT_TO = "upadhyayprateek574@gmail.com"
ALERT_FROM = "upadhyayprateek574@gmail.com"
SYMBOL = "NATURALGAS"
LOT_SIZE = 1250  # mmBtu per lot for NATURALGAS

MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def compute_dte(expiry_str: str, ref_date_str: str) -> int | None:
    try:
        day = int(expiry_str[:2])
        mon = MONTH_MAP.get(expiry_str[2:5].upper())
        yr = int(expiry_str[5:])
        if not mon:
            return None
        expiry_date = date(yr, mon, day)
        ref = date.fromisoformat(ref_date_str)
        return (expiry_date - ref).days
    except Exception:
        return None


def get_latest_price(symbol: str, expiry: str) -> float | None:
    """Retrieve the latest settlement price for the contract from prices.db."""
    if not PRICE_DB_PATH.exists():
        return None
    try:
        with sqlite3.connect(PRICE_DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT close FROM prices 
                WHERE symbol=? AND expiry=? 
                ORDER BY date DESC LIMIT 1
            """, (symbol, expiry))
            row = cur.fetchone()
            return float(row[0]) if row and row[0] is not None else None
    except Exception:
        return None


def format_inr(val: float | int) -> str:
    """Format numbers into Indian numbering format (e.g. 96,020 or 1,25,000)."""
    try:
        n = int(round(val))
        s = str(abs(n))
        if len(s) <= 3:
            res = s
        else:
            last3 = s[-3:]
            rem = s[:-3]
            groups = []
            while len(rem) > 2:
                groups.insert(0, rem[-2:])
                rem = rem[:-2]
            if rem:
                groups.insert(0, rem)
            res = ",".join(groups) + "," + last3
        return ("-" if n < 0 else "") + res
    except Exception:
        return f"{val:,.0f}"


def get_margin_transitions(symbol: str = SYMBOL):
    """
    Compare the two most recent margin publication dates across all active expiries.
    Returns:
        (today_date, prev_date, triggered_contracts, all_active_contracts)
    """
    if not DB_PATH.exists():
        print(f"Database {DB_PATH} does not exist.")
        return None

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date DESC LIMIT 2",
        (symbol,)
    )
    dates = [r[0] for r in cur.fetchall()]
    if len(dates) < 2:
        conn.close()
        return None

    today_date, prev_date = dates[0], dates[1]

    # Today's records (break ties with highest file_id)
    cur.execute("""
        SELECT expiry, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct,
               daily_volatility, annualized_volatility, file_id
        FROM margins
        WHERE date=? AND symbol=?
        ORDER BY expiry, file_id DESC
    """, (today_date, symbol))
    today_rows = {}
    for r in cur.fetchall():
        if r[0] not in today_rows:
            today_rows[r[0]] = r

    # Previous day's records
    cur.execute("""
        SELECT expiry, initial_margin_pct, elm_pct, tender_margin_pct, total_margin_pct,
               daily_volatility, annualized_volatility, file_id
        FROM margins
        WHERE date=? AND symbol=?
        ORDER BY expiry, file_id DESC
    """, (prev_date, symbol))
    prev_rows = {}
    for r in cur.fetchall():
        if r[0] not in prev_rows:
            prev_rows[r[0]] = r

    conn.close()

    all_active = []
    for exp, t_row in today_rows.items():
        dte = compute_dte(exp, today_date)
        if dte is None or dte < 0:
            continue
        p_row = prev_rows.get(exp)
        if not p_row:
            continue

        price = get_latest_price(symbol, exp) or 260.0

        t_im, p_im = t_row[1], p_row[1]
        delta_im = t_im - p_im

        t_tender = t_row[3] or 0.0
        p_tender = p_row[3] or 0.0
        delta_tender = t_tender - p_tender

        t_total, p_total = t_row[4], p_row[4]
        delta_total = t_total - p_total

        is_vol_shock = abs(delta_im) >= THRESHOLD
        is_tender_entry = (p_tender == 0.0 and t_tender > 0.0)

        rupee_margin_today = round(LOT_SIZE * price * (t_total / 100))
        rupee_margin_prev = round(LOT_SIZE * price * (p_total / 100))
        rupee_delta = rupee_margin_today - rupee_margin_prev

        all_active.append({
            "expiry": exp,
            "dte": dte,
            "price": price,
            "is_vol_shock": is_vol_shock,
            "is_tender_entry": is_tender_entry,
            "qualifies": is_vol_shock or is_tender_entry,
            "delta_im": delta_im,
            "delta_tender": delta_tender,
            "delta_total": delta_total,
            "today_total": t_total,
            "prev_total": p_total,
            "today_im": t_im,
            "prev_im": p_im,
            "today_tender": t_tender,
            "prev_tender": p_tender,
            "today_elm": t_row[2] or 1.25,
            "daily_vol": t_row[5],
            "ann_vol": t_row[6],
            "rupee_margin_today": rupee_margin_today,
            "rupee_margin_prev": rupee_margin_prev,
            "rupee_delta": rupee_delta,
        })

    all_active.sort(key=lambda x: x["dte"])
    triggered = [e for e in all_active if e["qualifies"]]

    return today_date, prev_date, triggered, all_active


def send_email(subject, body_html):
    password = os.environ.get("ALERT_EMAIL_PASSWORD")
    if not password:
        print("No ALERT_EMAIL_PASSWORD set -- skipping email.")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ALERT_FROM
    msg["To"] = ALERT_TO
    msg.attach(MIMEText(body_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(ALERT_FROM, password)
            server.sendmail(ALERT_FROM, ALERT_TO, msg.as_string())
        safe_subject = subject.encode('ascii', 'replace').decode('ascii')
        print(f"Alert email sent: {safe_subject}")
    except Exception as e:
        print(f"Email failed: {e}")
        sys.exit(1)


def main():
    transitions = get_margin_transitions(SYMBOL)
    if not transitions:
        print("Not enough margin history to evaluate transitions.")
        return

    today_date, prev_date, triggered, all_active = transitions

    print(f"--- Margin Surveillance Run: {prev_date} -> {today_date} ---")
    print(f"Active liquid contracts surveyed: {len(all_active)}")
    for c in all_active:
        print(f"  {c['expiry']} ({c['dte']:>3}d DTE): IM={c['today_im']:>5.2f}% (d={c['delta_im']:>+5.2f}pp) | Tdr={c['today_tender']:>4.1f}% | Total={c['today_total']:>5.2f}% (d={c['delta_total']:>+5.2f}pp) | Rs/Lot=Rs.{format_inr(c['rupee_margin_today'])}")

    if not triggered:
        print(f"No qualifying margin shocks (SPAN IM >= {THRESHOLD}pp or tender entry) — no alert sent.")
        return

    # Identify primary triggered contract
    front_month = all_active[0] if all_active else None
    primary = None
    for t in triggered:
        if front_month and t["expiry"] == front_month["expiry"]:
            primary = t
            break
    if not primary:
        primary = max(triggered, key=lambda x: abs(x["delta_im"]))

    is_front = (front_month and primary["expiry"] == front_month["expiry"])
    contract_role = "Front Month" if is_front else f"Active Contract ({primary['dte']}d DTE)"

    # Determine event classification & color scheme
    if primary["is_vol_shock"] and primary["today_tender"] > 0:
        event_badge = "VOLATILITY SHOCK + TENDER RAMP"
        banner_title = "🔥 MCX Margin Alert"
        header_bg = "#f85149"  # Red
        total_color = "#f85149"
        delta_color = "#f85149" if primary["delta_total"] > 0 else "#3fb950"
        action_advice = (
            f"<strong>⚠️ Dual Risk Alert:</strong> SPAN volatility shock ({primary['delta_im']:+.2f} pp) "
            f"combined with physical tender delivery ramp (+{primary['delta_tender']:.2f}%). "
            f"Total overnight capital call is <strong>+₹{format_inr(primary['rupee_delta'])}/lot</strong>. "
            f"Ensure account carries adequate excess cash before 11:30 PM IST close to prevent RMS liquidation."
        )
        dir_text = "HIKED ▲" if primary["delta_total"] > 0 else "CUT ▼"
        subject = f"MCX Margin Alert: NATURALGAS {primary['expiry']} {dir_text} {abs(primary['delta_total']):.2f}pp (Total {primary['today_total']:.2f}%) — {today_date}"

    elif primary["is_vol_shock"]:
        is_hike = primary["delta_im"] > 0
        dir_text = "HIKED ▲" if is_hike else "CUT ▼"
        event_badge = f"VOLATILITY {dir_text}"
        banner_title = "🔥 MCX Margin Alert" if is_hike else "MCX Margin Update"
        header_bg = "#f85149" if is_hike else "#3fb950"
        total_color = "#f85149" if is_hike else "#3fb950"
        delta_color = total_color
        if is_hike:
            action_advice = (
                f"<strong>⚠️ Volatility Expansion:</strong> Clearing house raised base SPAN margin by "
                f"<strong>{primary['delta_im']:+.2f} pp</strong> due to elevated realized volatility "
                f"({(primary['daily_vol'] or 0)*100:.2f}% daily / {(primary['ann_vol'] or 0)*100:.1f}% ann). "
                f"Overnight capital required increases by <strong>+₹{format_inr(primary['rupee_delta'])}/lot</strong>."
            )
        else:
            action_advice = (
                f"<strong>✅ Capital Release:</strong> Clearing house volatility decayed. Base SPAN margin "
                f"reduced by <strong>{abs(primary['delta_im']):.2f} pp</strong>, freeing "
                f"~₹{format_inr(abs(primary['rupee_delta']))}/lot in account capital."
            )
        subject = f"MCX Margin Alert: NATURALGAS {primary['expiry']} {dir_text} {abs(primary['delta_im']):.2f}pp (Total {primary['today_total']:.2f}%) — {today_date}"

    elif primary["is_tender_entry"]:
        event_badge = "MANDATORY TENDER WINDOW"
        banner_title = "⏳ MCX Tender Delivery Notice"
        header_bg = "#d29922"  # Amber
        total_color = "#d29922"
        delta_color = "#d29922"
        action_advice = (
            f"<strong>⏳ Delivery Window Entrance:</strong> Contract entered the mandatory physical tender window "
            f"({primary['dte']} trading days to expiry). Initial tender step of +5.00% is now active. "
            f"Non-delivery participants should execute calendar rolls to next active contract to avoid delivery risk."
        )
        subject = f"MCX Notice: NATURALGAS {primary['expiry']} Entered Physical Tender Window (5% Step · {primary['dte']}d DTE) — {today_date}"
    else:
        subject = f"MCX Margin Alert: NATURALGAS Margin Revision — {today_date}"
        header_bg = "#f85149"
        total_color = "#f85149"
        delta_color = "#f85149"
        event_badge = "MARGIN REVISION"
        banner_title = "🔥 MCX Margin Alert"
        action_advice = "Check open positions and margin collateral."

    # Tender breakdown text
    if primary["today_tender"] > 0:
        tender_delta_str = f" (+{primary['delta_tender']:.2f} pp)" if primary['delta_tender'] > 0 else ""
        tender_breakdown_html = f"<span style='color:#f85149;'>{primary['today_tender']:.2f}%{tender_delta_str}</span> <span style='font-size:11px;color:#8b949e;'>(Physical Tender Ramp)</span>"
    else:
        tender_breakdown_html = "<span style='color:#8b949e;'>0.00%</span> <span style='font-size:11px;color:#8b949e;'>(Outside Tender)</span>"

    im_delta_color = "#f85149" if primary["delta_im"] > 0 else ("#3fb950" if primary["delta_im"] < 0 else "#8b949e")
    im_arrow = "▲" if primary["delta_im"] > 0 else ("▼" if primary["delta_im"] < 0 else "→")

    # Rupee delta text
    if primary["rupee_delta"] > 0:
        rupee_delta_formatted = f"+₹{format_inr(primary['rupee_delta'])} / Lot Call"
    elif primary["rupee_delta"] < 0:
        rupee_delta_formatted = f"-₹{format_inr(abs(primary['rupee_delta']))} / Lot Release"
    else:
        rupee_delta_formatted = "₹0 Shift"

    # Term Structure Overview Table (if multiple active expiries exist)
    term_structure_table_html = ""
    if len(all_active) > 1:
        rows_html = ""
        for c in all_active:
            is_p = (c["expiry"] == primary["expiry"])
            row_bg = "background:rgba(56, 139, 253, 0.08);" if is_p else ""
            c_delta_color = "#f85149" if c["delta_total"] > 0.2 else ("#3fb950" if c["delta_total"] < -0.2 else "#8b949e")
            rows_html += f"""
            <tr style="{row_bg}border-bottom:1px solid #21262d;">
              <td style="padding:7px 8px;font-weight:{'700' if is_p else '500'};color:#e6edf3;">{c['expiry']}</td>
              <td style="padding:7px 8px;color:#8b949e;text-align:center;">{c['dte']}d</td>
              <td style="padding:7px 8px;text-align:right;">{c['today_im']:.2f}%</td>
              <td style="padding:7px 8px;text-align:right;color:{'#f85149' if c['today_tender'] > 0 else '#8b949e'};">{c['today_tender']:.1f}%</td>
              <td style="padding:7px 8px;text-align:right;font-weight:700;color:{c_delta_color};">{c['today_total']:.2f}%</td>
              <td style="padding:7px 8px;text-align:right;color:#e6edf3;">₹{format_inr(c['rupee_margin_today'])}</td>
            </tr>
            """
        term_structure_table_html = f"""
        <div style="margin-top:16px;margin-bottom:18px;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#8b949e;margin-bottom:6px;font-weight:600;">
            Term Structure Snapshot (All Active Expiries)
          </div>
          <table style="width:100%;border-collapse:collapse;font-size:11.5px;background:#0d1117;border:1px solid #30363d;border-radius:6px;overflow:hidden;">
            <thead>
              <tr style="background:#21262d;color:#8b949e;font-size:10px;text-transform:uppercase;">
                <th style="padding:6px 8px;text-align:left;">Expiry</th>
                <th style="padding:6px 8px;text-align:center;">DTE</th>
                <th style="padding:6px 8px;text-align:right;">SPAN IM</th>
                <th style="padding:6px 8px;text-align:right;">Tender</th>
                <th style="padding:6px 8px;text-align:right;">Total %</th>
                <th style="padding:6px 8px;text-align:right;">₹/Lot</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>
        """

    body_html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0d1117; color:#e6edf3; padding:24px; margin:0;">
  <div style="max-width:540px; margin:0 auto; background:#161b22; border:1px solid #30363d; border-radius:12px; overflow:hidden; box-shadow:0 8px 24px rgba(0,0,0,0.5);">
    
    <!-- Top Header Banner -->
    <div style="background:{header_bg}; padding:18px 24px;">
      <div style="display:flex; justify-content:space-between; align-items:center;">
        <h2 style="margin:0; color:white; font-size:18px; font-weight:700; letter-spacing:0.02em;">{banner_title}</h2>
        <span style="background:rgba(0,0,0,0.25); color:white; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600;">{event_badge}</span>
      </div>
      <p style="margin:4px 0 0; color:rgba(255,255,255,0.9); font-size:12px;">NATURALGAS · Clearing House Risk Revision · {today_date}</p>
    </div>

    <!-- Body Container -->
    <div style="padding:20px 24px;">

      <!-- Primary Highlight Card -->
      <div style="background:#0d1117; border:1px solid #30363d; border-radius:8px; padding:16px; margin-bottom:18px;">
        <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:#8b949e; margin-bottom:6px; display:flex; justify-content:space-between;">
          <span>PRIMARY CONTRACT: <strong style="color:#e6edf3;">{primary['expiry']}</strong> ({primary['dte']}d DTE · {contract_role})</span>
          <span style="color:#58a6ff;">@ ₹{primary['price']:.2f} Settle</span>
        </div>
        
        <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:4px;">
          <div>
            <div style="font-size:10px; color:#8b949e; letter-spacing:0.04em;">TOTAL GROSS MARGIN</div>
            <div style="font-size:26px; font-weight:700; color:{total_color}; line-height:1.2;">
              {primary['today_total']:.2f}%
            </div>
          </div>
          <div style="text-align:right;">
            <div style="font-size:10px; color:#8b949e; letter-spacing:0.04em;">OVERNIGHT CAPITAL SHIFT</div>
            <div style="font-size:15px; font-weight:700; color:{delta_color};">
              {primary['delta_total']:+.2f} pp ({rupee_delta_formatted})
            </div>
          </div>
        </div>

        <div style="font-size:11.5px; color:#8b949e; border-top:1px solid #21262d; padding-top:8px; margin-top:8px; display:flex; justify-content:space-between;">
          <span>Rupee Capital Required / Lot (1,250 mmBtu):</span>
          <strong style="color:#e6edf3;">₹{format_inr(primary['rupee_margin_today'])}</strong>
        </div>
      </div>

      <!-- Component Breakdown Table -->
      <table style="width:100%; border-collapse:collapse; font-size:13px; margin-bottom:18px;">
        <tr style="border-bottom:1px solid #21262d;">
          <td style="padding:8px 0; color:#8b949e;">SPAN Initial Margin (IM)</td>
          <td style="padding:8px 0; text-align:right; font-weight:600;">
            {primary['today_im']:.2f}% 
            <span style="font-size:11px; color:{im_delta_color}; margin-left:4px;">
              ({primary['delta_im']:+.2f} pp {im_arrow})
            </span>
          </td>
        </tr>
        <tr style="border-bottom:1px solid #21262d;">
          <td style="padding:8px 0; color:#8b949e;">Tender Period Margin</td>
          <td style="padding:8px 0; text-align:right; font-weight:600;">
            {tender_breakdown_html}
          </td>
        </tr>
        <tr style="border-bottom:1px solid #21262d;">
          <td style="padding:8px 0; color:#8b949e;">Extreme Loss Margin (ELM)</td>
          <td style="padding:8px 0; text-align:right; font-weight:600;">{primary['today_elm']:.2f}%</td>
        </tr>
        <tr style="border-bottom:1px solid #21262d;">
          <td style="padding:8px 0; color:#8b949e;">Daily Realized Volatility</td>
          <td style="padding:8px 0; text-align:right; font-weight:600;">
            {(primary['daily_vol'] or 0)*100:.3f}% 
            <span style="font-size:11px; color:#8b949e;">(Ann. {(primary['ann_vol'] or 0)*100:.1f}%)</span>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#8b949e;">Previous Reading ({prev_date})</td>
          <td style="padding:8px 0; text-align:right; color:#8b949e;">{primary['prev_total']:.2f}% Total (IM: {primary['prev_im']:.2f}%)</td>
        </tr>
      </table>

      <!-- Term Structure Table (All Active Expiries) -->
      {term_structure_table_html}

      <!-- Actionable RMS / Risk Advisory Box -->
      <div style="background:#21262d; border-left:3px solid {header_bg}; border-radius:4px; padding:12px 14px; font-size:12.5px; line-height:1.5; color:#c9d1d9; margin-bottom:20px;">
        {action_advice}
      </div>

      <!-- Action Button -->
      <div style="text-align:center; margin-bottom:8px;">
        <a href="https://yieldchaser.github.io/mcx-margins/" style="display:inline-block; background:#388bfd; color:white; text-decoration:none; padding:10px 24px; border-radius:6px; font-weight:600; font-size:13px; letter-spacing:0.02em;">
          Open Dashboard →
        </a>
      </div>

    </div>

    <!-- Footer -->
    <div style="padding:12px 24px; border-top:1px solid #30363d; font-size:11px; color:#8b949e; text-align:center; background:#0d1117;">
      MCX CCL Automated Clearing Surveillance · Not financial advice · <a href="https://github.com/yieldchaser/mcx-margins" style="color:#58a6ff; text-decoration:none;">GitHub</a>
    </div>

  </div>
</body>
</html>"""

    send_email(subject, body_html)


if __name__ == "__main__":
    main()
