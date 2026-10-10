"""Generate the Power BI project (PBIP: TMDL semantic model + PBIR report) for the P2 dashboard.

Reads the model workbook built by src/p2_build_model.py and writes:
  <out>/P2_FoodResilience.pbip, <out>/P2_FoodResilience.SemanticModel/, <out>/P2_FoodResilience.Report/
Open the .pbip in Power BI Desktop and refresh.

Data source (--source):
  embedded (default): each table carries the frozen snapshot inside the model (compressed JSON in its Power Query
                      partition). The report opens on any computer without a file path; Refresh reloads the same
                      snapshot. To change the data, rebuild the workbook and run this script again.
  excel:              each table reads powerbi/P2_PowerBI_model.xlsx through the ExcelPath parameter (--excel-path).

Usage: python powerbi/build_pbip.py --xlsx powerbi/P2_PowerBI_model.xlsx --base-theme <Fluent2 base theme json> --out <folder>
       [--source excel --excel-path "C:\\...\\P2_PowerBI_model.xlsx"]
"""
import argparse, base64, hashlib, json, os, shutil, uuid, zlib
import pandas as pd

NAME = "P2_FoodResilience"
TABLES = ["commodities", "categories", "demand_levels", "segments", "scenarios", "requirement_by_subgroup",
          "corridor_increments", "coverage_by_segment", "gap_by_subgroup", "off_port_requirements",
          "food_share_sensitivity", "nutrition", "supplier_concentration", "suppliers_top5", "corridor_weekly"]
SORT_BY = {("scenarios", "scope"): "scope_order", ("scenarios", "activity_level"): "activity_order",
           ("scenarios", "scenario"): "sort_order", ("demand_levels", "demand"): "sort_order",
           ("segments", "segment_name"): "segment_order", ("corridor_weekly", "corridor"): "corridor_order"}
COLUMN_FORMATS = {("food_share_sensitivity", "food_share"): "0%"}
HIDDEN = {"scope_order", "activity_order", "sort_order", "segment_order", "corridor_order"}
RELATIONSHIPS = [
    ("coverage_by_segment", "scenario_id", "scenarios", "scenario_id"), ("coverage_by_segment", "demand", "demand_levels", "demand"),
    ("coverage_by_segment", "segment", "segments", "segment"),
    ("gap_by_subgroup", "scenario_id", "scenarios", "scenario_id"), ("gap_by_subgroup", "demand", "demand_levels", "demand"),
    ("gap_by_subgroup", "subgroup_id", "commodities", "subgroup_id"),
    ("requirement_by_subgroup", "subgroup_id", "commodities", "subgroup_id"), ("requirement_by_subgroup", "demand", "demand_levels", "demand"),
    ("off_port_requirements", "subgroup_id", "commodities", "subgroup_id"), ("off_port_requirements", "demand", "demand_levels", "demand"),
    ("food_share_sensitivity", "scenario_id", "scenarios", "scenario_id"), ("food_share_sensitivity", "demand", "demand_levels", "demand"),
    ("food_share_sensitivity", "segment", "segments", "segment"),
    ("corridor_increments", "scenario_id", "scenarios", "scenario_id"), ("corridor_increments", "segment", "segments", "segment"),
    ("commodities", "category_id", "categories", "category_id"), ("nutrition", "category_id", "categories", "category_id"),
    ("commodities", "supplier_group", "supplier_concentration", "supplier_group"),
    ("suppliers_top5", "supplier_group", "supplier_concentration", "supplier_group"),
    ("suppliers_top5", "country", "countries", "country"),
    ("corridor_weekly", "segment", "segments", "segment"),
]
FOOD_SHARES = [("10%", 0.10), ("15%", 0.15), ("17.5%", 0.175), ("19.67% (benchmark)", 0.196656), ("20%", 0.20),
               ("22.5%", 0.225), ("25%", 0.25), ("30%", 0.30)]

WRAP = """VAR dem = SELECTEDVALUE ( demand_levels[demand], "High" )
		VAR sc = SELECTEDVALUE ( scenarios[scope], "C1-only" )
		VAR ac = SELECTEDVALUE ( scenarios[activity_level], "Low" )
		VAR fs = [Food share selected]
		RETURN
		    CALCULATE ( {expr}, demand_levels[demand] = dem, scenarios[scope] = sc, scenarios[activity_level] = ac )"""
DEM = """VAR dem = SELECTEDVALUE ( demand_levels[demand], "High" )
		RETURN
		    {expr}"""
