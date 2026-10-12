"""Мост между веб-приложением и расчётным ядром Qamqor (папка qamqor/ в корне репозитория).

Здесь нет ни одной формулы статуса или стресс-теста: всё считают qamqor/engine.py и
инструменты qamqor/tools.py. Этот модуль только
  - переводит анкету из формы «Моя семья» в описание семьи, которое понимает
    engine.check_household (и показывает, какие допущения для этого понадобились);
  - раскладывает ответы ядра в тот вид, который рисует интерфейс.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QAMQOR = ROOT / "qamqor"
sys.path.insert(0, str(QAMQOR))

import engine as E  # noqa: E402  (qamqor/engine.py)
import tools as T  # noqa: E402   (qamqor/tools.py)

T.load(str(QAMQOR / "out" / "households.csv"))

YEAR = 2024
PEERS_MIN_HOUSEHOLDS = 30  # меньше — сравнение с выборкой не показывается

# Допущения для полей, которые человек не заполнил. Показываются на экране.
WAGE_SHARE_ASSUMPTION = 0.66      # доля трудового дохода в доходе семьи
HOUSING_SHARE_ASSUMPTION = 0.125  # жильё и коммунальные как доля дохода семьи

# цвет уровня в интерфейсе; B и C различаются буквой, а не цветом
LEVEL_STATUS = {"A": "good", "B": "warning", "C": "warning", "D": "serious", "E": "critical"}

REGION_CODE = {name: code for code, name in E.REGION_NAMES.items()}


class InputError(ValueError):
    """Некорректный ввод. code — ключ сообщения, текст подставляет интерфейс."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def regions() -> list[dict]:
    return [
        {"code": int(code), "name": name, "sm": E.REGIONAL_SM[YEAR][code],
         "asp": round(E.TSA_SHARE * E.REGIONAL_SM[YEAR][code])}
        for code, name in sorted(E.REGION_NAMES.items())
    ]


def prediction() -> dict | None:
    """Эксперимент H4 (qamqor/poverty_challenge.py): готовые числа из его summary.json, без пересчёта."""
    path = QAMQOR / "results" / "poverty_challenge" / "summary.json"
    if not path.exists():
        return None
    s = json.loads(path.read_text(encoding="utf-8"))
    a = s["feature_sets"]["A"]
    return {
        "test_year": s["test_year"], "train_years": s["train_years"],
        "simple": a["best_simple"], "complex": a["best_complex"],
        "auc_simple": a["simple_metrics"]["auc"], "auc_complex": a["complex_metrics"]["auc"],
        "recall_top20": a["simple_metrics"]["recall_at_20_pct"],
        "auc_diff": a["complex_minus_simple"]["auc_diff"], "auc_diff_ci95": a["complex_minus_simple"]["auc_diff_ci95"],
        "rules": [{"min_children": int(name[0]), "flagged_pct": r["people_flagged_pct"], "rule_recall_pct": r["rule_recall_pct"],
                   "model_recall_pct": r["model_recall_pct"]} for name, r in a["model_vs_rules_same_share"].items()],
        "h4a": a["H4a"], "h4b": a["H4b"], "h4": a["H4"],
    }


def summary() -> dict:
    """Обзор по стране: инструмент gap_overview с разбивкой по регионам."""
    g = T.call("gap_overview", {"year": YEAR, "group_by": "region"})
    r = g["result"]
    overall = r["overall"]
    # доли «ниже минимума» и «B и C» по регионам берутся готовыми из инструмента simulate
    # (без шока и меры это база): складывать округлённые доли уровней самим нельзя
    base = {row["region"]: row for row in T.call("simulate", {"year": YEAR, "group_by": "region"})["result"]["by_group"]}
    by_region = []
    for row in r["by_group"]:
        code = REGION_CODE[row["region"]]
        by_region.append({
            "code": int(code),
            "name": row["region"],
            "sm": E.REGIONAL_SM[YEAR][code],
            "persons_pct_of_sample": row["persons_pct_of_sample"],
            "levels": {E.level(t): row[t] for t in E.TIERS},
            "pct_below_sm": base[row["region"]]["poor_baseline_pct"],
            "pct_at_risk": base[row["region"]]["at_risk_after_policy_pct"],
        })
    return {
        "year": YEAR,
        "persons_in_sample": overall["persons_in_sample"],
        "households_in_sample": overall["households_in_sample"],
        "sm_min": min(E.REGIONAL_SM[YEAR].values()),
        "sm_max": max(E.REGIONAL_SM[YEAR].values()),
        "pct_below_sm": overall["poverty_rate_sm_pct"],
        "pct_at_risk": overall["at_risk_pct"],
        "levels": {E.level(t): {"pct": overall["tiers_pct"][t], "status": LEVEL_STATUS[E.level(t)]} for t in E.TIERS},
        "three_lines": r["three_lines"],
        "stress_tests": r["stress_tests"],
        "by_region": by_region,
        "prediction": prediction(),
    }


