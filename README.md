# German district homelessness panel

A Kreis × wave panel of accommodated homeless persons (Destatis statistic 22971),
merged with lagged district covariates (unemployment, GDP, asking rents, population)
and state-level prices (CPI, GDP deflator). The spec is in
[`germany_homelessness_panel_dossier.md`](germany_homelessness_panel_dossier.md).

| File | Rows | Content |
|---|---|---|
| `data/panel_1600.csv` | 1,600 | 400 Kreise × waves 2022–2025. All core variables complete. **Main estimation sample.** |
| `data/panel.csv` | 2,000 | Same plus wave 2026. District GDP for 2025 is not yet published, so the GDP columns are empty for 2026. |
| `data/build_log.txt` | — | Harmonisation counts and validation checks from the last build. |
| `data/raw/manifest.csv` | — | Every source file with URL, download date, size, and SHA-256. |

No API keys or logins were needed for any source.

## Reproduce

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # (bin/ on macOS/Linux)
.venv/Scripts/python scripts/fetch_sources.py               # skips files already in data/raw; --force to refresh
.venv/Scripts/python scripts/build_panel.py
```

Raw files are committed, so `build_panel.py` runs offline.

## Timing

- **Wave *t*** = stock on the night of 31 Jan / 1 Feb of year *t*.
- **`cov_year` = *t* − 1.** Flow covariates (unemployment annual average, GDP, rents, CPI, deflator) refer to calendar year *t* − 1.
- **Population** is the 31 Dec *t* − 1 stock, one month before the count. It is the denominator for the per-1,000 rates.

## Variables

| Column | Unit | Source / construction |
|---|---|---|
| `ags` | 5-digit Kreis code (string, keep the leading zero) | 400 Kreise, boundaries of 2022–2025 |
| `kreis_name`, `state`, `state_name` | | GENESIS labels; state = first 2 digits of `ags` |
| `wave`, `cov_year` | year | see Timing |
| `homeless_total`, `homeless_german`, `homeless_foreign` | persons | GENESIS 22971-0080, all sexes and ages; NATD / NATA / total |
| `population` | persons, 31 Dec *t*−1 | GENESIS 12411-0015 |
| `homeless_per_1000` (+ `_german_`, `_foreign_`) | per 1,000 residents | homeless count / `population` × 1000 |
| `unemp_count` | persons, annual average | BA Statistik, registered unemployed (Arbeitslose), Kreis time series |
| `unemp_rate` | % of all civilian labour force | BA Statistik, Arbeitslosenquote (alle zivilen Erwerbspersonen) |
| `gdp_nominal` | Mio EUR, current prices | VGRdL Reihe 2 Band 1 (Aug 2025), sheet 1.1 |
| `gdp_real` | Mio EUR, 2020 prices | `gdp_nominal` / (`gdp_deflator_state` / 100) |
| `pop_vgr_1000` | 1,000 residents, annual average | VGRdL R2B1 sheet 5 (the denominator consistent with GDP) |
| `gdp_pc_nominal`, `gdp_pc_real` | EUR per resident | GDP / `pop_vgr_1000` |
| `rent_asking` | EUR/m² net cold | BBSR asking rents for re-lets, IDN ImmoDaten listings (revised 2010–2025 series) |
| `rent_real` | EUR/m², 2020 prices | `rent_asking` / (`cpi_state` / 100) |
| `cpi_state` | index, 2020 = 100 | GENESIS 61111-0010, Land CPI, annual |
| `gdp_deflator_state` | index, 2020 = 100 | VGRdL Reihe 1 Band 1: (nominal GDP / nominal GDP 2020) ÷ (chain-linked volume index / 100) × 100 |
| `price_level_2023` | Germany = 100, time-invariant | IW Köln / BBSR Regionaler Preisindex 2023 |
| `flag_zero` | 0/1 | homeless count published as "–" (zero). Kept as 0, not missing. |
| `flag_wave2022` | 0/1 | wave 2022 (first year of the statistic, undercounting, before Ukrainian refugees entered the count) |
| `flag_hanau_merged` | 0/1 | Main-Kinzig-Kreis in wave 2026, which includes Hanau's 920 people |
| `flag_eisenach_merged` | 0/1 | Wartburgkreis in wave 2022, which includes 10 people still reported under Eisenach |

## Sources and choices

### Homelessness: GENESIS 22971-0080
Pulled as JSON from `genesis.destatis.de/genesis/api/rest/tables/22971-0080/data`. The table was last changed on 2026-09-21. Cells are indexed by each dimension's `category.index`, not by list order. Status `-` is zero.
- 76 historic codes (labels containing `(bis ` / `(b.`) are dropped. They are all empty except Eisenach 16056 in wave 2022 (10 people), which is added to Wartburgkreis 16063.
- **Hanau.** Hanau 06415 became kreisfrei on 2026-01-01 and appears as its own unit only in wave 2026 (920 people, 885 of them foreign). It is added into Main-Kinzig-Kreis 06435 so the panel keeps 400 units.
- German + foreign differs from the total by at most 5, because each cell is rounded to a multiple of 5 independently. The published values are kept as they are.
- **Zero counts.** 37 Kreis-waves are zero (see `build_log.txt`). The dossier listed Cochem-Zell (07135) as zero in 2026, but the current table release shows 5. The other five 2026 zeros match.

### Unemployment: BA Statistik (not the Regionaldatenbank)
- **Why BA.** The Regionaldatenbank (regionalstatistik.de) web service requires a registered account. The INKAR bulk file stops at 2023. BA publishes the same source data keylessly as Excel time series, with annual averages for 1998–2025:
  - Arbeitslosenquoten – Kreise
  - Arbeitslose – Kreise und Gemeinden
- **Hanau.** BA projects the current (2026) boundaries back to all years, so Hanau is reported separately throughout. For Main-Kinzig + Hanau:
  - Counts are summed.
  - The rate is recomputed as Σ unemployed / Σ implied labour force, where labour force = count / rate. BA rates are published to one decimal, so the merged rate is accurate to about ±0.05 pp.
  - The merged rate is the only rate in the panel that is not rounded to one decimal.

### District GDP: VGRdL R2B1
- Kreise have 5-digit codes in the file. Berlin and Hamburg appear only at Land level (codes 11 and 02) and are mapped to 11000 and 02000.
- The file has no Hanau split.
- It covers years up to 2024, so wave 2026 has no GDP.

### Asking rents: BBSR, via its public Tableau dashboard
- **INKAR rejected.** The INKAR 2025 bulk CSV (434 MB) has the indicator `m_mietpr`, but values are **rounded to whole euros**. For example, Berlin goes 12 → 15 → 17. That is useless for within-Kreis variation, and the series also stops at 2024. The old INKAR JSON API (used by the R package `bonn`) now returns empty results.
- **What is used.** The cent-precision revised series 2010–2025 comes from BBSR's public Tableau dashboard (`Fachbeitrag_Mieten_2010_bis_2025_Krs24`), through a guest session (`scripts/fetch_bbsr_rents.py`).
- **Validation.**
  - 2025 values match the Deutschlandatlas `preis_miet` column for all 400 Kreise, to within 0.005 €.
  - Earlier years match INKAR's rounded values to within ±1 € in almost all cases. The small gaps reflect BBSR's revision of the series.
- **Boundaries.** Kreise as of 31.12.2024, with no Hanau split.
- **Caveat.** Listings under-represent the low-rent segment.
- **Fragility.** If BBSR renames the Tableau workbook, update `WORKBOOK` in the script. The committed CSV keeps the build reproducible.

### Prices
- **CPI.** GENESIS 61111-0010, 2020 = 100. All 16 Länder are complete for 2021–2025.
- **GDP deflator.** Derived from VGRdL R1B1:
  - nominal GDP: sheet 1.1
  - chain-linked index: sheet 6.1, block "Index (2020 = 100)"
  - Rebased to 2020.
  - **Caveat:** city-state deflators are volatile. Hamburg's is 122.1 in 2022 and falls to 120.3 in 2023. This comes from the published VGRdL data.
- **Price level.** IW Regionaler Preisindex 2023, used as a fixed cross-sectional control only.

### Population: GENESIS 12411-0015
Population on 31 Dec. Hanau is 0 (not yet split) through 31.12.2025, and Eisenach has been merged since 2021. No harmonisation was needed for 2021–2025.

## Resolution of the dossier's open items

| Open item | Resolution |
|---|---|
| Unemployment table code | Regionaldatenbank 13211-02-05-4 needs a login, so BA Excel time series were used instead (same underlying BA data). The 2025 annual average is already published (file created 27.03.2026). |
| INKAR rent indicator | `m_mietpr` (Angebotsmietpreise). INKAR only offers it rounded and only up to 2024, so the BBSR Tableau series was used. 2025 is published at Kreis level. |
| VGRdL sheet names and base year | R2B1 sheet `1.1` (GDP, Mio EUR) and `5` (residents). R1B1 sheets `1.1` (nominal) and `6.1` (chain-linked, 2020 = 100). |
| Do covariates use 2026 boundaries? | BA does (Hanau separate, merged here). VGRdL, BBSR rents, IW and population do not. |

## Analysis notes (from the dossier)
- **Wave 2022.** Wave 2022 is weak: use `flag_wave2022` and a drop-2022 robustness check.
- **Composition.** About 85% of those counted are foreign nationals. Model total, German and foreign counts separately.
- **Scope of the count.** It covers only people accommodated by municipalities or whose costs are reimbursed by social agencies.
- **Price identification.** CPI and the deflator vary only by state × year. With state fixed effects, price effects are identified from within-state changes over time.
