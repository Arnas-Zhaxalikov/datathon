"""
Qamqor AI — базовый прогон всех модулей (v0.3) / baseline run of all modules (v0.3).

Запуск / Run:
    python run_baseline.py out/households.csv results
"""
import json
import sys
from pathlib import Path

import pandas as pd

import engine as E


def load(path) -> pd.DataFrame:
    return pd.read_csv(path, dtype={"hh_id": str, "region": str})


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/households.csv")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results")
    out.mkdir(parents=True, exist_ok=True)
    allh = load(src)
    R = {"version": "0.3"}
    years = [int(y) for y in sorted(allh.year.unique())]
    by_year = {y: allh[allh.year == y].reset_index(drop=True) for y in years}

    # ---- 1. Gap Detector: кого система не видит / who is missed ---------------------------
    # RU: с v0.3 фактический региональный ПМ есть за все три года, поэтому динамика считается
    #     и на региональной черте. Бюджетная оставлена для сравнения с v0.1–v0.2.
    # EN: from v0.3 the actual regional SM exists for all three years, so the trend is also
    #     computed on the regional line. The budget line is kept for comparison with v0.1–v0.2.
    E.set_line_mode("budget")
    R["gap_by_year_budget_line"] = [E.summary(by_year[y], y) for y in years]
    E.set_line_mode("regional")
    R["gap_by_year_regional_line"] = [E.summary(by_year[y], y) for y in years]
    # RU: три черты по годам: черта АСП, бюджетный ПМ, региональный ПМ.
    # EN: three lines by year: the TSA line, the budget-law SM, the regional SM.
    R["three_lines_by_year"] = [E.three_lines(by_year[y], y) for y in years]
    R["regional_sm_by_year"] = {str(y): {E.REGION_NAMES[k]: v for k, v in E.REGIONAL_SM[y].items()} for y in years}
    R["national_sm_by_year"] = {str(y): {"actual": E.ACTUAL_SM_NATIONAL[y], "budget_law": round(E.SUBSISTENCE_MIN[y])} for y in years}
    # RU: доля ниже регионального ПМ по регионам и годам. EN: share below the regional SM by region and year.
    rows = {}
    for y in years:
        d = by_year[y]
        pm, pc = E.sm(d, y), E.per_capita(d)
        for k, g in d.groupby("region"):
            rows.setdefault(E.REGION_NAMES.get(k, k), {})[str(y)] = round(100 * E.share(pc[g.index] < pm[g.index] - E.EPS, g), 1)
    R["below_sm_by_region_by_year"] = [{"region": k, **v} for k, v in sorted(rows.items(), key=lambda kv: -kv[1][str(years[-1])])]
    df = allh[allh.year == 2024].reset_index(drop=True)
    # RU: одна и та же выборка при трёх разных чертах. EN: the same sample under three different lines.
    R["line_modes_2024"] = {}
    by_mode = {}
    for mode in ("budget", "actual", "regional"):
        E.set_line_mode(mode)
        R["line_modes_2024"][mode] = E.summary(df, 2024)
        by_mode[mode] = E.classify(df, 2024)
    # RU: дальше всё считается на региональной черте. EN: everything below uses the regional line.
    E.set_line_mode("regional")
    c = by_mode["regional"]
    R["regional_sm_2024"] = {E.REGION_NAMES[k]: round(v) for k, v in E.REGIONAL_SM[2024].items()}
    by_children = []
    for key, g in df.assign(_g=df["n_child"].clip(upper=4)).groupby("_g"):
        t = c.loc[g.index, "tier"]
        by_children.append({"n_child": "4+" if key == 4 else str(int(key)),
                            "persons_pct_of_sample": round(100 * g["size"].sum() / df["size"].sum(), 1),
                            **{k: round(100 * E.share(t == k, g), 1) for k in E.TIERS}})
    R["gap_by_children_2024"] = by_children
    rows = []
    for key, g in df.groupby("hh_type"):
        t = c.loc[g.index, "tier"]
        rows.append({"hh_type": key, "persons_pct_of_sample": round(100 * g["size"].sum() / df["size"].sum(), 1),
                     **{k: round(100 * E.share(t == k, g), 1) for k in E.TIERS}})
    R["gap_by_type_2024"] = rows
    # RU: почему семьи группы C уязвимы. EN: why tier C households are vulnerable.
    C = c[c.tier == "C_hidden_vulnerable"]
    dC = df.loc[C.index]
    R["hidden_vulnerable_reasons_2024"] = {k: round(100 * E.share(C[k], dC), 1)
                                           for k in C.columns if k.startswith(("fail_", "drv_"))}
    # RU: чувствительность к силе стресс-теста. EN: sensitivity to stress-test strength.
    sens = []
    for months, drop, util in [(1, 0.05, 0.10), (2, 0.10, 0.20), (3, 0.15, 0.30), (6, 0.25, 0.50)]:
        st = E.StressTests(months, drop, util)
        s = E.summary(df, 2024, st)
        sens.append({"main_earner_months_lost": months, "income_drop": drop, "utilities_rise": util,
                     "hidden_vulnerable_pct": s["tiers_pct"]["C_hidden_vulnerable"]})
    R["hidden_vulnerable_sensitivity_2024"] = sens
    def below(mode, g):
        m = by_mode[mode].loc[g.index]
        return round(100 * E.share(m["pc_income"] < m["sm"] - E.EPS, g), 1)

    R["gap_by_region_2024"] = sorted(
        [{"region": E.REGION_NAMES.get(k, k), "persons_pct_of_sample": round(100 * g["size"].sum() / df["size"].sum(), 1),
          "subsistence_minimum": round(E.REGIONAL_SM[2024][k]),
          "median_income_per_capita": round(E.weighted_median(c.loc[g.index, "pc_income"], g["size"])),
          "below_sm_one_national_line_pct": below("actual", g),
          "below_sm_regional_line_pct": below("regional", g),
          **{t: round(100 * E.share(c.loc[g.index, "tier"] == t, g), 1) for t in E.TIERS}} for k, g in df.groupby("region")],
        key=lambda x: -x["below_sm_regional_line_pct"])
    R["gap_urban_rural_2024"] = [
        {"area": "urban" if u == 1 else "rural", "persons_pct_of_sample": round(100 * g["size"].sum() / df["size"].sum(), 1),
         "below_sm_one_national_line_pct": below("actual", g), "below_sm_regional_line_pct": below("regional", g),
         **{t: round(100 * E.share(c.loc[g.index, "tier"] == t, g), 1) for t in E.TIERS}} for u, g in df.groupby("urban")]
    # RU: сколько людей меняют статус «ниже ПМ» при переходе от единой черты к региональной.
    # EN: how many people change "below SM" status when moving from one national line to regional lines.
    a_, r_ = by_mode["actual"], by_mode["regional"]
    pa, pr = a_["pc_income"] < a_["sm"] - E.EPS, r_["pc_income"] < r_["sm"] - E.EPS
    R["regional_line_reclassification_2024"] = {
        "become_poor_pct": round(100 * E.share(~pa & pr, df), 2),
        "stop_being_poor_pct": round(100 * E.share(pa & ~pr, df), 2)}
    R["uncertainty_2024"] = E.bootstrap(df, lambda d: {
        "poverty_rate_sm_pct": E.summary(d, 2024)["poverty_rate_sm_pct"],
        "tsa_eligible_pct": E.summary(d, 2024)["tiers_pct"]["A_tsa_eligible"],
        "hidden_vulnerable_pct": E.summary(d, 2024)["tiers_pct"]["C_hidden_vulnerable"]}, B=200)

    # ---- 1b. Шкала эквивалентности БНС / the BNS equivalence scale (v0.3) -----------------
    # RU: проверка чувствительности: что меняется, если считать доход не на человека, а на
    #     эквивалентного члена семьи (1 + 0,8 на каждого следующего).
    # EN: a sensitivity test: what changes if income is measured per equivalent member
    #     (1 + 0.8 per additional member) instead of per person.
    eq = E.equivalence_test(df, 2024, "n_child_group")
    R["equivalence_2024"] = {
        **{k: v for k, v in eq.items() if k != "by_group"},
        "by_children": eq["by_group"],
        "by_size": E.equivalence_test(df, 2024, "size_group")["by_group"],
        "by_type": E.equivalence_test(df, 2024, "hh_type")["by_group"],
        "by_elderly": E.equivalence_test(df, 2024, "n_elderly_group")["by_group"],
        "by_region": E.equivalence_test(df, 2024, "region")["by_group"],
        "by_urban": [{"area": "urban" if r["urban"] == "1" else "rural", **{k: v for k, v in r.items() if k != "urban"}}
                     for r in E.equivalence_test(df, 2024, "urban")["by_group"]],
    }
    R["equivalence_by_year"] = [{k: v for k, v in E.equivalence_test(by_year[y], y, None).items()} for y in years]

    # ---- 2. Policy Simulator: что если изменить правило / what if a rule changes ----------
    P_now = E.Policy("tsa", line_share=0.70, label="TSA top-up to 70% SM (pre-2025 rule)")
    P_2025 = E.Policy("tsa_median", label="TSA top-up to max(35% median, 70% SM) (2025 rule)")
    P_full = E.Policy("tsa", line_share=1.00, label="TSA top-up to 100% SM")
    R["policy_2024"] = [E.scenario(df, 2024, p) for p in (P_now, P_2025, P_full)]

    # ---- 3. Shock Simulator: что если изменятся условия / what if conditions change --------
    shocks = [E.Shock("wages", 0.10), E.Shock("earner_loss", 3), E.Shock("utilities", 0.30), E.Shock("prices", 0.10)]
    R["shock_2024"] = [E.scenario(df, 2024, None, s) for s in shocks]

    # ---- 4. Policy Comparison: при равном бюджете / at equal budget ------------------------
    budget = R["policy_2024"][2]["cost"]["per_capita_tenge_year"]   # RU: бюджет меры «до 100% ПМ» / EN: budget of "to 100% SM"
    # RU: АСП при полном и при 60%-м охвате, пособие на каждого ребёнка, пособие многодетным.
    # EN: TSA at full and at 60% take-up, an allowance for every child, an allowance for large families.
    cands = [E.Policy("tsa"), E.Policy("tsa", takeup=0.6), E.Policy("child_allowance", min_children=1),
             E.Policy("child_allowance", min_children=4)]
    R["compare_equal_budget_2024"] = E.compare(df, 2024, cands, equal_cost_per_capita=budget)
    R["compare_equal_budget_after_shock_2024"] = E.compare(df, 2024, cands, shock=E.Shock("wages", 0.10),
                                                           equal_cost_per_capita=budget)

    (out / "results.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=float), encoding="utf-8")
    c.join(df[["hh_id", "hh_type", "region", "urban", "size", "n_child"]]).to_csv(out / "households_classified_2024.csv", index=False)
    print("saved ->", out / "results.json")


if __name__ == "__main__":
    main()
