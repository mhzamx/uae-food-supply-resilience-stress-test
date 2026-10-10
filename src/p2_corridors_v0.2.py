"""P2 UAE Food Supply Resilience Stress Test - observed corridor layer (IMF PortWatch).

Fetches a frozen snapshot of daily port and chokepoint data and builds weekly
corridor summaries. Volumes are AIS-based estimates of TOTAL cargo, not food.
Results are OBSERVED total-cargo activity (not capacity, not food); this script
never applies food shares (E05, E07). Oman is split into C2a Sohar and C2b
Duqm+Salalah. C3a (Jeddah + King Abdullah Port) carries a low-reliability flag
for Aug-Sep 2026 (PortWatch anomaly at King Abdullah Port, E06).

v0.2 (Drive, E34, 2026-10-06):
- adds the scenario increments used by the gap method v0.1R (01 section 4A, E26):
  Low = closure average, Base = last 8 weeks, High synchronized = max 4-week
  rolling average of the CONTEMPORANEOUS sum C1+C2a+C2b, with each corridor's
  increment over its own base floored at 0 in every window (same rule as Low/Base);
- reports C1-only and the regional envelope in parallel (Miguel's decision, E33);
- reports C3a only as a separate sensitivity, plus its value in the synchronized window;
- adds the "C1 total" sensitivity (base + increment) requested in E32;
- renames corridor C3 to C3a.
Outputs in t/day of total cargo.
Usage:
  python src/p2_corridors_v0.2.py --fetch --data-dir data/snapshot_2026-10-05
  python src/p2_corridors_v0.2.py --data-dir data/snapshot_2026-10-05 --out-dir outputs
"""
import argparse, hashlib, json, os, time, urllib.parse, urllib.request
import pandas as pd

BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
PORTS = {  # portid: (name, corridor)
    "port362": ("Fujairah", "C1 Costa este EAU"),
    "port561": ("Khor Fakkan", "C1 Costa este EAU"),
    "port988": ("Sohar", "C2a Omán: Sohar"),
    "port984": ("Duqm", "C2b Omán: Duqm y Salalah"),
    "port746": ("Salalah", "C2b Omán: Duqm y Salalah"),
    "port518": ("Jeddah", "C3a Arabia Saudita: Jeddah y KAP (mar Rojo)"),
    "port2031": ("King Abdullah Port", "C3a Arabia Saudita: Jeddah y KAP (mar Rojo)"),
}
RELIABILITY = {
    "C1 Costa este EAU": "B: puertos de EAU",
    "C2a Omán: Sohar": "C: incluye demanda y trasbordo de Omán",
    "C2b Omán: Duqm y Salalah": "C: tramo terrestre largo; no implica capacidad para EAU",
    "C3a Arabia Saudita: Jeddah y KAP (mar Rojo)": "Baja en ago-sep 2026: anomalía PortWatch en King Abdullah Port (E06)",
}
CHOKES = {"chokepoint6": "Ormuz", "chokepoint4": "Bab el-Mandeb", "chokepoint1": "Suez", "chokepoint7": "Cabo de Buena Esperanza"}
START_YEAR = 2023
BASELINE = ("2025-03-01", "2026-02-27")   # 12 months before the war (28-feb-2026)
CLOSURE_START = "2026-03-01"
REF2023 = ("2023-01-02", "2023-10-30")    # before the Red Sea attacks of Nov-2023
SEGS = ["container", "dry_bulk", "general_cargo", "roro", "tanker"]

def query(service, where):
    rows, off = [], 0
    while True:
        p = {"where": where, "outFields": "*", "returnGeometry": "false", "f": "json",
             "orderByFields": "ObjectId", "resultRecordCount": 2000, "resultOffset": off}
        url = f"{BASE}/{service}/FeatureServer/0/query?" + urllib.parse.urlencode(p)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    d = json.load(r); break
            except Exception:
                time.sleep(3 * (attempt + 1))
        else:
            raise RuntimeError(f"failed {service} offset {off}")
        feats = d.get("features", [])
        rows += [f["attributes"] for f in feats]
        if not feats or not d.get("exceededTransferLimit"):
            break
        off += len(feats)
    return pd.DataFrame(rows)

