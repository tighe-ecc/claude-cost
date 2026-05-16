"""`claude-cost` command-line entry point."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import click
import pandas as pd
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from claude_cost import __version__
from claude_cost.model import Factors, apply_impact, load_default_factors, summarize
from claude_cost.parser import default_claude_dir, list_repos, load_dataframe
from claude_cost.plot import by_repo_plot, cumulative_plot, daily_impact_plot


_console = Console()


def _parse_since(since: str | None) -> datetime | None:
    """Accept `7d`, `30d`, `24h`, `1w`, or an ISO date/datetime."""
    if not since:
        return None
    s = since.strip().lower()
    units = {"d": "days", "h": "hours", "w": "weeks", "m": "minutes"}
    if s and s[-1] in units and s[:-1].isdigit():
        kwargs = {units[s[-1]]: int(s[:-1])}
        return datetime.now(tz=timezone.utc) - timedelta(**kwargs)
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as exc:
        raise click.BadParameter(
            f"--since must be `Nd`/`Nh`/`Nw` or ISO date/datetime, got {since!r}"
        ) from exc


def _filter(
    df: pd.DataFrame,
    since: datetime | None,
    until: datetime | None,
    model: str | None,
) -> pd.DataFrame:
    if df.empty:
        return df
    if since is not None:
        df = df[df["timestamp"] >= since]
    if until is not None:
        df = df[df["timestamp"] <= until]
    if model:
        df = df[df["model"].str.contains(model, case=False, na=False)]
    return df


def _render_summary(summary: dict[str, Any], factors: Factors) -> None:
    head = Text()
    head.append("\nClaude Code environmental footprint\n", style="bold")
    head.append(f"  records:    {summary['n_records']:,}\n", style="dim")
    head.append(f"  tokens:     {summary['total_tokens']:,}\n", style="dim")
    head.append(f"  energy:     {summary['total_kwh']:.4f} kWh\n", style="bold cyan")
    head.append(
        f"  carbon:     {summary['total_kg_co2e']*1000:.2f} g CO₂e   "
        f"({summary['total_kg_co2e']:.4f} kg)\n",
        style="bold magenta",
    )
    head.append(
        f"  water:      {summary['total_liters_water']*1000:.1f} mL    "
        f"({summary['total_liters_water']:.3f} L)\n",
        style="bold yellow",
    )
    head.append(f"  region:     {factors.region}  ", style="dim")
    head.append(
        f"({factors.kgco2e_per_kwh} kgCO₂e/kWh, {factors.liters_per_kwh} L/kWh)\n",
        style="dim",
    )
    _console.print(head)

    if summary["equivalents"]:
        eq = summary["equivalents"]
        eq_table = Table(title="In human terms", show_header=False, title_style="dim")
        eq_table.add_column("metric", style="dim")
        eq_table.add_column("value", justify="right")
        eq_table.add_row("car miles driven (US passenger avg)", f"{eq['miles_driven_us_passenger_car']:.2f}")
        eq_table.add_row("smartphone charges", f"{eq['smartphone_charges']:.1f}")
        eq_table.add_row("tree-years to sequester this CO₂e", f"{eq['tree_years_to_sequester']:.3f}")
        eq_table.add_row("8-min showers (water)", f"{eq['showers_8min']:.2f}")
        eq_table.add_row("500 mL water bottles", f"{eq['bottles_of_water_500ml']:.1f}")
        _console.print(eq_table)

    if summary["by_model"]:
        m = Table(title="By model", title_style="dim")
        m.add_column("model", style="cyan")
        m.add_column("tokens", justify="right")
        m.add_column("kWh", justify="right")
        m.add_column("g CO₂e", justify="right")
        m.add_column("L water", justify="right")
        for model, row in summary["by_model"].items():
            m.add_row(
                model,
                f"{int(row['total_tokens']):,}",
                f"{row['kwh']:.4f}",
                f"{row['kg_co2e']*1000:.2f}",
                f"{row['liters_water']:.3f}",
            )
        _console.print(m)

    if summary["by_repo"]:
        r = Table(title="By repo (top 10 by CO₂e)", title_style="dim")
        r.add_column("repo", style="cyan")
        r.add_column("tokens", justify="right")
        r.add_column("g CO₂e", justify="right")
        r.add_column("L water", justify="right")
        items = list(summary["by_repo"].items())[:10]
        for repo, row in items:
            short = repo.split("/")[-1] if "/" in repo else repo
            r.add_row(
                short,
                f"{int(row['total_tokens']):,}",
                f"{row['kg_co2e']*1000:.2f}",
                f"{row['liters_water']:.3f}",
            )
        _console.print(r)


_REGIONS = ["aws-us-west-2", "aws-us-east-1", "gcp-us-central1", "us-avg", "world-avg"]


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="claude-cost")
@click.pass_context
def main(ctx: click.Context) -> None:
    """Environmental footprint of your Claude Code usage."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(report)


