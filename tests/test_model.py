"""Tests for the env-impact conversion model."""

from __future__ import annotations

import pandas as pd
import pytest

from claude_cost.model import apply_impact, load_default_factors, summarize


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-05-01T10:00:00Z", "2026-05-02T11:00:00Z"], utc=True
            ),
            "session_id": ["s1", "s2"],
            "request_id": ["r1", "r2"],
            "cwd": ["/r/a", "/r/b"],
            "model": ["claude-opus-4-7", "claude-haiku-4-5"],
            "input_tokens": [100, 100],
            "output_tokens": [1000, 1000],
            "cache_creation_tokens": [0, 0],
            "cache_read_tokens": [0, 0],
            "service_tier": ["standard", "standard"],
            "total_input_tokens": [100, 100],
            "total_tokens": [1100, 1100],
        }
    )


def test_apply_impact_assigns_columns(sample_df: pd.DataFrame) -> None:
    factors = load_default_factors()
    out = apply_impact(sample_df, factors)
    assert {"kwh", "kg_co2e", "liters_water"}.issubset(out.columns)
    assert (out["kwh"] >= 0).all()


def test_haiku_uses_less_energy_than_opus(sample_df: pd.DataFrame) -> None:
    factors = load_default_factors()
    out = apply_impact(sample_df, factors)
    opus_kwh = out.loc[out["model"] == "claude-opus-4-7", "kwh"].iloc[0]
    haiku_kwh = out.loc[out["model"] == "claude-haiku-4-5", "kwh"].iloc[0]
    assert haiku_kwh < opus_kwh


def test_carbon_and_water_scale_with_region(sample_df: pd.DataFrame) -> None:
    default = load_default_factors()
    oregon = load_default_factors(region="aws-us-west-2")
    out_default = apply_impact(sample_df, default)
    out_oregon = apply_impact(sample_df, oregon)
    # Oregon eGRID NWPP < US-avg → less CO2 for the same kWh.
    assert out_oregon["kg_co2e"].sum() < out_default["kg_co2e"].sum()
    # kWh itself doesn't depend on region.
    assert pytest.approx(out_default["kwh"].sum()) == out_oregon["kwh"].sum()


def test_summarize_equivalents_present(sample_df: pd.DataFrame) -> None:
    factors = load_default_factors()
    out = apply_impact(sample_df, factors)
    s = summarize(out, factors)
    assert s["n_records"] == 2
    assert s["total_tokens"] == 2200
    eq = s["equivalents"]
    assert {"miles_driven_us_passenger_car", "smartphone_charges",
            "tree_years_to_sequester", "showers_8min"}.issubset(eq.keys())


def test_synthetic_model_has_zero_impact() -> None:
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-05-01T10:00:00Z"], utc=True),
            "session_id": ["s1"],
            "request_id": ["r1"],
            "cwd": ["/r/a"],
            "model": ["<synthetic>"],
            "input_tokens": [0],
            "output_tokens": [0],
            "cache_creation_tokens": [0],
            "cache_read_tokens": [0],
            "service_tier": [None],
            "total_input_tokens": [0],
            "total_tokens": [0],
        }
    )
    factors = load_default_factors()
    out = apply_impact(df, factors)
    assert out["kwh"].sum() == 0.0
