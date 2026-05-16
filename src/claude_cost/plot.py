"""matplotlib plots for an impacted DataFrame."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd


_BG = "#0e1117"
_FG = "#e6edf3"
_ACCENT = "#5eead4"
_ACCENT2 = "#fda4af"
_ACCENT3 = "#fbbf24"
_GRID = "#30363d"


def _style_axis(ax):
    ax.set_facecolor(_BG)
    for spine in ax.spines.values():
        spine.set_color(_GRID)
    ax.tick_params(colors=_FG)
    ax.xaxis.label.set_color(_FG)
    ax.yaxis.label.set_color(_FG)
    ax.title.set_color(_FG)
    ax.grid(True, color=_GRID, alpha=0.5, linewidth=0.5)


def daily_impact_plot(
    df: pd.DataFrame,
    output_path: Path | str,
    *,
    title: str = "Daily Claude Code footprint",
) -> Path:
    """Render a 3-panel plot: tokens, kg CO2e, liters of water, per day.

    Returns the resolved output path.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if df.empty:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=_BG)
        ax.text(
            0.5,
            0.5,
            "No usage records found.",
            ha="center",
            va="center",
            color=_FG,
            fontsize=14,
        )
        ax.set_facecolor(_BG)
        ax.axis("off")
        fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
        plt.close(fig)
        return output_path

    daily = (
        df.assign(date=df["timestamp"].dt.tz_convert("UTC").dt.date)
        .groupby("date")[["total_tokens", "kg_co2e", "liters_water"]]
        .sum()
    )

    fig, axes = plt.subplots(3, 1, figsize=(11, 8), sharex=True, facecolor=_BG)
    fig.suptitle(title, color=_FG, fontsize=14, fontweight="bold", y=0.995)

    panels = [
        ("Tokens / day", "total_tokens", _ACCENT, "tokens"),
        ("kg CO₂e / day", "kg_co2e", _ACCENT2, "kg CO₂e"),
        ("Liters of water / day", "liters_water", _ACCENT3, "L"),
    ]
    for ax, (label, col, color, unit) in zip(axes, panels):
        ax.bar(daily.index, daily[col], color=color, width=0.85, alpha=0.85)
        ax.set_ylabel(unit, color=_FG)
        ax.set_title(label, loc="left", color=_FG, fontsize=11)
        _style_axis(ax)

    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=10))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    return output_path


def by_repo_plot(
    df: pd.DataFrame,
    output_path: Path | str,
    *,
    top_n: int = 10,
    metric: str = "kg_co2e",
) -> Path:
    """Horizontal bar chart of the top-N repos by `metric`."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if df.empty:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=_BG)
        ax.text(0.5, 0.5, "No usage records found.", ha="center", va="center", color=_FG)
        ax.axis("off")
        fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
        plt.close(fig)
        return output_path

    grp = (
        df.assign(repo=df["cwd"].fillna("<unknown>"))
        .groupby("repo")[[metric, "total_tokens"]]
        .sum()
        .sort_values(metric, ascending=True)
        .tail(top_n)
    )
    short = [r.split("/")[-1] if "/" in r else r for r in grp.index]
    fig, ax = plt.subplots(figsize=(11, max(3, 0.5 * len(grp))), facecolor=_BG)
    ax.barh(short, grp[metric], color=_ACCENT2, alpha=0.9)
    units = {"kg_co2e": "kg CO₂e", "liters_water": "L water", "total_tokens": "tokens"}
    ax.set_xlabel(units.get(metric, metric), color=_FG)
    ax.set_title(f"Top {len(grp)} repos by {units.get(metric, metric)}", color=_FG, fontsize=12, loc="left")
    _style_axis(ax)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    return output_path


def cumulative_plot(
    df: pd.DataFrame,
    output_path: Path | str,
) -> Path:
    """Cumulative CO2e + liters-water over time on a single twin-axis chart."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if df.empty:
        fig, ax = plt.subplots(figsize=(10, 4), facecolor=_BG)
        ax.text(0.5, 0.5, "No usage records found.", ha="center", va="center", color=_FG)
        ax.axis("off")
        fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
        plt.close(fig)
        return output_path

    ts = df.sort_values("timestamp").set_index("timestamp")
    cum_co2 = ts["kg_co2e"].cumsum()
    cum_water = ts["liters_water"].cumsum()

    fig, ax = plt.subplots(figsize=(11, 5), facecolor=_BG)
    ax.plot(cum_co2.index, cum_co2.values, color=_ACCENT2, linewidth=2, label="kg CO₂e")
    ax.set_ylabel("kg CO₂e (cumulative)", color=_ACCENT2)
    ax.tick_params(axis="y", colors=_ACCENT2)
    _style_axis(ax)

    ax2 = ax.twinx()
    ax2.plot(cum_water.index, cum_water.values, color=_ACCENT3, linewidth=2, label="L water")
    ax2.set_ylabel("Liters water (cumulative)", color=_ACCENT3)
    ax2.tick_params(axis="y", colors=_ACCENT3)
    for spine in ax2.spines.values():
        spine.set_color(_GRID)

    ax.set_title("Cumulative Claude Code footprint", color=_FG, fontsize=13, loc="left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150, facecolor=_BG, bbox_inches="tight")
    plt.close(fig)
    return output_path
