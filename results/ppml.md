# Population-weighted PPML: homelessness on log covariates

Sample: `data/panel_1600.csv` (400 Kreise x waves 2022-2025). Outcome: homeless per 1,000 residents,
weighted by population (31 Dec t-1). Equivalent to PPML on counts with a log-population offset.
Regressors are logs of: unemployment rate, state CPI, real GDP per capita, real asking rent (all year t-1).
Coefficients are elasticities. SEs clustered by Kreis in parentheses. * p<0.1, ** p<0.05, *** p<0.01.
Kreise with zero homeless in every wave are dropped under Kreis FE (no within variation).

### Outcome: Total homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | -0.020 (0.162) | 11.826 (9.296) | 0.215* (0.119) | 1.808*** (0.211) | 1600 | 0 |
| (2) Kreis + wave FE | 1.082*** (0.409) | 10.542 (9.381) | -0.471 (0.443) | 1.388 (1.121) | 1588 | 12 |
| (3) Kreis + wave FE, drop 2022 | 0.239 (0.347) | 8.064 (6.948) | -0.094 (0.361) | 0.966 (0.590) | 1185 | 15 |

### Outcome: German homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | 0.849*** (0.228) | -4.227 (2.819) | 0.601*** (0.121) | 1.272*** (0.331) | 1600 | 0 |
| (2) Kreis + wave FE | 0.025 (0.243) | -2.670 (2.930) | 0.200 (0.229) | 0.325 (0.419) | 1572 | 28 |
| (3) Kreis + wave FE, drop 2022 | 0.218 (0.366) | -7.318** (3.660) | 0.023 (0.244) | -0.259 (0.610) | 1176 | 24 |

### Outcome: Foreign homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | -0.208 (0.164) | 19.461 (11.923) | 0.132 (0.132) | 1.931*** (0.229) | 1600 | 0 |
| (2) Kreis + wave FE | 1.072** (0.482) | 18.013 (12.312) | -0.494 (0.517) | 1.679 (1.393) | 1540 | 60 |
| (3) Kreis + wave FE, drop 2022 | 0.183 (0.391) | 11.575 (8.332) | -0.080 (0.401) | 1.278* (0.656) | 1146 | 54 |

Cross-check, spec (2) total, statsmodels GLM with dummies vs pyfixest, max |diff| = 5.60e-13
