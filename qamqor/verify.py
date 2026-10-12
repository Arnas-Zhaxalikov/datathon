"""
Qamqor AI — независимая проверка итогов / an independent check of the results (v0.3).

RU: Часть 1 пересчитывает главные цифры прямо из таблицы домохозяйств обычным pandas, не
    используя engine.py, и сравнивает с results.json. Черты берутся из
    ref/regional_sm_annual_2022_2024.csv, а не из кода ядра, поэтому заодно проверяется, что в
    ядро они перенесены без ошибок.
    Часть 2 вызывает расчётные инструменты из tools.py и проверяет, что они возвращают те же
    числа, что записаны в results.json: итоговый файл и ассистент не могут разойтись.
EN: Part 1 recomputes the headline figures straight from the household table with plain pandas,
    without engine.py, and compares them with results.json. The lines are read from
    ref/regional_sm_annual_2022_2024.csv, not from the engine code, so this also checks that they
    were copied into the engine without errors.
    Part 2 calls the calculation tools in tools.py and checks that they return the same numbers as
    results.json: the final file and the assistant cannot drift apart.

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


def same(name, a, b):
    global ok
    good = a == b
    ok &= good
    print(f"{'OK  ' if good else 'DIFF'} {name}" + ("" if good else f": {a} vs {b}"))


# ---- Часть 1: независимый пересчёт / Part 1: independent recomputation -------------------
BUDGET = {2022: (3 * 36018 + 9 * 37389) / 12, 2023: 40567, 2024: 43407}
CITY = {"Astana city": "71", "Almaty city": "75", "Shymkent city": "79"}
# RU: базовый набор из трёх стресс-тестов. EN: the base set of three stress tests.
MONTHS, KEEP, PRICES, UTIL = 3, 0.45, 0.10, 0.30

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
    # RU: уровни A–E. Наёмная часть заработка главного кормильца замещается на 45%.
    # EN: levels A–E. The wage part of the main earner's earnings is replaced at 45%.
    wage_share = (d.inc_wage / d.inc_labor.replace(0, np.nan)).fillna(0).clip(0, 1)
    lost = d.main_earner_labor * MONTHS / 12 * (1 - KEEP * wage_share)
    fails = ((d.income - lost) / n < line).astype(int) + (d.income / (1 + PRICES) / n < line).astype(int) \
        + ((d.income - d.utilities * UTIL) / n < line).astype(int)
    above = pc >= line
    chk(f"{y} level E", f(pc < 0.7 * line), g["tiers_pct"]["E_below_tsa_line"])
    chk(f"{y} level D", f((pc >= 0.7 * line) & (pc < line)), g["tiers_pct"]["D_below_sm"])
    chk(f"{y} level C", f(above & (fails >= 2)), g["tiers_pct"]["C_fails_two_or_more"])
    chk(f"{y} level B", f(above & (fails == 1)), g["tiers_pct"]["B_fails_one_test"])
    chk(f"{y} level A", f(above & (fails == 0)), g["tiers_pct"]["A_resilient"])
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
    shocked = [d.income - 0.1 * d.inc_labor, d.income - lost, d.income - 0.3 * d.utilities, d.income / 1.1]
    assert len(shocked) == len(R["shock_2024"])
    for inc, r in zip(shocked, R["shock_2024"]):
        chk("2024 shock: " + r["shock"], f(inc / n < line), r["after_shock"]["poverty_rate_sm_pct"])
    cost = np.maximum(0, 0.7 * line * 12 * d["size"] - d.income).sum() / w.sum()
    chk("2024 top-up to the TSA line, tenge per person per year", cost,
        R["policy_2024"][0]["cost"]["per_capita_tenge_year"], tol=0.51)
    # RU: профиль уровней B и C: доля группы и доля с одним работающим. EN: the B and C profile.
    grp = above & (fails >= 1)
    prof = R["levels_b_c_profile_2024"]["groups"]["B_and_C"]
    chk("2024 levels B and C, share of people", f(grp), prof["persons_pct_of_sample"])
    chk("2024 levels B and C, one earner", 100 * ((d.n_earners == 1)[grp] * w[grp]).sum() / w[grp].sum(),
        prof["one_earner_pct"], tol=0.051)

# ---- Часть 2: инструменты возвращают те же числа / Part 2: the tools return the same numbers --
import tools

tools.load(sys.argv[1])
for y in (2022, 2023, 2024):
    g = tools.call("gap_overview", {"year": y, "profile": y == 2024})["result"]
    same(f"tools gap_overview {y}: overall", g["overall"], next(r for r in R["gap_by_year_regional_line"] if r["year"] == y))
    same(f"tools gap_overview {y}: three_lines", g["three_lines"], next(r for r in R["three_lines_by_year"] if r["year"] == y))
    if y == 2024:
        same("tools gap_overview 2024: levels B and C profile", g["levels_b_c_profile"], R["levels_b_c_profile_2024"])
eq = tools.call("gap_overview", {"year": 2024, "group_by": "n_child", "equivalence_scale": True})["result"]["equivalence_scale"]
same("tools gap_overview 2024: equivalence scale headline",
     {k: v for k, v in eq.items() if k not in ("by_group", "note")},
     {k: v for k, v in R["equivalence_2024"].items() if not k.startswith("by_")})
for r in R["shock_2024"]:
    kind, size = next((k, s) for k, s in [("wages", 0.10), ("earner_loss", 3), ("utilities", 0.30), ("prices", 0.10)]
                      if r["shock"] == tools.E.Shock(k, s).name())
    s = tools.call("simulate", {"year": 2024, "shock": {"kind": kind, "size": size}})["result"]
    same("tools simulate 2024: " + r["shock"], s, r)
s = tools.call("simulate", {"year": 2024, "policy": {"kind": "tsa", "line_share": 0.7,
                                                     "label": "TSA top-up to 70% SM (pre-2025 rule)"}})["result"]
same("tools simulate 2024: TSA top-up to 70% SM", s, R["policy_2024"][0])
cands = [{"kind": "tsa", "line_share": 1.0}, {"kind": "tsa"}, {"kind": "tsa", "takeup": 0.6},
         {"kind": "child_allowance", "min_children": 1}, {"kind": "child_allowance", "min_children": 4}]
c = tools.call("compare_policies", {"year": 2024, "policies": cands, "equal_budget": True, "focus_levels_b_c": True,
                                    "shock": {"kind": "prices", "size": 0.10}})["result"]["levels_b_c"]
ref = next(r for r in R["levels_b_c_equal_budget_2024"] if r["shock"] == c["shock"])
for k in ("group_persons_pct_of_sample", "group_below_sm_after_shock_no_policy_pct"):
    same(f"tools compare_policies 2024, levels B and C after {c['shock']}: {k}", c[k], ref[k])
# RU: одна семья: 2 взрослых и 2 детей в Астане, один наёмный кормилец. EN: one household.
one = tools.call("check_household", {"year": 2024, "region": "Astana city", "utilities_month": 25000, "members": [
    {"age": 36, "labor_month": 260000}, {"age": 34}, {"age": 8}, {"age": 3}]})["result"]
same("tools check_household: level and failed tests are returned",
     (one["level"], one["tier"][0], isinstance(one["failed_tests"], list)), (one["level"], one["level"], True))
print(f"     check_household example: level {one['level']}, {one['income_per_capita_month']} tenge per person, "
      f"failed tests: {one['failed_tests']}")

print("ALL OK" if ok else "SOME DIFFER")
sys.exit(0 if ok else 1)
