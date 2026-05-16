---
name: claude-cost
description: Estimate the environmental footprint (kWh, kg CO₂e, liters of water) of your Claude Code token usage. Reads ~/.claude transcripts; can filter by repo or date range. Use when the user asks how much carbon/water/energy their AI usage has cost, asks for a "Claude cost" or "Claude quote" report, or requests a plot of their token spend over time.
---

# claude-cost

A skill that converts the user's Claude Code token usage into a citation-backed
environmental footprint. Defaults are sourced from peer-reviewed papers
(Luccioni et al. 2024 FAccT, Patel et al. 2025 arXiv:2508.15734, Li et al.
2023, EPA eGRID, Microsoft and Google sustainability reports) — never invent
numbers, and don't downplay or hype them. Treat outputs as order-of-magnitude.

## What to do

The `claude-cost` CLI is installed in the user's environment. Run it via Bash
and relay the output to the user. The PNG output gets shown inline by reading
it back with the Read tool.

**Common requests → commands:**

| Ask | Run |
| --- | --- |
| "What's my Claude cost?" / "Claude quote" / "footprint" | `claude-cost report` |
| "...for this repo" | `claude-cost report --repo "$(pwd)"` |
| "...in the last week / 30 days" | `claude-cost report --since 7d` |
| "Show me a plot" | `claude-cost plot --since 30d -o /tmp/claude-cost.png` then Read it |
| "Cumulative over time" | `claude-cost plot --since 90d --cumulative -o /tmp/cc-cum.png` |
| "Which repo cost the most?" | `claude-cost plot --by-repo -o /tmp/cc-repos.png` |
| "Full report I can share" | `claude-cost html -o /tmp/claude-cost.html` then offer to open |
| "What sources back this?" | `claude-cost cite` |
| "Use the Oregon grid" | add `--region aws-us-west-2` to any command |

## Reporting style

- Lead with the headline numbers (energy, CO₂e in grams, water in mL or L).
- Always include a relatable equivalent (car miles, showers, smartphone charges).
- When asked for "total cost," state it in **kg CO₂e and liters of water**, not
  dollars — that's the whole point of this skill.
- If the user asks about a specific repo, pass `--repo` with the absolute path
  (use `pwd` to get it).
- When showing a plot, run the `plot` subcommand and then immediately
  `Read` the PNG so the user sees it inline.
- After the first run in a conversation, point out: *"All numbers are estimates
  — run `claude-cost cite` for the sources behind every factor."*

## Region note

If unsure where Anthropic runs the user's inference, **don't guess** — use the
default (a mid-range US grid average, ~0.35 kg CO₂e/kWh, 3.5 L/kWh). Only pass
`--region` when the user explicitly asks for a specific region or has set one
in their environment.

## Don't

- Don't invent grid intensities, water factors, or per-token energy.
- Don't claim Anthropic's exact footprint — we only see public proxies.
- Don't present in dollars; the user has the API console for that.
