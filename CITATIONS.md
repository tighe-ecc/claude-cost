# Citations

Every default factor in `claude-cost` is sourced. This document lists each
source, the figure it backs, and a stable URL.

Run `claude-cost cite` to get the same list from the live `factors.toml`.

## Per-token / per-inference energy

| Source | Used for | Citation |
| --- | --- | --- |
| **Epoch AI (2025)** | Per-output-token energy for frontier-class LLMs (~0.0005 Wh/output token, scaling linearly with context above ~10k tokens) | You, Josh. *How much energy does ChatGPT use?* Epoch AI Gradient Updates, Feb 7 2025. <https://epoch.ai/gradient-updates/how-much-energy-does-chatgpt-use> |
| **Patel et al., Google (2025)** | Per-prompt all-in energy including PUE, idle servers, accelerator+CPU+DRAM (0.24 Wh per median Gemini text prompt, production measurement) | Patel, S. et al. *Measuring the environmental impact of delivering AI at Google Scale*. arXiv:2508.15734, 2025. <https://arxiv.org/abs/2508.15734> |
| **Luccioni, Jernite, Strubell (FAccT 2024)** | Direct measurement of per-inference energy across many text-gen models on 8×A100-80GB hardware (BLOOMz-7B ~0.10 Wh/inference). Used as a sanity check against frontier-class extrapolation. | Luccioni, A. S., Jernite, Y., & Strubell, E. *Power Hungry Processing: Watts Driving the Cost of AI Deployment?* ACM FAccT 2024. <https://arxiv.org/abs/2311.16863> · DOI [10.1145/3630106.3658542](https://doi.org/10.1145/3630106.3658542) |
| **Luccioni, Viguier, Ligozat (2022/2023)** | BLOOM-176B deployment-inclusive per-query energy (~4 Wh per query, GCP us-central1, 18-day production trace). Outer bound for large dense models. | Luccioni, A. S., Viguier, S., & Ligozat, A.-L. *Estimating the Carbon Footprint of BLOOM, a 176B Parameter Language Model*. JMLR 2023. <https://arxiv.org/abs/2211.02001> |
| **de Vries (Joule 2023)** | Upper-bound modeling of ChatGPT-class per-query energy (~2.9 Wh/query); industry-level projections. | de Vries, A. *The growing energy footprint of artificial intelligence*. *Joule* 7(10), 2023. <https://www.cell.com/joule/fulltext/S2542-4351(23)00365-3> · DOI [10.1016/j.joule.2023.09.004](https://doi.org/10.1016/j.joule.2023.09.004) |
| **IEA (2025)** | Industry context — efficiency improvements and inference-energy projections through 2030. | International Energy Agency. *Energy and AI*, 2025. <https://www.iea.org/reports/energy-and-ai> |

## Water consumption

| Source | Used for | Citation |
| --- | --- | --- |
| **Li, Yang, Islam, Ren (2023)** | Per-kWh water consumption (scope-1 on-site + scope-2 thermoelectric off-site); per-query mL water for GPT-3-class models. | Li, P., Yang, J., Islam, M. A., & Ren, S. *Making AI Less "Thirsty": Uncovering and Addressing the Secret Water Footprint of AI Models*. arXiv:2304.03271, 2023 (also CACM 2025). <https://arxiv.org/abs/2304.03271> |
| **Microsoft 2024 ESR** | On-site fleet WUE (0.30 L/kWh FY24); zero-water cooling rollout. | Microsoft Corporation. *2024 Environmental Sustainability Report*. <https://www.microsoft.com/corporate-responsibility/sustainability/report> |
| **Google 2024 Environmental Report** | On-site fleet PUE (1.09) and water-use disclosures. | Google LLC. *2024 Environmental Report*. <https://sustainability.google/reports/google-2024-environmental-report/> |

## Grid carbon intensity

| Source | Used for | Citation |
| --- | --- | --- |
| **EPA eGRID2023** | Subregion-level location-based emission rates (NWPP, SRVC, MROW). | U.S. Environmental Protection Agency. *Emissions & Generation Resource Integrated Database (eGRID2023)*. <https://www.epa.gov/egrid> |
| **EIA (2022 US average)** | National-average emission rate for the US grid. | U.S. Energy Information Administration. *How much carbon dioxide is produced per kilowatthour of U.S. electricity generation?* <https://www.eia.gov/tools/faqs/faq.php?id=74&t=11> |
| **Ember (2024)** | World-average power-sector carbon intensity. | Ember. *Global Electricity Review 2024*. <https://ember-climate.org/insights/research/global-electricity-review-2024/> |

## Human-relatable equivalents

| Source | Used for | Citation |
| --- | --- | --- |
| **EPA Greenhouse Gas Equivalencies Calculator** | Car-miles (0.398 kg CO₂e/mi), smartphone charges (8.22 g CO₂e), tree-year sequestration (21.77 kg CO₂e/yr). | U.S. EPA. *Greenhouse Gas Equivalencies Calculator*. <https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator> |
| **EPA WaterSense** | 8-minute shower at 2.0 gpm rating. | U.S. EPA WaterSense. <https://www.epa.gov/watersense> |
| **Mekonnen & Hoekstra (2012)** | Water footprint of a quarter-pound beef burger (~6,810 L). | Mekonnen, M. M., & Hoekstra, A. Y. *A Global Assessment of the Water Footprint of Farm Animal Products*. Ecosystems 15, 2012. <https://doi.org/10.1007/s10021-011-9517-8> |

## What we do not cite — and why

- **Anthropic-published per-token energy or per-token water:** none exists
  publicly as of this writing. Any tool that gives a precise Anthropic-specific
  number is making it up.
- **Training-time emissions:** the published numbers are for specific models
  with one-time costs; per-query amortization depends on assumed query volume
  over the model's lifetime, which is not public. We count only inference.
- **Embodied carbon / water** from data-center construction and semiconductor
  manufacturing: excluded for the same reason — credible per-token allocation
  isn't published.
