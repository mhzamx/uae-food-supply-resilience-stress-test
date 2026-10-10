# P2 common narrative and KPI wording

**Frozen analytical baseline · 6 October 2026**  
Project lead: Miguel Ángel Hernández Aranda. Applies to the English executive summary, README and dashboard. Analytical values follow the approved workbook and the exact-RNI nutrition correction.

## Canonical paragraph

Public data support a bounded stress-test result rather than a single observed national food-coverage percentage. C1-only (UAE east-coast ports) and the regional envelope (C1 + C2a + C2b) are reported in parallel as a UAE-attributable port floor and a conditional regional ceiling that includes Oman’s own demand and transshipment. Under the 19.6656% reference allocation benchmark, C1-only Low covers approximately 99.3%–91.8% of the modeled port-routed shipment requirement across low–high resident demand, with a modeled gap of 44.9–621.3 t/day. The regional Low envelope reaches 100% if accessible to the UAE. The physical ceiling is 100% in both scopes. The container case is borderline: Low includes the initial ramp-up, the benchmark has confidence C, and total C1 activity reduces the high-demand gap to 404.9 t/day and closes the low-demand gap. The central calculation retains increments. Inland road/rail transfer, customs, cold-chain execution, origin concentration and inferred route exposure determine how this modeled headroom can become effective supply.

## Shared labels and definitions

| Field | Frozen wording / definition |
|---|---|
| Project | UAE Food Supply Resilience Stress Test |
| Basket | Nine essential price-policy categories; distinct from the official 18-item Strategy 2051 basket |
| Demand | Estimated 2026 resident import-dependent requirement; scenario based on 2023 FAOSTAT balances and resident scaling |
| Tourism | Separate sensitivity; proxy national scenario, not measured UAE-wide tourism demand |
| Shipment requirement | RNI × commodity-specific k_ship, split by physical form; compatible physical units only |
| C1-only | C1-only (UAE east-coast ports): Fujairah and Khor Fakkan; UAE-attributable floor of this port analysis |
| Regional envelope | C1 + C2a (Sohar) + C2b (Duqm + Salalah); conditional ceiling, including Oman demand/transshipment |
| Observed | Published trade and AIS-based total cargo activity; no observed food allocation or available capacity implied |
| Inferred | Normal maritime route by origin country; conditional origins retained |
| Scenario | Requirement, allocation, coverage, gaps and origin-based upper bounds |
| ACR_phys / C_phys | min(1, incremental total cargo / physical requirement); gross physical ceiling |
| ACR_ref / C_ref | min(1, incremental total cargo × allocation share / physical requirement); reference allocation benchmark |
| Gap_ref | max(0, requirement − reference allocated cargo), within modeled port segments; modeled gap, not observed shortage |
| Aggregate port ACR | 1 − sum(port gaps) / sum(CONT + GS requirements); not an average of commodity ratios |
| Allocation share | 19.6656%; broad HS01–24 / non-fuel import weight, confidence C as a segment proxy |
| Low / Base / High synchronized | Closure average / last eight complete weeks / own maximum four-week contemporaneous corridor sum, per segment and scope |
| C1 total | Sensitivity adding C1 baseline; not a replacement for central incremental calculation |
| TER | Unverified regional road-route requirement; central C3b credit = 0 |
| GL | Crude/upstream cooking-oil requirement; port coverage not estimable from petroleum-dominated PortWatch liquid bulk |
| Priority | Analytical judgment across port stress, inland/cold-chain uncertainty, supplier concentration and route exposure; no numeric risk score |
| NA / unverified / zero | Distinct states; missing mode, quantity or coverage evidence is not zero |

## Frozen KPI ledger

| KPI | Low demand | High demand | Evidence / qualifier |
|---|---:|---:|---|
| CONT physical requirement, t/day | 4,453.521 | 5,029.974 | Brecha J |
| GS physical requirement, t/day | 2,247.644 | 2,510.648 | Brecha J |
| Port-modeled requirement, t/day | 6,701.165 | 7,540.622 | CONT + GS; about 95.7% of physical shipment requirement |
| TER requirement, t/day | 176.492 | 202.126 | Not verified road flow |
| GL requirement, t/day | 123.449 | 137.972 | Not estimable port coverage |
| C1-only Low container ACR_ref | 98.99% | 87.65% | Incremental benchmark |
| C1-only Low aggregate port ACR_ref | ~99.3% | ~91.8% | Dry bulk remains 100% |
| C1-only Low port Gap_ref, t/day | 44.9 | 621.3 | Central calculation retained |
| Regional Low port ACR_ref | 100% | 100% | Conditional UAE access to Oman |
| Physical ceiling, either scope | 100% | 100% | Not observed food coverage |
| C1 total Low Gap_ref, t/day | 0 | 404.9 | Separate E32 sensitivity; low-demand trigger GREEN |
| Energy, million kcal/day | 28,771.7 | 32,254.1 | Exact RNI A; analytical basket only |
| Protein, t/day | 763.6 | 860.6 | Exact RNI A; analytical basket only |

