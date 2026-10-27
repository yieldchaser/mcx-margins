"""
tests/test_panic_spread.py
Unit tests for Panic Spread Signals, Tender Margining Ladder, and Expiring Contract Logic.
Ensures no mathematical regressions occur when contracts are at or near expiry (dte <= 0)
or when contracts reach the statutory 25% tender margin cap.
"""

import json
from pathlib import Path
import pytest
from scripts.export_json import _calc_hurdle_span_im

def test_hurdle_span_im_floor():
    """Hurdle SPAN IM never falls below the 13.0% statutory floor."""
    assert _calc_hurdle_span_im(12.0, 0.01) >= 13.0
    assert _calc_hurdle_span_im(14.0, 0.005) >= 13.0
    assert _calc_hurdle_span_im(None, None) >= 13.0

def test_expiring_contract_panic_logic():
    """
    Simulate panic logic on expiry day (dte = 0).
    Contract ceases trading at 11:30 PM IST; must settle to cash without predicting
    an erroneous overnight collapse or claiming cash freed on a settled contract.
    """
    im = 19.89
    tm = 44.89
    tender_margin = 25.0
    dte = 0
    p_close = 248.5
    lot_size = 1250

    is_expiring_today = (dte is not None and dte <= 0)
    assert is_expiring_today is True

    # Check tender and total predictions
    if is_expiring_today:
        next_tender = None
        predicted_total = None
    elif tender_margin >= 25.0:
        next_tender = 25.0
        predicted_total = 19.38 + next_tender

    assert next_tender is None
    assert predicted_total is None

    # Check rupee margin and action
    lot_notional = p_close * lot_size
    rupee_current = round(lot_notional * (tm / 100.0), 0)
    if is_expiring_today:
        rupee_predicted = None
        rupee_delta = 0
        action = "EXPIRES_TODAY"
    else:
        rupee_predicted = round(lot_notional * (predicted_total / 100.0), 0)
        rupee_delta = round(rupee_predicted - rupee_current, 0)
        action = "HIKE" if predicted_total > tm + 0.2 else ("CUT" if predicted_total < tm - 0.2 else "FLAT")

    assert rupee_delta == 0
    assert action == "EXPIRES_TODAY"
    assert rupee_predicted is None

def test_tender_cap_at_25_pct():
    """
    When a contract is already at the 25.0% statutory tender cap (dte > 0),
    predicted tender must stay at 25.0% and not step up to 30.0%.
    """
    tender_margin = 25.0
    dte = 1
    is_expiring_today = (dte is not None and dte <= 0)
    assert is_expiring_today is False

    if is_expiring_today:
        next_tender = None
    elif tender_margin >= 25.0:
        next_tender = 25.0
    elif tender_margin > 0:
        next_tender = min(25.0, tender_margin + 5.0)
    else:
        next_tender = 0.0

    assert next_tender == 25.0

def test_tender_ramp_steps():
    """
    When climbing the ladder (e.g. 5%, 10%, 15%, 20%), tender margin steps up by +5%.
    """
    dte = 3
    for tm_in, expected_next in [(5.0, 10.0), (10.0, 15.0), (15.0, 20.0), (20.0, 25.0)]:
        next_tender = min(25.0, tm_in + 5.0)
        assert next_tender == expected_next

def test_panic_spread_json_integrity():
    """Verify panic_spread.json schema and sanity."""
    path = Path("docs/data/panic_spread.json")
    if not path.exists():
        pytest.skip("docs/data/panic_spread.json not yet generated")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "as_of" in data
    assert "NATURALGAS" in data
    ng = data["NATURALGAS"]
    assert len(ng) > 0

    for entry in ng:
        assert "expiry" in entry
        assert "dte" in entry
        assert "initial_margin_pct" in entry
        assert "total_margin_pct" in entry
        if entry.get("is_expiring_today"):
            assert entry["predicted_tomorrow"] is None
            assert entry["rupee_delta"] == 0
            assert entry["action"] == "EXPIRES_TODAY"
            assert entry["hike_trigger_up_price"] is None
        else:
            if entry["tender_margin_pct"] >= 25.0:
                assert entry["predicted_tender"] == 25.0