CREF = "MIN ( 1, DIVIDE ( {d} * fs, {r} ) )"
MEASURES = [  # (name, folder, format, expression)
    ("Food share selected", "0 Inputs", "0.0%", 'SELECTEDVALUE ( \'Food share\'[Food share], 0.196656 )'),
    ("Scenario shown", "0 Inputs", None, """VAR dem = SELECTEDVALUE ( demand_levels[demand], "High" )
		VAR sc = SELECTEDVALUE ( scenarios[scope], "C1-only" )
		VAR ac = SELECTEDVALUE ( scenarios[activity_level], "Low" )
		RETURN sc & " | " & ac & " activity | " & dem & " 2026 demand | food share " & FORMAT ( [Food share selected], "0.0%" )"""),
    ("Requirement (t/d)", "1 Coverage", "#,0", WRAP.format(expr="SUM ( coverage_by_segment[requirement_t_day] )")),
    ("Delta cargo (t/d)", "1 Coverage", "#,0", WRAP.format(expr="SUM ( coverage_by_segment[delta_cargo_t_day] )")),
    ("Gap_ref (t/d)", "1 Coverage", "#,0.0", WRAP.format(expr="SUMX ( coverage_by_segment, coverage_by_segment[requirement_t_day] * ( 1 - "
        + CREF.format(d="coverage_by_segment[delta_cargo_t_day]", r="coverage_by_segment[requirement_t_day]") + " ) )")),
    ("Gap_phys (t/d)", "1 Coverage", "#,0.0", WRAP.format(expr="SUMX ( coverage_by_segment, coverage_by_segment[requirement_t_day] * ( 1 - "
        "MIN ( 1, DIVIDE ( coverage_by_segment[delta_cargo_t_day], coverage_by_segment[requirement_t_day] ) ) ) )")),
    ("ACR_ref", "1 Coverage", "0.0%", "VAR r = [Requirement (t/d)] RETURN IF ( r > 0, 1 - DIVIDE ( [Gap_ref (t/d)], r ) )"),
    ("ACR_phys", "1 Coverage", "0.0%", "VAR r = [Requirement (t/d)] RETURN IF ( r > 0, 1 - DIVIDE ( [Gap_phys (t/d)], r ) )"),
    ("ACR_ref container", "1 Coverage", "0.00%", 'CALCULATE ( [ACR_ref], segments[segment] = "CONT" )'),
    ("ACR_ref dry bulk", "1 Coverage", "0.00%", 'CALCULATE ( [ACR_ref], segments[segment] = "GS" )'),
    ("Gap_ref container (t/d)", "1 Coverage", "#,0.0", 'CALCULATE ( [Gap_ref (t/d)], segments[segment] = "CONT" )'),
    ("Break-even food share container", "1 Coverage", "0.0%",
        'CALCULATE ( DIVIDE ( [Requirement (t/d)], [Delta cargo (t/d)] ), segments[segment] = "CONT" )'),
    ("KPI port ACR_ref C1 Low", "2 KPI", "0.0%", 'CALCULATE ( [ACR_ref], scenarios[scope] = "C1-only", scenarios[activity_level] = "Low" )'),
    ("KPI port ACR_ref regional Low", "2 KPI", "0.0%", 'CALCULATE ( [ACR_ref], scenarios[scope] = "Regional envelope", scenarios[activity_level] = "Low" )'),
    ("KPI container gap C1 Low (t/d)", "2 KPI", "#,0.0", 'CALCULATE ( [Gap_ref container (t/d)], scenarios[scope] = "C1-only", scenarios[activity_level] = "Low" )'),
    ("KPI container gap C1 total Low (t/d)", "2 KPI", "#,0.0",
        'CALCULATE ( [Gap_ref container (t/d)], scenarios[scope] = "C1 total (sensitivity)", scenarios[activity_level] = "Low" )'),
    ("Requirement: containers (t/d)", "2 KPI", "#,0", 'CALCULATE ( [Requirement (t/d)], segments[segment] = "CONT" )'),
    ("Requirement: dry bulk (t/d)", "2 KPI", "#,0", 'CALCULATE ( [Requirement (t/d)], segments[segment] = "GS" )'),
    ("Requirement: road, TER (t/d)", "2 KPI", "#,0", "[TER requirement (t/d)]"),
    ("Requirement: liquid bulk, GL (t/d)", "2 KPI", "#,0", "[GL requirement (t/d)]"),
    ("Port-modeled share", "2 KPI", "0.0%", "DIVIDE ( [Requirement (t/d)], [Requirement (t/d)] + [TER requirement (t/d)] + [GL requirement (t/d)] )"),
    ("Gap_ref by subgroup (t/d)", "3 Commodities", "#,0.0", WRAP.format(expr="SUMX ( gap_by_subgroup, gap_by_subgroup[shipment_requirement_t_day] * ( 1 - "
        + CREF.format(d="gap_by_subgroup[segment_delta_cargo_t_day]", r="gap_by_subgroup[segment_requirement_t_day]") + " ) )")),
    ("Gap_ref by subgroup (bar)", "3 Commodities", "#,0.0", "VAR g = [Gap_ref by subgroup (t/d)] RETURN IF ( g > 0.001, g )"),
    ("Truck-equivalent trips covered", "3 Commodities", "#,0", WRAP.format(expr="SUMX ( gap_by_subgroup, DIVIDE ( gap_by_subgroup[shipment_requirement_t_day] * "
        + CREF.format(d="gap_by_subgroup[segment_delta_cargo_t_day]", r="gap_by_subgroup[segment_requirement_t_day]") + ", gap_by_subgroup[payload_t] ) )")),
    ("Truck-equivalent trips gap", "3 Commodities", "#,0.0", WRAP.format(expr="SUMX ( gap_by_subgroup, DIVIDE ( gap_by_subgroup[shipment_requirement_t_day] * ( 1 - "
        + CREF.format(d="gap_by_subgroup[segment_delta_cargo_t_day]", r="gap_by_subgroup[segment_requirement_t_day]") + " ), gap_by_subgroup[payload_t] ) )")),
    ("TER requirement (t/d)", "4 Outside port model", "#,0.0", DEM.format(expr='CALCULATE ( SUM ( off_port_requirements[shipment_requirement_t_day] ), off_port_requirements[segment] = "TER", demand_levels[demand] = dem )')),
    ("GL requirement (t/d)", "4 Outside port model", "#,0.0", DEM.format(expr='CALCULATE ( SUM ( off_port_requirements[shipment_requirement_t_day] ), off_port_requirements[segment] = "GL", demand_levels[demand] = dem )')),
    ("TER residual after regional upper bound (t/d)", "4 Outside port model", "#,0.0", DEM.format(expr='CALCULATE ( SUM ( off_port_requirements[residual_after_upper_bound_t_day] ), off_port_requirements[segment] = "TER", demand_levels[demand] = dem )')),
    ("C_ref container (sensitivity)", "5 Sensitivity", "0%", """VAR dem = SELECTEDVALUE ( demand_levels[demand], "High" )
		VAR sid = SELECTEDVALUE ( scenarios[scenario_id] )
		RETURN
		    IF ( sid IN { "S01", "S02", "S03", "S04", "S07" },
		        CALCULATE ( AVERAGE ( food_share_sensitivity[c_ref] ), segments[segment] = "CONT", demand_levels[demand] = dem ) )"""),
    ("Weekly imports (kt)", "6 Corridors", "#,0", """VAR seg = SELECTEDVALUE ( segments[segment], "CONT" )
		RETURN
		    DIVIDE ( CALCULATE ( SUM ( corridor_weekly[imports_t_week] ), corridor_weekly[period] <> "Earlier", segments[segment] = seg ), 1000 )"""),
    ("Increment (t/d)", "6 Corridors", "#,0", """VAR seg = SELECTEDVALUE ( segments[segment], "CONT" )
		RETURN
		    CALCULATE ( SUM ( corridor_increments[delta_cargo_t_day] ), segments[segment] = seg )"""),
    ("HHI", "7 Suppliers", "#,0", "SUM ( supplier_concentration[hhi] )"),
    ("Transit change vs base", "6 Corridors", "+0.0%;-0.0%;0.0%", "DIVIDE ( SUM ( chokepoints[closure_transits_week] ) - SUM ( chokepoints[base_transits_week] ), SUM ( chokepoints[base_transits_week] ) )"),
    ("Largest supplier share", "7 Suppliers", "0.0%", "DIVIDE ( MAX ( suppliers_top5[share_value_pct] ), 100 )"),
    ("Basket items in Top 5", "7 Suppliers", "0", "DISTINCTCOUNT ( suppliers_top5[supplier_group] )"),
    ("Largest-share product", "7 Suppliers", None, "VAR m = MAX ( suppliers_top5[share_value_pct] ) RETURN CALCULATE ( FIRSTNONBLANK ( suppliers_top5[supplier_group_name], 1 ), suppliers_top5[share_value_pct] = m )"),
    ("Top 1 share", "7 Suppliers", "0.0%", "DIVIDE ( SUM ( supplier_concentration[top1_share_pct] ), 100 )"),
    ("Red Sea confirmed", "7 Suppliers", "0.0%", "DIVIDE ( SUM ( supplier_concentration[red_sea_confirmed_pct] ), 100 )"),
    ("Red Sea conditional", "7 Suppliers", "0.0%", "DIVIDE ( SUM ( supplier_concentration[conditional_pct] ), 100 )"),
    ("No Red Sea or regional", "7 Suppliers", "0.0%", "DIVIDE ( SUM ( supplier_concentration[no_red_sea_or_regional_pct] ), 100 )"),
    ("Outside Top 5", "7 Suppliers", "0.0%", "DIVIDE ( SUM ( supplier_concentration[outside_top5_pct] ), 100 )"),
    ("Import-dependent requirement (t/d)", "8 Nutrition", "#,0", DEM.format(expr='IF ( dem = "High", SUM ( categories[rni_a_2026_high_t_day] ), SUM ( categories[rni_a_2026_low_t_day] ) )')),
    ("Import-dependent energy (million kcal/d)", "8 Nutrition", "#,0", DEM.format(expr='IF ( dem = "High", SUM ( nutrition[import_dependent_million_kcal_day_high] ), SUM ( nutrition[import_dependent_million_kcal_day_low] ) )')),
    ("Import-dependent protein (t/d)", "8 Nutrition", "#,0.0", DEM.format(expr='IF ( dem = "High", SUM ( nutrition[import_dependent_protein_t_day_high] ), SUM ( nutrition[import_dependent_protein_t_day_low] ) )')),
    ("Tonnage share", "8 Nutrition", "0.0%", "DIVIDE ( [Import-dependent requirement (t/d)], CALCULATE ( [Import-dependent requirement (t/d)], ALL ( categories ) ) )"),
    ("Energy share", "8 Nutrition", "0.0%", "DIVIDE ( [Import-dependent energy (million kcal/d)], CALCULATE ( [Import-dependent energy (million kcal/d)], ALL ( categories ) ) )"),
    ("Protein share", "8 Nutrition", "0.0%", "DIVIDE ( [Import-dependent protein (t/d)], CALCULATE ( [Import-dependent protein (t/d)], ALL ( categories ) ) )"),
]


def tag(*parts):
    return str(uuid.UUID(hashlib.md5("|".join(parts).encode()).hexdigest()))


def hexid(*parts):
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:20]


def qname(n):
    return f"'{n}'" if any(ch in n for ch in " ()/-%&.,") else n


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def wjson(path, obj):
    write(path, json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- semantic model
def tmdl_type(s):
    if pd.api.types.is_bool_dtype(s):
        return "boolean", "type logical", None
    if pd.api.types.is_datetime64_any_dtype(s):
        return "dateTime", "type datetime", "yyyy-mm-dd"
    if pd.api.types.is_integer_dtype(s):
        return "int64", "Int64.Type", "0"
    if pd.api.types.is_float_dtype(s):
        return "double", "type number", None
    return "string", "type text", None


def embedded_rows(df):
    """Frozen snapshot of a sheet as base64 raw-deflate JSON rows (the format Power BI uses for entered data)."""
    rows = []
    for rec in df.itertuples(index=False):
        row = []
        for v in rec:
            if v is None or (not isinstance(v, (str, bool)) and pd.isna(v)):
                row.append(None)
            elif isinstance(v, pd.Timestamp):
                row.append(v.strftime("%Y-%m-%dT%H:%M:%S"))
            elif hasattr(v, "item"):
                row.append(v.item())
            else:
                row.append(v)
        rows.append(row)
    raw = json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    return base64.b64encode(comp.compress(raw) + comp.flush()).decode("ascii")


def table_tmdl(name, df, source="embedded"):
    lines = [f"table {name}", f"\tlineageTag: {tag('t', name)}", ""]
    mtypes = []
    for c in df.columns:
        dt, mt, fmt = tmdl_type(df[c])
        fmt = COLUMN_FORMATS.get((name, c), fmt)
        mtypes.append(f'{{"{c}", {mt}}}')
        lines.append(f"\tcolumn {c}")
        lines.append(f"\t\tdataType: {dt}")
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        if c in HIDDEN:
            lines.append("\t\tisHidden")
        lines.append(f"\t\tlineageTag: {tag('c', name, c)}")
        lines.append(f"\t\tsummarizeBy: {'sum' if dt in ('double', 'int64') and c not in HIDDEN and not c.endswith(('order', '_id')) else 'none'}")
        lines.append(f"\t\tsourceColumn: {c}")
        if (name, c) in SORT_BY:
            lines.append(f"\t\tsortByColumn: {SORT_BY[(name, c)]}")
        lines.append("")
        lines.append("\t\tannotation SummarizationSetBy = Automatic")
        lines.append("")
    if source == "excel":
        m = (f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
             f"\t\t\t\t    Source = Excel.Workbook(File.Contents(ExcelPath), null, true),\n"
             f"\t\t\t\t    Sheet = Source{{[Item=\"{name}\",Kind=\"Sheet\"]}}[Data],\n"
             f"\t\t\t\t    Promoted = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),\n"
             f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted,{{{', '.join(mtypes)}}})\n"
             f"\t\t\t\tin\n\t\t\t\t    Typed\n")
    else:
        cols = ", ".join(json.dumps(c, ensure_ascii=False) for c in df.columns)
        m = (f"\tpartition {name} = m\n\t\tmode: import\n\t\tsource =\n\t\t\t\tlet\n"
             f"\t\t\t\t    // frozen snapshot of sheet {name} in powerbi/P2_PowerBI_model.xlsx, embedded by build_pbip.py\n"
             f"\t\t\t\t    Rows = Json.Document(Binary.Decompress(Binary.FromText(\"{embedded_rows(df)}\", BinaryEncoding.Base64), Compression.Deflate)),\n"
             f"\t\t\t\t    Promoted = Table.FromRows(Rows, {{{cols}}}),\n"
             f"\t\t\t\t    Typed = Table.TransformColumnTypes(Promoted,{{{', '.join(mtypes)}}})\n"
             f"\t\t\t\tin\n\t\t\t\t    Typed\n")
    lines.append(m)
    lines.append("\tannotation PBI_ResultType = Table\n")
    return "\n".join(lines)