_common = [
    click.option("--repo", "repo_filter", default=None, help="Filter to records whose cwd starts with this path."),
    click.option("--since", default=None, help="Only count records on/after this (Nd/Nh/Nw or ISO date)."),
    click.option("--until", default=None, help="Only count records on/before this (ISO date/datetime)."),
    click.option("--model", default=None, help="Substring filter on model ID."),
    click.option("--region", type=click.Choice(_REGIONS), default=None, help="Override grid+water factors with a named region."),
    click.option("--factors", "factors_path", type=click.Path(exists=True, dir_okay=False), default=None, help="Path to a custom factors.toml."),
    click.option("--claude-home", type=click.Path(file_okay=False), default=None, help="Override ~/.claude path."),
]


def _add_common(cmd):
    for dec in reversed(_common):
        cmd = dec(cmd)
    return cmd


def _build_df_and_factors(**kwargs) -> tuple[pd.DataFrame, Factors]:
    repo_filter = kwargs["repo_filter"]
    since = _parse_since(kwargs["since"])
    until = _parse_since(kwargs["until"])
    model_filter = kwargs["model"]
    region = kwargs["region"]
    factors_path = kwargs["factors_path"]
    claude_home = kwargs["claude_home"]

    if claude_home:
        os.environ["CLAUDE_HOME"] = str(Path(claude_home).expanduser())

    df = load_dataframe(cwd_filter=repo_filter)
    df = _filter(df, since, until, model_filter)
    factors = load_default_factors(path=factors_path, region=region)
    df = apply_impact(df, factors)
    return df, factors


@main.command()
@_add_common
def report(**kwargs) -> None:
    """Print a summary report to the terminal (this is the default command)."""
    df, factors = _build_df_and_factors(**kwargs)
    if df.empty:
        _console.print("[dim]No matching records.[/]")
        return
    _render_summary(summarize(df, factors), factors)


@main.command()
@_add_common
@click.option("--output", "-o", type=click.Path(), default="claude-cost-daily.png", help="PNG output path.")
@click.option("--cumulative/--no-cumulative", default=False, help="Cumulative line instead of daily bars.")
@click.option("--by-repo", "by_repo", is_flag=True, help="Top-N repos bar chart.")
@click.option("--metric", default="kg_co2e", help="Metric for --by-repo (kg_co2e, liters_water, total_tokens).")
@click.option("--show/--no-show", default=False, help="Open the PNG when done.")
def plot(output, cumulative, by_repo, metric, show, **kwargs) -> None:
    """Render a PNG plot of usage over time."""
    df, factors = _build_df_and_factors(**kwargs)
    if cumulative:
        path = cumulative_plot(df, output)
    elif by_repo:
        path = by_repo_plot(df, output, metric=metric)
    else:
        path = daily_impact_plot(df, output)
    _console.print(f"[green]Wrote[/] {path}")
    if show:
        _open_file(path)


