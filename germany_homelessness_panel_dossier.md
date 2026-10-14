# Dossier: German district homelessness panel

Purpose: build a district (Kreis) × wave panel of accommodated homeless persons with lagged covariates (unemployment, district GDP, asking rents) and state-level prices (CPI, GDP deflator). Hand this file to Claude Code as the spec.

## 1. Unit and waves

- **Unit:** 400 Kreise (kreisfreie Städte + Landkreise), 5-digit AGS code. Berlin (11000) and Hamburg (02000) are single units. First 2 digits = state (01–16).
- **Waves:** homelessness stock on the night of 31 Jan–1 Feb of 2022, 2023, 2024, 2025, 2026.
- **Alignment rule:** wave Jan *t* gets covariates for calendar year *t−1*.
- **Complete panel today:** waves 2022–2025 (4 × 400). Wave 2026 lacks district GDP for 2025 (not yet published); keep it in with GDP missing.

| Wave (31 Jan) | Unemployment (annual avg) | District GDP | Asking rents | State CPI (annual) | State GDP deflator |
|---|---|---|---|---|---|
| 2022 | 2021 | 2021 | 2021 | 2021 | 2021 |
| 2023 | 2022 | 2022 | 2022 | 2022 | 2022 |
| 2024 | 2023 | 2023 | 2023 | 2023 | 2023 |
| 2025 | 2024 | 2024 | 2024 | 2024 | 2024 |
| 2026 | 2025 | missing | 2025 | 2025 | 2025 |

Optional fixed cross-section control: IW/BBSR Regionaler Preisindex 2023 (district price level, Germany = 100), time-invariant.

## 2. Sources

### 2.1 Homelessness (outcome)
- **Table:** GENESIS 22971-0080 "Untergebrachte wohnungslose Personen: Kreise, Stichtag, Nationalität, Geschlecht, Altersgruppen". Last change 2026-09-21.
- **Page:** https://genesis.destatis.de/datenbank/online/statistic/22971/table/22971-0080
- **JSON endpoint:** `GET https://genesis.destatis.de/genesis/api/rest/tables/22971-0080/data` (structure: `/structure`). It works from a browser session on genesis.destatis.de. The old `www-genesis.destatis.de/genesisWS/rest/2020/...` API redirects and no longer works.
- **Dimensions** (`data[0].id` order, sizes):
  - statistic: 1
  - content: 1
  - NAT: 3 (NATD, NATA, %TOTAL%)
  - GES02: 4 (GESM, GESW, UNBEKANNT, %TOTAL%)
  - STAG: 5 (2022-01-31 … 2026-01-31)
  - ALT026: 7 (5 age bands, UNBEKANNT, %TOTAL%)
  - KREISE: 477 codes (includes historic codes)
- **Values:** `value` is a flat row-major array over that order, so the index is `((((nat*4+ges)*5+stag)*7+alt)*477+kreis)`. The position of each code comes from `dimension.<VAR>.category.index`, not from list order. `status` maps index → flag: `"-"` = zero or nothing, `"e"` = value present.
- **Total cell:** NAT=%TOTAL%, GES02=%TOTAL%, ALT026=%TOTAL%. Also keep NATD and NATA (German / foreign) to control for the refugee share.
- **Data rules:** all values rounded to a multiple of 5 (max deviation 2). No revisions.

### 2.2 Unemployment (annual average)
- **Source:** Statistik der Bundesagentur für Arbeit. Registered unemployed and unemployment rate based on all civilian labour force, annual averages by Kreis.
- **Access:** BA statistics portal (statistik.arbeitsagentur.de) or Regionaldatenbank (regionalstatistik.de, statistic 13211). **Confirm the exact table code** before scripting.
- **Need:** years 2021–2025, all 400 Kreise. Variables: unemployed count and rate (alle zivilen Erwerbspersonen).

### 2.3 District GDP
- **Source:** Arbeitskreis VGR der Länder, Reihe 2 Band 1. GDP and GVA for kreisfreie Städte and Landkreise, 1992 and 1994–2024, calculated August 2025.
- **File:** https://www.statistikportal.de/sites/default/files/2026-09/vgrdl_r2b1_bs2025_4.xlsx
- **Page:** https://www.statistikportal.de/de/vgrdl/ergebnisse-kreisebene/bruttoinlandsprodukt-bruttowertschoepfung-kreise
- **Prices:** current prices only. No price-adjusted series exists at Kreis level. Deflate with the state GDP deflator (2.6).

