#!/usr/bin/env python3
"""Send email alert if front-month NATURALGAS margin changed by > THRESHOLD pct points."""

import sqlite3
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

THRESHOLD = 2.0  # percentage points
DB_PATH = Path("data/margins.db")
ALERT_TO = "upadhyayprateek574@gmail.com"
ALERT_FROM = "upadhyayprateek574@gmail.com"
SYMBOL = "NATURALGAS"


def get_front_month_margins():
    """Return list of (date, initial_margin_pct, expiry, total_margin_pct, daily_vol, ann_vol)
    for the two most recent trading days."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get two most recent distinct dates
    cur.execute(
        "SELECT DISTINCT date FROM margins WHERE symbol=? ORDER BY date DESC LIMIT 2",
        (SYMBOL,)
    )
    dates = [r[0] for r in cur.fetchall()]
    if len(dates) < 2:
        conn.close()
        return None

    results = []
    for d in dates:
        # Front month = smallest non-negative DTE
        cur.execute("""
            SELECT m.initial_margin_pct, m.expiry, m.total_margin_pct,
                   m.daily_volatility, m.annualized_volatility
            FROM margins m
            WHERE m.date = ? AND m.symbol = ?
            ORDER BY m.expiry ASC
            LIMIT 1
        """, (d, SYMBOL))
        row = cur.fetchone()
        if row:
            results.append((d, row[0], row[1], row[2], row[3], row[4]))

    conn.close()
    return results if len(results) == 2 else None


def send_email(subject, body_html):
    password = os.environ.get("ALERT_EMAIL_PASSWORD")
    if not password:
        print("No ALERT_EMAIL_PASSWORD set — skipping email.")
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
        print(f"Alert email sent: {subject}")
    except Exception as e:
        print(f"Email failed: {e}")
        sys.exit(1)


def main():
    data = get_front_month_margins()
    if not data:
        print("Not enough data to compare.")
        return

    today_date, today_margin, today_expiry, today_total, today_vol, today_ann_vol = data[0]
    prev_date, prev_margin = data[1][0], data[1][1]

    change = today_margin - prev_margin
    abs_change = abs(change)

    print(f"Today ({today_date}): {today_margin:.2f}% | Prev ({prev_date}): {prev_margin:.2f}% | Change: {change:+.2f}%")

    if abs_change < THRESHOLD:
        print(f"Change {abs_change:.2f}% below threshold {THRESHOLD}% — no alert.")
        return

    direction = "HIKED ▲" if change > 0 else "CUT ▼"
    color = "#f85149" if change > 0 else "#3fb950"
    action_advice = (
        "Consider pre-funding your margin account. MCX may continue hiking if volatility remains elevated."
        if change > 0 else
        "Capital efficiency improving. Favorable conditions for new or expanded positions."
    )

    subject = f"MCX Margin Alert: NATURALGAS {direction} {abs_change:.2f}pp — {today_date}"

    body_html = f"""
    <html><body style="font-family:Inter,Arial,sans-serif;background:#0d1117;color:#e6edf3;padding:24px;">
      <div style="max-width:520px;margin:0 auto;background:#161b22;border:1px solid #30363d;border-radius:12px;overflow:hidden;">
        <div style="background:{color};padding:16px 24px;">
          <h2 style="margin:0;color:white;font-size:18px;">🔥 MCX Margin Alert</h2>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.85);font-size:13px;">NATURALGAS Front Month · {today_date}</p>
        </div>
        <div style="padding:24px;">
          <table style="width:100%;border-collapse:collapse;font-size:14px;">
            <tr><td style="padding:8px 0;color:#8b949e;">Contract</td><td style="padding:8px 0;font-weight:600;">{today_expiry}</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Today's Margin</td><td style="padding:8px 0;font-weight:700;font-size:18px;color:{color};">{today_margin:.2f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Previous ({prev_date})</td><td style="padding:8px 0;">{prev_margin:.2f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Change</td><td style="padding:8px 0;font-weight:700;color:{color};">{change:+.2f} pp &nbsp; {direction}</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Daily Vol</td><td style="padding:8px 0;">{(today_vol or 0)*100:.3f}%</td></tr>
            <tr><td style="padding:8px 0;color:#8b949e;">Ann. Vol</td><td style="padding:8px 0;">{(today_ann_vol or 0)*100:.1f}%</td></tr>
          </table>
          <div style="margin-top:16px;padding:12px 16px;background:#21262d;border-radius:8px;font-size:13px;color:#8b949e;">
            💡 {action_advice}
          </div>
          <div style="margin-top:20px;text-align:center;">
            <a href="https://yieldchaser.github.io/mcx-margins/" style="display:inline-block;background:#388bfd;color:white;text-decoration:none;padding:10px 24px;border-radius:6px;font-weight:600;font-size:13px;">
              Open Dashboard →
            </a>
          </div>
        </div>
        <div style="padding:12px 24px;border-top:1px solid #30363d;font-size:11px;color:#8b949e;text-align:center;">
          MCX CCL data · Not financial advice · <a href="https://github.com/yieldchaser/mcx-margins" style="color:#388bfd;">GitHub</a>
        </div>
      </div>
    </body></html>
    """

    send_email(subject, body_html)


if __name__ == "__main__":
    main()