def fetch(data_dir):
    os.makedirs(data_dir, exist_ok=True)
    ids = ",".join(f"'{p}'" for p in PORTS)
    ports = query("Daily_Ports_Data", f"portid IN ({ids}) AND year>={START_YEAR}")
    cids = ",".join(f"'{c}'" for c in CHOKES)
    chokes = query("Daily_Chokepoints_Data", f"portid IN ({cids}) AND year>={START_YEAR}")
    for df, name in [(ports, "corridor_ports_daily"), (chokes, "chokepoints_daily")]:
        df = df.sort_values(["portid", "date"]).reset_index(drop=True)
        df.to_csv(os.path.join(data_dir, f"{name}_2026-10-05.csv"), index=False)
    with open(os.path.join(data_dir, "SHA256SUMS"), "w") as fh:
        for f in sorted(os.listdir(data_dir)):
            if f.endswith(".csv"):
                h = hashlib.sha256(open(os.path.join(data_dir, f), "rb").read()).hexdigest()
                fh.write(f"{h}  {f}\n")

def weekly(df, cols):
    df = df.copy(); df["date"] = pd.to_datetime(df["date"])
    df["week"] = df["date"] - pd.to_timedelta(df["date"].dt.weekday, unit="D")
    return df.groupby(["portid", "week"], as_index=False)[cols].sum()

def build(data_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    p = pd.read_csv(os.path.join(data_dir, "corridor_ports_daily_2026-10-05.csv"))
    c = pd.read_csv(os.path.join(data_dir, "chokepoints_daily_2026-10-05.csv"))
    last_day = pd.to_datetime(p["date"]).max()
    imp = [f"import_{s}" for s in SEGS]
    w = weekly(p, imp + ["portcalls_cargo", "portcalls_tanker"])
    # keep only complete weeks
    w = w[w["week"] + pd.Timedelta(days=6) <= last_day]
    w["port"] = w["portid"].map(lambda x: PORTS[x][0]); w["corridor"] = w["portid"].map(lambda x: PORTS[x][1])
    w["import_dry_cargo"] = w[["import_container", "import_dry_bulk", "import_general_cargo", "import_roro"]].sum(axis=1)
    w.to_csv(os.path.join(out_dir, "corridor_ports_weekly.csv"), index=False)
    cw = weekly(c, ["n_container", "n_dry_bulk", "n_general_cargo", "n_roro", "n_tanker", "n_cargo", "n_total", "capacity_cargo"])
    cw = cw[cw["week"] + pd.Timedelta(days=6) <= pd.to_datetime(c["date"]).max()]
    cw["chokepoint"] = cw["portid"].map(CHOKES)
    cw.to_csv(os.path.join(out_dir, "chokepoints_weekly.csv"), index=False)
    # corridor x segment summary
    segs = {"Contenedores": "import_container", "Granel seco": "import_dry_bulk",
            "Carga general + RoRo": None, "Tanqueros (granel líquido, incluye petróleo)": "import_tanker",
            "Total carga seca (sin tanqueros)": "import_dry_cargo"}
    cor = w.groupby(["corridor", "week"], as_index=False)[imp + ["import_dry_cargo"]].sum()
    cor["gen_roro"] = cor["import_general_cargo"] + cor["import_roro"]
    rows = []
    for corr, g in cor.groupby("corridor"):
        b = g[(g.week >= BASELINE[0]) & (g.week <= BASELINE[1])]
        k = g[g.week >= CLOSURE_START].sort_values("week")
        for lab, col in segs.items():
            col = col or "gen_roro"
            bm = b[col].mean(); km = k[col].mean()
            roll = k[col].rolling(4).mean()
            last8 = k[col].tail(8).mean()
            rows.append({"Corredor": corr, "Segmento": lab, "Medida": "Actividad observada de carga total (no capacidad, no alimentos)",
                "Confiabilidad": RELIABILITY[corr],
                "Base t/semana (mar-2025 a feb-2026)": round(bm), "Cierre t/semana (mar a sep 2026)": round(km),
                "Cambio %": round(100 * (km / bm - 1), 1) if bm else None,
                "Máx. promedio 4 semanas en cierre (t/semana)": round(roll.max()),
                "Últimas 8 semanas (t/semana)": round(last8),
                "Incremento observado sobre base, cierre (t/semana)": round(km - bm),
                "Incremento observado sobre base, máx. 4 semanas (t/semana)": round(roll.max() - bm),
                "Semanas base": len(b), "Semanas cierre": len(k)})
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(out_dir, "corridor_summary.csv"), index=False)
    crow = []
    for ch, g in cw.groupby("chokepoint"):
        b = g[(g.week >= BASELINE[0]) & (g.week <= BASELINE[1])]; k = g[g.week >= CLOSURE_START]
        r23 = g[(g.week >= REF2023[0]) & (g.week <= REF2023[1])]
        for lab, col in [("Buques de carga (sin tanqueros)", "n_cargo"), ("Tanqueros", "n_tanker")]:
            bm, km = b[col].mean(), k[col].mean()
            crow.append({"Estrecho": ch, "Tipo": lab, "Referencia ene-oct 2023 tránsitos/semana": round(r23[col].mean(), 1), "Base tránsitos/semana": round(bm, 1),
                         "Cierre tránsitos/semana": round(km, 1), "Cambio %": round(100 * (km / bm - 1), 1) if bm else None,
                         "Últimas 4 semanas": round(k.sort_values('week')[col].tail(4).mean(), 1)})
    pd.DataFrame(crow).to_csv(os.path.join(out_dir, "chokepoints_summary.csv"), index=False)
    return summ

