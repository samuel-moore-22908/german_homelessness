"""Population-weighted PPML of homelessness on log unemployment, prices, GDP per capita and rent.

Outcome is the homelessness rate (homeless per 1,000 residents). PPML on the rate with
population weights has the same first-order conditions as PPML on the count with
log(population) as an offset, so coefficients are elasticities of the count holding
population fixed.

Regressors (all cov_year = wave - 1):
  ln_unemp   log unemployment rate (BA, % of civilian labour force)
  ln_cpi     log state CPI (2020 = 100)
  ln_gdppc   log real GDP per capita (state-deflated, 2020 EUR)
  ln_rent    log real asking rent (CPI-deflated, 2020 EUR/m2)

Sample: data/panel_1600.csv (waves 2022-2025). Writes results/ppml.md and results/ppml.csv.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"
X = ["ln_unemp", "ln_cpi", "ln_gdppc", "ln_rent"]
OUTCOMES = {"homeless_total": "Total", "homeless_german": "German", "homeless_foreign": "Foreign"}


def load() -> pd.DataFrame:
    p = pd.read_csv(ROOT / "data" / "panel_1600.csv", dtype={"ags": str, "state": str})
    p["ln_unemp"] = np.log(p.unemp_rate)
    p["ln_cpi"] = np.log(p.cpi_state)
    p["ln_gdppc"] = np.log(p.gdp_pc_real)
    p["ln_rent"] = np.log(p.rent_real)
    for y in OUTCOMES:
        p[f"rate_{y}"] = 1000 * p[y] / p.population
    return p


def specs(d: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    rhs = " + ".join(X)
    return [
        ("(1) State + wave FE", f"{rhs} | state + wave", d),
        ("(2) Kreis + wave FE", f"{rhs} | ags + wave", d),
        ("(3) Kreis + wave FE, drop 2022", f"{rhs} | ags + wave", d[d.wave > 2022]),
    ]


def statsmodels_check(d: pd.DataFrame) -> pd.Series:
    """Spec (2) for the total, with explicit dummies via statsmodels GLM, as a cross-check."""
    keep = d.groupby("ags").homeless_total.transform("sum") > 0  # all-zero Kreise carry no information
    d = d[keep]
    Z = pd.get_dummies(d[["ags", "wave"]].astype(str), drop_first=True, dtype=float)
    Xm = sm.add_constant(pd.concat([d[X], Z], axis=1))
    m = sm.GLM(d["rate_homeless_total"], Xm, family=sm.families.Poisson(),
               var_weights=d.population).fit(cov_type="cluster", cov_kwds={"groups": d.ags.astype("category").cat.codes})
    return m.params[X]


def main() -> None:
    d = load()
    RES.mkdir(exist_ok=True)
    rows, lines = [], []
    for y, ylab in OUTCOMES.items():
        lines.append(f"\n### Outcome: {ylab} homeless per 1,000 residents\n")
        lines.append("| Spec | " + " | ".join(X) + " | N | Obs dropped (all-zero Kreise) |")
        lines.append("|---|" + "---|" * (len(X) + 2))
        for name, rhs, sub in specs(d):
            fit = pf.fepois(f"rate_{y} ~ {rhs}", data=sub, weights="population", vcov={"CRV1": "ags"})
            t = fit.tidy()
            n = fit._N
            cells = []
            for x in X:
                b, se, pv = t.loc[x, "Estimate"], t.loc[x, "Std. Error"], t.loc[x, "Pr(>|t|)"]
                stars = "***" if pv < 0.01 else "**" if pv < 0.05 else "*" if pv < 0.1 else ""
                cells.append(f"{b:.3f}{stars} ({se:.3f})")
                rows.append({"outcome": ylab, "spec": name, "term": x, "coef": b, "se": se, "p": pv, "n": n})
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {n} | {len(sub) - n} |")

    chk = statsmodels_check(d)
    pyf = pd.DataFrame(rows).query("outcome == 'Total' and spec == '(2) Kreis + wave FE'").set_index("term").coef
    lines.append("\nCross-check, spec (2) total, statsmodels GLM with dummies vs pyfixest, max |diff| = "
                 f"{(chk - pyf).abs().max():.2e}")

    header = [
        "# Population-weighted PPML: homelessness on log covariates",
        "",
        "Sample: `data/panel_1600.csv` (400 Kreise x waves 2022-2025). Outcome: homeless per 1,000 residents,",
        "weighted by population (31 Dec t-1). Equivalent to PPML on counts with a log-population offset.",
        "Regressors are logs of: unemployment rate, state CPI, real GDP per capita, real asking rent (all year t-1).",
        "Coefficients are elasticities. SEs clustered by Kreis in parentheses. * p<0.1, ** p<0.05, *** p<0.01.",
        "Kreise with zero homeless in every wave are dropped under Kreis FE (no within variation).",
    ]
    (RES / "ppml.md").write_text("\n".join(header + lines) + "\n", encoding="utf-8")
    pd.DataFrame(rows).to_csv(RES / "ppml.csv", index=False)
    print("\n".join(header + lines))


if __name__ == "__main__":
    main()
