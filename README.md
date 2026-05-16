# claude-cost

> **Environmental footprint of your Claude Code usage.** A small Python tool
> that parses your local Claude Code transcripts and converts token spend into
> citation-backed estimates of energy (kWh), carbon (kg CO₂e), and water
> (liters).

```
Claude Code environmental footprint
  records:    3,456
  tokens:     518,699,134
  energy:     19.7782 kWh
  carbon:     6921.86 g CO₂e   (6.9219 kg)
  water:      69218.6 mL       (69.219 L)

  In human terms
    car miles driven (US passenger avg)   17.39
    smartphone charges                    842.1
    tree-years to sequester this CO₂e     0.318
    8-min showers (water)                 1.14
    500 mL water bottles                  138.4
```

## Why

You can see what your AI usage costs you in dollars — your API console will
tell you. You cannot easily see what it costs the world.

This tool answers that second question. It walks the JSONL transcripts that
Claude Code writes to `~/.claude/projects/` and applies a chain of *cited*
conversion factors:

```
tokens → kWh → kg CO₂e + liters of water
        (energy)  (grid)    (water-use)
```

Every default factor in [`factors.toml`](src/claude_cost/data/factors.toml)
links back to a peer-reviewed paper, an EPA/EIA dataset, or a published
provider sustainability report. Run `claude-cost cite` to see them all.

## Install

```bash
# from PyPI (once published)
pip install claude-cost

# or from source
git clone https://github.com/tighe-ecc/claude-cost
cd claude-cost
uv venv && source .venv/bin/activate
uv pip install -e .
```

Optionally drop a Claude Code skill into `~/.claude/skills/` so you can invoke
it from chat:

```bash
claude-cost install-skill
```

Then in Claude Code:

```
> /claude-cost
> /claude-cost report --since 7d --repo $(pwd)
```

## Use

```bash
# Default report — all-time totals, top models, top repos, equivalents
claude-cost

# Filter by time window
claude-cost --since 7d
claude-cost --since 30d
claude-cost --since 2026-04-01

# Filter to one repo
claude-cost --repo ~/code/my-project

# Region-specific grid + water
claude-cost --region aws-us-west-2     # Oregon (eGRID NWPP)
claude-cost --region aws-us-east-1     # Virginia (eGRID SRVC)
claude-cost --region world-avg         # Ember world average

# Plot
claude-cost plot --since 30d -o footprint.png            # daily bars
claude-cost plot --since 90d --cumulative -o cum.png     # running total
claude-cost plot --by-repo -o repos.png                  # top repos

# Self-contained HTML report (embedded plots, sources, equivalents)
claude-cost html -o report.html

# List every repo Claude Code has seen
claude-cost repos

# JSON for downstream scripts
claude-cost json --since 7d > footprint.json

# Show every paper / dataset backing the defaults
claude-cost cite
```

## What gets counted

Each `assistant` turn in a transcript carries a `message.usage` object with
four token counts:

| token class | what it is | energy per token |
| --- | --- | --- |
| `output_tokens` | tokens the model generated (one forward pass each) | highest |
| `input_tokens` | uncached prompt tokens (one batched prefill) | ~½ of output |
| `cache_creation_input_tokens` | first time a prompt prefix is seen | ~prefill |
| `cache_read_input_tokens` | KV-cache hit on a previously cached prefix | ~10% of prefill |

`<synthetic>` model entries (tool-result messages injected server-side, no
inference) are zeroed out. Duplicate `requestId`s are deduped.

## The numbers behind the numbers

| factor | default | source |
| --- | --- | --- |
| Energy per 1k output tokens (frontier model) | 0.50 Wh | Epoch AI 2025; Patel et al. 2025 (Google); Luccioni et al. 2024 (FAccT) |
| Energy per 1k input tokens | 0.25 Wh | derived from Epoch 2025 input-scaling |
| Energy per 1k cache-read tokens | 0.025 Wh | KV-hit, ~10% of prefill |
| Grid CO₂e intensity (default) | 0.350 kg/kWh | EPA eGRID2023 + EIA US-avg, mid-range |
| Water (default, scope-1+2) | 3.5 L/kWh | Li et al. 2023; Microsoft 2024 ESR |
| Car-mile equivalent | 0.398 kg CO₂e/mi | [EPA GHG Equivalencies](https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator) |
| Tree-year sequestration | 21.77 kg CO₂e/yr | EPA GHG Equivalencies |
| 8-min shower @ 2.0 gpm | 60.56 L | EPA WaterSense |

See [`CITATIONS.md`](CITATIONS.md) for the full bibliography with stable URLs,
or run `claude-cost cite`.

### Important caveats

- **Anthropic does not publish per-token inference energy.** We extrapolate
  from measurements of comparably-sized transformer LLMs (Luccioni et al.
  2024, Patel et al. 2025, Epoch AI 2025). Treat all output as
  order-of-magnitude.
- **Grid intensity is location-based**, not market-based. We do *not* subtract
  PPAs or RECs — the question is "what did this kWh actually pull from the
  grid?" not "what does the provider report under their Scope-2 accounting?"
- **Water is operational only.** Embodied water from data-center construction
  and chip manufacturing is excluded.
- **No training cost is allocated.** This counts only the energy your
  inference call consumed at the moment you made it.

If those assumptions are wrong for your purpose, override them: pass a
`--factors path/to/your.toml` or use `--region` for a built-in alternative.

## Custom factors

Copy `src/claude_cost/data/factors.toml`, edit the numbers, and pass the path
via `--factors`. The file is heavily commented — every default explains
*why* it has its value, and what source it comes from.

## Privacy

`claude-cost` reads only local files under `~/.claude/projects/` and never
sends anything anywhere. There is no telemetry. Treat the transcripts as
sensitive — they may contain content you typed into prompts.

## License

MIT.

## Acknowledgements

This tool is only useful because researchers have spent years measuring the
otherwise-invisible costs of AI:

- Sasha Luccioni and collaborators (BLOOM carbon footprint; *Power Hungry
  Processing*; many talks about the politics of AI sustainability)
- Pengfei Li, Mohammad Atiqul Islam, Shaolei Ren and collaborators (*Making
  AI Less Thirsty*)
- The EPA eGRID and EIA teams who keep emission rates publicly available
- Epoch AI, the IEA, and the authors of de Vries (*Joule*, 2023) for
  inference-side energy modeling

Built one evening with [Claude Code](https://www.anthropic.com/claude-code) at
a cost of ~261 Wh of energy, ~91 g CO₂e, and ~915 mL of water (≈ 11 smartphone
charges and ~2 bottles' worth) — measured by this tool, on this tool.
