"""Download every raw source into data/raw/ and write data/raw/manifest.csv.

No API keys or logins are needed. The BBSR rents come from a separate script
(fetch_bbsr_rents.py) because they need a Tableau guest session; this script
runs it at the end and records its output in the manifest as well.

Usage:  python scripts/fetch_sources.py [--force]
"""
import argparse
import csv
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
GENESIS = "https://genesis.destatis.de/genesis/api/rest/tables"
BA = "https://statistik.arbeitsagentur.de/Statistikdaten/Detail/Aktuell/iiia4"

SOURCES = [
    # (local file, url, description)
    ("22971-0080.json", f"{GENESIS}/22971-0080/data",
     "Destatis GENESIS 22971-0080: accommodated homeless persons by Kreis, reference date, nationality, sex, age"),
    ("22971-0080_structure.json", f"{GENESIS}/22971-0080/structure",
     "Labels for 22971-0080"),
    ("12411-0015.json", f"{GENESIS}/12411-0015/data",
     "Destatis GENESIS 12411-0015: population by Kreis on 31 Dec"),
    ("12411-0015_structure.json", f"{GENESIS}/12411-0015/structure",
     "Labels for 12411-0015"),
    ("61111-0010.json", f"{GENESIS}/61111-0010/data",
     "Destatis GENESIS 61111-0010: CPI by Land, annual (2020=100)"),
    ("61111-0010_structure.json", f"{GENESIS}/61111-0010/structure",
     "Labels for 61111-0010"),
    ("ba_arbeitslosenquoten_kreise.xlsx",
     f"{BA}/kreise-arbeitslosenquoten/arbeitslosenquoten-k-0-xlsx.xlsx?__blob=publicationFile",
     "BA Statistik: unemployment rates (all civilian labour force), Kreise, time series 1998-2025"),
    ("ba_arbeitslose_kgd_ab1998_d.xlsx",
     f"{BA}/arbeitslose-kgd-ab1998/arbeitslose-kgd-ab1998-d-0-xlsx.xlsx?__blob=publicationFile",
     "BA Statistik: registered unemployed, Germany by Kreis, time series 1998-2025"),
    ("vgrdl_r2b1_bs2025_4.xlsx",
     "https://www.statistikportal.de/sites/default/files/2026-09/vgrdl_r2b1_bs2025_4.xlsx",
     "VGRdL Reihe 2 Band 1: GDP at current prices by Kreis, 1992-2024"),
    ("vgrdl_r1b1_bs2025.xlsx",
     "https://www.statistikportal.de/sites/default/files/2026-03/vgrdl_r1b1_bs2025.xlsx",
     "VGRdL Reihe 1 Band 1: Land GDP nominal and chain-linked, 1991-2025"),
    ("IW_Regionaler_Preisindex_2023.xlsx",
     "https://www.iwkoeln.de/fileadmin/user_upload/Studien/Kurzberichte/Visuals/2024/Regionaler_Preisindex_2023.xlsx",
     "IW Koeln / BBSR regional price level 2023 by Kreis (Germany=100)"),
    ("Deutschlandatlas_Daten.xlsx",
     "https://deutschlandatlas.bund.de/fileadmin/Downloaddateien/Open_Data/Deutschlandatlas_Daten.xlsx",
     "Deutschlandatlas open data (used only to cross-check 2025 BBSR rents)"),
]

RENTS = ("bbsr_rents_tableau.csv",
         "https://tableau.bbsr.bund.de/t/bbr/views/Fachbeitrag_Mieten_2010_bis_2025_Krs24_FINAL_17804753193550/DMietenKarte",
         "BBSR asking rents (net cold, re-lets) by Kreis 2010-2025, scraped from public Tableau dashboard")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="re-download files that already exist")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (research data pull)"
    for name, url, _ in SOURCES:
        path = RAW / name
        if path.exists() and not args.force:
            print("exists ", name)
            continue
        print("fetch  ", name)
        r = s.get(url, timeout=600)
        r.raise_for_status()
        path.write_bytes(r.content)

    if args.force or not (RAW / RENTS[0]).exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "fetch_bbsr_rents.py")], check=True)

    with open(RAW / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "url", "description", "downloaded", "bytes", "sha256"])
        for name, url, desc in SOURCES + [RENTS]:
            p = RAW / name
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()
            w.writerow([name, url, desc, mtime, p.stat().st_size, sha256(p)])
    print("wrote manifest")


if __name__ == "__main__":
    main()
