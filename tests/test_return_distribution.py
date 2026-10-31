"""
Test Suite for Empirical Return Distribution & Fat-Tail Leptokurtosis Engine.

Validates:
1. Roll-consistent data extraction (5,079 rows for NATURALGAS, 932 for NATGASMINI).
2. Sample moments (Mean, Sample Std Dev, Annualized Vol, Fisher-Pearson Skewness, Excess Kurtosis).
3. Freedman-Diaconis adaptive binning formula (w = 2 * IQR * N^(-1/3)).
4. Continuous scaled Gaussian PDF overlay integration.
5. Clearinghouse Volatility Shock Multiplier gamma(z) = sqrt(0.94 + 0.06 * z^2).
6. Breakeven Survival Leverage for Long and Short portfolios and structural asymmetry.
7. Tail Risk Multiplier TRM_3s.
8. JSON schema integrity and manifest registration.
"""

import json
import math
import sqlite3
from pathlib import Path
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_JSON_PATH = REPO_ROOT / "docs" / "data" / "return_distribution.json"
MANIFEST_PATH = REPO_ROOT / "docs" / "data" / "manifest.json"
PRICE_DB_PATH = REPO_ROOT / "data" / "prices.db"
MARGIN_DB_PATH = REPO_ROOT / "data" / "margins.db"


