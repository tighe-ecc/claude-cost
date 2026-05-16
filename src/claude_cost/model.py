"""Convert token usage into environmental footprint.

The factors live in ``data/factors.toml`` and every default is sourced — see
the ``[sources]`` table in that file and ``CITATIONS.md`` in the repo root.
Conversion chain::

    tokens  --(energy factors)-->  kWh
             --(grid intensity)-->  kg CO2e
             --(water-use eff.)-->  liters

Different token classes carry different per-token energy because their compute
profile differs:

- **output tokens**: each one requires a full forward pass through the model.
  This is the dominant cost.
- **input tokens (uncached)**: one batched prefill pass — much cheaper per
  token than autoregressive generation.
- **cache-creation tokens**: same prefill cost as uncached input.
- **cache-read tokens**: server-side KV cache hit — only a few percent of the
  prefill energy survives the read.

Model classes (Opus / Sonnet / Haiku) get separate energy profiles because the
parameter count drives FLOPs-per-token linearly.

Everything is best-effort. We can't measure Anthropic's actual fleet, so the
output is **estimated order-of-magnitude impact**, not a sustainability audit.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover
    import tomli as tomllib


_DEFAULT_FACTORS_PATH = Path(__file__).parent / "data" / "factors.toml"


@dataclass(frozen=True)
class EnergyProfile:
    """Per-1000-tokens energy (Wh) for one model class."""

    wh_per_1k_output: float
    wh_per_1k_input: float
    wh_per_1k_cache_creation: float
    wh_per_1k_cache_read: float
    source: str

    def kwh(
        self,
        output_tokens: int,
        input_tokens: int,
        cache_creation_tokens: int,
        cache_read_tokens: int,
    ) -> float:
        wh = (
            output_tokens * self.wh_per_1k_output
            + input_tokens * self.wh_per_1k_input
            + cache_creation_tokens * self.wh_per_1k_cache_creation
            + cache_read_tokens * self.wh_per_1k_cache_read
        ) / 1000.0
        return wh / 1000.0  # Wh → kWh


@dataclass(frozen=True)
class Factors:
    """All cited conversion factors loaded from factors.toml."""

    profiles: dict[str, EnergyProfile]
    model_profiles: dict[str, str]
    default_profile: str
    kgco2e_per_kwh: float
    kgco2e_per_kwh_source: str
    liters_per_kwh: float
    liters_per_kwh_source: str
    equivalents: dict[str, float]
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)
    region: str = "default"

    def profile_for(self, model: str) -> EnergyProfile:
        name = self.model_profiles.get(model, self.default_profile)
        return self.profiles[name]


def load_default_factors(
    path: Path | str | None = None,
    *,
    region: str | None = None,
) -> Factors:
    """Load factors.toml. If `region` is given, swap in that region's grid+water."""
    factors_path = Path(path) if path else _DEFAULT_FACTORS_PATH
    with factors_path.open("rb") as fh:
        raw = tomllib.load(fh)

    profiles: dict[str, EnergyProfile] = {}
    for name, data in raw["energy"]["profiles"].items():
        profiles[name] = EnergyProfile(
            wh_per_1k_output=float(data["wh_per_1k_output_tokens"]),
            wh_per_1k_input=float(data["wh_per_1k_input_tokens"]),
            wh_per_1k_cache_creation=float(data["wh_per_1k_cache_creation_tokens"]),
            wh_per_1k_cache_read=float(data["wh_per_1k_cache_read_tokens"]),
            source=str(data.get("source", "")),
        )

    grid = raw["grid"]
    water = raw["water"]

    region_key = region or "default"
    if region and region in grid.get("regions", {}):
        kgco2e_per_kwh = float(grid["regions"][region]["kgco2e_per_kwh"])
        kgco2e_source = str(grid["regions"][region].get("source", grid["default"]["source"]))
    else:
        kgco2e_per_kwh = float(grid["default"]["kgco2e_per_kwh"])
        kgco2e_source = str(grid["default"]["source"])

    if region and region in water.get("regions", {}):
        liters_per_kwh = float(water["regions"][region]["liters_per_kwh"])
        water_source = str(water["regions"][region].get("source", water["default"]["source"]))
    else:
        liters_per_kwh = float(water["default"]["liters_per_kwh"])
        water_source = str(water["default"]["source"])

    return Factors(
        profiles=profiles,
        model_profiles={k: str(v) for k, v in raw["model_profiles"].items()},
        default_profile=str(raw["energy"]["default_profile"]),
        kgco2e_per_kwh=kgco2e_per_kwh,
        kgco2e_per_kwh_source=kgco2e_source,
        liters_per_kwh=liters_per_kwh,
        liters_per_kwh_source=water_source,
        equivalents={k: float(v) for k, v in raw["equivalents"].items()},
        sources={k: dict(v) for k, v in raw.get("sources", {}).items()},
        region=region_key,
    )


