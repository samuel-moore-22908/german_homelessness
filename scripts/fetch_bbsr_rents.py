"""Pull BBSR asking rents (Kreis level, 2010-2025) from the public BBSR Tableau dashboard.

The dashboard backs the BBSR article "Wohnungsmieten" (Fachbeitrag Mieten 2010 bis 2025,
Kreise Gebietsstand 31.12.2024). It is the only keyless source we found that gives the
revised series at cent precision for every year; the INKAR bulk CSV rounds to whole euros.

Output: data/raw/bbsr_rents_tableau.csv (one row per Kreis x year, all dashboard columns).
"""
import json
import re
from pathlib import Path

import pandas as pd
import requests
from tableauscraper import TableauScraper, utils

HOST = "https://tableau.bbsr.bund.de"
WORKBOOK = "Fachbeitrag_Mieten_2010_bis_2025_Krs24_FINAL_17804753193550"
VIEW = "DMietenKarte"
WORKSHEET = "Mietenkarte"
YEARS = range(2010, 2026)
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "bbsr_rents_tableau.csv"


def open_session() -> TableauScraper:
    """Start a guest viewing session and bootstrap it into a TableauScraper object."""
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0"
    s.get(f"{HOST}/t/bbr/views/{WORKBOOK}/{VIEW}?:embed=y&:showVizHome=no", timeout=120)
    r = s.post(
        f"{HOST}/vizql/t/bbr/w/{WORKBOOK}/v/{VIEW}/startSession/viewing?:embed=y",
        headers={"Accept": "application/json"},
        timeout=120,
    )
    r.raise_for_status()
    cfg = r.json()
    cfg["sessionid"] = r.headers.get("X-Session-Id", cfg["sessionid"])
    boot = s.post(
        f"{HOST}{cfg['vizql_root']}/bootstrapSession/sessions/{cfg['sessionid']}",
        data={"sheet_id": cfg["sheetId"], "showParams": cfg["showParams"],
              "stickySessionKey": cfg["stickySessionKey"]},
        timeout=300,
    )
    boot.raise_for_status()
    m = re.search(r"\d+;({.*})\d+;({.*})", boot.text, re.MULTILINE)

    ts = TableauScraper()
    ts.session = s
    ts.host = HOST
    ts.tableauData = cfg
    ts.info = json.loads(m.group(1))
    ts.data = json.loads(m.group(2))
    pm = ts.data["secondaryInfo"]["presModelMap"]
    ts.dataSegments = pm["dataDictionary"]["presModelHolder"]["genDataDictionaryPresModel"]["dataSegments"]
    ts.parameters = utils.getParameterControlInput(ts.info)
    ts.dashboard = ts.info["sheetName"]
    ts.filters = utils.getFiltersForAllWorksheet(ts.logger, ts.data, ts.info, rootDashboard=ts.dashboard)
    return ts


def main() -> None:
    ts = open_session()
    ws = ts.getWorksheet(WORKSHEET)
    frames = []
    for y in YEARS:
        wb = ws.setFilter("YEAR(Jahr)", y)
        d = wb.getWorksheet(WORKSHEET).data.copy()
        d["year_requested"] = y
        print(y, d.shape)
        frames.append(d)
    out = pd.concat(frames, ignore_index=True)
    # Drop the map geometry (megabytes of polygons) and generated lat/lon.
    out = out.drop(columns=[c for c in out.columns if "Geometrie" in c or "generated" in c])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, encoding="utf-8")
    print("wrote", OUT, out.shape)


if __name__ == "__main__":
    main()
