"""
Qamqor AI — слой инструментов для языковой модели / the tool layer for the language model.

RU: Языковая модель ничего не считает сама. Она выбирает инструмент из TOOLS, передаёт
    параметры, получает от call() готовый JSON с цифрами и объясняет его человеку.
    TOOLS записаны в формате «function calling», который понимают Claude, GPT и др.
EN: The language model computes nothing itself. It picks a tool from TOOLS, passes
    parameters, gets ready JSON numbers back from call(), and explains them to a person.
    TOOLS use the "function calling" format understood by Claude, GPT and others.

Пример / Example:
    import tools
    tools.load("out/households.csv")
    tools.call("simulate", {"year": 2024, "policy": {"kind": "tsa", "line_share": 1.0}})
"""
from __future__ import annotations

import pandas as pd

import engine as E

_DATA: pd.DataFrame | None = None

_POLICY = {
    "type": "object",
    "description": "A support measure. Omit for no policy change.",
    "properties": {
        "kind": {"type": "string", "enum": ["tsa", "tsa_median", "child_allowance", "none"],
                 "description": "tsa: top-up to line_share x subsistence minimum; tsa_median: the 2025 rule, "
                                "max(median_share x median income, floor_share x subsistence minimum); "
                                "child_allowance: amount tenge per month per child."},
        "line_share": {"type": "number", "description": "For tsa. 0.7 = the pre-2025 rule, 1.0 = the full subsistence minimum."},
        "median_share": {"type": "number"}, "floor_share": {"type": "number"},
        "amount": {"type": "number", "description": "For child_allowance: tenge per month per child."},
        "min_children": {"type": "integer", "description": "For child_allowance: only families with at least this many children."},
        "takeup": {"type": "number", "description": "Share of eligible households that claim, 0..1. Default 1."},
    },
    "required": ["kind"],
}
_SHOCK = {
    "type": "object",
    "description": "A change in economic conditions. Omit for no shock.",
    "properties": {
        "kind": {"type": "string", "enum": ["wages", "earner_loss", "utilities", "prices", "none"],
                 "description": "wages: labour income falls by size; earner_loss: main earner loses size months of "
                                "earnings; utilities: housing and utility costs rise by size; prices: general price rise by size."},
        "size": {"type": "number", "description": "0.10 means 10%; for earner_loss it is the number of months."},
    },
    "required": ["kind", "size"],
}
_YEAR = {"type": "integer", "enum": [2022, 2023, 2024],
         "description": "Survey year. Default 2024. Regional subsistence minimums are available for all three years."}
_GROUP = {"type": "string", "enum": ["hh_type", "region", "urban", "n_child"],
          "description": "How to break the result down. Default hh_type. Use region to compare regions and the cities "
                         "of Astana, Almaty and Shymkent; urban splits towns from villages."}
_LINE = {"type": "string", "enum": ["regional", "actual", "budget"],
         "description": "Which subsistence minimum is the poverty line. regional (default): the actual minimum of the "
                        "household's own region; actual: one national actual minimum; budget: the budget-law minimum."}
_REGION = {"type": "string", "enum": sorted(E.REGION_NAMES.values()),
           "description": "Region or city where the household lives. Sets the regional subsistence minimum."}

_STRESS = {"type": "string", "enum": ["weak", "base", "strong"],
           "description": "Strength of the four stress tests. base (default): main earner 3 months without earnings "
                          "(employees keep 45%, self-employed nothing), cost of living +10%, housing and utilities +30%, "
                          "one more dependant. weak: 2 months, +5%, +15%, a dependant for half a year. "
                          "strong: 6 months, +15%, +50%, two more dependants."}

_LEVELS = ("the A-E income map: A above the subsistence minimum and passing all four stress tests, B failing one test, "
           "C failing two or more, D below the subsistence minimum but not below the TSA line, E below the TSA line "
           "(income-eligible for TSA). A is the most resilient level, E the lowest income")

