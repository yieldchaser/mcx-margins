"""
Database module for MCX CCL margin data.
Uses SQLite for storage.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path("data/margins.db")


def get_connection() -> sqlite3.Connection:
    """Get a database connection, creating the DB if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS margins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                expiry TEXT NOT NULL DEFAULT '',
                instrument_id TEXT,
                file_id INTEGER,
                initial_margin_pct REAL,
                elm_pct REAL,
                tender_margin_pct REAL,
                total_margin_pct REAL,
                additional_long_margin_pct REAL,
                additional_short_margin_pct REAL,
                special_long_margin_pct REAL,
                special_short_margin_pct REAL,
                delivery_margin_pct REAL,
                daily_volatility REAL,
                annualized_volatility REAL,
                raw_data TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(date, symbol, expiry, file_id)
            );

            CREATE INDEX IF NOT EXISTS idx_margins_date ON margins(date);
            CREATE INDEX IF NOT EXISTS idx_margins_symbol ON margins(symbol);
            CREATE INDEX IF NOT EXISTS idx_margins_date_symbol ON margins(date, symbol);
        """)
        conn.commit()
        print("[db] Database initialized")
    finally:
        conn.close()


def upsert_margin(row: dict) -> bool:
    """
    Insert or update a margin record.
    Returns True if inserted/updated, False if error.
    """
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO margins (
                date, symbol, expiry, instrument_id, file_id,
                initial_margin_pct, elm_pct,
                tender_margin_pct, total_margin_pct,
                additional_long_margin_pct, additional_short_margin_pct,
                special_long_margin_pct, special_short_margin_pct,
                delivery_margin_pct, daily_volatility, annualized_volatility,
                raw_data
            ) VALUES (
                :date, :symbol, :expiry, :instrument_id, :file_id,
                :initial_margin_pct, :elm_pct,
                :tender_margin_pct, :total_margin_pct,
                :additional_long_margin_pct, :additional_short_margin_pct,
                :special_long_margin_pct, :special_short_margin_pct,
                :delivery_margin_pct, :daily_volatility, :annualized_volatility,
                :raw_data
            )
            ON CONFLICT(date, symbol, expiry, file_id) DO UPDATE SET
                instrument_id = excluded.instrument_id,
                initial_margin_pct = excluded.initial_margin_pct,
                elm_pct = excluded.elm_pct,
                tender_margin_pct = excluded.tender_margin_pct,
                total_margin_pct = excluded.total_margin_pct,
                additional_long_margin_pct = excluded.additional_long_margin_pct,
                additional_short_margin_pct = excluded.additional_short_margin_pct,
                special_long_margin_pct = excluded.special_long_margin_pct,
                special_short_margin_pct = excluded.special_short_margin_pct,
                delivery_margin_pct = excluded.delivery_margin_pct,
                daily_volatility = excluded.daily_volatility,
                annualized_volatility = excluded.annualized_volatility,
                raw_data = excluded.raw_data
        """, {
            "date": row.get("date"),
            "symbol": row.get("symbol"),
            "expiry": row.get("expiry", ""),
            "instrument_id": row.get("instrument_id"),
            "file_id": row.get("file_id"),
            "initial_margin_pct": row.get("initial_margin_pct"),
            "elm_pct": row.get("elm_pct"),
            "tender_margin_pct": row.get("tender_margin_pct"),
            "total_margin_pct": row.get("total_margin_pct"),
            "additional_long_margin_pct": row.get("additional_long_margin_pct"),
            "additional_short_margin_pct": row.get("additional_short_margin_pct"),
            "special_long_margin_pct": row.get("special_long_margin_pct"),
            "special_short_margin_pct": row.get("special_short_margin_pct"),
            "delivery_margin_pct": row.get("delivery_margin_pct"),
            "daily_volatility": row.get("daily_volatility"),
            "annualized_volatility": row.get("annualized_volatility"),
            "raw_data": json.dumps(row),
        })
        conn.commit()
        return True
    except Exception as e:
        print(f"[db] Error upserting row: {e}")
        return False
    finally:
        conn.close()


def get_margins(symbol: str = None, date: str = None) -> list[dict]:
    """Query margins from the database."""
    conn = get_connection()
    try:
        query = "SELECT * FROM margins WHERE 1=1"
        params = []

        if symbol:
            query += " AND UPPER(symbol) LIKE UPPER(?)"
            params.append(f"%{symbol}%")

        if date:
            query += " AND date = ?"
            params.append(date)

        query += " ORDER BY date DESC, symbol ASC, expiry ASC"

        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_summary() -> list[dict]:
    """Get a summary of all data in the database."""
    conn = get_connection()
    try:
        cursor = conn.execute("""
            SELECT
                symbol,
                COUNT(*) as record_count,
                MIN(date) as earliest_date,
                MAX(date) as latest_date,
                AVG(initial_margin_pct) as avg_initial_margin,
                MIN(initial_margin_pct) as min_initial_margin,
                MAX(initial_margin_pct) as max_initial_margin
            FROM margins
            WHERE initial_margin_pct IS NOT NULL
            GROUP BY symbol
            ORDER BY symbol ASC
        """)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_dates() -> list[str]:
    """Get all unique dates in the database."""
    conn = get_connection()
    try:
        cursor = conn.execute("SELECT DISTINCT date FROM margins ORDER BY date DESC")
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()
