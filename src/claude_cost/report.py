"""Self-contained HTML report. Plots embedded as base64 PNGs."""

from __future__ import annotations

import base64
import html
import io
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from claude_cost.model import Factors, summarize
from claude_cost.plot import by_repo_plot, cumulative_plot, daily_impact_plot


def _png_to_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def render_html(df: pd.DataFrame, factors: Factors, output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    s = summarize(df, factors)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        p_daily = daily_impact_plot(df, tmp / "daily.png")
        p_cum = cumulative_plot(df, tmp / "cumulative.png")
        p_repo = by_repo_plot(df, tmp / "by_repo.png", metric="kg_co2e")
        b_daily = _png_to_b64(p_daily) if p_daily.exists() else ""
        b_cum = _png_to_b64(p_cum) if p_cum.exists() else ""
        b_repo = _png_to_b64(p_repo) if p_repo.exists() else ""

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    n = s["n_records"]
    total_tokens = s["total_tokens"]
    kwh = s["total_kwh"]
    kg = s["total_kg_co2e"]
    liters = s["total_liters_water"]
    eq = s["equivalents"]

    sources_rows = []
    for key, src in factors.sources.items():
        cite = f"{src.get('authors','')} ({src.get('year','')}). <em>{html.escape(src.get('title',''))}</em>"
        venue = src.get("venue")
        if venue:
            cite += f". {html.escape(venue)}"
        url = src.get("url", "")
        url_cell = f'<a href="{html.escape(url)}">{html.escape(url)}</a>' if url else ""
        sources_rows.append(
            f"<tr><td><code>{html.escape(key)}</code></td>"
            f"<td>{cite}</td><td>{url_cell}</td></tr>"
        )

    model_rows = []
    for model, row in s["by_model"].items():
        model_rows.append(
            f"<tr><td><code>{html.escape(model)}</code></td>"
            f"<td>{int(row['total_tokens']):,}</td>"
            f"<td>{row['kwh']:.4f}</td>"
            f"<td>{row['kg_co2e']*1000:.2f}</td>"
            f"<td>{row['liters_water']:.3f}</td></tr>"
        )

    repo_rows = []
    for repo, row in list(s["by_repo"].items())[:20]:
        repo_rows.append(
            f"<tr><td><code>{html.escape(repo)}</code></td>"
            f"<td>{int(row['total_tokens']):,}</td>"
            f"<td>{row['kg_co2e']*1000:.2f}</td>"
            f"<td>{row['liters_water']:.3f}</td></tr>"
        )

    html_str = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>claude-cost report</title>
<style>
  :root {{
    --bg: #0e1117; --panel: #161b22; --fg: #e6edf3; --dim: #8b949e;
    --accent: #5eead4; --accent2: #fda4af; --accent3: #fbbf24;
    --border: #30363d;
  }}
  * {{ box-sizing: border-box; }}
  body {{ background: var(--bg); color: var(--fg); font-family: -apple-system,
         BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; margin: 0;
         line-height: 1.5; }}
  .wrap {{ max-width: 1100px; margin: 0 auto; padding: 32px 24px 64px; }}
  h1, h2 {{ font-weight: 600; letter-spacing: -0.01em; }}
  h1 {{ font-size: 28px; margin: 0 0 4px; }}
  h2 {{ font-size: 18px; margin: 32px 0 12px; color: var(--accent); }}
  .meta {{ color: var(--dim); font-size: 13px; margin-bottom: 24px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
           gap: 12px; margin: 12px 0 24px; }}
  .card {{ background: var(--panel); border: 1px solid var(--border);
           border-radius: 10px; padding: 16px; }}
  .card .label {{ color: var(--dim); font-size: 12px; text-transform: uppercase;
                  letter-spacing: 0.05em; }}
  .card .value {{ font-size: 28px; font-weight: 600; margin-top: 6px; }}
  .card .sub {{ color: var(--dim); font-size: 13px; margin-top: 2px; }}
  .accent-co2 .value {{ color: var(--accent2); }}
  .accent-water .value {{ color: var(--accent3); }}
  .accent-energy .value {{ color: var(--accent); }}
  img {{ max-width: 100%; border-radius: 10px; border: 1px solid var(--border);
         background: var(--panel); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }}
  th, td {{ padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ color: var(--dim); font-weight: 500; text-transform: uppercase;
        font-size: 11px; letter-spacing: 0.05em; }}
  td:nth-child(n+2):not(:last-child) {{ text-align: right; font-variant-numeric: tabular-nums; }}
  code {{ font-size: 12px; color: var(--accent); background: rgba(94, 234, 212, 0.08);
          padding: 1px 5px; border-radius: 4px; }}
  a {{ color: var(--accent); }}
  .footnote {{ color: var(--dim); font-size: 12px; margin-top: 24px;
               border-top: 1px solid var(--border); padding-top: 16px; }}
</style>
</head>
<body>
<div class="wrap">
  <h1>claude-cost</h1>
  <div class="meta">
    Report generated {now} · {n:,} assistant turns ·
    region <code>{html.escape(factors.region)}</code>
    ({factors.kgco2e_per_kwh} kg CO₂e/kWh, {factors.liters_per_kwh} L/kWh)
  </div>

  <div class="grid">
    <div class="card accent-energy">
      <div class="label">Energy</div>
      <div class="value">{kwh:.3f} kWh</div>
      <div class="sub">{kwh*1000:.0f} Wh total</div>
    </div>
    <div class="card accent-co2">
      <div class="label">Carbon</div>
      <div class="value">{kg*1000:.1f} g CO₂e</div>
      <div class="sub">{kg:.4f} kg CO₂e</div>
    </div>
    <div class="card accent-water">
      <div class="label">Water</div>
      <div class="value">{liters:.2f} L</div>
      <div class="sub">{liters*1000:.0f} mL total</div>
    </div>
    <div class="card">
      <div class="label">Tokens</div>
      <div class="value">{total_tokens:,}</div>
      <div class="sub">{n:,} assistant turns</div>
    </div>
  </div>

  <h2>In human terms</h2>
  <div class="grid">
    <div class="card"><div class="label">car miles</div>
      <div class="value">{eq['miles_driven_us_passenger_car']:.2f}</div>
      <div class="sub">US passenger avg, EPA</div></div>
    <div class="card"><div class="label">smartphone charges</div>
      <div class="value">{eq['smartphone_charges']:.0f}</div>
      <div class="sub">EPA equivalencies</div></div>
    <div class="card"><div class="label">tree-years to absorb</div>
      <div class="value">{eq['tree_years_to_sequester']:.3f}</div>
      <div class="sub">urban tree, EPA</div></div>
    <div class="card"><div class="label">8-min showers</div>
      <div class="value">{eq['showers_8min']:.2f}</div>
      <div class="sub">@ 2.0 gpm (WaterSense)</div></div>
    <div class="card"><div class="label">500 mL bottles of water</div>
      <div class="value">{eq['bottles_of_water_500ml']:.1f}</div></div>
  </div>

  <h2>Daily</h2>
  <img alt="daily" src="data:image/png;base64,{b_daily}">

  <h2>Cumulative</h2>
  <img alt="cumulative" src="data:image/png;base64,{b_cum}">

  <h2>Top repos by CO₂e</h2>
  <img alt="repos" src="data:image/png;base64,{b_repo}">

  <h2>By model</h2>
  <table>
    <thead><tr><th>model</th><th>tokens</th><th>kWh</th><th>g CO₂e</th><th>L water</th></tr></thead>
    <tbody>{''.join(model_rows)}</tbody>
  </table>

  <h2>By repo</h2>
  <table>
    <thead><tr><th>cwd</th><th>tokens</th><th>g CO₂e</th><th>L water</th></tr></thead>
    <tbody>{''.join(repo_rows)}</tbody>
  </table>

  <h2>Sources</h2>
  <table>
    <thead><tr><th>key</th><th>citation</th><th>url</th></tr></thead>
    <tbody>{''.join(sources_rows)}</tbody>
  </table>

  <p class="footnote">
    All conversion factors are best-effort. Anthropic does not publish per-token
    inference energy. We extrapolate from peer-reviewed measurements of similarly
    sized transformer LLMs (Luccioni et al. 2024 FAccT; Patel et al. 2025
    arXiv:2508.15734; Epoch AI 2025) and use eGRID location-based emission rates
    for grid intensity. Water uses Li et al. 2023 plus Microsoft / Google
    sustainability reports. Treat outputs as order-of-magnitude. See the table
    above for exact citations.
  </p>
</div>
</body>
</html>"""

    output.write_text(html_str, encoding="utf-8")
    return output