def _open_file(path: Path) -> None:
    if sys.platform == "darwin":
        os.system(f'open "{path}"')
    elif sys.platform.startswith("linux"):
        os.system(f'xdg-open "{path}" 2>/dev/null')
    elif sys.platform == "win32":
        os.startfile(str(path))  # type: ignore[attr-defined]


@main.command()
@click.option("--claude-home", type=click.Path(file_okay=False), default=None)
def repos(claude_home) -> None:
    """List every cwd seen across transcripts, with record counts."""
    if claude_home:
        os.environ["CLAUDE_HOME"] = str(Path(claude_home).expanduser())
    rows = list_repos()
    if not rows:
        _console.print("[dim]No transcripts found under[/] " + str(default_claude_dir()))
        return
    t = Table(title=f"Repos in {default_claude_dir()}", title_style="dim")
    t.add_column("records", justify="right")
    t.add_column("cwd", style="cyan")
    for cwd, n in rows:
        t.add_row(f"{n:,}", cwd)
    _console.print(t)


@main.command(name="json")
@_add_common
def emit_json(**kwargs) -> None:
    """Dump the impacted summary as JSON (for scripts / dashboards)."""
    df, factors = _build_df_and_factors(**kwargs)
    s = summarize(df, factors)
    s["factors"] = {
        "region": factors.region,
        "kgco2e_per_kwh": factors.kgco2e_per_kwh,
        "kgco2e_per_kwh_source": factors.kgco2e_per_kwh_source,
        "liters_per_kwh": factors.liters_per_kwh,
        "liters_per_kwh_source": factors.liters_per_kwh_source,
    }
    click.echo(json.dumps(s, default=str, indent=2))


@main.command()
@_add_common
@click.option("--output", "-o", type=click.Path(), default="claude-cost-report.html")
def html(output, **kwargs) -> None:
    """Render a self-contained HTML report with embedded plots + sources."""
    from claude_cost.report import render_html

    df, factors = _build_df_and_factors(**kwargs)
    out = render_html(df, factors, Path(output))
    _console.print(f"[green]Wrote[/] {out}")


@main.command(name="install-skill")
@click.option(
    "--target",
    type=click.Path(),
    default=None,
    help="Target directory for the skill (default: ~/.claude/skills/claude-cost).",
)
@click.option("--force", is_flag=True, help="Overwrite if the skill already exists.")
def install_skill(target: str | None, force: bool) -> None:
    """Copy the bundled Claude Code skill into ~/.claude/skills/.

    After running this, the user can invoke `/claude-cost` from Claude Code.
    The skill itself just shells out to this CLI.
    """
    import shutil

    if target:
        dest = Path(target).expanduser()
    else:
        dest = Path.home() / ".claude" / "skills" / "claude-cost"

    src_root = Path(__file__).resolve().parent.parent.parent / "skill" / "claude-cost"
    if not src_root.exists():
        # Wheel-installed shared-data path.
        candidate = Path(sys.prefix) / "share" / "claude-cost" / "skill" / "claude-cost"
        if candidate.exists():
            src_root = candidate
    if not src_root.exists():
        _console.print(f"[red]Could not locate bundled skill source[/] (looked in {src_root}).")
        sys.exit(1)

    if dest.exists() and not force:
        _console.print(f"[yellow]{dest} already exists.[/] Re-run with --force to overwrite.")
        sys.exit(1)

    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src_root, dest)
    _console.print(f"[green]Installed[/] {dest}")
    _console.print("Run [bold]/claude-cost[/] from Claude Code to use it.")


@main.command()
def cite() -> None:
    """Print every source backing the default factors."""
    factors = load_default_factors()
    t = Table(title="Sources backing default factors", title_style="dim")
    t.add_column("key", style="dim")
    t.add_column("citation")
    t.add_column("url", style="blue")
    for key, src in factors.sources.items():
        cite_str = f"{src.get('authors','')} ({src.get('year','')}). {src.get('title','')}"
        venue = src.get("venue")
        if venue:
            cite_str += f". {venue}"
        t.add_row(key, cite_str, src.get("url", ""))
    _console.print(t)


if __name__ == "__main__":
    main()
