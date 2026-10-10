# P2 data model v0.1 — model review (revision 2, 2026-10-06)

Revision 2 states the reconstruction maxima separately, gives explicit units for the nutrition differences and labels the C1 total rows as total activity. No model value changed.

Full model (src/p2_build_model.py, data/model_inputs_2026-10-06/, results/, powerbi/P2_PowerBI_model.xlsx, powerbi/measures.dax, docs/dashboard_spec.md). English tables for results/ and Power BI.

## How the model reproduces the workbook
- Segment requirements, corridor increments and C1-only Low gaps are the values REGISTERED in "Brecha v0.1" (I, J, K, L, Q, R). C1-only increments keep the rounded J values (22,418 / 28,420 t/d), as registered.
- CONT subgroup requirements are split with the registered section-K proportions, so every subgroup gap reproduces K exactly. GS (wheat grain, raw sugar) and TER (fresh poultry, fresh dairy) are split with the published mixes and scaled to the registered totals. GL = registered.
- model_checks.csv rebuilds segment totals from the published rounded inputs (RNI x k_ship x mix). The largest absolute difference is 0.293 t/d (GS, low demand); the largest relative difference is 0.0413 % (GL, low demand). These maxima occur in different rows. Registered workbook values remain the scenario inputs.

## Verification against the workbook: 73 of 78 checks match
All gaps, C_ref, break-even shares, thresholds (22,646.3 / 25,577.5), C1 total (404.9 t/d; 91.95 %), spares in O, K by subgroup, trucks (104.49 + 46.91; gap 21.34), TER/GL and residuals, executive-summary aggregates (6,701.165 / 7,540.622; 99.33 % / 91.76 %), Top1/Top3 shares.

Nutrition discrepancy (Nutrición v0.1): the tab applies densities to RNI A rounded to integers. With exact RNI A: energy 28,771.7–32,254.1 million kcal/d (registered 28,768.3–32,253.7); protein 763.6–860.6 t/d (763.7–860.7); pulses protein share 13.76 % (13.78 %). The energy and protein totals change by 0.02 % or less; the pulses share changes by 0.02 percentage points (about 0.15 % relative). Resolved: the workbook tab now uses exact values.

## Container coverage by scenario (benchmark 19.6656 %)
| scope | activity_level | demand | Activity t/d (increment; total for C1 total) | ACR_phys % | ACR_ref % | Gap_ref t/d | Break-even % |
|---|---|---|---|---|---|---|---|
| Regional envelope | Low | Low | 29109.6 | 100.0 | 100.0 | 0.0 | 15.3 |
| Regional envelope | Low | High | 29109.6 | 100.0 | 100.0 | 0.0 | 17.28 |
| Regional envelope | Base | Low | 39898.8 | 100.0 | 100.0 | 0.0 | 11.16 |
| Regional envelope | Base | High | 39898.8 | 100.0 | 100.0 | 0.0 | 12.61 |
| Regional envelope | High synchronized | Low | 69862.2 | 100.0 | 100.0 | 0.0 | 6.37 |
| Regional envelope | High synchronized | High | 69862.2 | 100.0 | 100.0 | 0.0 | 7.2 |
| C1-only | Low | Low | 22418.0 | 100.0 | 98.99 | 44.9 | 19.87 |
| C1-only | Low | High | 22418.0 | 100.0 | 87.65 | 621.3 | 22.44 |
| C1-only | Base | Low | 28420.0 | 100.0 | 100.0 | 0.0 | 15.67 |
| C1-only | Base | High | 28420.0 | 100.0 | 100.0 | 0.0 | 17.7 |
| C1-only | High synchronized | Low | 34673.7 | 100.0 | 100.0 | 0.0 | 12.84 |
| C1-only | High synchronized | High | 34673.7 | 100.0 | 100.0 | 0.0 | 14.51 |
| C1 total (sensitivity) | Low | Low | 23518.7 | 100.0 | 100.0 | 0.0 | 18.94 |
| C1 total (sensitivity) | Low | High | 23518.7 | 100.0 | 91.95 | 404.9 | 21.39 |
| C1 total (sensitivity) | Base | Low | 29521.3 | 100.0 | 100.0 | 0.0 | 15.09 |
| C1 total (sensitivity) | Base | High | 29521.3 | 100.0 | 100.0 | 0.0 | 17.04 |
| C1 total (sensitivity) | High synchronized | Low | 35774.5 | 100.0 | 100.0 | 0.0 | 12.45 |
| C1 total (sensitivity) | High synchronized | High | 35774.5 | 100.0 | 100.0 | 0.0 | 14.06 |