@pytest.fixture(scope="module")
def dist_data():
    """Load the generated return_distribution.json payload."""
    if not DIST_JSON_PATH.exists():
        from scripts.export_return_distribution import export_return_distribution
        export_return_distribution()
    with open(DIST_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_schema_top_level(dist_data):
    """Verify top-level keys and timestamp format."""
    assert "generated_at" in dist_data
    assert "symbols" in dist_data
    assert "NATURALGAS" in dist_data["symbols"]
    assert "NATGASMINI" in dist_data["symbols"]


def test_sample_counts_and_dates(dist_data):
    """Verify exact roll-consistent trading session sample sizes and date boundaries."""
    ng = dist_data["symbols"]["NATURALGAS"]
    assert ng["sample_size"] == 5079
    assert ng["date_range"]["start"] == "2007-01-01"
    assert ng["date_range"]["end"] == "2026-10-29"
    assert ng["lot_size"] == 1250

    ngm = dist_data["symbols"]["NATGASMINI"]
    assert ngm["sample_size"] == 932
    assert ngm["date_range"]["start"] == "2023-03-14"
    assert ngm["date_range"]["end"] == "2026-10-29"
    assert ngm["lot_size"] == 250


def test_higher_central_moments(dist_data):
    """Verify higher central moments match verified empirical benchmarks."""
    ng_moments = dist_data["symbols"]["NATURALGAS"]["simple_returns"]["moments"]

    # Natural Gas 5,079 days baseline:
    # mu ~ -0.073%, s ~ 3.1812%, sigma_ann ~ 50.50%
    assert abs(ng_moments["mean"] - (-0.000730)) < 1e-4
    assert abs(ng_moments["median"] - (-0.000907)) < 1e-4
    assert abs(ng_moments["std_dev"] - 0.031812) < 1e-4
    expected_ann = ng_moments["std_dev"] * math.sqrt(252.0)
    assert abs(ng_moments["annualized_vol"] - expected_ann) < 1e-4

    # Positive skewness (upside squeeze tail)
    assert ng_moments["skewness"] > 0.30
    assert abs(ng_moments["skewness"] - 0.3486) < 1e-2

    # High excess kurtosis (heavy fat tails / leptokurtosis)
    assert ng_moments["excess_kurtosis"] > 4.5
    assert abs(ng_moments["excess_kurtosis"] - 4.9050) < 1e-2

    # NatGasMini moments
    ngm_moments = dist_data["symbols"]["NATGASMINI"]["simple_returns"]["moments"]
    assert abs(ngm_moments["mean"] - (-0.000318)) < 1e-4
    assert abs(ngm_moments["std_dev"] - 0.038213) < 1e-4
    assert ngm_moments["excess_kurtosis"] > 7.0


def test_freedman_diaconis_adaptive_binning(dist_data):
    """Verify Freedman-Diaconis adaptive binning formula: w = 2 * IQR * N^(-1/3)."""
    ng_sr = dist_data["symbols"]["NATURALGAS"]["simple_returns"]
    n = dist_data["symbols"]["NATURALGAS"]["sample_size"]
    iqr = ng_sr["quantiles"]["iqr"]
    expected_w_fd = 2.0 * iqr * (n ** (-1.0 / 3.0))

    bins_fd = ng_sr["bins_fd"]
    assert abs(bins_fd["bin_width"] - expected_w_fd) < 1e-5
    assert abs(bins_fd["bin_width"] - 0.004108) < 1e-5

    # Sum of counts must equal sample size N
    total_counts = sum(bins_fd["counts"])
    assert total_counts == n


def test_fixed_binning(dist_data):
    """Verify fixed 0.50% binning."""
    ng_sr = dist_data["symbols"]["NATURALGAS"]["simple_returns"]
    n = dist_data["symbols"]["NATURALGAS"]["sample_size"]
    bins_fixed = ng_sr["bins_fixed"]
    assert bins_fixed["bin_width"] == 0.0050
    assert sum(bins_fixed["counts"]) == n


def test_continuous_scaled_gaussian_overlay(dist_data):
    """
    Verify continuous scaled Gaussian PDF overlay:
    C(x) = [N * w / (s * sqrt(2*pi))] * exp(-(x - mu)^2 / (2*s^2)).
    Area under curve must approximate total observation count.
    """
    ng_sr = dist_data["symbols"]["NATURALGAS"]["simple_returns"]
    n = dist_data["symbols"]["NATURALGAS"]["sample_size"]
    s = ng_sr["moments"]["std_dev"]
    mu = ng_sr["moments"]["mean"]
    bins_fd = ng_sr["bins_fd"]
    w = bins_fd["bin_width"]

    for i in range(min(10, len(bins_fd["bin_centers"]))):
        x = bins_fd["bin_centers"][i]
        factor = (n * w) / (s * math.sqrt(2.0 * math.pi))
        expected_c = factor * math.exp(-0.5 * ((x - mu) / s) ** 2)
        assert abs(bins_fd["gaussian_fit"][i] - expected_c) < 0.05

    # Total area under Gaussian PDF matches N * w -> sum of C(x) approximates N
    sum_gaussian = sum(bins_fd["gaussian_fit"])
    assert abs(sum_gaussian - n) / n < 0.05


def test_clearinghouse_volatility_multiplier(dist_data):
    """
    Verify Clearinghouse Volatility Innovation Multiplier:
    gamma(z) = sqrt(0.94 + 0.06 * z^2).
    """
    matrix = dist_data["symbols"]["NATURALGAS"]["stress_matrix"]
    z_map = {row["z_score"]: row for row in matrix}

    # At z = 0: gamma(0) = sqrt(0.94) ~ 0.9695
    assert abs(z_map[0.0]["vol_multiplier"] - math.sqrt(0.94)) < 1e-4

    # At z = 1: gamma(1) = sqrt(0.94 + 0.06) = 1.0000
    assert abs(z_map[1.0]["vol_multiplier"] - 1.0000) < 1e-4

    # At z = 2: gamma(2) = sqrt(0.94 + 0.24) = sqrt(1.18) ~ 1.0863
    assert abs(z_map[2.0]["vol_multiplier"] - math.sqrt(1.18)) < 1e-4

    # At z = 3: gamma(3) = sqrt(0.94 + 0.54) = sqrt(1.48) ~ 1.2166
    assert abs(z_map[3.0]["vol_multiplier"] - math.sqrt(1.48)) < 1e-4

    # At z = 4: gamma(4) = sqrt(0.94 + 0.96) = sqrt(1.90) ~ 1.3784
    assert abs(z_map[4.0]["vol_multiplier"] - math.sqrt(1.90)) < 1e-4


def test_breakeven_survival_leverage_and_asymmetry(dist_data):
    """
    Verify Breakeven Position Survival Leverage:
    L_Survive_Long = 1 / [delta + (1 - delta) * M_pred]
    L_Survive_Short = 1 / [delta + (1 + delta) * M_pred]
    And prove structural asymmetry: L_Survive_Short < L_Survive_Long for all delta > 0.
    """
    matrix = dist_data["symbols"]["NATURALGAS"]["stress_matrix"]

    for row in matrix:
        z = row["z_score"]
        delta = abs(row["price_shock_pct"]) / 100.0
        m_pred = row["projected_margin_pct"] / 100.0

        expected_l_long = 1.0 / (delta + (1.0 - delta) * m_pred)
        expected_l_short = 1.0 / (delta + (1.0 + delta) * m_pred)

        assert abs(row["survival_leverage_long"] - expected_l_long) < 0.05
        assert abs(row["survival_leverage_short"] - expected_l_short) < 0.05

        if abs(z) > 0:
            # Short leverage must be strictly lower than Long leverage
            assert row["survival_leverage_short"] < row["survival_leverage_long"], (
                f"Asymmetry failed at z={z}: short {row['survival_leverage_short']} >= long {row['survival_leverage_long']}"
            )


def test_tail_risk_multiplier(dist_data):
    """Verify Tail Risk Multiplier TRM_3s is greater than 1.0 (leptokurtic fat tails)."""
    ng_tails = dist_data["symbols"]["NATURALGAS"]["simple_returns"]["tail_frequencies"]
    trm_3s = ng_tails["beyond_3s"]["trm"]
    assert trm_3s > 4.0
    assert abs(trm_3s - 4.38) < 0.05


def test_manifest_integration():
    """Verify docs/data/manifest.json contains return_distribution.json entry."""
    assert MANIFEST_PATH.exists()
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    dataset_paths = [d["path"] for d in manifest.get("datasets", [])]
    assert "data/return_distribution.json" in dataset_paths