TOOLS = [
    {
        "name": "gap_overview",
        "description": "Who is missed by the official poverty definition. Returns shares of people on " + _LEVELS + "; "
                       "optionally by household type or region, plus which tests levels B and C fail. Always includes "
                       "three_lines: the share of people below the TSA line, the budget-law minimum and the regional "
                       "minimum, and the uncovered band between the first and the third. Set equivalence_scale to true "
                       "to add a sensitivity test with the Bureau's equivalence scale (first member 1, each further 0.8). "
                       "Set profile to true to add the profile of levels B and C: children, earners, regions, and which "
                       "shock brings each level below the minimum.",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "group_by": _GROUP, "line_mode": _LINE, "stress_version": _STRESS,
            "equivalence_scale": {"type": "boolean", "description": "Add the equivalence-scale sensitivity test. Default false."},
            "profile": {"type": "boolean", "description": "Add the profile of levels B and C. Default false."}}},
    },
    {
        "name": "simulate",
        "description": "Static what-if. Applies an optional shock, then an optional policy, and compares poverty, "
                       "levels A-E, inequality, cost and beneficiaries with the baseline. Use for questions like "
                       "'what if the TSA threshold is raised' or 'what if utility tariffs rise 30%'.",
        "input_schema": {"type": "object", "properties": {"year": _YEAR, "policy": _POLICY, "shock": _SHOCK,
                                                          "group_by": _GROUP, "line_mode": _LINE, "stress_version": _STRESS}},
    },
    {
        "name": "compare_policies",
        "description": "Runs several policies side by side, optionally after a shock. If equal_budget is true, each "
                       "policy is first tuned to cost the same as the first one, so the comparison is fair. With a shock "
                       "and equal_budget, set focus_levels_b_c to true to also get the result for levels B and C: what "
                       "share of them ends up below the subsistence minimum after the shock with each policy, and what "
                       "part of each policy's spending reaches them.",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "policies": {"type": "array", "items": _POLICY, "minItems": 2},
            "shock": _SHOCK, "equal_budget": {"type": "boolean"}, "line_mode": _LINE, "stress_version": _STRESS,
            "focus_levels_b_c": {"type": "boolean", "description": "Add the result for levels B and C. Needs shock and equal_budget."}},
            "required": ["policies"]},
    },
    {
        "name": "check_household",
        "description": "Citizen side. Profiles one household from a description: income per person, its level on "
                       + _LEVELS + ", the list of failed stress tests, TSA income eligibility and top-up, margin above "
                       "the subsistence minimum of its region, drivers.",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "region": _REGION, "stress_version": _STRESS,
            "members": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
                "age": {"type": "number"}, "labor_month": {"type": "number"},
                "self_employed": {"type": "boolean", "description": "True if labor_month is self-employment income. "
                                  "An employee keeps 45% of earnings in the main-earner test, a self-employed person nothing."},
                "pension_month": {"type": "number"}, "other_month": {"type": "number"}}, "required": ["age"]}},
            "utilities_month": {"type": "number", "description": "Housing and utility costs, tenge per month."}},
            "required": ["members"]},
    },
]

CAVEATS = [
    "Synthetic data without survey weights: shares are shares of the sample. Use them for relative and methodological "
    "statements only; do not turn them into numbers of people or money for the country.",
    "Regional subsistence minimums are the Bureau of National Statistics annual values for 2022-2024; the 2022 regional values are rebuilt from monthly data with the Bureau's method.",
    "Levels A-E: A is the most resilient, E is below the TSA line. In versions before 0.3 the letters ran the other way.",
    "The main earner's employment type is not in the household table: the wage share of the household's labour income is used to apply the 45% replacement.",
    "Static model: no behavioural response; full take-up unless stated.",
    "Income-based poverty; official statistics use consumption.",
]
# RU: оговорки для check_household: про выборку там говорить нечего. EN: caveats for check_household: nothing about the sample applies.
HOUSEHOLD_CAVEATS = [
    "Levels A-E: A is the most resilient, E is below the TSA line.",
    "Static estimate from stated income; TSA also has non-income conditions not modelled here.",
    "Income-based poverty; official statistics use consumption.",
]