def _members(*, hh_size, n_child, n_employed, income, wage, labor_total, self_employed) -> list[dict]:
    """Описание семьи для engine.check_household.

    Результат ядра зависит от размера семьи, общего дохода, заработка и типа занятости
    главного кормильца; остальной доход записывается первому взрослому как «прочий».
    """
    adults = max(hh_size - n_child, 1)
    members = [{"age": 35.0} for _ in range(adults)] + [{"age": 8.0} for _ in range(hh_size - adults)]
    other_workers = max(min(n_employed, hh_size) - 1, 0)
    rest_labor = max(labor_total - wage, 0.0)
    if n_employed > 0:
        members[0].update(labor_month=wage, self_employed=bool(self_employed))
        for i in range(1, 1 + other_workers):
            # заработок остальных работающих не должен превышать заработок главного кормильца
            members[i]["labor_month"] = min(rest_labor / other_workers, wage)
    assigned = sum(m.get("labor_month", 0.0) for m in members)
    members[0]["other_month"] = max(income - assigned, 0.0)
    return members


def _check(members, housing, region, st) -> dict:
    return E.check_household(members, housing, YEAR, st=st, region=str(region))


def _peers(region: int, n_child: int) -> dict | None:
    """Доля людей ниже минимума среди семей с тем же числом детей в регионе (выборка 2024)."""
    df = T._year_df(YEAR)
    sub = df[(df["region"] == str(region)) & (df["n_child"] == n_child)]
    if len(sub) < PEERS_MIN_HOUSEHOLDS:
        return None
    below = E.per_capita(sub) < E.sm(sub, YEAR) - E.EPS
    return {"households": int(len(sub)), "n_child": n_child, "pct_below_sm": round(100 * E.share(below, sub), 1)}


