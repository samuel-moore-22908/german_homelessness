# Population-weighted PPML: homelessness on log covariates

Sample: `data/panel_1600.csv` (400 Kreise x waves 2022-2025). Outcome: homeless per 1,000 residents,
weighted by population (31 Dec t-1). Equivalent to PPML on counts with a log-population offset.
Regressors are logs of: unemployment rate, state CPI, real GDP per capita, real asking rent (all year t-1).
Coefficients are elasticities. SEs clustered by state (16 clusters) in parentheses;
p-values from t(15). * p<0.1, ** p<0.05, *** p<0.01.
Kreise with zero homeless in every wave are dropped under Kreis FE (no within variation).

### Outcome: Total homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | -0.020 (0.314) | 11.826 (9.432) | 0.215 (0.164) | 1.808*** (0.307) | 1600 | 0 |
| (2) Kreis + wave FE | 1.082* (0.570) | 10.542 (9.761) | -0.471 (0.571) | 1.388 (1.309) | 1588 | 12 |
| (3) Kreis + wave FE, drop 2022 | 0.239 (0.384) | 8.064 (7.680) | -0.094 (0.451) | 0.966 (0.706) | 1185 | 15 |

### Outcome: German homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | 0.849** (0.341) | -4.227 (2.983) | 0.601*** (0.174) | 1.272** (0.449) | 1600 | 0 |
| (2) Kreis + wave FE | 0.025 (0.251) | -2.670 (2.826) | 0.200 (0.283) | 0.325 (0.475) | 1572 | 28 |
| (3) Kreis + wave FE, drop 2022 | 0.218 (0.418) | -7.318 (4.415) | 0.023 (0.303) | -0.259 (0.647) | 1176 | 24 |

### Outcome: Foreign homeless per 1,000 residents

| Spec | ln_unemp | ln_cpi | ln_gdppc | ln_rent | N | Obs dropped (all-zero Kreise) |
|---|---|---|---|---|---|---|
| (1) State + wave FE | -0.208 (0.297) | 19.461 (12.100) | 0.132 (0.167) | 1.931*** (0.346) | 1600 | 0 |
| (2) Kreis + wave FE | 1.072 (0.657) | 18.013 (12.787) | -0.494 (0.639) | 1.679 (1.580) | 1540 | 60 |
| (3) Kreis + wave FE, drop 2022 | 0.183 (0.431) | 11.575 (9.058) | -0.080 (0.502) | 1.278 (0.792) | 1146 | 54 |

Cross-check, spec (2) total, statsmodels GLM with dummies vs pyfixest, max |diff| = 5.60e-13