def food_share_tmdl():
    rows = ", ".join(f'{{"{l}", {v}, {i}}}' for i, (l, v) in enumerate(FOOD_SHARES, start=1))
    return f"""table 'Food share'
	lineageTag: {tag('t', 'Food share')}

	column Label
		dataType: string
		lineageTag: {tag('c', 'Food share', 'Label')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Label]
		sortByColumn: Sort

		annotation SummarizationSetBy = Automatic

	column 'Food share'
		dataType: double
		formatString: 0.00%
		lineageTag: {tag('c', 'Food share', 'Food share')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Food share]

		annotation SummarizationSetBy = Automatic

	column Sort
		dataType: int64
		formatString: 0
		isHidden
		lineageTag: {tag('c', 'Food share', 'Sort')}
		summarizeBy: none
		isNameInferred
		sourceColumn: [Sort]

		annotation SummarizationSetBy = Automatic

	partition 'Food share' = calculated
		mode: import
		source = DATATABLE ( "Label", STRING, "Food share", DOUBLE, "Sort", INTEGER, {{ {rows} }} )

"""


def countries_tmdl():
    flags = pd.read_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "country_flags.csv"))
    rows = ", ".join("{" + ", ".join(json.dumps(str(r[c]), ensure_ascii=False) for c in ("country", "map_name", "iso2", "flag")) + "}"
                     for _, r in flags.iterrows())
    cols = []
    for c in ("country", "map_name", "iso2", "flag"):
        extra = "\t\tdataCategory: ImageUrl\n" if c == "flag" else ""
        cols.append(f"""\tcolumn {c}\n\t\tdataType: string\n{extra}\t\tlineageTag: {tag('c', 'countries', c)}\n\t\tsummarizeBy: none\n"""
                    f"""\t\tisNameInferred\n\t\tsourceColumn: [{c}]\n\n\t\tannotation SummarizationSetBy = Automatic\n""")
    return (f"table countries\n\tlineageTag: {tag('t', 'countries')}\n\n" + "\n".join(cols) +
            f"""\n\tpartition countries = calculated\n\t\tmode: import\n\t\tsource = DATATABLE ( "country", STRING, "map_name", STRING, "iso2", STRING, "flag", STRING, {{ {rows} }} )\n\n""")


CHOKE_NAMES = {"Ormuz": "Hormuz", "Bab el-Mandeb": "Bab el-Mandeb", "Suez": "Suez", "Cabo de Buena Esperanza": "Cape of Good Hope"}
CHOKE_TYPES = {"Buques de carga (sin tanqueros)": "Cargo ships (no tankers)", "Tanqueros": "Tankers"}


def chokepoints_tmdl():
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "outputs", "chokepoints_summary.csv")
    d = pd.read_csv(src)
    rows = ", ".join("{" + f'"{CHOKE_NAMES[r.iloc[0]]}", "{CHOKE_TYPES[r.iloc[1]]}", {float(r.iloc[3])}, {float(r.iloc[4])}, {float(r.iloc[5]) / 100}' + "}"
                     for _, r in d.iterrows())
    cols = [("chokepoint", "string", None), ("ship_type", "string", None), ("base_transits_week", "double", "#,0.0"),
            ("closure_transits_week", "double", "#,0.0"), ("change_vs_base", "double", "+0.0%;-0.0%;0.0%")]
    out = [f"table chokepoints\n\tlineageTag: {tag('t', 'chokepoints')}\n"]
    for c, dt, fmt in cols:
        out.append(f"\tcolumn {c}\n\t\tdataType: {dt}\n" + (f"\t\tformatString: {fmt}\n" if fmt else "") +
                   f"\t\tlineageTag: {tag('c', 'chokepoints', c)}\n\t\tsummarizeBy: none\n\t\tisNameInferred\n\t\tsourceColumn: [{c}]\n\n"
                   f"\t\tannotation SummarizationSetBy = Automatic\n")
    out.append(f'\tpartition chokepoints = calculated\n\t\tmode: import\n\t\tsource = DATATABLE ( "chokepoint", STRING, "ship_type", STRING, '
               f'"base_transits_week", DOUBLE, "closure_transits_week", DOUBLE, "change_vs_base", DOUBLE, {{ {rows} }} )\n\n')
    return "\n".join(out)


def measures_tmdl():
    out = ["table _Measures", f"\tlineageTag: {tag('t', '_Measures')}", ""]
    for name, folder, fmt, expr in MEASURES:
        if "\n" in expr:
            body = "\n" + "\n".join("\t\t\t" + ln.lstrip("\t") for ln in expr.split("\n"))
        else:
            body = expr
        out.append(f"\tmeasure {qname(name)} =" + (body if body.startswith("\n") else " " + body))
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out.append(f"\t\tdisplayFolder: {folder}")
        out.append(f"\t\tlineageTag: {tag('m', name)}")
        out.append("")
    out += ["\tcolumn Column1", "\t\tdataType: string", "\t\tisHidden", f"\t\tlineageTag: {tag('c', '_Measures', 'Column1')}",
            "\t\tsummarizeBy: none", "\t\tsourceColumn: Column1", "",
            "\tpartition _Measures = m", "\t\tmode: import", '\t\tsource = Table.FromRecords({[Column1 = ""]})', "",
            "\tannotation PBI_ResultType = Table", ""]
    return "\n".join(out)


def build_model(xlsx, excel_path, out, source="embedded"):
    sm = os.path.join(out, f"{NAME}.SemanticModel")
    d = os.path.join(sm, "definition")
    wjson(os.path.join(sm, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": NAME}, "config": {"version": "2.0", "logicalId": tag("sm", NAME)}})
    wjson(os.path.join(sm, "definition.pbism"), {"version": "4.2", "settings": {}})
    write(os.path.join(d, "database.tmdl"), "database\n\tcompatibilityLevel: 1606\n\n")
    if source == "excel":
        write(os.path.join(d, "expressions.tmdl"),
              f'expression ExcelPath = "{excel_path}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
              f"\tlineageTag: {tag('e', 'ExcelPath')}\n\n\tannotation PBI_NavigationStepName = Navigation\n\n\tannotation PBI_ResultType = Text\n\n")
    names = TABLES + ["Food share", "countries", "chokepoints", "_Measures"]
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3", "\tsourceQueryCulture: en-US",
             "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", "",
             "annotation __PBI_TimeIntelligenceEnabled = 0", "",
             f"annotation PBI_QueryOrder = {json.dumps((['ExcelPath'] if source == 'excel' else []) + TABLES + ['_Measures'])}", "",
             'annotation PBI_ProTooling = ["TMDLView_Desktop","DevMode"]', ""]
    model += [f"ref table {qname(n)}" for n in names] + ["", "ref cultureInfo en-US", ""]
    write(os.path.join(d, "model.tmdl"), "\n".join(model))
    for t in TABLES:
        df = pd.read_excel(xlsx, sheet_name=t)
        write(os.path.join(d, "tables", f"{t}.tmdl"), table_tmdl(t, df, source))
    write(os.path.join(d, "tables", "Food share.tmdl"), food_share_tmdl())
    write(os.path.join(d, "tables", "countries.tmdl"), countries_tmdl())
    write(os.path.join(d, "tables", "chokepoints.tmdl"), chokepoints_tmdl())
    write(os.path.join(d, "tables", "_Measures.tmdl"), measures_tmdl())
    rel = []
    for ft, fc, tt, tc in RELATIONSHIPS:
        rel += [f"relationship {tag('r', ft, fc, tt)}", f"\tfromColumn: {ft}.{fc}", f"\ttoColumn: {tt}.{tc}", ""]
    write(os.path.join(d, "relationships.tmdl"), "\n".join(rel))
    write(os.path.join(d, "cultures", "en-US.tmdl"), "cultureInfo en-US\n\n")


# ---------------------------------------------------------------- report
INK, INK2, GRID, MUTED, PANEL, PAGE = "#0B0B0B", "#52514E", "#E1E0D9", "#898781", "#FCFCFB", "#F9F9F7"
SCOPE_COL = {"C1-only": "#EB6834", "Regional envelope": "#2A78D6", "C1 total (sensitivity)": "#898781"}
FOOTER = ("Scenario model on public data: IMF PortWatch (AIS estimates of total cargo, not food), UN Comtrade 2023, FAOSTAT 2023. "
          "Modeled coverage, not observed. UAE Food Supply Resilience Stress Test v0.1 · Miguel Ángel Hernández Aranda")
SCHEMA_V = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.13.0/schema.json"

# Dark style (Overview). Series colours validated for the dark surface (OKLCH L 0.48-0.67, adjacent CVD >= 6 with direct labels).
D_BG, D_PANEL, D_BORDER = "#07121F", "#0B1B2B", "#183750"
D_TXT, D_TXT2, D_TXT3 = "#E6F1FF", "#8BA6C1", "#5B7590"
D_CYAN, D_AMBER = "#22D3EE", "#F59E0B"          # accents: coverage / gap and concentration (text and KPI values)
D_SERIES = ["#00A3C0", "#9085E9", "#D55181", "#C98500"]  # chart series: cyan, violet, magenta, yellow
D_OUT = ["#6B7F94", "#46586B"]                   # outside the port model (neutral)
LAYOUT = {  # x, y, w, h on the 1280 x 720 page; make_backgrounds.py draws the panels from these boxes
    "left_top": (16, 74, 320, 380), "center": (348, 74, 584, 380), "right": (944, 74, 320, 618),
    "left_bottom": (16, 464, 452, 228), "center_bottom": (480, 464, 452, 228)}
PANELS = {  # panel boxes per page (Overview uses LAYOUT)
    "routes": {"strip": (16, 74, 1248, 108), "chart": (16, 192, 1248, 268), "matrix": (16, 470, 780, 222), "notes": (808, 470, 456, 222)},
    "gap": {"strip": (16, 74, 1248, 66), "chart": (16, 150, 780, 542), "kpis": (808, 150, 456, 362), "off": (808, 522, 456, 170)},
    "sensitivity": {"chart": (16, 74, 780, 618), "matrix": (808, 74, 456, 618)},
    "suppliers": {"hhi": (16, 74, 620, 618), "routes": (648, 74, 616, 618)},
    "nutrition": {"chart": (16, 74, 780, 618), "kpis": (808, 74, 456, 300), "notes": (808, 384, 456, 308)},
    "method": {"left": (16, 74, 620, 618), "right": (648, 74, 616, 618)}}
IMAGES = {k: f"bg_{k}.png" for k in ["overview"] + list(PANELS)}
WORLD_MAP_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2.0.2/countries-50m.json"  # TopoJSON (ISC licence; Natural Earth data, public domain)


def L(v):
    return {"expr": {"Literal": {"Value": v}}}


def S(text):
    return L("'" + text.replace("'", "''") + "'")


def C(hexc):
    return {"solid": {"color": L(f"'{hexc}'")}}


def col(e, p):
    return {"Column": {"Expression": {"SourceRef": {"Entity": e}}, "Property": p}}


def mea(p):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Measures"}}, "Property": p}}


def proj(field, name=None):
    k = "Column" if "Column" in field else "Measure"
    e = field[k]["Expression"]["SourceRef"]["Entity"]; p = field[k]["Property"]
    out = {"field": field, "queryRef": f"{e}.{p}", "nativeQueryRef": name or p}
    if name:
        out["displayName"] = name
    return out


def container(title=None, subtitle=None, alt=None, background=True):
    o = {"title": [{"properties": {"show": L("true" if title else "false")}}],
         "background": [{"properties": {"show": L("true" if background else "false"), "color": C(PANEL), "transparency": L("0.0D")}}],
         "border": [{"properties": {"show": L("false")}}], "dropShadow": [{"properties": {"show": L("false")}}],
         "general": [{"properties": {"altText": S(alt or title or "visual")}}]}
    if title:
        o["title"][0]["properties"].update({"fontSize": L("12.0D"), "fontColor": C(INK), "bold": L("false"),
                                             "fontFamily": S("Segoe UI Semibold"), "text": S(title)})
    o["subTitle"] = [{"properties": {"show": L("true" if subtitle else "false")}}]
    if subtitle:
        o["subTitle"][0]["properties"].update({"text": S(subtitle), "fontColor": C(INK2), "fontSize": L("9.0D")})
    return o


def in_filter(alias, entity, prop, values):
    return {"Version": 2, "From": [{"Name": alias, "Entity": entity, "Type": 0}],
            "Where": [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}}],
                                            "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in values]}}}]}