### 2.4 Asking rents
- **Source:** BBSR, net cold asking rents (€/m²) for re-let existing flats of 30–130 m², from IDN ImmoDaten listings. Kreis level, 2010–2025 (revised series).
- **Access:** BBSR INKAR (https://www.inkar.de). **Confirm the indicator name and export method.** The R package `bonn` wraps the INKAR API.
- **Caveat:** listings underrepresent the low-rent segment.

### 2.5 State CPI
- **Annual:** GENESIS 61111-0010 "Verbraucherpreisindex: Bundesländer, Jahre". 16 states, years 1995–2025.
  - Coverage is complete for all states only from 2015: SH (01) and HH (02) start in 2015, HB (04) in 2005, the rest in 1995.
  - Endpoint: `GET https://genesis.destatis.de/genesis/api/rest/tables/61111-0010/data`. Dimension order: statistic, content, DLAND (16), JAHR (31).
- **Monthly:** 61111-0011, for robustness checks.

### 2.6 State GDP deflator (derived)
- **Source:** VGRdL Reihe 1 Band 1, 1991–2025, calculated August 2025/February 2026.
- **File:** https://www.statistikportal.de/sites/default/files/2026-03/vgrdl_r1b1_bs2025.xlsx
- **Method:** implicit deflator = nominal GDP / chain-linked real GDP index, rebased to a common year. Nominal GDP and the price-adjusted chain-linked GDP (section 6.1) are on separate sheets.

### 2.7 Optional: regional price index 2023
- **Source:** IW Köln and BBSR. All 400 Kreise, index with Germany = 100, for 2023 (2022 wave also exists). Raw-data spreadsheet on the study page.
- **Page:** https://www.iwkoeln.de/studien/ralph-henger-christoph-schroeder-jan-wendt-hendrik-boehmer-clemens-fabian-gruben-wo-es-sich-am-guenstigsten-und-wo-am-teuersten-lebt.html
- **Use:** fixed district price level only.

## 3. Geography cleaning (apply to every source)

1. **Drop historic codes.** Drop 22971-0080 rows whose label contains `(bis ` or `(b.`. There are about 75 such codes and they are empty in all waves.
2. **Hanau.** Hanau (06415) became kreisfrei on 2026-01-01. In wave 2026, add 06415 into Main-Kinzig-Kreis (06435) so the panel has 400 units throughout. Check whether other sources report Hanau separately, and harmonise them the same way.
3. **Eisenach.** Eisenach (16056) merged into Wartburgkreis (16063) on 2021-07-01, but wave 2022 still shows 10 people under 16056. Add them to 16063. Also check covariate sources for 2021 values reported under 16056.
4. **Common boundaries.** Use territorial boundaries as of 2022–2025 (400 Kreise). Map Kreis → state by the first 2 digits of the code.
5. **Zero rows.** A few live Kreise show `"-"` (zero) in some waves, e.g. 2026: 07135, 16076, 09475, 16062, 16074, 16068. Treat them as 0, not missing, but flag them.

## 4. Analysis notes

- **Wave 2022 is weak.** It was the first year of the statistic, with undercounting, and Ukrainian refugees enter the count only from 2023. Include a wave-2022 dummy and run a robustness check that drops it.
- **Refugee composition.** About 85% of those counted are foreign nationals, and Ukrainians were 128,900 of 452,900 in 2026. Model total, German-only and foreign counts separately.
- **Scope of the count.** It covers only people accommodated by municipalities or with costs reimbursed by social agencies. It excludes rough sleepers, people staying with friends or family, women's shelters, and asylum seekers in refugee accommodation; refugees whose asylum application was approved but who remain in such accommodation are included.
- **Price variation is state × year only** (16 states). With state fixed effects, the price effect is identified from within-state changes over time alone.
- **Real variables:** real GDP per capita = nominal district GDP / state GDP deflator. Real rents = asking rent / state CPI.

## 5. Deliverable for Claude Code

- One tidy file `panel.csv`, long format, with columns:
  - `ags`, `kreis_name`, `state`, `wave` (2022–2026), `cov_year` (= wave − 1)
  - `homeless_total`, `homeless_german`, `homeless_foreign`
  - `unemp_count`, `unemp_rate`
  - `gdp_nominal`, `gdp_real`
  - `rent_asking`, `rent_real`
  - `cpi_state`, `gdp_deflator_state`
  - `price_level_2023` (optional), `flag_zero`, `flag_wave2022`
- A short README listing source files, download dates, and every harmonisation step.

## 6. Open items to verify

- Exact Regionaldatenbank or BA table code for annual unemployment by Kreis, and the 2025 annual average release date.
- Name and export method of the INKAR asking-rent indicator, and whether 2025 is published at Kreis level.
- Sheet names and base year in the two VGRdL Excel files.
- Whether the BA or INKAR covariate data already use 2026 boundaries, i.e. whether Hanau appears separately.