def apply_impact(df: pd.DataFrame, factors: Factors | None = None) -> pd.DataFrame:
    """Add ``kwh``, ``kg_co2e``, ``liters_water`` columns to a usage DataFrame.

    Input must come from :func:`claude_cost.parser.load_dataframe`.
    """
    if factors is None:
        factors = load_default_factors()

    if df.empty:
        out = df.copy()
        out["kwh"] = 0.0
        out["kg_co2e"] = 0.0
        out["liters_water"] = 0.0
        return out

    def _row_kwh(row: pd.Series) -> float:
        profile = factors.profile_for(row["model"])
        return profile.kwh(
            output_tokens=int(row["output_tokens"]),
            input_tokens=int(row["input_tokens"]),
            cache_creation_tokens=int(row["cache_creation_tokens"]),
            cache_read_tokens=int(row["cache_read_tokens"]),
        )

    out = df.copy()
    out["kwh"] = out.apply(_row_kwh, axis=1).astype(float)
    out["kg_co2e"] = out["kwh"] * factors.kgco2e_per_kwh
    out["liters_water"] = out["kwh"] * factors.liters_per_kwh
    return out


def summarize(df: pd.DataFrame, factors: Factors) -> dict[str, Any]:
    """Roll up totals and human-relatable equivalents from an impacted DataFrame."""
    if df.empty:
        return {
            "n_records": 0,
            "total_tokens": 0,
            "total_kwh": 0.0,
            "total_kg_co2e": 0.0,
            "total_liters_water": 0.0,
            "equivalents": {},
            "by_model": {},
            "by_repo": {},
        }

    total_kg = float(df["kg_co2e"].sum())
    total_l = float(df["liters_water"].sum())
    eq = factors.equivalents
    equivalents = {
        "miles_driven_us_passenger_car": total_kg / eq["kg_co2e_per_mile_driven"],
        "smartphone_charges": total_kg / eq["kg_co2e_per_smartphone_charge"],
        "tree_years_to_sequester": total_kg / eq["kg_co2e_per_tree_year"],
        "showers_8min": total_l / eq["liters_per_shower_8min"],
        "bottles_of_water_500ml": total_l / 0.5,
    }
    return {
        "n_records": int(len(df)),
        "total_tokens": int(df["total_tokens"].sum()),
        "total_kwh": float(df["kwh"].sum()),
        "total_kg_co2e": total_kg,
        "total_liters_water": total_l,
        "equivalents": equivalents,
        "by_model": (
            df.groupby("model")[["total_tokens", "kwh", "kg_co2e", "liters_water"]]
            .sum()
            .sort_values("kg_co2e", ascending=False)
            .to_dict(orient="index")
        ),
        "by_repo": (
            df.assign(repo=df["cwd"].fillna("<unknown>"))
            .groupby("repo")[["total_tokens", "kwh", "kg_co2e", "liters_water"]]
            .sum()
            .sort_values("kg_co2e", ascending=False)
            .to_dict(orient="index")
        ),
    }