class Page:
    def __init__(self, key, display, image=None, color=None):
        self.name = hexid("page", key); self.display = display; self.visuals = []; self.z = 0
        self.image = image; self.color = color or PAGE

    def add(self, vtype, pos, visual, cobj, filters=None):
        vid = hexid(self.name, str(len(self.visuals)))
        x, y, w, h = pos
        v = {"$schema": SCHEMA_V, "name": vid,
             "position": {"x": x, "y": y, "z": self.z, "height": h, "width": w, "tabOrder": self.z},
             "visual": dict({"visualType": vtype}, **visual)}
        v["visual"]["visualContainerObjects"] = cobj
        v["visual"]["drillFilterOtherVisuals"] = True
        if filters:
            v["filterConfig"] = {"filters": filters}
        self.z += 1000
        self.visuals.append(v)

    def text(self, pos, runs, size="9pt", color=INK2, bold=False, alt="text", head_color=INK):
        paragraphs = []
        for r in runs:
            head = isinstance(r, tuple)
            r = r[0] if head else r
            style = {"fontFamily": "Segoe UI Semibold" if (bold or head) else "Segoe UI", "fontSize": size,
                     "color": head_color if head else color}
            paragraphs.append({"textRuns": [{"value": r if r else " ", "textStyle": style}]})
        self.add("textbox", pos, {"objects": {"general": [{"properties": {"paragraphs": paragraphs}}]}},
                 {"background": [{"properties": {"show": L("false")}}], "border": [{"properties": {"show": L("false")}}],
                  "general": [{"properties": {"altText": S(alt)}}]})

    def header(self, title, subtitle):
        self.text((24, 16, 1232, 40), [title], size="20pt", color=INK, bold=True, alt="Page title")
        self.text((24, 56, 1232, 28), [subtitle], size="10pt", color=INK2, alt="Page subtitle")
        self.text((24, 680, 1232, 24), [FOOTER], size="8pt", color=INK2, alt="Sources and notes")

    def slicer(self, pos, field, label, default=None):
        objs = {"data": [{"properties": {"mode": S("Dropdown")}}],
                "selection": [{"properties": {"singleSelect": L("true"), "strictSingleSelect": L("true"),
                                              "selectAllCheckboxEnabled": L("false")}}],
                "header": [{"properties": {"show": L("true"), "fontColor": C(INK2)}}],
                "items": [{"properties": {"fontColor": C(INK), "background": C(PANEL)}}]}
        if default:
            e, p = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
            objs["general"] = [{"properties": {"filter": {"filter": in_filter("s", e, p, [default])}}}]
        self.add("slicer", pos, {"query": {"queryState": {"Values": {"projections": [proj(field, label)]}}}, "objects": objs},
                 container(alt=f"Slicer: {label}", background=False))

    def card(self, pos, measure, title, subtitle=None, precision=None, size=26):
        lab = {"fontSize": L(f"{size}.0D"), "color": C(INK), "labelDisplayUnits": L("1.0D")}
        if precision is not None:
            lab["labelPrecision"] = L(f"{precision}L")
        self.add("card", pos, {"query": {"queryState": {"Values": {"projections": [proj(mea(measure))]}}},
                               "objects": {"labels": [{"properties": lab}], "categoryLabels": [{"properties": {"show": L("false")}}]}},
                 container(title, subtitle, alt=f"Card: {title}"))

    def chart(self, vtype, pos, title, subtitle, state, objects=None, sort=None, filters=None):
        visual = {"query": {"queryState": state}}
        if sort:
            visual["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
        base = {"legend": [{"properties": {"show": L("true"), "position": S("Top"), "labelColor": C(INK2)}}],
                "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(INK2)}}],
                "valueAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(INK2), "gridlineColor": C(GRID)}}]}
        base.update(objects or {})
        visual["objects"] = base
        self.add(vtype, pos, visual, container(title, subtitle), filters)

    def matrix(self, pos, title, subtitle, rows, cols, values, sort=None, text=10, pad=4):
        state = {"Rows": {"projections": rows}, "Values": {"projections": values}}
        if cols:
            state["Columns"] = {"projections": cols}
        visual = {"query": {"queryState": state},
                  "objects": {"columnHeaders": [{"properties": {"fontColor": C(INK2), "bold": L("true")}}],
                              "rowHeaders": [{"properties": {"fontColor": C(INK)}}],
                              "values": [{"properties": {"fontColor": C(INK)}}],
                              "grid": [{"properties": {"textSize": L(f"{text}.0D"), "rowPadding": L(f"{pad}.0D")}}],
                              "subTotals": [{"properties": {"rowSubtotals": L("false"), "columnSubtotals": L("false")}}]}}
        if sort:
            visual["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
        self.add("pivotTable", pos, visual, container(title, subtitle))


def dp_series(entity, prop, colors):
    return [{"properties": {"fill": C(c)}, "selector": {"data": [{"scopeId": {"Comparison": {"ComparisonKind": 0,
            "Left": col(entity, prop), "Right": {"Literal": {"Value": f"'{v}'"}}}}}]}} for v, c in colors.items()]


def dp_measures(colors):
    return [{"properties": {"fill": C(c)}, "selector": {"metadata": f"_Measures.{m}"}} for m, c in colors.items()]


def build_report(out, base_theme):
    rp = os.path.join(out, f"{NAME}.Report")
    d = os.path.join(rp, "definition")
    wjson(os.path.join(rp, ".platform"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": NAME}, "config": {"version": "2.0", "logicalId": tag("rp", NAME)}})
    wjson(os.path.join(rp, "definition.pbir"), {"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    wjson(os.path.join(d, "version.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    theme_name = "P2_Food_Resilience_theme.json"
    shutil.copy(base_theme, os.path.join(_mk(os.path.join(rp, "StaticResources", "SharedResources", "BaseThemes")), "Fluent2-CY26SU09.json"))
    wjson(os.path.join(rp, "StaticResources", "RegisteredResources", theme_name), THEME)
    here = os.path.dirname(os.path.abspath(__file__))
    for img in IMAGES.values():
        shutil.copy(os.path.join(here, "assets", img), os.path.join(rp, "StaticResources", "RegisteredResources", img))
    ver = {"visual": "2.13.0", "report": "3.4.0", "page": "2.3.1"}
    wjson(os.path.join(d, "report.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.3.0/schema.json",
        "themeCollection": {"baseTheme": {"name": "Fluent2-CY26SU09", "reportVersionAtImport": ver, "type": "SharedResources"},
                            "customTheme": {"name": theme_name, "reportVersionAtImport": ver, "type": "RegisteredResources"}},
        "objects": {"section": [{"properties": {"verticalAlignment": S("Top")}}]},
        "resourcePackages": [
            {"name": "SharedResources", "type": "SharedResources", "items": [{"name": "Fluent2-CY26SU09", "path": "BaseThemes/Fluent2-CY26SU09.json", "type": "BaseTheme"}]},
            {"name": "RegisteredResources", "type": "RegisteredResources",
             "items": [{"name": theme_name, "path": theme_name, "type": "CustomTheme"}] + [{"name": i, "path": i, "type": "Image"} for i in IMAGES.values()]}],
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True, "locale": "en-US"}})
    pages = make_pages()
    wjson(os.path.join(d, "pages", "pages.json"), {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json",
        "pageOrder": [p.name for p in pages], "activePageName": pages[0].name})
    for p in pages:
        wjson(os.path.join(d, "pages", p.name, "page.json"), {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json",
            "name": p.name, "displayName": p.display, "displayOption": "FitToPage", "height": 720, "width": 1280,
            "objects": page_objects(p)})
        for v in p.visuals:
            wjson(os.path.join(d, "pages", p.name, "visuals", v["name"], "visual.json"), v)


def page_objects(p):
    bg = {"color": C(p.color), "transparency": L("0.0D")}
    if p.image:
        bg["image"] = {"image": {"name": S(p.image),
                                 "url": {"expr": {"ResourcePackageItem": {"PackageName": "RegisteredResources", "PackageType": 1, "ItemName": p.image}}},
                                 "scaling": S("Fit")}}
    return {"background": [{"properties": bg}], "outspace": [{"properties": {"color": C(p.color)}}]}


def _mk(p):
    os.makedirs(p, exist_ok=True)
    return p


THEME = {"name": "P2 Food Resilience (dark)", "dataColors": D_SERIES + ["#5BC6DA", "#9EDDEA", "#6B7F94", "#46586B"],
         "good": "#00A3C0", "neutral": "#C98500", "bad": "#D55181", "foreground": D_TXT, "foregroundNeutralSecondary": D_TXT2,
         "firstLevelElements": D_TXT, "secondLevelElements": D_TXT2, "thirdLevelElements": D_BORDER, "fourthLevelElements": D_TXT3,
         "background": D_PANEL, "secondaryBackground": D_BORDER, "tableAccent": D_CYAN,
         "textClasses": {"callout": {"fontSize": 24, "fontFace": "Segoe UI Semibold", "color": D_TXT},
                         "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": D_TXT},
                         "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": D_TXT},
                         "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": D_TXT}}}


def scenario_slicers(p, y=96):
    p.slicer((24, y, 300, 64), col("scenarios", "scope"), "Scope", "C1-only")
    p.slicer((340, y, 300, 64), col("scenarios", "activity_level"), "Activity level", "Low")
    p.slicer((656, y, 300, 64), col("demand_levels", "demand"), "2026 demand", "High")
    p.slicer((972, y, 284, 64), col("Food share", "Label"), "Food share of incremental cargo", "19.67% (benchmark)")


def d_container(alt):
    return {"title": [{"properties": {"show": L("false")}}], "subTitle": [{"properties": {"show": L("false")}}],
            "background": [{"properties": {"show": L("false")}}], "border": [{"properties": {"show": L("false")}}],
            "dropShadow": [{"properties": {"show": L("false")}}], "general": [{"properties": {"altText": S(alt)}}]}


def d_panel_title(p, box, label):
    x, y, w, _ = box
    p.text((x + 10, y + 6, w - 20, 26), [label], size="9pt", color=D_CYAN, bold=True, alt=f"Panel title: {label}")


def d_card(p, pos, measure, label, color, size=24, precision=None):
    lab = {"fontSize": L(f"{size}D"), "color": C(color), "labelDisplayUnits": L("1D"), "fontFamily": S("Segoe UI Semibold")}
    if precision is not None:
        lab["labelPrecision"] = L(f"{precision}L")
    p.add("card", pos, {"query": {"queryState": {"Values": {"projections": [proj(mea(measure), label)]}}},
                        "objects": {"labels": [{"properties": lab}],
                                    "categoryLabels": [{"properties": {"show": L("true"), "color": C(D_TXT2), "fontSize": L("9D")}}]}},
          d_container(f"KPI: {label}"))


def d_tiles(p, pos, field, label, default, filters=None):
    e, prop = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
    objs = {"data": [{"properties": {"mode": S("Basic")}}],
            "general": [{"properties": {"orientation": L("1D"), "filter": {"filter": in_filter("s", e, prop, [default])}}}],
            "selection": [{"properties": {"singleSelect": L("true"), "strictSingleSelect": L("true"), "selectAllCheckboxEnabled": L("false")}}],
            "header": [{"properties": {"show": L("true"), "fontColor": C(D_TXT2), "textSize": L("8D"), "outline": S("None")}}],
            "items": [{"properties": {"fontColor": C(D_TXT), "background": C(D_PANEL), "textSize": L("9D"),
                                      "outline": S("Frame"), "outlineColor": C(D_BORDER)}}]}
    p.add("slicer", pos, {"query": {"queryState": {"Values": {"projections": [proj(field, label)]}}}, "objects": objs},
          d_container(f"Scenario buttons: {label}"), filters)


def d_dropdown(p, pos, field, label, default):
    e, prop = field["Column"]["Expression"]["SourceRef"]["Entity"], field["Column"]["Property"]
    objs = {"data": [{"properties": {"mode": S("Dropdown")}}],
            "general": [{"properties": {"filter": {"filter": in_filter("s", e, prop, [default])}}}],
            "selection": [{"properties": {"singleSelect": L("true"), "strictSingleSelect": L("true"), "selectAllCheckboxEnabled": L("false")}}],
            "header": [{"properties": {"show": L("true"), "fontColor": C(D_TXT2), "textSize": L("8D"), "outline": S("None")}}],
            "items": [{"properties": {"fontColor": C(D_TXT), "background": C(D_PANEL), "textSize": L("9D"),
                                      "outline": S("Frame"), "outlineColor": C(D_BORDER)}}]}
    p.add("slicer", pos, {"query": {"queryState": {"Values": {"projections": [proj(field, label)]}}}, "objects": objs},
          d_container(f"Dropdown: {label}"))


def d_header(p, title, subtitle, title_w=560):
    p.text((16, 8, title_w, 34), [title], size="18pt", color=D_TXT, bold=True, alt="Page title")
    p.text((16, 40, title_w, 22), [subtitle], size="9pt", color=D_TXT2, alt="Page subtitle")
    p.text((16, 694, 1248, 24), [FOOTER], size="8pt", color=D_TXT2, alt="Sources and notes")


def d_inner(box, top=28, pad=8):
    x, y, w, h = box
    return (x + pad, y + top, w - 2 * pad, h - top - pad)


def d_matrix(p, pos, rows, cols, values, alt, text=11, pad=6, sort=None):
    state = {"Rows": {"projections": rows}, "Values": {"projections": values}}
    if cols:
        state["Columns"] = {"projections": cols}
    visual = {"query": {"queryState": state},
              "objects": {"columnHeaders": [{"properties": {"fontColor": C(D_TXT2), "backColor": C(D_PANEL), "bold": L("true"),
                                                            "outline": S("BottomOnly"), "outlineColor": C(D_BORDER)}}],
                          "rowHeaders": [{"properties": {"fontColor": C(D_TXT), "backColor": C(D_PANEL), "outline": S("None")}}],
                          "values": [{"properties": {"fontColorPrimary": C(D_TXT), "backColorPrimary": C(D_PANEL),
                                                     "fontColorSecondary": C(D_TXT), "backColorSecondary": C(D_PANEL)}}],
                          "grid": [{"properties": {"textSize": L(f"{text}D"), "rowPadding": L(f"{pad}D"), "gridHorizontal": L("true"),
                                                   "gridHorizontalColor": C(D_BORDER), "gridVertical": L("false"), "outlineColor": C(D_BORDER)}}],
                          "subTotals": [{"properties": {"rowSubtotals": L("false"), "columnSubtotals": L("false")}}]}}
    if sort:
        visual["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    p.add("pivotTable", pos, visual, d_container(alt))


def d_chart(p, vtype, pos, state, objects, alt, sort=None, filters=None):
    visual = {"query": {"queryState": state}, "objects": d_axes(objects)}
    if sort:
        visual["query"]["sortDefinition"] = {"sort": sort, "isDefaultSort": False}
    p.add(vtype, pos, visual, d_container(alt), filters)


def bar_labels(size=9, units="1D", precision="0L"):
    return [{"properties": {"show": L("true"), "color": C(D_TXT), "fontSize": L(f"{size}D"),
                            "labelDisplayUnits": L(units), "labelPrecision": L(precision)}}]


def d_axes(extra=None):
    o = {"legend": [{"properties": {"show": L("true"), "position": S("Top"), "labelColor": C(D_TXT2), "fontSize": L("8D")}}],
         "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT2), "fontSize": L("8D"), "gridlineShow": L("false")}}],
         "valueAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT2), "fontSize": L("8D"), "gridlineColor": C(D_BORDER)}}]}
    o.update(extra or {})
    return o


def make_overview():
    p = Page("overview", "Overview", image=IMAGES["overview"], color=D_BG)
    lt, ce, ri, lb, cb = (LAYOUT[k] for k in ("left_top", "center", "right", "left_bottom", "center_bottom"))
    # header
    p.text((16, 8, 356, 34), ["UAE FOOD SUPPLY RESILIENCE"], size="18pt", color=D_TXT, bold=True, alt="Report title")
    p.text((16, 40, 356, 22), ["Hormuz + Red Sea/Suez stress test · baseline frozen 6 Oct 2026"], size="9pt", color=D_TXT2, alt="Report subtitle")
    d_tiles(p, (380, 6, 340, 56), col("scenarios", "scope"), "Scope", "C1-only")
    d_tiles(p, (730, 6, 320, 56), col("scenarios", "activity_level"), "Activity level", "Low")
    d_tiles(p, (1060, 6, 204, 56), col("demand_levels", "demand"), "2026 demand", "High")
    # left top: requirement by mode
    d_panel_title(p, lt, "2026 REQUIREMENT BY MODE · T/DAY")
    mode_cols = {"Requirement: containers (t/d)": D_SERIES[0], "Requirement: dry bulk (t/d)": D_SERIES[1],
                 "Requirement: road, TER (t/d)": D_OUT[0], "Requirement: liquid bulk, GL (t/d)": D_OUT[1]}
    mode_lab = ["Containers", "Dry bulk", "Road", "Liquid bulk"]
    p.add("donutChart", (lt[0] + 8, lt[1] + 30, lt[2] - 16, 248),
          {"query": {"queryState": {"Y": {"projections": [proj(mea(m), n) for m, n in zip(mode_cols, mode_lab)]}}},
           "objects": {"legend": [{"properties": {"show": L("true"), "position": S("Bottom"), "labelColor": C(D_TXT2), "fontSize": L("8D")}}],
                       "labels": [{"properties": {"show": L("true"), "color": C(D_TXT), "fontSize": L("9D"), "labelStyle": S("Data"),
                                                  "labelDisplayUnits": L("1D"), "labelPrecision": L("0L")}}],
                       "centerValue": [{"properties": {"show": L("false")}}],
                       "dataPoint": dp_measures(mode_cols)}},
          d_container("Donut: 2026 shipment requirement by transport mode"))
    d_card(p, (lt[0] + 8, lt[1] + 282, lt[2] - 16, 90), "Port-modeled share", "Share modeled at ports", D_CYAN, 22, 1)
    # centre: supplier globe and scenario KPIs
    d_panel_title(p, ce, "WHERE THE BASKET COMES FROM · CLICK A COUNTRY")
    p.add("shapeMap", (ce[0] + 12, ce[1] + 28, ce[2] - 24, ce[3] - 36),
          {"query": {"queryState": {"Category": {"projections": [proj(col("countries", "map_name"), "Country")]},
                                    "Tooltips": {"projections": [proj(mea("Largest-share product"), "Product"),
                                                                 proj(mea("Largest supplier share"), "Largest single-product share"),
                                                                 proj(mea("Basket items in Top 5"), "Basket items in Top 5")]}}},
           "objects": {"shape": [{"properties": {"datasourceType": S("url"), "mapUrl": S(WORLD_MAP_URL), "projectionEnum": S("orthographic")}}],
                       "dataPoint": [{"properties": {"fill": C(D_CYAN)}}],
                       "defaultColors": [{"properties": {"defaultShow": L("true"), "defaultColor": C("#14304A"),
                                                         "borderColor": C(D_BG), "borderThickness": L("1D")}}]}},
          d_container("Map: supplier countries of the basket; tooltip shows each country's largest single-product import-value share"))
    kx1, kx2, ky1, ky2, kw, kh = ce[0] + 12, ce[0] + ce[2] - 192, ce[1] + 28, ce[1] + ce[3] - 92, 180, 86
    d_card(p, (kx1, ky1, kw, kh), "ACR_ref", "Port coverage", D_CYAN, 24, 1)
    d_card(p, (kx2, ky1, kw, kh), "Gap_ref (t/d)", "Port gap · t/day", D_AMBER, 24, 1)
    d_card(p, (kx1, ky2, kw, kh), "ACR_ref container", "Container coverage", D_CYAN, 24, 2)
    d_card(p, (kx2, ky2, kw, kh), "KPI container gap C1 total Low (t/d)", "C1 total gap · t/day", D_AMBER, 24, 1)
    # right: supplier table with flags
    d_panel_title(p, ri, "MAIN SUPPLIERS · LARGEST SINGLE-PRODUCT SHARE")
    # the table keeps ~18 px of inner padding per side plus an 8 px scrollbar: 312 px visual -> 268 px of columns
    widths = {"countries.flag": 22, "countries.country": 78, "_Measures.Largest-share product": 88,
              "_Measures.Largest supplier share": 42, "_Measures.Basket items in Top 5": 38}
    p.add("tableEx", (ri[0] + 4, ri[1] + 30, ri[2] - 8, ri[3] - 62),
          {"query": {"queryState": {"Values": {"projections": [
              proj(col("countries", "flag"), " "), proj(col("countries", "country"), "Country"),
              proj(mea("Largest-share product"), "Product"), proj(mea("Largest supplier share"), "Share"),
              proj(mea("Basket items in Top 5"), "Items")]}},
              "sortDefinition": {"sort": [{"field": mea("Largest supplier share"), "direction": "Descending"}], "isDefaultSort": False}},
           "objects": {"grid": [{"properties": {"gridVertical": L("false"), "gridHorizontal": L("true"), "gridHorizontalColor": C(D_BORDER),
                                                "rowPadding": L("4D"), "textSize": L("8D"), "imageHeight": L("16D"),
                                                "outlineColor": C(D_BORDER)}}],
                       "columnWidth": [{"properties": {"value": L(f"{w}D")}, "selector": {"metadata": m}} for m, w in widths.items()],
                       "columnHeaders": [{"properties": {"fontColor": C(D_TXT2), "backColor": C(D_PANEL), "fontSize": L("8D"),
                                                         "outline": S("BottomOnly"), "outlineColor": C(D_BORDER),
                                                         # fixed column widths, written the way current Power BI Desktop
                                                         # stores "Column width > Sizing behavior: Fixed width"
                                                         "autoSizeColumnWidth": L("true"), "columnAdjustment": S("fixedWidth"),
                                                         "defaultColumnWidth": L("90D")}}],
                       "values": [{"properties": {"fontColorPrimary": C(D_TXT), "backColorPrimary": C(D_PANEL),
                                                  "fontColorSecondary": C(D_TXT), "backColorSecondary": C(D_PANEL)}}],
                       "total": [{"properties": {"totals": L("false")}}],
                       "columnFormatting": [{"properties": {"dataBars": {"positiveColor": C("#0E7490"), "negativeColor": C(D_AMBER),
                                                                          "axisColor": C(D_BORDER), "reverseDirection": L("false"), "hideText": L("false")}},
                                             "selector": {"metadata": "_Measures.Largest supplier share"}}]}},
          d_container("Table: main supplier countries with the product of their largest single-product import-value share and the number of basket items where they are a Top-5 supplier"))
    p.text((ri[0] + 10, ri[1] + 592, ri[2] - 20, 22), ["Items = basket items where the country is a Top-5 supplier"],
           size="8pt", color=D_TXT2, alt="Definition of Items in the supplier table")
    # bottom left: weekly container imports
    d_panel_title(p, lb, "WEEKLY CONTAINER IMPORTS AT ALTERNATIVE PORTS · KT/WEEK")
    corr = {"C1 UAE east coast (Fujairah, Khor Fakkan)": D_SERIES[0], "C2a Oman: Sohar": D_SERIES[1], "C2b Oman: Duqm, Salalah": D_SERIES[2]}
    p.add("lineChart", (lb[0] + 8, lb[1] + 28, lb[2] - 16, lb[3] - 36),
          {"query": {"queryState": {"Category": {"projections": [proj(col("corridor_weekly", "week"), "Week")]},
                                    "Series": {"projections": [proj(col("corridor_weekly", "corridor_code"), "Corridor")]},
                                    "Y": {"projections": [proj(mea("Weekly imports (kt)"), "Imports (kt/week)")]}},
                     "sortDefinition": {"sort": [{"field": col("corridor_weekly", "week"), "direction": "Ascending"}], "isDefaultSort": False}},
           "objects": d_axes({"dataPoint": dp_series("corridor_weekly", "corridor_code", {"C1": D_SERIES[0], "C2a": D_SERIES[1], "C2b": D_SERIES[2]}),
                              "lineStyles": [{"properties": {"strokeWidth": L("2L"), "showMarker": L("false")}}]})},
          d_container("Line chart: weekly container imports by corridor"),
          [{"name": hexid("f", "ov_corr"), "field": col("corridor_weekly", "corridor_code"), "type": "Categorical",
            "filter": in_filter("c", "corridor_weekly", "corridor_code", ["C1", "C2a", "C2b"])}])
    # bottom centre: most concentrated items
    d_panel_title(p, cb, "MOST CONCENTRATED ITEMS · HHI 0–10,000")
    top5 = ["Raw sugar", "Frozen poultry", "Rice, all forms", "Eggs in shell", "Fresh/chilled poultry"]
    p.add("clusteredColumnChart", (cb[0] + 8, cb[1] + 28, cb[2] - 16, cb[3] - 36),
          {"query": {"queryState": {"Category": {"projections": [proj(col("supplier_concentration", "supplier_group_name"), "Item")]},
                                    "Y": {"projections": [proj(mea("HHI"), "HHI")]}},
                     "sortDefinition": {"sort": [{"field": mea("HHI"), "direction": "Descending"}], "isDefaultSort": False}},
           "objects": d_axes({"legend": [{"properties": {"show": L("false")}}],
                              "valueAxis": [{"properties": {"show": L("false"), "gridlineShow": L("false")}}],
                              "dataPoint": [{"properties": {"fill": C(D_AMBER)}}],
                              "labels": [{"properties": {"show": L("true"), "color": C(D_TXT), "fontSize": L("9D"),
                                                         "labelDisplayUnits": L("1D"), "labelPrecision": L("0L")}}]})},
          d_container("Column chart: the five most concentrated basket items by HHI"),
          [{"name": hexid("f", "ov_hhi"), "field": col("supplier_concentration", "supplier_group_name"), "type": "Categorical",
            "filter": in_filter("h", "supplier_concentration", "supplier_group_name", top5)}])
    p.text((16, 694, 1248, 24), ["Modeled scenario on public data: IMF PortWatch (AIS estimates of total cargo, not food), UN Comtrade 2023, FAOSTAT 2023. "
                                 "Coverage is modeled, not observed. v0.1 · Miguel Ángel Hernández Aranda · Static PDF export · globe and table interactivity in the .pbix"],
           size="8pt", color=D_TXT2, alt="Sources and notes")
    return p


def page_routes():
    p = Page("routes", "Alternative routes", image=IMAGES["routes"], color=D_BG); P = PANELS["routes"]
    d_header(p, "ALTERNATIVE ROUTES", "Observed weekly cargo at ports outside Hormuz · IMF PortWatch AIS estimates of total cargo, not food", 640)
    seg_filter = [{"name": hexid("f", "segtiles"), "field": col("segments", "segment_name"), "type": "Categorical",
                   "filter": in_filter("g", "segments", "segment_name", ["Container", "Dry bulk", "General cargo + RoRo"])}]
    d_tiles(p, (700, 6, 564, 56), col("segments", "segment_name"), "Cargo segment", "Container", seg_filter)
    d_panel_title(p, P["strip"], "CHOKEPOINT TRANSITS · CARGO SHIPS, NO TANKERS · CLOSURE AVERAGE VS PRE-WAR BASE")
    x, y, w, h = P["strip"]
    for i, (name, colr) in enumerate([("Hormuz", D_AMBER), ("Bab el-Mandeb", D_TXT), ("Suez", D_TXT), ("Cape of Good Hope", D_TXT)]):
        pos = (x + 12 + i * 306, y + 22, 300, 82)
        p.add("card", pos, {"query": {"queryState": {"Values": {"projections": [proj(mea("Transit change vs base"), name)]}}},
                            "objects": {"labels": [{"properties": {"fontSize": L("20D"), "color": C(colr), "fontFamily": S("Segoe UI Semibold")}}],
                                        "categoryLabels": [{"properties": {"show": L("true"), "color": C(D_TXT2), "fontSize": L("9D")}}]}},
              d_container(f"KPI: {name} transits"),
              [{"name": hexid("f", "chk", name), "field": col("chokepoints", "chokepoint"), "type": "Categorical",
                "filter": in_filter("k", "chokepoints", "chokepoint", [name])},
               {"name": hexid("f", "chkt", name), "field": col("chokepoints", "ship_type"), "type": "Categorical",
                "filter": in_filter("t", "chokepoints", "ship_type", ["Cargo ships (no tankers)"])}])
    d_panel_title(p, P["chart"], "WEEKLY IMPORTS BY CORRIDOR · THOUSAND TONNES PER WEEK · SELECTED SEGMENT")
    corr = {"C1 UAE east coast (Fujairah, Khor Fakkan)": D_SERIES[0], "C2a Oman: Sohar": D_SERIES[1],
            "C2b Oman: Duqm, Salalah": D_SERIES[2], "C3a Saudi Red Sea: Jeddah, KAP (low reliability)": "#6B7F94"}
    d_chart(p, "lineChart", d_inner(P["chart"]),
            {"Category": {"projections": [proj(col("corridor_weekly", "week"), "Week")]},
             "Series": {"projections": [proj(col("corridor_weekly", "corridor"), "Corridor")]},
             "Y": {"projections": [proj(mea("Weekly imports (kt)"), "Imports (kt/week)")]}},
            {"dataPoint": dp_series("corridor_weekly", "corridor", corr),
             "lineStyles": [{"properties": {"strokeWidth": L("2L"), "showMarker": L("false")}}]},
            "Line chart: weekly imports by corridor", sort=[{"field": col("corridor_weekly", "week"), "direction": "Ascending"}])
    d_panel_title(p, P["matrix"], "ACTIVITY OVER THE PRE-WAR BASE · T/DAY · C1 TOTAL ROW = BASE + INCREMENT")
    d_matrix(p, d_inner(P["matrix"]), [proj(col("scenarios", "scope"), "Scope")], [proj(col("scenarios", "activity_level"), "Activity level")],
             [proj(mea("Increment (t/d)"), "Increment (t/day)")], "Matrix: activity over the pre-war base by scope and activity level", text=12, pad=8)
    d_panel_title(p, P["notes"], "ACTIVITY, NOT CAPACITY")
    p.text(d_inner(P["notes"], top=32, pad=12), [
        "PortWatch estimates total cargo from ship signals. It does not show how much of it was food or how much room was left.",
        "Increments over the base count as 0 when a corridor is below it. The C1 total row is total activity: base + increment.",
        "C1-only is the UAE-attributable floor; the regional envelope adds Oman's ports, which also serve Oman's own demand and need a land leg.",
        "C3a (Saudi Red Sea) has a PortWatch anomaly in Aug–Sep 2026 and is only a separate sensitivity."],
        size="9pt", color=D_TXT, alt="Notes on corridor activity")
    return p


def page_gap():
    p = Page("gap", "Gap by commodity", image=IMAGES["gap"], color=D_BG); P = PANELS["gap"]
    d_header(p, "GAP BY COMMODITY", "Gap = requirement × (1 − ACR_ref), split in proportion within each segment · a modeled gap, not an observed shortage", 1000)
    x, y, w, h = P["strip"]
    d_tiles(p, (x + 12, y + 4, 340, 58), col("scenarios", "scope"), "Scope", "C1-only")
    d_tiles(p, (x + 362, y + 4, 320, 58), col("scenarios", "activity_level"), "Activity level", "Low")
    d_tiles(p, (x + 692, y + 4, 204, 58), col("demand_levels", "demand"), "2026 demand", "High")
    d_dropdown(p, (x + 912, y + 6, 324, 54), col("Food share", "Label"), "Food share of incremental cargo", "19.67% (benchmark)")
    d_panel_title(p, P["chart"], "MODELED GAP BY COMMODITY FORM · T/DAY · PROPORTIONAL ALLOCATION, NOT OBSERVED SHORTAGE")
    cx, cy, cw, ch = d_inner(P["chart"])
    p.text((cx + 2, cy + ch - 24, cw - 4, 24),
           ["Not shown: forms with a gap ≤0.001 t/day (zero included), forms outside the port model (right) and bread (counted in wheat)."],
           size="8pt", color=D_TXT2, alt="Note on forms not shown in the gap chart")
    d_chart(p, "clusteredBarChart", (cx, cy, cw, ch - 26),
            {"Category": {"projections": [proj(col("commodities", "subgroup"), "Commodity form")]},
             "Y": {"projections": [proj(mea("Gap_ref by subgroup (bar)"), "Gap (t/day)")]}},
            {"dataPoint": [{"properties": {"fill": C(D_AMBER)}}], "labels": bar_labels(10, "1D", "1L"),
             "legend": [{"properties": {"show": L("false")}}], "valueAxis": [{"properties": {"show": L("false"), "gridlineShow": L("false")}}],
             "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT), "fontSize": L("10D")}}]},
            "Bar chart: modeled gap by commodity form", sort=[{"field": mea("Gap_ref by subgroup (bar)"), "direction": "Descending"}])
    d_panel_title(p, P["kpis"], "SELECTED SCENARIO · CONTAINERS")
    kx, ky, kw, kh = P["kpis"]
    d_card(p, (kx + 12, ky + 30, kw - 24, 92), "ACR_ref container", "Container coverage (ACR_ref)", D_CYAN, 26, 2)
    d_card(p, (kx + 12, ky + 128, kw - 24, 92), "Gap_ref container (t/d)", "Container gap · t/day", D_AMBER, 26, 1)
    d_card(p, (kx + 12, ky + 226, kw - 24, 92), "Truck-equivalent trips covered", "Truck-equivalent trips/day · covered container volume", D_TXT, 26, 0)
    p.add("textbox", (kx + 12, ky + 320, kw - 24, 30),
          {"objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{"value": "Lower bound · container forms only · not trips to close the gap",
                                                                                 "textStyle": {"fontFamily": "Segoe UI", "fontSize": "8pt", "color": D_TXT2}}],
                                                                  "horizontalTextAlignment": "center"}]}}]}},
          {"background": [{"properties": {"show": L("false")}}], "border": [{"properties": {"show": L("false")}}],
           "general": [{"properties": {"altText": S("Qualifier of the truck-equivalent trips card")}}]})
    d_panel_title(p, P["off"], "OUTSIDE THE PORT MODEL · T/DAY")
    ox, oy, ow, oh = P["off"]
    d_card(p, (ox + 12, oy + 34, ow // 2 - 18, 120), "TER requirement (t/d)", "Road: fresh poultry, dairy", D_TXT, 22, 1)
    d_card(p, (ox + ow // 2 + 6, oy + 34, ow // 2 - 18, 120), "GL requirement (t/d)", "Liquid bulk: crude oil", D_TXT, 22, 1)
    return p


def page_sensitivity():
    p = Page("sensitivity", "Food-share sensitivity", image=IMAGES["sensitivity"], color=D_BG); P = PANELS["sensitivity"]
    d_header(p, "FOOD-SHARE SENSITIVITY", "Container coverage as the food share of incremental cargo changes (C1 total: total activity, base + increment) · benchmark 19.67%, confidence C", 840)
    d_tiles(p, (1060, 6, 204, 56), col("demand_levels", "demand"), "2026 demand", "High")
    sc_cols = {"C1-only | Low": D_SERIES[0], "C1-only | Base": "#5BC6DA", "C1-only | High synchronized": "#9EDDEA",
               "Regional envelope | Low": D_SERIES[1], "C1 total (sensitivity) | Low": D_SERIES[2]}
    d_panel_title(p, P["chart"], "CONTAINER ACR_REF BY FOOD SHARE · EACH LINE REACHES 100% AT ITS BREAK-EVEN")
    d_chart(p, "lineChart", d_inner(P["chart"]),
            {"Category": {"projections": [proj(col("food_share_sensitivity", "food_share"), "Food share")]},
             "Series": {"projections": [proj(col("scenarios", "scenario"), "Scenario")]},
             "Y": {"projections": [proj(mea("C_ref container (sensitivity)"), "Container ACR_ref")]}},
            {"dataPoint": dp_series("scenarios", "scenario", sc_cols),
             "lineStyles": [{"properties": {"strokeWidth": L("2L"), "showMarker": L("false")}}],
             "valueAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT2), "fontSize": L("8D"),
                                           "gridlineColor": C(D_BORDER), "start": L("0.4D"), "end": L("1.0D")}}]},
            "Line chart: container ACR_ref by food share", sort=[{"field": col("food_share_sensitivity", "food_share"), "direction": "Ascending"}])
    d_panel_title(p, P["matrix"], "FOOD SHARE NEEDED FOR FULL CONTAINER COVERAGE")
    mx, my, mw, mh = P["matrix"]
    d_matrix(p, (mx + 8, my + 32, mw - 16, 420), [proj(col("scenarios", "scenario"), "Scenario")], None,
             [proj(mea("Break-even food share container"), "Break-even share")], "Matrix: break-even food share by scenario", text=11, pad=8)
    p.text((mx + 12, my + 470, mw - 24, 140), ["Break-even = requirement ÷ incremental cargo; for the C1 total rows, requirement ÷ total activity (base + increment). A value below the 19.67% benchmark means the scenario is covered under the benchmark.",
                                               "",
                                               "C1 containers · high demand · 19.6656% benchmark: threshold 25,577.5 t/day of total incremental cargo; first 8 weeks 14,852; remaining 21 weeks 25,300."],
           size="9pt", color=D_TXT2, alt="Break-even note and container threshold context")
    return p


def page_suppliers():
    p = Page("suppliers", "Suppliers and routes", image=IMAGES["suppliers"], color=D_BG); P = PANELS["suppliers"]
    d_header(p, "SUPPLIERS AND ROUTES", "UN Comtrade 2023 import values · routes inferred by origin country, not tracked by shipment", 900)
    d_panel_title(p, P["hhi"], "SUPPLIER CONCENTRATION · HHI 0–10,000")
    d_chart(p, "clusteredBarChart", d_inner(P["hhi"]),
            {"Category": {"projections": [proj(col("supplier_concentration", "supplier_group_name"), "Commodity form")]},
             "Y": {"projections": [proj(mea("HHI"), "HHI")]}},
            {"dataPoint": [{"properties": {"fill": C(D_AMBER)}}], "labels": bar_labels(10),
             "legend": [{"properties": {"show": L("false")}}], "valueAxis": [{"properties": {"show": L("false"), "gridlineShow": L("false")}}],
             "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT), "fontSize": L("10D")}}]},
            "Bar chart: supplier concentration by commodity form", sort=[{"field": mea("HHI"), "direction": "Descending"}])
    rcols = {"Red Sea confirmed": D_SERIES[2], "Red Sea conditional": D_SERIES[3], "No Red Sea or regional": D_SERIES[0], "Outside Top 5": "#46586B"}
    d_panel_title(p, P["routes"], "ROUTE EXPOSURE WITHIN THE TOP 5 SUPPLIERS · SHARE OF IMPORT VALUE")
    d_chart(p, "barChart", d_inner(P["routes"]),
            {"Category": {"projections": [proj(col("supplier_concentration", "supplier_group_name"), "Commodity form")]},
             "Y": {"projections": [proj(mea(m), m) for m in rcols]}},
            {"dataPoint": dp_measures(rcols), "labels": bar_labels(8, "1D", "1L"),
             "valueAxis": [{"properties": {"show": L("true"), "showAxisTitle": L("false"), "labelColor": C(D_TXT2), "fontSize": L("8D"),
                                           "gridlineShow": L("true"), "gridlineColor": C(D_BORDER), "start": L("0D"), "end": L("1D")}}],
             "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT), "fontSize": L("10D")}}]},
            "Stacked bar chart: route exposure within the Top 5 suppliers", sort=[{"field": mea("Red Sea confirmed"), "direction": "Descending"}])
    return p


def page_nutrition():
    p = Page("nutrition", "Nutrition", image=IMAGES["nutrition"], color=D_BG); P = PANELS["nutrition"]
    d_header(p, "NUTRITION", "Import-dependent requirement of the analytical basket (2026 residents) by tonnage, energy and protein · FAOSTAT 2023 densities", 840)
    d_tiles(p, (1060, 6, 204, 56), col("demand_levels", "demand"), "2026 demand", "High")
    ncols = {"Tonnage share": "#6B7F94", "Energy share": D_SERIES[3], "Protein share": D_SERIES[0]}
    d_panel_title(p, P["chart"], "SHARE OF THE IMPORT-DEPENDENT REQUIREMENT BY CATEGORY · LABELS: ENERGY AND PROTEIN · GREY BAR: TONNAGE")
    d_chart(p, "clusteredBarChart", d_inner(P["chart"]),
            {"Category": {"projections": [proj(col("categories", "category"), "Category")]},
             "Y": {"projections": [proj(mea(m), m) for m in ncols]}},
            {"dataPoint": dp_measures(ncols), "valueAxis": [{"properties": {"show": L("false"), "gridlineShow": L("false")}}],
             "labels": [{"properties": {"show": L("true"), "color": C(D_TXT), "fontSize": L("8D"), "labelPrecision": L("1L"),
                                        "labelOverflow": L("true"), "labelPosition": S("OutsideEnd")}},
                        {"properties": {"show": L("false")}, "selector": {"metadata": "_Measures.Tonnage share"}}],
             "categoryAxis": [{"properties": {"showAxisTitle": L("false"), "labelColor": C(D_TXT), "fontSize": L("10D"), "innerPadding": L("12L")}}]},
            "Bar chart: tonnage, energy and protein shares by category", sort=[{"field": mea("Energy share"), "direction": "Descending"}])
    d_panel_title(p, P["kpis"], "IMPORT-DEPENDENT REQUIREMENT OF THE BASKET")
    kx, ky, kw, kh = P["kpis"]
    d_card(p, (kx + 12, ky + 34, kw - 24, 120), "Import-dependent energy (million kcal/d)", "Energy · million kcal per day", D_SERIES[3], 28, 1)
    d_card(p, (kx + 12, ky + 164, kw - 24, 120), "Import-dependent protein (t/d)", "Protein · tonnes per day", D_CYAN, 28, 1)
    d_panel_title(p, P["notes"], "WHY IT MATTERS")
    p.text(d_inner(P["notes"], top=32, pad=12), [
        "Wheat and cooking oil carry most of the energy; wheat, poultry and pulses most of the protein.",
        "A small disruption in a dense product can matter more than a larger tonnage of another, so priorities by tonnage and by nutrition differ.",
        "Bread is part of wheat and has no separate requirement. Pulses carry low confidence."],
        size="10pt", color=D_TXT, alt="Nutrition notes")
    return p


def page_method():
    p = Page("method", "Method and limits", image=IMAGES["method"], color=D_BG); P = PANELS["method"]
    d_header(p, "METHOD AND LIMITS", "Version 0.1 · Results are modeled scenarios based on published trade data, AIS-based activity estimates, inferred routes and stated assumptions.", 1240)
    p.text(d_inner(P["left"], top=14, pad=16), [
        ("METHOD", "h"),
        "1. Net import requirement: FAOSTAT 2023 food minus counted local production, scaled to 2026 residents (low and high population factors).",
        "2. Shipment weight: requirement × k_ship (Comtrade weight / FAOSTAT imports), then split by physical form before a mode is assigned.",
        "3. Alternative-route activity: PortWatch cargo increment over the pre-war base at C1 (UAE east coast), C2a/C2b (Oman) and C3a (Saudi Red Sea, separate sensitivity). Low = closure average; Base = last 8 weeks; High = best synchronized 4 weeks.",
        "4. Two coverage measures: physical ceiling (ACR_phys) and reference allocation (ACR_ref, allocation share 19.6656%). Gap_ref is a modeled gap, not an observed shortage.",
        "5. Outside the port model: fresh poultry and dairy (TER, regional road route not verified) and crude cooking oil (GL, port coverage not estimable).",
        "6. Risk layers shown beside the gap, never multiplied into tonnes: supplier concentration, inferred route exposure and nutrition."],
        size="12pt", color=D_TXT, alt="Method", head_color=D_CYAN)
    p.text(d_inner(P["right"], top=14, pad=16), [
        ("LIMITS", "h"),
        "• PortWatch measures total cargo from ship signals, not food and not capacity.",
        "• The food share of incremental cargo is not observed; the benchmark has confidence C.",
        "• Mode of transport is not observed: regional origin (Saudi Arabia, Oman) does not prove road flow.",
        "• C1 has official road-and-rail continuity evidence; no cross-border rail credit is given to Oman in this version.",
        "• Routes are inferred by origin country; Canada, the USA and eggs from Türkiye are conditional.",
        "• King Abdullah Port shows a data anomaly in Aug–Sep 2026.",
        "• Pulses carry low confidence (large FAOSTAT residual).",
        "",
        ("SECURITY LIMITS", "h"),
        "No reserve stocks, no days-to-depletion, no facility-level capacity, routes or single points of failure. All outputs are at corridor level.",
        "",
        ("CODE AND DATA", "h"),
        "MIT licence for code. Source data keep their own terms; the code licence does not relicense them. World map: world-atlas TopoJSON (Natural Earth). Flags: flag-icons (MIT)."],
        size="12pt", color=D_TXT, alt="Limits", head_color=D_CYAN)
    return p


def make_pages():
    pages = []
    pages.append(make_overview())

    pages += [page_routes(), page_gap(), page_sensitivity(), page_suppliers(), page_nutrition(), page_method()]
    return pages


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", required=True); ap.add_argument("--base-theme", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--source", choices=["embedded", "excel"], default="embedded")
    ap.add_argument("--excel-path", help="full path of P2_PowerBI_model.xlsx on the computer that will refresh (only with --source excel)")
    a = ap.parse_args()
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    os.makedirs(a.out)
    wjson(os.path.join(a.out, f"{NAME}.pbip"), {"version": "1.0", "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
                                                "settings": {"enableAutoRecovery": True}})
    if a.source == "excel" and not a.excel_path:
        ap.error("--excel-path is required with --source excel")
    build_model(a.xlsx, a.excel_path, a.out, a.source)
    build_report(a.out, a.base_theme)
    n = sum(len(f) for _, _, f in os.walk(a.out))
    print(f"PBIP written to {a.out} ({n} files)")


if __name__ == "__main__":
    main()
