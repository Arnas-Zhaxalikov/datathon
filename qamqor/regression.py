"""
Qamqor AI — регрессионный анализ / regression analysis (v0.3.2).

RU: Что связано с бедностью, если держать остальное постоянным. Три модели на семьях 2024 года
    (и проверка на 2022–2024): (1) линейная — логарифм дохода на человека относительно
    регионального ПМ; (2) логистическая — ниже ПМ или нет; (3) логистическая — уровни B и C
    (не проходят стресс-тест) среди тех, кто выше ПМ. Плюс разложение «детского штрафа»: сколько падения дохода на
    человека объясняется делением на большее число членов, а сколько — меньшим доходом семьи.
    Это связи, а не причины; данные синтетические.
EN: What is associated with poverty, holding the rest fixed. Three models on 2024 households
    (with a check on 2022–2024): (1) linear — log income per person relative to the regional SM;
    (2) logistic — below the SM or not; (3) logistic — levels B and C among those above the SM.
    Plus a decomposition of the "child penalty": how much of the fall in income per person comes
    from dividing by more members and how much from lower household income.
    These are associations, not causes; the data is synthetic.

Запуск / Run:
    python regression.py out/households.csv results
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import engine as E

warnings.filterwarnings("ignore")
RHS = "n_child + n_elderly + n_working_age + n_earners + urban + C(region)"
MAIN = ["n_child", "n_elderly", "n_working_age", "n_earners", "urban"]


def prepare(hh):
    parts = []
    for y, d in hh.groupby("year"):
        d = d.reset_index(drop=True)
        c = E.classify(d, int(y))
        d["ratio"] = c["pc_income"] / c["sm"]
        d["poor"] = (d["ratio"] < 1).astype(int)
        # RU: уровни B и C: выше ПМ, но не проходят хотя бы один стресс-тест. EN: levels B and C.
        d["hidden"] = c["tier"].isin(E.AT_RISK).astype(int)
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d = d[d.income > 0].copy()
    d["log_ratio"] = np.log(d["ratio"])
    d["log_income"] = np.log(d["income"])
    return d


def ols_table(m):
    ci = m.conf_int()
    return {k: {"effect_pct": round(100 * (np.exp(m.params[k]) - 1), 1),
                "ci95_pct": [round(100 * (np.exp(ci.loc[k, 0]) - 1), 1), round(100 * (np.exp(ci.loc[k, 1]) - 1), 1)],
                "p": float(f"{m.pvalues[k]:.3g}")} for k in MAIN}


def logit_table(m):
    ci = m.conf_int()
    ame = m.get_margeff().summary_frame()
    return {k: {"odds_ratio": round(float(np.exp(m.params[k])), 2),
                "ci95": [round(float(np.exp(ci.loc[k, 0])), 2), round(float(np.exp(ci.loc[k, 1])), 2)],
                "avg_effect_points": round(100 * float(ame.loc[k, "dy/dx"]), 2),
                "p": float(f"{m.pvalues[k]:.3g}")} for k in MAIN}


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/households.csv")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results")
    E.set_line_mode("regional")
    d = prepare(pd.read_csv(src, dtype={"hh_id": str, "region": str}))
    d24 = d[d.year == 2024]
    R = {"version": "0.3.4", "note": "Household-level, robust standard errors (HC1). Associations, not causes. Synthetic data.",
         "households_2024": int(len(d24))}

    m1 = smf.ols(f"log_ratio ~ {RHS}", d24).fit(cov_type="HC1")
    R["ols_income_per_person_2024"] = {"r2": round(m1.rsquared, 3), "effects": ols_table(m1)}
    # RU: вклад блоков в R2. EN: contribution of blocks to R2.
    steps = [("children only", "n_child"), ("+ elderly and working-age adults", "n_child + n_elderly + n_working_age"),
             ("+ number of earners", "n_child + n_elderly + n_working_age + n_earners"),
             ("+ urban or rural", "n_child + n_elderly + n_working_age + n_earners + urban"), ("+ region", RHS)]
    R["r2_steps_2024"] = [{"model": n, "r2": round(smf.ols(f"log_ratio ~ {f}", d24).fit().rsquared, 3)} for n, f in steps]

    m2 = smf.logit(f"poor ~ {RHS}", d24).fit(disp=0, cov_type="HC1", maxiter=200)
    R["logit_poor_2024"] = {"pseudo_r2": round(m2.prsquared, 3), "effects": logit_table(m2)}
    nonpoor = d24[d24.poor == 0]
    m3 = smf.logit(f"hidden ~ {RHS}", nonpoor).fit(disp=0, cov_type="HC1", maxiter=200)
    R["logit_levels_b_c_among_nonpoor_2024"] = {"pseudo_r2": round(m3.prsquared, 3), "households": int(len(nonpoor)),
                                                       "effects": logit_table(m3)}

    # RU: «детский штраф»: доход на человека и доход семьи. EN: the "child penalty": income per person and household income.
    pen = {}
    for name, f in [("children only", "n_child"), ("holding adults, elderly, earners, region fixed", RHS)]:
        a = smf.ols(f"log_ratio ~ {f}", d24).fit(cov_type="HC1")
        b = smf.ols(f"log_income ~ {f}", d24).fit(cov_type="HC1")
        pen[name] = {"per_person_income_pct_per_child": round(100 * (np.exp(a.params["n_child"]) - 1), 1),
                     "household_income_pct_per_child": round(100 * (np.exp(b.params["n_child"]) - 1), 1)}
    # RU: чисто арифметический эффект: тот же доход семьи делится на одного человека больше.
    # EN: the purely arithmetic effect: the same household income divided by one more person.
    mech = float(np.average(np.log(d24["size"] / (d24["size"] + 1)), weights=None))
    pen["arithmetic_effect_of_one_more_member_pct"] = round(100 * (np.exp(mech) - 1), 1)
    R["child_penalty_2024"] = pen

    # RU: устойчивость по годам. EN: stability across years.
    R["by_year"] = []
    for y in (2022, 2023, 2024):
        dy = d[d.year == y]
        a = smf.ols(f"log_ratio ~ {RHS}", dy).fit(cov_type="HC1")
        b = smf.logit(f"poor ~ {RHS}", dy).fit(disp=0, maxiter=200)
        R["by_year"].append({"year": y, "r2": round(a.rsquared, 3),
                             "income_pct_per_child": round(100 * (np.exp(a.params["n_child"]) - 1), 1),
                             "income_pct_per_earner": round(100 * (np.exp(a.params["n_earners"]) - 1), 1),
                             "odds_ratio_child": round(float(np.exp(b.params["n_child"])), 2),
                             "odds_ratio_earner": round(float(np.exp(b.params["n_earners"])), 2)})
    # RU: регионы относительно среднего (после учёта состава семьи). EN: regions after controlling for composition.
    reg = {E.REGION_NAMES[k.split("[T.")[1].rstrip("]")]: round(100 * (np.exp(v) - 1), 1) for k, v in m1.params.items() if k.startswith("C(region)")}
    R["region_effect_vs_Abai_pct_2024"] = dict(sorted(reg.items(), key=lambda kv: kv[1]))
    # RU: мультиколлинеарность. EN: collinearity check.
    X = d24[MAIN].astype(float)
    Xc = (X - X.mean()) / X.std()
    R["vif"] = {c: round(float(1 / (1 - smf.ols(f"{c} ~ " + " + ".join(k for k in MAIN if k != c), d24).fit().rsquared)), 2) for c in MAIN}

    out.mkdir(parents=True, exist_ok=True)
    (out / "regression.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=float), encoding="utf-8", newline="\n")
    print("saved ->", out / "regression.json")


if __name__ == "__main__":
    main()