ALT = ["C1 Costa este EAU", "C2a Omán: Sohar", "C2b Omán: Duqm y Salalah"]
C3A = "C3a Arabia Saudita: Jeddah y KAP (mar Rojo)"
SCEN_SEGS = {"Contenedor": "import_container", "Granel seco": "import_dry_bulk", "Carga general + RoRo": "gen_roro"}

def scenarios(w, out_dir):
    """Scenario increments over the pre-war base, t/day of total cargo (gap method v0.1R)."""
    w = w.copy(); w["gen_roro"] = w["import_general_cargo"] + w["import_roro"]
    cor = w.groupby(["corridor", "week"], as_index=False)[list(SCEN_SEGS.values())].sum()
    rows = []
    for seg, col in SCEN_SEGS.items():
        p = cor.pivot(index="week", columns="corridor", values=col).sort_index()
        base = p[(p.index >= BASELINE[0]) & (p.index <= BASELINE[1])].mean()
        k = p[p.index >= CLOSURE_START]
        inc_low = (k.mean() - base).clip(lower=0) / 7
        inc_base = (k.tail(8).mean() - base).clip(lower=0) / 7
        roll_inc = (k.rolling(4).mean() - base).clip(lower=0) / 7      # per corridor, per window
        for scope, cols in [("C1-only (puertos de la costa este de EAU)", ALT[:1]),
                            ("Regional envelope C1+C2a+C2b", ALT)]:
            sync = roll_inc[cols].sum(axis=1)
            end = sync.idxmax(); start = k.index[k.index.get_loc(end) - 3]
            rows.append({"Segmento": seg, "Alcance": scope,
                         "Low t/día": round(inc_low[cols].sum(), 3), "Base t/día": round(inc_base[cols].sum(), 3),
                         "High sincronizado t/día": round(sync.max(), 3),
                         "Ventana high (inicio de semanas)": f"{start.date()} a {end.date()}",
                         "C3a en la misma ventana t/día": round(roll_inc.loc[end, C3A], 3),
                         "Envolvente histórica no sincronizada t/día": round(roll_inc[cols].max().sum(), 3)})
        rows.append({"Segmento": seg, "Alcance": "C3a solo (sensibilidad separada, confiabilidad baja)",
                     "Low t/día": round(inc_low[C3A], 3), "Base t/día": round(inc_base[C3A], 3),
                     "High sincronizado t/día": None, "Ventana high (inicio de semanas)": "",
                     "C3a en la misma ventana t/día": None,
                     "Envolvente histórica no sincronizada t/día": round(roll_inc[C3A].max(), 3)})
        c1 = ALT[0]   # E32 sensitivity: C1 total activity (base + increment), Low
        rows.append({"Segmento": seg, "Alcance": "Sensibilidad C1 total (base + incremento)",
                     "Low t/día": round(k[c1].mean() / 7, 3), "Base t/día": round(k[c1].tail(8).mean() / 7, 3),
                     "High sincronizado t/día": round(k[c1].rolling(4).mean().max() / 7, 3),
                     "Ventana high (inicio de semanas)": "", "C3a en la misma ventana t/día": None,
                     "Envolvente histórica no sincronizada t/día": None})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(out_dir, "scenario_increments_v0.2.csv"), index=False)
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--data-dir", required=True); ap.add_argument("--out-dir", default="outputs")
    a = ap.parse_args()
    if a.fetch:
        if os.path.exists(os.path.join(a.data_dir, "SHA256SUMS")):
            raise SystemExit("snapshot already exists; a new download is a new cut")
        fetch(a.data_dir)
    else:
        print(build(a.data_dir, a.out_dir).to_string())
        w = pd.read_csv(os.path.join(a.out_dir, "corridor_ports_weekly.csv"), parse_dates=["week"])
        print(scenarios(w, a.out_dir).to_string())