## C1-only Low: Gap_ref by subgroup (t/d)
| subgroup_id | container_type | High | Low |
|---|---|---|---|
| butter_ghee | Reefer | 5.423 | 0.386 |
| dairy_cheese | Reefer | 11.013 | 0.782 |
| dairy_powder | Dry | 58.682 | 4.167 |
| eggs | Reefer | 12.813 | 0.765 |
| oil_refined | Dry | 106.003 | 7.739 |
| poultry_frozen | Reefer | 166.919 | 12.032 |
| pulses | Dry | 73.542 | 5.363 |
| rice | Dry | 160.502 | 11.721 |
| sugar_refined | Dry | 26.444 | 1.933 |

## Shipment requirement by subgroup (t/d)
| subgroup_id | segment | High | Low |
|---|---|---|---|
| butter_ghee | CONT | 43.901 | 38.297 |
| dairy_cheese | CONT | 89.154 | 77.585 |
| dairy_fresh | TER | 158.097 | 137.607 |
| dairy_powder | CONT | 475.051 | 413.425 |
| eggs | CONT | 103.726 | 75.899 |
| oil_crude | GL | 137.972 | 123.449 |
| oil_refined | CONT | 858.132 | 767.818 |
| poultry_fresh | TER | 44.029 | 38.885 |
| poultry_frozen | CONT | 1351.268 | 1193.744 |
| pulses | CONT | 595.348 | 532.085 |
| rice | CONT | 1299.32 | 1162.888 |
| sugar_raw | GS | 591.618 | 529.643 |
| sugar_refined | CONT | 214.073 | 191.781 |
| wheat_grain | GS | 1919.03 | 1718.001 |

## Outside the port model
| subgroup_id | segment | demand | shipment_requirement_t_day | regional_origin_share_upper_bound | residual_after_upper_bound_t_day |
|---|---|---|---|---|---|
| poultry_fresh | TER | Low | 38.885 | 0.956 | 1.699 |
| dairy_fresh | TER | Low | 137.607 | 0.651 | 48.08 |
| oil_crude | GL | Low | 123.449 | 0.144 | 105.611 |
| poultry_fresh | TER | High | 44.029 | 0.956 | 1.924 |
| dairy_fresh | TER | High | 158.097 | 0.651 | 55.239 |
| oil_crude | GL | High | 137.972 | 0.144 | 118.035 |

## Reconstruction check
| check | registered | rebuilt_from_rounded_inputs | difference | relative_difference_pct |
|---|---|---|---|---|
| Segment requirement GS, low demand | 2247.644 | 2247.351 | -0.293 | -0.013 |
| Segment requirement CONT, low demand | 4453.521 | 4453.561 | 0.04 | 0.0009 |
| Segment requirement TER, low demand | 176.492 | 176.499 | 0.007 | 0.0042 |
| Segment requirement GL, low demand | 123.449 | 123.5 | 0.051 | 0.0413 |
| Segment requirement GS, high demand | 2510.648 | 2510.851 | 0.203 | 0.0081 |
| Segment requirement CONT, high demand | 5029.974 | 5029.899 | -0.075 | -0.0015 |
| Segment requirement TER, high demand | 202.126 | 202.157 | 0.031 | 0.0152 |
| Segment requirement GL, high demand | 137.972 | 137.98 | 0.008 | 0.0059 |

