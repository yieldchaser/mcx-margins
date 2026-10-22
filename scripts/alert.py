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
    msg.attach(MIMEText(body_html, "html", "utf-8"))

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

        advisory_title = "CLEARING RISK ADVISORY"
        advisory_badge = "ACTION REQUIRED &middot; CAPITAL CALL"
        advisory_border = "rgba(248, 81, 73, 0.45)"
        advisory_badge_bg = "rgba(248, 81, 73, 0.15)"
        advisory_badge_color = "#f85149"
        advisory_badge_border = "rgba(248, 81, 73, 0.35)"
        driver_title = "Risk Drivers"
        driver_desc = f"SPAN Volatility Expansion ({primary['delta_im']:+.2f} pp) + Physical Tender Window Ramp (+{primary['delta_tender']:.2f}%)"
        impact_title = "Capital Call"
        impact_desc = f"+₹{format_inr(primary['rupee_delta'])} / Lot required overnight"
        impact_color = "#f85149"
        action_title = "RMS Protocol"
        action_desc = "Account must carry adequate free margin collateral before the 11:30 PM IST close to prevent automated RMS liquidation. Non-delivery participants should execute calendar rolls before physical tender lock-in."

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

        advisory_title = "CLEARING RISK ADVISORY" if is_hike else "MARGIN SURVEILLANCE UPDATE"
        advisory_badge = "ACTION REQUIRED &middot; CAPITAL CALL" if is_hike else "CAPITAL RELEASE"
        advisory_border = "rgba(248, 81, 73, 0.45)" if is_hike else "rgba(63, 185, 80, 0.45)"
        advisory_badge_bg = "rgba(248, 81, 73, 0.15)" if is_hike else "rgba(63, 185, 80, 0.15)"
        advisory_badge_color = "#f85149" if is_hike else "#3fb950"
        advisory_badge_border = "rgba(248, 81, 73, 0.35)" if is_hike else "rgba(63, 185, 80, 0.35)"

        if is_hike:
            driver_title = "Risk Driver"
            driver_desc = f"Base SPAN margin expansion ({primary['delta_im']:+.2f} pp) driven by elevated realized volatility ({(primary['daily_vol'] or 0)*100:.2f}% daily / {(primary['ann_vol'] or 0)*100:.1f}% ann)"
            impact_title = "Capital Call"
            impact_desc = f"+₹{format_inr(primary['rupee_delta'])} / Lot required overnight"
            impact_color = "#f85149"
            action_title = "RMS Protocol"
            action_desc = "Fund account with sufficient collateral buffer prior to 11:30 PM IST to absorb clearing house margin increases."
        else:
            driver_title = "Market Driver"
            driver_desc = f"Realized volatility cooled. Clearing house reduced base SPAN margin by {abs(primary['delta_im']):.2f} pp."
            impact_title = "Capital Effect"
            impact_desc = f"~₹{format_inr(abs(primary['rupee_delta']))} / Lot released in available trading margin"
            impact_color = "#3fb950"
            action_title = "Account Note"
            action_desc = "Lower margin requirements restore buying power and ease account leverage pressure."

        subject = f"MCX Margin Alert: NATURALGAS {primary['expiry']} {dir_text} {abs(primary['delta_im']):.2f}pp (Total {primary['today_total']:.2f}%) — {today_date}"

    elif primary["is_tender_entry"]:
        event_badge = "MANDATORY TENDER WINDOW"
        banner_title = "MCX Tender Delivery Notice"
        header_bg = "#d29922"  # Amber
        total_color = "#d29922"
        delta_color = "#d29922"

        advisory_title = "DELIVERY SURVEILLANCE NOTICE"
        advisory_badge = "CALENDAR ROLL MANDATE"
        advisory_border = "rgba(210, 153, 34, 0.45)"
        advisory_badge_bg = "rgba(210, 153, 34, 0.15)"
        advisory_badge_color = "#d29922"
        advisory_badge_border = "rgba(210, 153, 34, 0.35)"
        driver_title = "Calendar Event"
        driver_desc = f"Contract entered mandatory physical delivery tender period ({primary['dte']} trading days to expiry). Initial tender step of +5.00% active."
        impact_title = "Capital Impact"
        impact_desc = f"+₹{format_inr(primary['rupee_delta'])} / Lot tender step addition"
        impact_color = "#d29922"
        action_title = "Roll Mandate"
        action_desc = "Non-delivery participants should execute calendar rolls to next active contract to avoid progressive daily 5% margin escalations and physical settlement obligations."

        subject = f"MCX Notice: NATURALGAS {primary['expiry']} Entered Physical Tender Window (5% Step | {primary['dte']}d DTE) — {today_date}"
    else:
        subject = f"MCX Margin Alert: NATURALGAS Margin Revision — {today_date}"
        header_bg = "#f85149"
        total_color = "#f85149"
        delta_color = "#f85149"
        event_badge = "MARGIN REVISION"
        banner_title = "🔥 MCX Margin Alert"

        advisory_title = "SURVEILLANCE NOTICE"
        advisory_badge = "GENERAL NOTICE"
        advisory_border = "#30363d"
        advisory_badge_bg = "rgba(139, 148, 158, 0.15)"
        advisory_badge_color = "#8b949e"
        advisory_badge_border = "rgba(139, 148, 158, 0.35)"
        driver_title = "Event"
        driver_desc = "Clearing house adjusted margin parameters."
        impact_title = "Capital Impact"
        impact_desc = f"₹{format_inr(abs(primary['rupee_delta']))} / Lot shift"
        impact_color = "#e6edf3"
        action_title = "Advisory"
        action_desc = "Review active positions and collateral requirements in the dashboard."

    # Tender breakdown text
    if primary["today_tender"] > 0:
        tender_delta_str = f" (+{primary['delta_tender']:.2f} pp)" if primary['delta_tender'] > 0 else ""
        tender_breakdown_html = f"<span style='color:#f85149;'>{primary['today_tender']:.2f}%{tender_delta_str}</span> <span style='font-size:11px;color:#8b949e;white-space:nowrap;'>&middot; Tender Window</span>"
    else:
        tender_breakdown_html = "<span style='color:#8b949e;'>0.00%</span> <span style='font-size:11px;color:#8b949e;white-space:nowrap;'>&middot; Outside Window</span>"

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
            row_bg = "background-color:rgba(56, 139, 253, 0.08);" if is_p else ""
            c_delta_color = "#f85149" if c["delta_total"] > 0.2 else ("#3fb950" if c["delta_total"] < -0.2 else "#8b949e")
            rows_html += f"""
            <tr style="{row_bg}border-bottom:1px solid #21262d;">
              <td style="padding:7px 8px;font-weight:{'700' if is_p else '500'};color:#e6edf3;">{c['expiry']}</td>
              <td style="padding:7px 8px;color:#8b949e;text-align:center;font-variant-numeric:tabular-nums;">{c['dte']}d</td>
              <td style="padding:7px 8px;text-align:right;font-variant-numeric:tabular-nums;color:#e6edf3;">{c['today_im']:.2f}%</td>
              <td style="padding:7px 8px;text-align:right;color:{'#f85149' if c['today_tender'] > 0 else '#8b949e'};font-variant-numeric:tabular-nums;">{c['today_tender']:.1f}%</td>
              <td style="padding:7px 8px;text-align:right;font-weight:700;color:{c_delta_color};font-variant-numeric:tabular-nums;">{c['today_total']:.2f}%</td>
              <td style="padding:7px 8px;text-align:right;color:#e6edf3;font-variant-numeric:tabular-nums;">₹{format_inr(c['rupee_margin_today'])}</td>
            </tr>
            """
        term_structure_table_html = f"""
        <div style="margin-top:14px;margin-bottom:16px;">
          <div style="font-size:10.5px;text-transform:uppercase;letter-spacing:0.07em;color:#8b949e;margin-bottom:6px;font-weight:700;">
            Term Structure Snapshot (All Active Expiries)
          </div>
          <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size:11.5px;background-color:#0d1117;border:1px solid #30363d;border-radius:6px;overflow:hidden;">
            <thead>
              <tr style="background-color:#21262d;color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:0.04em;">
                <th style="padding:7px 8px;text-align:left;font-weight:600;">Expiry</th>
                <th style="padding:7px 8px;text-align:center;font-weight:600;">DTE</th>
                <th style="padding:7px 8px;text-align:right;font-weight:600;">SPAN IM</th>
                <th style="padding:7px 8px;text-align:right;font-weight:600;">Tender</th>
                <th style="padding:7px 8px;text-align:right;font-weight:600;">Total %</th>
                <th style="padding:7px 8px;text-align:right;font-weight:600;">₹/Lot</th>
              </tr>
            </thead>
            <tbody>
              {rows_html}
            </tbody>
          </table>
        </div>
        """

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="dark light">
  <meta name="supported-color-schemes" content="dark light">
  <title>{banner_title}</title>
  <style>
    :root {{
      color-scheme: dark light;
      supported-color-schemes: dark light;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      margin: 0;
      padding: 0;
      background-color: #0d1117;
      color: #e6edf3;
      -webkit-font-smoothing: antialiased;
    }}
    table {{
      border-collapse: collapse;
      mso-table-lspace: 0pt;
      mso-table-rspace: 0pt;
    }}
    td {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}
    @media only screen and (max-width: 580px) {{
      .wrapper-td {{ padding: 10px 8px !important; }}
      .card-td {{ padding: 14px 14px !important; }}
      .banner-td {{ padding: 14px 16px !important; }}
      .kpi-num {{ font-size: 24px !important; }}
    }}
  </style>