| Container activity level | C1-only increment, t/day | Regional increment, t/day |
|---|---:|---:|
| Low | 22,418 | 29,109.644 |
| Base | 28,420 | 39,898.797 |
| High synchronized | 34,673.690 | 69,862.190 |

C1 High uses week starts **6–27 July 2026**; regional High uses **13 July–3 August**. The high-demand C1 High spare is **1,788.8 t/day**, low-demand spare **2,365.3 t/day**; high-demand break-even allocation share **14.51%** and ACR at a 10% share **68.93%**. Different segment maxima may occur in different windows; do not sum their maxima as one contemporaneous system peak.

The high-demand container threshold is **25,577.5 t/day of total incremental cargo** at the default allocation share. First eight weeks: **14,852 t/day**; remaining 21 weeks: **25,300 t/day**. The gap-closing cargo-equivalent is **3,159.5 t/day**, or **47.22%** of the C2b Low increment under the same benchmark.

## Concentration, route and nutrition wording

Supplier concentration uses **2023 import value**, excluding World and aggregating HS codes by partner before calculation. HHI uses the 0–10,000 scale. Raw sugar: Brazil 98.7%, HHI 9,748; frozen poultry: Brazil 83.2%, HHI 6,961; rice: India 72.1%, HHI 5,508; eggs: Türkiye 66.4%, HHI 4,645. [S77, S83]

Inferred confirmed Red Sea exposure within Top Five suppliers: wheat **56.6%**, crude/upstream oil **47.7%**, by import value. “Confirmed” is a route-classification label within an inferred layer; it does not mean a tracked shipment. Türkiye eggs and Canada/US routes remain conditional. Do not extrapolate Top Five coverage to all imports. [Exposición de ruta; S80, S83]

TER origin shares use **weight within each subgroup**: fresh poultry 95.63%, fresh/yogurt dairy 65.06%, Saudi Arabia + Oman / World. Residual = sum(requirement × (1 − regional weight share)); approximately **49.8–57.2 t/day** at executive precision. Historical L values 49.776/57.163 are registered inputs; R’s rounded-input reconstruction gives 49.781/57.172. Do not claim three-decimal reproducibility from the published rounded factors. [S81; Brecha L/R]

Nutrition uses exact RNI A with no intermediate rounding. High-demand shares: wheat ~33.4% energy/~39.4% protein; oil ~27.4% energy; poultry ~27.6% protein; pulses **13.76% protein** (13.8% at one decimal). S84’s historical derived totals are superseded by the corrected Nutrición formulas, not by a new FAOSTAT release.

## Execution evidence and publication wording

C1 has official road-and-rail continuity evidence; avoid “domestic” and “trucking-only.” S85’s four daily rail services and S86’s dedicated three-times-weekly service describe different announcements; do not add them as current simultaneous service capacity. S88 documents reefer capability, not available food-specific daily throughput. No cross-border rail credit is granted to C2 in this version. [S85–S88]

Cape rerouting adds a **service-specific transit-time reference** of roughly 7–14 days from Maersk MECL; it is not a universal UAE commodity penalty. Cost penalties remain qualitative without a comparable lane/commodity tariff. C3a is a separate sensitivity; a PortWatch near-zero does not establish port closure. [S36–S47, S80, S89]

Code licence: **MIT**. Project lead: **Miguel Ángel Hernández Aranda**. Source data retain their own terms; the MIT code licence does not relicense source data.

**References:** Source IDs (S01–S89) refer to the source register in `P2_Source_QC_EN.md` and `P2_Source_QC.csv`. Tab and block labels (for example Brecha J/O or Nutrición) refer to the project's analytical workbook, whose inputs are frozen in `data/model_inputs_2026-10-06/` and whose tables are reproduced in `results/`. E-numbers refer to entries in the project's decision log, which is not published.