def load(path: str = "out/households.csv") -> None:
    """RU: загрузить таблицу домохозяйств один раз. EN: load the household table once."""
    global _DATA
    _DATA = pd.read_csv(path, dtype={"hh_id": str, "region": str})


def _year_df(year: int) -> pd.DataFrame:
    if _DATA is None:
        load()
    return _DATA[_DATA["year"] == year].reset_index(drop=True)


def _policy(d):
    return E.Policy(**d) if d else None


def _shock(d):
    return E.Shock(**d) if d else None


def _clean(x):
    """RU: приводит числа numpy к обычным, чтобы JSON был чистым. EN: turns numpy numbers into plain ones for clean JSON."""
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (bool, str)) or x is None:
        return x
    if hasattr(x, "item"):
        return x.item()
    return x


def call(name: str, args: dict | None = None) -> dict:
    """RU: выполнить инструмент и вернуть JSON. EN: run a tool and return JSON."""
    a = dict(args or {})
    year = int(a.get("year", 2024))
    previous = E.LINE_MODE
    if a.get("line_mode"):
        E.set_line_mode(a["line_mode"])
    try:
        return _run(name, a, year)
    finally:
        E.set_line_mode(previous)


def _run(name: str, a: dict, year: int) -> dict:
    st = E.stress_tests(a.get("stress_version", "base"))
    if name == "check_household":
        out = E.check_household(a["members"], a.get("utilities_month", 0.0), year, st=st, region=a.get("region"))
        return {"result": _clean(out), "caveats": HOUSEHOLD_CAVEATS}
    df = _year_df(year)
    if name == "gap_overview":
        g = a.get("group_by", "hh_type")
        c = E.classify(df, year, st)
        rows = []
        for key, part in df.groupby(g):
            t = c.loc[part.index, "tier"]
            label = E.REGION_NAMES.get(str(key), str(key)) if g == "region" else str(key)
            rows.append({g: label, "persons_pct_of_sample": round(100 * part["size"].sum() / df["size"].sum(), 1),
                         **{k: round(100 * E.share(t == k, part), 1) for k in E.TIERS}})
        # RU: какие тесты не проходят уровни B и C и какие у них структурные причины.
        # EN: which tests levels B and C fail and what their structural drivers are.
        R = c[c["tier"].isin(E.AT_RISK)]
        labels = E.test_labels(st)
        why = {labels.get(k, k): round(100 * E.share(R[k], df.loc[R.index]), 1)
               for k in R.columns if k.startswith(("fail_", "drv_"))}
        out = {"overall": E.summary(df, year, st), "stress_tests": labels, "three_lines": E.three_lines(df, year),
               "by_group": rows, "why_levels_b_c_pct": why}
        if a.get("profile"):
            out["levels_b_c_profile"] = E.at_risk_profile(df, year, st)
        if a.get("equivalence_scale"):
            # RU: проверка чувствительности, всегда на региональной черте. EN: a sensitivity test, always on the regional line.
            out["equivalence_scale"] = E.equivalence_test(df, year, g)
            out["equivalence_scale"]["note"] = ("Sensitivity test. TSA is per-capita by law, so say 'would be reclassified under "
                                                "the Bureau's scale', not 'misclassified'. 'Same line' lowers poverty by "
                                                "construction; 'same headcount' shows who changes places.")
    elif name == "simulate":
        out = E.scenario(df, year, _policy(a.get("policy")), _shock(a.get("shock")), st=st,
                         group_by=a.get("group_by", "hh_type"))
    elif name == "compare_policies":
        pols = [_policy(p) for p in a["policies"]]
        shock = _shock(a.get("shock"))
        budget = None
        if a.get("equal_budget"):
            budget = E.scenario(df, year, pols[0], shock, st=st, group_by=None)["cost"]["per_capita_tenge_year"]
        out = E.compare(df, year, pols, shock, equal_cost_per_capita=budget, st=st)
        if a.get("focus_levels_b_c") and shock is not None and budget is not None:
            out["levels_b_c"] = E.compare_for_group(df, year, pols, shock, budget, st)
    else:
        raise ValueError(f"unknown tool: {name}")
    return {"result": _clean(out), "caveats": CAVEATS}
