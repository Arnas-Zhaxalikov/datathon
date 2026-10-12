"""
Qamqor AI — независимая проверка итогов / an independent check of the results (v0.3).

RU: Пересчитывает главные цифры прямо из таблицы домохозяйств обычным pandas, не используя
    engine.py, и сравнивает с results.json. Черты берутся из ref/regional_sm_annual_2022_2024.csv,
    а не из кода ядра, поэтому заодно проверяется, что в ядро они перенесены без ошибок.
EN: Recomputes the headline figures straight from the household table with plain pandas, without
    engine.py, and compares them with results.json. The lines are read from
    ref/regional_sm_annual_2022_2024.csv, not from the engine code, so this also checks that they
    were copied into the engine without errors.

Запуск / Run:
    python verify.py out/households.csv ref/regional_sm_annual_2022_2024.csv results/results.json
"""
import json
import sys

import numpy as np
import pandas as pd

hh = pd.read_csv(sys.argv[1], dtype={"hh_id": str, "region": str})
sm = pd.read_csv(sys.argv[2], dtype={"region_code": str})
R = json.load(open(sys.argv[3], encoding="utf-8"))
ok = True


def chk(name, mine, theirs, tol=0.006):
    global ok
    good = abs(mine - theirs) <= tol
    ok &= good
    print(f"{'OK  ' if good else 'DIFF'} {name}: independent {mine:.3f} vs engine {theirs}")


BUDGET = {2022: (3 * 36018 + 9 * 37389) / 12, 2023: 40567, 2024: 43407}
CITY = {"Astana city": "71", "Almaty city": "75", "Shymkent city": "79"}

for y in (2022, 2023, 2024):
    d = hh[hh.year == y].copy()
    line = d.region.map(dict(zip(sm.region_code, sm[f"sm_{y}"]))).astype(float)
    assert line.notna().all(), "a region code has no subsistence minimum"
    w, n = d["size"], d["size"] * 12
    pc = d.income / n
    f = lambda m: 100 * (m * w).sum() / w.sum()   # person-weighted share, %
    t = next(r for r in R["three_lines_by_year"] if r["year"] == y)
    g = next(r for r in R["gap_by_year_regional_line"] if r["year"] == y)
    e = next(r for r in R["equivalence_by_year"] if r["year"] == y)
    chk(f"{y} below regional SM", f(pc < line), t["below_regional_sm_pct"])
    chk(f"{y} below TSA line", f(pc < 0.7 * line), t["below_tsa_line_pct"])
    chk(f"{y} below budget-law SM", f(pc < BUDGET[y]), t["below_budget_sm_pct"])
    chk(f"{y} tier A", f(pc < 0.7 * line), g["tiers_pct"]["A_tsa_eligible"])
    chk(f"{y} tier B", f((pc >= 0.7 * line) & (pc < line)), g["tiers_pct"]["B_poor_not_eligible"])
    fail = (((d.income - d.main_earner_labor * 3 / 12) / n < line) | (d.income * 0.85 / n < line)
            | ((d.income - d.utilities * 0.3) / n < line))
    chk(f"{y} tier C", f(fail & (pc >= line)), g["tiers_pct"]["C_hidden_vulnerable"])
    pe = d.income / (1 + 0.8 * (d["size"] - 1)) / 12
    chk(f"{y} equivalised income, same line", f(pe < line), e["below_sm_equivalised_same_line_pct"])
    if y != 2024:
        continue
    for row in R["gap_by_region_2024"]:
        code = CITY.get(row["region"]) or sm.loc[sm.region == row["region"], "region_code"].iloc[0]
        m = d.region == code
        chk(f"2024 {row['region']}", 100 * ((pc < line)[m] * w[m]).sum() / w[m].sum(),
            row["below_sm_regional_line_pct"], tol=0.051)
    k4 = d.n_child >= 4
    row = next(r for r in R["equivalence_2024"]["by_children"] if r["n_child_group"] == "4+")
    chk("2024 4+ children, per capita", 100 * ((pc < line)[k4] * w[k4]).sum() / w[k4].sum(),
        row["below_sm_per_capita_pct"], tol=0.051)
    chk("2024 4+ children, equivalised", 100 * ((pe < line)[k4] * w[k4]).sum() / w[k4].sum(),
        row["below_sm_equivalised_same_line_pct"], tol=0.051)
    shocked = {"Labour income -10%": d.income - 0.1 * d.inc_labor,
               "Main earner loses 3 months of earnings": d.income - d.main_earner_labor * 0.25,
               "Housing and utility costs +30%": d.income - 0.3 * d.utilities,
               "Prices +10%": d.income / 1.1}
    for r in R["shock_2024"]:
        chk("2024 shock: " + r["shock"], f(shocked[r["shock"]] / n < line), r["after_shock"]["poverty_rate_sm_pct"])
    cost = np.maximum(0, 0.7 * line * 12 * d["size"] - d.income).sum() / w.sum() * 20e6 / 1e9
    chk("2024 top-up to the TSA line, bn tenge", cost,
        R["policy_2024"][0]["cost"]["illustrative_national_bln_tenge_year"], tol=0.06)

print("ALL OK" if ok else "SOME DIFFER")
sys.exit(0 if ok else 1)