def classify_household(
    *,
    hh_size: int,
    n_child: int,
    n_employed: int,
    income_monthly: float,
    region: int,
    earner_wage: float | None = None,
    earner_self_employed: bool = False,
    transfers: float | None = None,
    housing_cost: float | None = None,
    months_without_wage: float = 3,
    cost_of_living_pct: float = 10,
    housing_rise_pct: float = 30,
    whatif_extra_wage: float = 0,
    whatif_child_allowance: float = 0,
) -> dict:
    if str(region) not in E.REGION_NAMES:
        raise InputError("err_region")
    if hh_size < 1 or income_monthly < 0:
        raise InputError("err_values")
    if n_child < 0 or n_employed < 0 or n_child > hh_size or n_employed > hh_size:
        raise InputError("err_members")
    if any(v is not None and v < 0 for v in (earner_wage, transfers, housing_cost)):
        raise InputError("err_values")
    if (earner_wage or 0) + (transfers or 0) > income_monthly:
        raise InputError("err_amounts")
    if not (0 <= months_without_wage <= 12 and 0 <= cost_of_living_pct <= 100 and housing_rise_pct >= 0
            and whatif_extra_wage >= 0 and whatif_child_allowance >= 0):
        raise InputError("err_values")

    # ---- допущения для пустых полей -------------------------------------------------------
    assumptions = []
    labor_total = income_monthly - transfers if transfers is not None else income_monthly * WAGE_SHARE_ASSUMPTION
    if n_employed == 0 and earner_wage is None:
        wage = 0.0
        assumptions.append({"field": "earner_wage", "basis": "no_workers", "value": 0})
    elif earner_wage is None:
        wage = labor_total / n_employed
        assumptions.append({
            "field": "earner_wage",
            "basis": "minus_transfers" if transfers is not None else "wage_share",
            "value": round(wage), "share_pct": round(WAGE_SHARE_ASSUMPTION * 100), "workers": n_employed,
        })
    else:
        wage = float(earner_wage)
    if housing_cost is None:
        housing = income_monthly * HOUSING_SHARE_ASSUMPTION
        assumptions.append({"field": "housing_cost", "basis": "income_share", "value": round(housing),
                            "share_pct": HOUSING_SHARE_ASSUMPTION * 100})
    else:
        housing = float(housing_cost)

    st = E.StressTests(
        main_earner_months_lost=months_without_wage,
        cost_of_living_rise=cost_of_living_pct / 100.0,
        utilities_rise=housing_rise_pct / 100.0,
    )
    family = dict(hh_size=hh_size, n_child=n_child, n_employed=max(n_employed, 1 if wage > 0 else 0),
                  income=income_monthly, wage=wage, labor_total=max(labor_total, wage),
                  self_employed=earner_self_employed)
    res = _check(_members(**family), housing, region, st)

    level = res["level"]
    sm, asp, pc = res["subsistence_minimum"], res["tsa_line"], res["income_per_capita_month"]
    above = pc >= sm
    tests = [{"key": t["key"], "income_pc": t["income_per_capita_month"], "failed": t["failed"],
              # предупреждение — только если тест опускает ниже минимума семью, которая была выше
              "crosses": bool(t["failed"] and above)} for t in res["tests"]]
    worst = min(tests, key=lambda t: t["income_pc"])
    margin = res["margin_above_sm_month_per_capita"]
    if level == "E":
        outcome = {"topup_family": res["tsa_topup_month_whole_family"]}
    elif level == "D":
        outcome = {"gap_pc": -margin, "gap_family": -margin * hh_size, "above_asp_pc": pc - asp}
    else:
        outcome = {"margin_pc": margin, "margin_family": margin * hh_size,
                   "failing": [t["key"] for t in tests if t["failed"]]}

    # ---- а что, если: та же семья с добавкой к доходу --------------------------------------
    what_if = None
    added = whatif_extra_wage + whatif_child_allowance * n_child
    if added > 0:
        extra = dict(family, income=income_monthly + added, labor_total=family["labor_total"] + whatif_extra_wage,
                     n_employed=min(family["n_employed"] + (1 if whatif_extra_wage > 0 else 0), hh_size))
        after = _check(_members(**extra), housing, region, st)
        what_if = {"added_wage": round(whatif_extra_wage), "added_allowance": round(whatif_child_allowance * n_child),
                   "income_pc": after["income_per_capita_month"], "level": after["level"],
                   "status": LEVEL_STATUS[after["level"]]}

    return {
        "year": YEAR,
        "region": {"code": int(region), "name": res["region"]},
        "sm": sm,
        "asp": asp,
        "level": level,
        "status": LEVEL_STATUS[level],
        "hh_size": hh_size,
        "n_child": n_child,
        "income_monthly": res["inputs"]["income_month"],
        "income_pc": pc,
        "pct_of_sm": round(100 * pc / sm, 1),
        "earner_wage": res["inputs"]["main_earner_labor_month"],
        "earner_keeps_pct": res["inputs"]["main_earner_keeps_pct"],
        "housing_cost": res["inputs"]["utilities_month"],
        "assumptions": assumptions,
        "stress": {"months": months_without_wage, "cost_of_living_pct": cost_of_living_pct,
                   "housing_rise_pct": housing_rise_pct},
        "tests": tests,
        "worst": {"key": worst["key"], "income_pc": worst["income_pc"]},
        "outcome": outcome,
        "what_if": what_if,
        "peers": _peers(int(region), n_child),
    }
