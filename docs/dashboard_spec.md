# Dashboard specification (v0.2)

Power BI report for the UAE Food Supply Resilience Stress Test, in English: seven pages of 1280 × 720 px with a dark theme. `powerbi/build_pbip.py` generates the whole report as a Power BI project (TMDL model and PBIR report), with the frozen data snapshot embedded in the model. The delivered files are `powerbi/P2_FoodResilience.pbix` and the static export `powerbi/export/P2_FoodResilience.pdf`.

## Global rules

- **Theme.** "P2 Food Resilience (dark)", Segoe UI.
  - Page background `#07121F`; panels `#0B1B2B` with `#183750` borders, drawn into the page background images.
  - Text `#E6F1FF` (primary) and `#8BA6C1` (secondary).
  - Accents: cyan `#22D3EE` for coverage, amber `#F59E0B` for gaps and concentration.
  - Chart series: `#00A3C0`, `#9085E9`, `#D55181`, `#C98500`. Items outside the port model use the neutral greys `#6B7F94` and `#46586B`.
- **Scenario controls.** Single-select button tiles:
  - Scope: C1-only, Regional envelope, C1 total (sensitivity);
  - Activity level: Low, Base, High synchronized;
  - 2026 demand: Low, High.
  - Defaults: C1-only, Low, high demand.
  - The food share of incremental cargo is a dropdown on the Gap page with eight values from 10 % to 30 %. Its default is the 19.67 % benchmark (19.6656 %); the measures use the same benchmark when nothing is selected.
- **Two scopes, never one.** C1-only is the UAE-attributable floor and the regional envelope the conditional ceiling. Neither is labeled the main scope.
- **Wording.**
  - `ACR_ref` is shown as coverage under the reference allocation.
  - `ACR_phys` is the physical ceiling.
  - `Gap_ref` is a modeled gap, not an observed shortage.
  - "Observed" describes PortWatch activity only, never coverage.
- **Footer on every page.** Sources (IMF PortWatch AIS estimates of total cargo, not food; UN Comtrade 2023; FAOSTAT 2023), the statement that coverage is modeled, not observed, version and project lead. The Overview footer also notes that the PDF is a static export and that the globe and the table are interactive in the `.pbix`.
- **Accessibility.** Every visual has alt text. Panel titles are text boxes.
- **Security limits.** Corridor level only:
  - no reserve stocks;
  - no days-to-depletion;
  - no facility-level capacity, routes or single points of failure.

## Pages

**1. Overview**
- Header and the Scope, Activity level and 2026 demand tiles.
- *2026 requirement by mode*: donut (containers, dry bulk, road TER, liquid bulk GL) and the share modeled at ports.
- *Where the basket comes from*: an orthographic Shape Map globe of supplier countries.
  - Its tooltip shows the country's largest single-product share, the product and the number of basket items where the country is a Top-5 supplier.
  - Clicking a country filters the supplier table; a second click clears it.
  - The map loads the world-atlas TopoJSON from jsDelivr, so it needs an internet connection.
  - Four cards: port coverage, port gap (t/day), container coverage and the C1 total Low container gap (t/day).
- *Main suppliers*: flag, country, product, share (with a data bar) and items, with fixed column widths and a note defining Items.
- *Weekly container imports at alternative ports*: line chart for C1, C2a and C2b in kt/week.
- *Most concentrated items*: the five items with the highest HHI.

**2. Alternative routes**
- Cargo-segment tiles: Container, Dry bulk, General cargo + RoRo.
- *Chokepoint transits*: four cards (Hormuz, Bab el-Mandeb, Suez, Cape of Good Hope). Each shows the closure average against the pre-war base for cargo ships, excluding tankers, from `outputs/chokepoints_summary.csv`.
- *Weekly imports by corridor*: line chart in kt/week for the selected segment. C3a is drawn in grey and labeled low reliability.
- *Activity over the pre-war base*: matrix of scope × activity level in t/day. The C1 total row is total activity (base + increment).
- *Activity, not capacity*: notes on what PortWatch measures.

**3. Gap by commodity**
- Scope, Activity level and 2026 demand tiles, plus the food-share dropdown.
- *Modeled gap by commodity form*: bar chart, proportional allocation within each segment. A note lists the forms not shown: a gap of 0.001 t/day or less, forms outside the port model, and bread, which is counted in wheat.
- *Selected scenario · containers*: container coverage, container gap and truck-equivalent trips per day for the covered container volume. The trips card is labeled "Lower bound · container forms only · not trips to close the gap".
- *Outside the port model*: TER (fresh poultry and dairy, road) and GL (crude cooking oil, liquid bulk) requirements in t/day.

**4. Food-share sensitivity**
- 2026 demand tiles.
- *Container ACR_ref by food share*: one line each for C1-only Low, Base and High synchronized, the regional envelope Low and C1 total Low. The axis runs from 40 % to 100 %.
- *Food share needed for full container coverage*: break-even food share by scenario.
- Notes: how break-even is computed, and the C1 container threshold at the benchmark.

**5. Suppliers and routes**
- *Supplier concentration*: HHI (0–10,000) by commodity form.
- *Route exposure within the Top 5 suppliers*: stacked bars by share of import value. The four parts are Red Sea confirmed, Red Sea conditional, No Red Sea or regional, and Outside Top 5. Routes are inferred by origin country.

**6. Nutrition**
- 2026 demand tiles.
- *Share of the import-dependent requirement by category*: tonnage (grey bar, unlabeled), energy and protein.
- Cards for import-dependent energy (million kcal/day) and protein (t/day).
- Notes on why nutrition and tonnage priorities differ.

**7. Method and limits**
- Method steps, limits, security limits, and code and data licences. The text follows the frozen narrative.

## Data model

- **Model workbook tables.** 15 tables from `powerbi/P2_PowerBI_model.xlsx`. Each is embedded as a frozen snapshot (compressed JSON in its Power Query partition), so the report opens without a file path.
- **Calculated tables.**
  - `Food share`: the eight dropdown values.
  - `countries`: 30 supplier countries with map names and flag images, from `powerbi/assets/country_flags.csv`.
  - `chokepoints`: from `outputs/chokepoints_summary.csv`.
- **Measures.** 47, in `_Measures`, defined in `powerbi/build_pbip.py`, which is the authoritative source. `powerbi/measures.dax` is an earlier reference set and differs from the generator in places.
- **Relationships.** 21, all single direction and one-to-many.

## Build

1. Optional, to change the data: rebuild `results/` and the model workbook with `src/p2_build_model.py`.
2. Extract the Fluent 2 base theme from the included `.pbix` (see the README).
3. Run `python powerbi/build_pbip.py --xlsx powerbi/P2_PowerBI_model.xlsx --base-theme <Fluent2-CY26SU09.json> --out <folder>`.
   - The default `--source embedded` embeds the snapshot.
   - `--source excel --excel-path <path>` connects the model to the workbook instead.
4. Open `<folder>/P2_FoodResilience.pbip` in Power BI Desktop, refresh once and save as `.pbix`.
5. Export the PDF with File > Export > Export to PDF. If a page comes out blank in the first export after opening the file, open that page and export again.

The model and the report need no manual steps. Two helper scripts are only needed if the design changes:

- `powerbi/make_backgrounds.py` redraws the page backgrounds in `powerbi/assets/` from the panel layout in `build_pbip.py`. It requires Pillow and is only needed if the layout changes.
- `powerbi/assets/make_flags.py` built `country_flags.csv` from the flag-icons SVGs. It requires cairosvg and Pillow.