</head>
<body style="font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; margin:0; padding:0; background-color:#0d1117; color:#e6edf3;">
  <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#0d1117; width:100%;">
    <tr>
      <td class="wrapper-td" align="center" style="padding:24px 12px;">
        
        <!-- Main Email Container Box -->
        <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width:540px; background-color:#161b22; border:1px solid #30363d; border-radius:10px; overflow:hidden;">
          
          <!-- Top Header Banner -->
          <tr>
            <td class="banner-td" style="background-color:{header_bg}; padding:16px 20px;">
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="vertical-align:middle;">
                    <div style="color:#ffffff; font-size:18px; font-weight:700; letter-spacing:0.02em; line-height:1.2;">
                      {banner_title}
                    </div>
                  </td>
                  <td style="text-align:right; vertical-align:middle;">
                    <span style="display:inline-block; background-color:rgba(0,0,0,0.28); color:#ffffff; padding:3px 8px; border-radius:4px; font-size:10px; font-weight:700; letter-spacing:0.04em; text-transform:uppercase; white-space:nowrap;">
                      {event_badge}
                    </span>
                  </td>
                </tr>
              </table>
              <div style="margin-top:4px; color:rgba(255,255,255,0.92); font-size:11.5px; letter-spacing:0.01em;">
                NATURALGAS &middot; Clearing House Risk Revision &middot; {today_date}
              </div>
            </td>
          </tr>

          <!-- Inner Content Body -->
          <tr>
            <td class="card-td" style="padding:18px 20px;">

              <!-- Primary Highlight Card -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#0d1117; border:1px solid #30363d; border-radius:8px; overflow:hidden; margin-bottom:16px;">
                <tr>
                  <td style="padding:14px 16px;">
                    
                    <!-- Contract Header Row -->
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-bottom:10px;">
                      <tr>
                        <td style="font-size:11px; text-transform:uppercase; letter-spacing:0.06em; color:#8b949e; font-weight:600;">
                          PRIMARY CONTRACT: <strong style="color:#e6edf3;">{primary['expiry']}</strong>
                          <span style="color:#8b949e; font-weight:400; margin-left:2px;">({primary['dte']}d DTE &middot; {contract_role})</span>
                        </td>
                        <td style="text-align:right; font-size:11.5px; color:#58a6ff; font-weight:600; white-space:nowrap;">
                          @ ₹{primary['price']:.2f} Settle
                        </td>
                      </tr>
                    </table>

                    <!-- Big KPI Metrics Row -->
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-bottom:8px;">
                      <tr>
                        <td style="vertical-align:bottom; width:45%;">
                          <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.06em; color:#8b949e; margin-bottom:3px; font-weight:600;">
                            TOTAL GROSS MARGIN
                          </div>
                          <div class="kpi-num" style="font-size:28px; font-weight:800; color:{total_color}; line-height:1; font-variant-numeric:tabular-nums;">
                            {primary['today_total']:.2f}%
                          </div>
                        </td>
                        <td style="vertical-align:bottom; text-align:right; width:55%;">
                          <div style="font-size:10px; text-transform:uppercase; letter-spacing:0.06em; color:#8b949e; margin-bottom:3px; font-weight:600;">
                            OVERNIGHT CAPITAL SHIFT
                          </div>
                          <div style="font-size:16px; font-weight:700; color:{delta_color}; line-height:1.2; font-variant-numeric:tabular-nums;">
                            {primary['delta_total']:+.2f} pp
                          </div>
                          <div style="font-size:12px; font-weight:600; color:{delta_color}; margin-top:2px;">
                            ({rupee_delta_formatted})
                          </div>
                        </td>
                      </tr>
                    </table>

                    <!-- Rupee Capital Row -->
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="border-top:1px solid #21262d; margin-top:10px;">
                      <tr>
                        <td style="font-size:11.5px; color:#8b949e; padding-top:8px;">
                          Rupee Capital Required / Lot (1,250 mmBtu):
                        </td>
                        <td style="text-align:right; font-size:13px; font-weight:700; color:#e6edf3; padding-top:8px; font-variant-numeric:tabular-nums;">
                          ₹{format_inr(primary['rupee_margin_today'])}
                        </td>
                      </tr>
                    </table>

                  </td>
                </tr>
              </table>

              <!-- Component Breakdown Table -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size:12.5px; margin-bottom:16px;">
                <tr style="border-bottom:1px solid #21262d;">
                  <td style="padding:7px 0; color:#8b949e;">SPAN Initial Margin (IM)</td>
                  <td style="padding:7px 0; text-align:right; font-weight:600; font-variant-numeric:tabular-nums; color:#e6edf3;">
                    {primary['today_im']:.2f}% 
                    <span style="font-size:11px; color:{im_delta_color}; margin-left:4px;">
                      ({primary['delta_im']:+.2f} pp {im_arrow})
                    </span>
                  </td>
                </tr>
                <tr style="border-bottom:1px solid #21262d;">
                  <td style="padding:7px 0; color:#8b949e;">Tender Period Margin</td>
                  <td style="padding:7px 0; text-align:right; font-weight:600; font-variant-numeric:tabular-nums;">
                    {tender_breakdown_html}
                  </td>
                </tr>
                <tr style="border-bottom:1px solid #21262d;">
                  <td style="padding:7px 0; color:#8b949e;">Extreme Loss Margin (ELM)</td>
                  <td style="padding:7px 0; text-align:right; font-weight:600; font-variant-numeric:tabular-nums; color:#e6edf3;">{primary['today_elm']:.2f}%</td>
                </tr>
                <tr style="border-bottom:1px solid #21262d;">
                  <td style="padding:7px 0; color:#8b949e;">Daily Realized Volatility</td>
                  <td style="padding:7px 0; text-align:right; font-weight:600; font-variant-numeric:tabular-nums; color:#e6edf3;">
                    {(primary['daily_vol'] or 0)*100:.3f}% 
                    <span style="font-size:11px; color:#8b949e; font-weight:400;">(Ann. {(primary['ann_vol'] or 0)*100:.1f}%)</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:7px 0; color:#8b949e;">Previous Reading ({prev_date})</td>
                  <td style="padding:7px 0; text-align:right; color:#8b949e; font-variant-numeric:tabular-nums;">{primary['prev_total']:.2f}% Total (IM: {primary['prev_im']:.2f}%)</td>
                </tr>
              </table>

              <!-- Term Structure Table (All Active Expiries) -->
              {term_structure_table_html}

              <!-- Institutional Risk & Clearing Advisory Module -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color:#0d1117; border:1px solid {advisory_border}; border-radius:8px; overflow:hidden; margin-top:14px; margin-bottom:18px;">
                <tr>
                  <td style="padding:9px 14px; background-color:#21262d; border-bottom:1px solid #30363d;">
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0">
                      <tr>
                        <td style="font-size:10.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.07em; color:#8b949e;">
                          {advisory_title}
                        </td>
                        <td style="text-align:right;">
                          <span style="display:inline-block; font-size:9.5px; font-weight:700; text-transform:uppercase; letter-spacing:0.04em; padding:2px 7px; border-radius:3px; background-color:{advisory_badge_bg}; color:{advisory_badge_color}; border:1px solid {advisory_badge_border}; white-space:nowrap;">
                            {advisory_badge}
                          </span>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td style="padding:12px 14px;">
                    <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="font-size:12px;">
                      <tr>
                        <td style="padding:4px 0; color:#8b949e; width:92px; vertical-align:top; font-weight:600; white-space:nowrap;">{driver_title}:</td>
                        <td style="padding:4px 0 4px 6px; color:#e6edf3; font-weight:600;">{driver_desc}</td>
                      </tr>
                      <tr>
                        <td style="padding:4px 0; color:#8b949e; vertical-align:top; font-weight:600; white-space:nowrap;">{impact_title}:</td>
                        <td style="padding:4px 0 4px 6px; color:{impact_color}; font-weight:700; font-variant-numeric:tabular-nums;">{impact_desc}</td>
                      </tr>
                      <tr>
                        <td style="padding:6px 0 2px 0; color:#8b949e; vertical-align:top; font-weight:600; white-space:nowrap;">{action_title}:</td>
                        <td style="padding:6px 0 2px 6px; color:#c9d1d9; line-height:1.5;">{action_desc}</td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Action Button -->
              <table role="presentation" width="100%" border="0" cellspacing="0" cellpadding="0" style="margin-bottom:8px;">
                <tr>
                  <td align="center">
                    <a href="https://yieldchaser.github.io/mcx-margins/" style="display:inline-block; background-color:#1f6feb; color:#ffffff; text-decoration:none; padding:10px 24px; border-radius:6px; font-weight:600; font-size:13px; letter-spacing:0.02em;">
                      Open Dashboard →
                    </a>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:12px 20px; border-top:1px solid #30363d; font-size:11px; color:#8b949e; text-align:center; background-color:#0d1117;">
              MCX CCL Automated Clearing Surveillance &middot; Not financial advice &middot; <a href="https://github.com/yieldchaser/mcx-margins" style="color:#58a6ff; text-decoration:none;">GitHub</a>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>
</body>
</html>"""

    send_email(subject, body_html)


if __name__ == "__main__":
    main()
