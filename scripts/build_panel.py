"""Build the Kreis x wave homelessness panel from the raw files in data/raw/.

Run scripts/fetch_sources.py first. Writes:
  data/panel.csv        400 Kreise x 5 waves (2022-2026) = 2000 rows
  data/panel_1600.csv   waves 2022-2025 only (complete covariates) = 1600 rows
  data/build_log.txt    harmonisation counts and validation checks

Alignment: wave = reference date 31 Jan of year t; covariates refer to calendar
year t-1 (cov_year). Population is the 31 Dec t-1 stock, i.e. one month before
the count.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data"
WAVES = [2022, 2023, 2024, 2025, 2026]
COV_YEARS = [w - 1 for w in WAVES]

# Territorial changes relative to the 400-Kreis frame of 2022-2025.
# Eisenach (16056) merged into Wartburgkreis (16063) on 2021-07-01.
# Hanau (06415) left Main-Kinzig-Kreis (06435) on 2026-01-01.
MERGE = {"16056": "16063", "06415": "06435"}

STATES = {
    "01": "Schleswig-Holstein", "02": "Hamburg", "03": "Niedersachsen", "04": "Bremen",
    "05": "Nordrhein-Westfalen", "06": "Hessen", "07": "Rheinland-Pfalz",
    "08": "Baden-Württemberg", "09": "Bayern", "10": "Saarland", "11": "Berlin",
    "12": "Brandenburg", "13": "Mecklenburg-Vorpommern", "14": "Sachsen",
    "15": "Sachsen-Anhalt", "16": "Thüringen",
}

log_lines: list[str] = []


def log(msg: str) -> None:
    print(msg)
    log_lines.append(msg)


def fix_mojibake(s: str) -> str:
    """GENESIS structure labels are UTF-8 bytes decoded as Latin-1."""
    try:
        return s.encode("latin1").decode("utf8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def harmonise(df: pd.DataFrame, sum_cols: list[str], key: str = "ags") -> pd.DataFrame:
    """Recode merged/split Kreise onto the 400-unit frame and sum the given columns."""
    df = df.copy()
    moved = df[key].isin(MERGE)
    for old, new in MERGE.items():
        rows = df[df[key] == old]
        if len(rows) and rows[sum_cols].fillna(0).to_numpy().sum() != 0:
            log(f"  harmonise: {old} -> {new}, {len(rows)} rows, sums {rows[sum_cols].sum(min_count=1).to_dict()}")
    df.loc[moved, key] = df.loc[moved, key].map(MERGE)
    other = [c for c in df.columns if c not in sum_cols]
    return df.groupby(other, as_index=False, dropna=False)[sum_cols].sum(min_count=1)


# ---------------------------------------------------------------- GENESIS cubes

def genesis_cube(name: str) -> tuple[pd.DataFrame, dict]:
    """Flatten a GENESIS JSON-stat style cube into a long DataFrame.

    Each dimension's code -> position mapping comes from category.index (not list order).
    Status "-" means 'nothing / zero' (the value field then holds 0).
    """
    d = json.load(open(RAW / f"{name}.json", encoding="utf-8"))["data"][0]
    dims, sizes = d["id"], d["size"]
    codes = []
    for dim in dims:
        idx = d["dimension"][dim]["category"]["index"]
        codes.append([c for c, _ in sorted(idx.items(), key=lambda kv: kv[1])])
    grid = pd.MultiIndex.from_product(codes, names=dims).to_frame(index=False)
    assert len(grid) == np.prod(sizes) == len(d["value"])
    grid["value"] = d["value"]
    grid["status"] = d["status"]
    labels = json.load(open(RAW / f"{name}_structure.json", encoding="utf-8"))["variableValues"]
    labels = {k: fix_mojibake(v["label"]["de"]) for k, v in labels.items()}
    return grid, labels


def load_homeless() -> pd.DataFrame:
    cube, labels = genesis_cube("22971-0080")
    cube = cube[(cube.GES02 == "%TOTAL%") & (cube.ALT026 == "%TOTAL%")]
    cube = cube.assign(wave=cube.STAG.str[:4].astype(int), ags=cube.KREISE)

    historic = [k for k in cube.ags.unique()
                if re.search(r"\(bis |\(b\.", labels.get(k, ""))]
    hist_vals = cube[cube.ags.isin(historic) & (cube.value != 0)]
    log(f"homeless: {len(historic)} historic codes dropped; nonzero cells among them: "
        f"{hist_vals[['ags', 'wave', 'NAT', 'value']].to_dict('records')}")
    # Eisenach carries counts in wave 2022 despite its historic label; keep it for the merge.
    cube = cube[~cube.ags.isin(set(historic) - {"16056"})]

    wide = cube.pivot_table(index=["ags", "wave"], columns="NAT", values="value", aggfunc="sum").reset_index()
    wide = wide.rename(columns={"%TOTAL%": "homeless_total", "NATD": "homeless_german", "NATA": "homeless_foreign"})
    wide.columns.name = None
    cols = ["homeless_total", "homeless_german", "homeless_foreign"]
    wide = harmonise(wide, cols)
    names = pd.Series(labels, name="kreis_name_genesis")
    return wide.merge(names, left_on="ags", right_index=True, how="left")


def load_population() -> pd.DataFrame:
    cube, _ = genesis_cube("12411-0015")
    cube = cube.assign(cov_year=cube.STAG.str[:4].astype(int), ags=cube.KREISE)
    cube = cube[cube.cov_year.isin(COV_YEARS) & cube.ags.str.fullmatch(r"\d{5}")]
    df = cube[["ags", "cov_year", "value"]].rename(columns={"value": "population"})
    df = harmonise(df, ["population"])
    return df[df.population > 0]


def load_cpi() -> pd.DataFrame:
    cube, _ = genesis_cube("61111-0010")
    cube = cube.rename(columns={"DLAND": "state", "JAHR": "cov_year", "value": "cpi_state"})
    cube["cov_year"] = cube.cov_year.astype(int)
    cube.loc[cube.status == "-", "cpi_state"] = np.nan  # '-' = series not available (SH/HH pre-2015)
    return cube[["state", "cov_year", "cpi_state"]]


# ---------------------------------------------------------------- BA unemployment

def ba_annual(file: str, sheet: str) -> pd.DataFrame:
    """Annual-average block of a BA Kreis time-series sheet -> long (ags, cov_year, value)."""
    raw = pd.read_excel(RAW / file, sheet_name=sheet, header=None, dtype=str)
    header = raw.iloc[10]
    year_cols = {j: int(v) for j, v in header.items() if isinstance(v, str) and re.fullmatch(r"\d{4}", v)}
    rows = raw[raw[0].fillna("").str.match(r"^\d{5} ")]
    out = rows[[0, *year_cols]].rename(columns={0: "region", **year_cols})
    out = out.melt(id_vars="region", var_name="cov_year", value_name="v")
    out["ags"] = out.region.str[:5]
    out["v"] = pd.to_numeric(out.v, errors="coerce")
    return out[out.cov_year.isin(COV_YEARS)][["ags", "cov_year", "v"]]


def load_unemployment() -> pd.DataFrame:
    cnt = ba_annual("ba_arbeitslose_kgd_ab1998_d.xlsx", "Auswertung").rename(columns={"v": "unemp_count"})
    rate = ba_annual("ba_arbeitslosenquoten_kreise.xlsx", "Jahreszahlen").rename(columns={"v": "unemp_rate"})
    df = cnt.merge(rate, on=["ags", "cov_year"], how="outer")
    # BA publishes on the current (2026) boundaries, so Hanau is split out for all years.
    # Recover the civilian labour force implied by count / rate, then re-aggregate.
    df["labour_force"] = df.unemp_count / (df.unemp_rate / 100)
    df = harmonise(df.drop(columns="unemp_rate"), ["unemp_count", "labour_force"])
    df["unemp_rate"] = 100 * df.unemp_count / df.labour_force
    return df.drop(columns="labour_force")


# ---------------------------------------------------------------- VGRdL GDP

def vgrdl_kreis(sheet: str, value_name: str) -> pd.DataFrame:
    raw = pd.read_excel(RAW / "vgrdl_r2b1_bs2025_4.xlsx", sheet_name=sheet, header=None, dtype=str)
    header = raw.iloc[4]
    year_cols = {j: int(float(v)) for j, v in header.items() if isinstance(v, str) and re.fullmatch(r"\d{4}(\.0)?", v)}
    code = raw[2].fillna("")
    # Kreise have 5-digit codes; Berlin and Hamburg appear only at Land level ("11", "02").
    keep = code.str.fullmatch(r"\d{5}") | code.isin(["11", "02"])
    df = raw[keep][[2, *year_cols]].rename(columns={2: "ags", **year_cols})
    df["ags"] = df.ags.replace({"11": "11000", "02": "02000"})
    df = df.melt(id_vars="ags", var_name="cov_year", value_name=value_name)
    df[value_name] = pd.to_numeric(df[value_name], errors="coerce")
    return harmonise(df[df.cov_year.isin(COV_YEARS)], [value_name])


def load_state_deflator() -> pd.DataFrame:
    """Implicit Land GDP deflator (2020=100) = nominal index / chain-linked volume index."""
    def block(sheet: str, start_label: str | None) -> pd.DataFrame:
        raw = pd.read_excel(RAW / "vgrdl_r1b1_bs2025.xlsx", sheet_name=sheet, header=None)
        names = raw.iloc[2].astype(str).str.replace("_x000D_\n", "", regex=False).str.replace("\n", "")
        start = 5 if start_label is None else raw.index[raw[1].astype(str).str.startswith(start_label)][0] + 1
        rows = []
        for i in range(start, len(raw)):
            y = raw.iloc[i, 0]
            if not isinstance(y, (int, float)) or pd.isna(y):
                break
            rows.append(raw.iloc[i])
        b = pd.DataFrame(rows)
        b.columns = names
        return b.rename(columns={names[0]: "year"}).set_index("year")

    nominal = block("1.1", None)          # Mio EUR, current prices
    volume = block("6.1", "Index")        # chain-linked index, 2020 = 100
    land_cols = [c for c in nominal.columns if c in volume.columns][:16]
    defl = (nominal[land_cols] / nominal.loc[2020, land_cols]) / (volume[land_cols] / 100) * 100
    name_to_code = {v.replace("-", "").replace(" ", ""): k for k, v in STATES.items()}
    defl.columns = [name_to_code[c.replace("-", "").replace(" ", "")] for c in defl.columns]
    out = defl.stack().rename("gdp_deflator_state").reset_index()
    out.columns = ["cov_year", "state", "gdp_deflator_state"]
    out["cov_year"] = out.cov_year.astype(int)
    return out


# ---------------------------------------------------------------- rents, price level

def load_rents() -> pd.DataFrame:
    df = pd.read_csv(RAW / "bbsr_rents_tableau.csv", dtype=str)
    assert (df["YEAR(Jahr)-value"] == df["year_requested"]).all()
    df = pd.DataFrame({
        "ags": df["KRS-alias"].str.zfill(8).str[:5],
        "cov_year": df["year_requested"].astype(int),
        "rent_asking": pd.to_numeric(df["AGG(mietqmoa_best_gew_round)-alias"], errors="coerce"),
    })
    return df[df.cov_year.isin(COV_YEARS)]


def check_rents_against_atlas(rents: pd.DataFrame) -> None:
    atlas = pd.read_excel(RAW / "Deutschlandatlas_Daten.xlsx", sheet_name="Deutschlandatlas_KRS1224",
                          header=None, dtype=str).iloc[4:404, [0, 11]]
    atlas.columns = ["krs", "preis_miet"]
    atlas["ags"] = atlas.krs.str.zfill(8).str[:5]
    atlas["preis_miet"] = pd.to_numeric(atlas.preis_miet)
    m = rents[rents.cov_year == 2025].merge(atlas, on="ags")
    log(f"rents: 2025 BBSR vs Deutschlandatlas preis_miet: n={len(m)}, "
        f"max |diff|={(m.rent_asking - m.preis_miet).abs().max():.3f}")


def load_price_level() -> pd.DataFrame:
    df = pd.read_excel(RAW / "IW_Regionaler_Preisindex_2023.xlsx", sheet_name="Kreise", dtype=str)
    return pd.DataFrame({"ags": df["AGS"].str.zfill(5),
                         "price_level_2023": pd.to_numeric(df["Preisniveau (D=100)"])})


# ---------------------------------------------------------------- assemble

def main() -> None:
    log("== loading")
    hl = load_homeless()
    frame = sorted(load_price_level().ags)  # IW list = the 400 Kreise of 2022-2025
    assert len(frame) == 400
    hl = hl[hl.ags.isin(frame)]
    log(f"homeless: {len(hl)} rows after restricting to 400-Kreis frame")

    pop = load_population()
    unemp = load_unemployment()
    gdp = vgrdl_kreis("1.1", "gdp_nominal")          # Mio EUR, current prices
    pop_vgr = vgrdl_kreis("5", "pop_vgr_1000")        # annual average residents, 1000
    rents = load_rents()
    check_rents_against_atlas(rents)
    cpi = load_cpi()
    defl = load_state_deflator()
    plevel = load_price_level()

    base = pd.MultiIndex.from_product([frame, WAVES], names=["ags", "wave"]).to_frame(index=False)
    base["cov_year"] = base.wave - 1
    base["state"] = base.ags.str[:2]
    base["state_name"] = base.state.map(STATES)

    p = (base.merge(hl, on=["ags", "wave"], how="left")
             .merge(pop, on=["ags", "cov_year"], how="left")
             .merge(unemp, on=["ags", "cov_year"], how="left")
             .merge(gdp, on=["ags", "cov_year"], how="left")
             .merge(pop_vgr, on=["ags", "cov_year"], how="left")
             .merge(rents, on=["ags", "cov_year"], how="left")
             .merge(cpi, on=["state", "cov_year"], how="left")
             .merge(defl, on=["state", "cov_year"], how="left")
             .merge(plevel, on="ags", how="left"))

    names = pd.read_excel(RAW / "IW_Regionaler_Preisindex_2023.xlsx", sheet_name="Kreise", dtype=str)
    names = names.assign(ags=names["AGS"].str.zfill(5))[["ags", "Landkreis / kreisfreie Stadt"]]
    p = p.merge(names.rename(columns={"Landkreis / kreisfreie Stadt": "kreis_name"}), on="ags", how="left")
    p["kreis_name"] = p.kreis_name_genesis.fillna(p.kreis_name)

    # Derived variables
    p["homeless_per_1000"] = 1000 * p.homeless_total / p.population
    p["homeless_german_per_1000"] = 1000 * p.homeless_german / p.population
    p["homeless_foreign_per_1000"] = 1000 * p.homeless_foreign / p.population
    p["gdp_real"] = p.gdp_nominal / (p.gdp_deflator_state / 100)              # Mio EUR, 2020 prices
    p["gdp_pc_nominal"] = 1e3 * p.gdp_nominal / p.pop_vgr_1000                # EUR per resident
    p["gdp_pc_real"] = 1e3 * p.gdp_real / p.pop_vgr_1000
    p["rent_real"] = p.rent_asking / (p.cpi_state / 100)                      # EUR/m2, 2020 prices
    p["flag_zero"] = (p.homeless_total == 0).astype(int)
    p["flag_wave2022"] = (p.wave == 2022).astype(int)
    p["flag_hanau_merged"] = ((p.ags == "06435") & (p.wave == 2026)).astype(int)
    p["flag_eisenach_merged"] = ((p.ags == "16063") & (p.wave == 2022)).astype(int)

    cols = ["ags", "kreis_name", "state", "state_name", "wave", "cov_year",
            "homeless_total", "homeless_german", "homeless_foreign", "population",
            "homeless_per_1000", "homeless_german_per_1000", "homeless_foreign_per_1000",
            "unemp_count", "unemp_rate",
            "gdp_nominal", "gdp_real", "pop_vgr_1000", "gdp_pc_nominal", "gdp_pc_real",
            "rent_asking", "rent_real", "cpi_state", "gdp_deflator_state", "price_level_2023",
            "flag_zero", "flag_wave2022", "flag_hanau_merged", "flag_eisenach_merged"]
    p = p[cols].sort_values(["ags", "wave"]).reset_index(drop=True)
    for c in ["homeless_total", "homeless_german", "homeless_foreign", "population", "unemp_count"]:
        p[c] = p[c].round().astype("Int64")

    # ------------------------------------------------------------ checks
    log("== checks")
    log(f"rows={len(p)}, Kreise={p.ags.nunique()}, waves={sorted(p.wave.unique())}")
    miss = p.isna().groupby(p.wave).sum()
    miss = miss.loc[:, miss.any()]
    log("missing cells by wave:\n" + (miss.to_string() if len(miss.columns) else "  none"))
    for w, g in p.groupby("wave"):
        nat = g.homeless_german + g.homeless_foreign - g.homeless_total
        log(f"wave {w}: total={g.homeless_total.sum():,}  german={g.homeless_german.sum():,}  "
            f"foreign={g.homeless_foreign.sum():,}  zero-Kreise={g.flag_zero.sum()}  "
            f"|german+foreign-total| max={nat.abs().max()} (independent rounding to 5)")
    zero = p[p.flag_zero == 1][["ags", "kreis_name", "wave"]]
    log("zero-count Kreis-waves:\n" + zero.to_string(index=False))
    log(f"unemp_rate range {p.unemp_rate.min():.1f}-{p.unemp_rate.max():.1f}; "
        f"rent range {p.rent_asking.min():.2f}-{p.rent_asking.max():.2f}; "
        f"deflator range {p.gdp_deflator_state.min():.1f}-{p.gdp_deflator_state.max():.1f}")

    core = p[p.wave <= 2025]
    covars = ["homeless_total", "unemp_rate", "gdp_nominal", "rent_asking", "cpi_state", "gdp_deflator_state"]
    log(f"panel_1600: rows={len(core)}, complete on {covars}: {core[covars].notna().all(axis=1).sum()}")

    p.to_csv(OUT / "panel.csv", index=False, encoding="utf-8")
    core.to_csv(OUT / "panel_1600.csv", index=False, encoding="utf-8")
    (OUT / "build_log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    log(f"wrote {OUT / 'panel.csv'} and {OUT / 'panel_1600.csv'}")


if __name__ == "__main__":
    main()
