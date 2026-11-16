"""
Blue Margin — Zero-Dependency MCX Market Session & Seasonal Calendar Helper
scripts/mcx_session.py

Dynamically resolves MCX trading session state, season (Summer vs Winter),
and exchange closing time based on US Daylight Saving Time (DST).

Requires ONLY standard library (datetime, timezone, timedelta, zoneinfo).
Zero external dependencies (no pandas, pyarrow, fyers). Safe for minimal CI runners.
"""

from datetime import datetime, timezone, timedelta
try:
    import zoneinfo
except ImportError:
    zoneinfo = None

# MCX Full Holidays (both Morning and Evening sessions closed)
MCX_FULL_HOLIDAYS = {
    # 2026
    "2026-01-26": "Republic Day",
    "2026-03-03": "Holi",
    "2026-03-21": "Id-Ul-Fitr (Ramzan Id)",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-27": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-08-15": "Independence Day",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-10": "Diwali Balipratipada",
    "2026-11-24": "Gurunanak Jayanti",
    "2026-12-25": "Christmas",
    # 2027
    "2027-01-26": "Republic Day",
    "2027-03-22": "Holi",
    "2027-03-26": "Good Friday",
    "2027-04-14": "Dr. Ambedkar Jayanti",
    "2027-05-01": "Maharashtra Day",
    "2027-08-15": "Independence Day",
    "2027-10-02": "Mahatma Gandhi Jayanti",
    "2027-12-25": "Christmas",
}

# MCX Evening-Only Holidays (Morning 09:00-17:00 closed, Evening 17:00-close open)
MCX_EVENING_ONLY_HOLIDAYS = {
    # 2026
    "2026-02-15": "Mahashivratri",
    "2026-03-27": "Ram Navami",
    "2026-03-31": "Mahavir Jayanti",
    # 2027
    "2027-03-06": "Mahashivratri",
    "2027-04-16": "Ram Navami",
}

def get_mcx_session_info(dt_ist=None):
    """
    Dynamically resolves MCX trading session state, season (Summer vs Winter),
    and exchange closing time based on US Daylight Saving Time (DST).

    MCX Trading Session Rules:
    - Pre-Market Standby: 08:50 AM to 09:00 AM IST
    - Morning Open: 09:00:00 AM IST
    - Summer Closing (US DST EDT active): 23:30 PM IST (11:30 PM IST)
    - Winter Closing (US Standard EST active): 23:55 PM IST (11:55 PM IST)
    - Weekends (Saturday & Sunday): Market is CLOSED all day.
    """
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    if dt_ist is None:
        dt_ist = datetime.now(ist_tz)
    elif dt_ist.tzinfo is None:
        dt_ist = dt_ist.replace(tzinfo=ist_tz)
    else:
        dt_ist = dt_ist.astimezone(ist_tz)

    # 1. Determine Summer (US EDT) vs Winter (US EST)
    is_dst = False
    try:
        if zoneinfo:
            ny_tz = zoneinfo.ZoneInfo("America/New_York")
            dt_ny = dt_ist.astimezone(timezone.utc).astimezone(ny_tz)
            is_dst = bool(dt_ny.dst() and dt_ny.dst().total_seconds() != 0)
    except Exception:
        pass

    if not is_dst and (not zoneinfo or "dt_ny" not in locals()):
        # Fallback standard calendar calculation (starts 2nd Sun March, ends 1st Sun Nov)
        year = dt_ist.year
        mar1 = datetime(year, 3, 1, tzinfo=ist_tz)
        mar_second_sun = 1 + (6 - mar1.weekday()) % 7 + 7
        dst_start = datetime(year, 3, mar_second_sun, 2, 0, tzinfo=ist_tz)
        nov1 = datetime(year, 11, 1, tzinfo=ist_tz)
        dst_end = datetime(year, 11, 1 + (6 - nov1.weekday()) % 7, 2, 0, tzinfo=ist_tz)
        is_dst = dst_start <= dt_ist < dst_end

    season_name = "Summer (US DST)" if is_dst else "Winter (US Standard)"
    close_hour, close_min = (23, 30) if is_dst else (23, 55)
    close_total_mins = close_hour * 60 + close_min
    open_standby_mins = 8 * 60 + 50 # 08:50 AM IST

    # 2. Check Weekends
    if dt_ist.weekday() >= 5: # 5 = Saturday, 6 = Sunday
        day_name = "Saturday" if dt_ist.weekday() == 5 else "Sunday"
        return False, f"Weekend ({day_name})", season_name, (close_hour, close_min)

    # 3. Check Known Full-Day MCX Trading Holidays
    date_str = dt_ist.strftime("%Y-%m-%d")
    if date_str in MCX_FULL_HOLIDAYS:
        return False, f"MCX Full Holiday ({MCX_FULL_HOLIDAYS[date_str]})", season_name, (close_hour, close_min)

    # 4. Check Holidays where Morning session is closed but Evening opens at 17:00 IST
    cur_mins = dt_ist.hour * 60 + dt_ist.minute
    if date_str in MCX_EVENING_ONLY_HOLIDAYS and cur_mins < 17 * 60:
        return False, f"MCX Holiday Morning Session ({MCX_EVENING_ONLY_HOLIDAYS[date_str]} - opens at 17:00 IST)", season_name, (close_hour, close_min)

    # 5. Check Time Windows
    if cur_mins < open_standby_mins:
        return False, f"Overnight / Pre-market (opens at 09:00 IST, standby 08:50 IST)", season_name, (close_hour, close_min)
    if cur_mins > close_total_mins:
        return False, f"Post-close night session (closed at {close_hour}:{close_min:02d} IST)", season_name, (close_hour, close_min)

    return True, f"Market OPEN ({season_name}, 09:00 - {close_hour}:{close_min:02d} IST)", season_name, (close_hour, close_min)
