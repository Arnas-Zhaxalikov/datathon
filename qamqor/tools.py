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

TOOLS = [
    {
        "name": "gap_overview",
        "description": "Who is missed by the official poverty definition. Returns shares of people in four tiers: "
                       "A income-eligible for TSA, B below the subsistence minimum but not TSA-eligible, "
                       "C hidden vulnerable (above the minimum but failing a stress test), D resilient; "
                       "optionally by household type or region, plus the reasons tier C is vulnerable. Always includes "
                       "three_lines: the share of people below the TSA line, the budget-law minimum and the regional "
                       "minimum, and the uncovered band between the first and the third. Set equivalence_scale to true "
                       "to add a sensitivity test with the Bureau's equivalence scale (first member 1, each further 0.8).",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "group_by": _GROUP, "line_mode": _LINE,
            "equivalence_scale": {"type": "boolean", "description": "Add the equivalence-scale sensitivity test. Default false."}}},
    },
    {
        "name": "simulate",
        "description": "Static what-if. Applies an optional shock, then an optional policy, and compares poverty, "
                       "tiers, inequality, cost and beneficiaries with the baseline. Use for questions like "
                       "'what if the TSA threshold is raised' or 'what if utility tariffs rise 30%'.",
        "input_schema": {"type": "object", "properties": {"year": _YEAR, "policy": _POLICY, "shock": _SHOCK,
                                                          "group_by": _GROUP, "line_mode": _LINE}},
    },
    {
        "name": "compare_policies",
        "description": "Runs several policies side by side, optionally after a shock. If equal_budget is true, each "
                       "policy is first tuned to cost the same as the first one, so the comparison is fair.",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "policies": {"type": "array", "items": _POLICY, "minItems": 2},
            "shock": _SHOCK, "equal_budget": {"type": "boolean"}, "line_mode": _LINE}, "required": ["policies"]},
    },
    {
        "name": "check_household",
        "description": "Citizen side. Profiles one household from a description: income per person, TSA income "
                       "eligibility and top-up, margin above the subsistence minimum of its region, stress tests, drivers.",
        "input_schema": {"type": "object", "properties": {
            "year": _YEAR, "region": _REGION,
            "members": {"type": "array", "minItems": 1, "items": {"type": "object", "properties": {
                "age": {"type": "number"}, "labor_month": {"type": "number"},
                "pension_month": {"type": "number"}, "other_month": {"type": "number"}}, "required": ["age"]}},
            "utilities_month": {"type": "number", "description": "Housing and utility costs, tenge per month."}},
            "required": ["members"]},
    },
]

CAVEATS = [
    "Synthetic data: figures are illustrative, not official estimates.",
    "Regional subsistence minimums are the Bureau of National Statistics annual values for 2022-2024; the 2022 regional values are rebuilt from monthly data with the Bureau's method.",
    "No survey weights: shares are shares of the sample.",
    "Static model: no behavioural response; full take-up unless stated.",
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
    if name == "check_household":
        out = E.check_household(a["members"], a.get("utilities_month", 0.0), year, region=a.get("region"))
        return {"result": _clean(out), "caveats": CAVEATS[3:]}
    df = _year_df(year)
    if name == "gap_overview":
        g = a.get("group_by", "hh_type")
        c = E.classify(df, year)
        rows = []
        for key, part in df.groupby(g):
            t = c.loc[part.index, "tier"]
            label = E.REGION_NAMES.get(str(key), str(key)) if g == "region" else str(key)
            rows.append({g: label, "persons_pct_of_sample": round(100 * part["size"].sum() / df["size"].sum(), 1),
                         **{k: round(100 * E.share(t == k, part), 1) for k in E.TIERS}})
        C = c[c["tier"] == "C_hidden_vulnerable"]
        why = {k: round(100 * E.share(C[k], df.loc[C.index]), 1) for k in C.columns if k.startswith(("fail_", "drv_"))}
        out = {"overall": E.summary(df, year), "three_lines": E.three_lines(df, year),
               "by_group": rows, "why_hidden_vulnerable_pct": why}
        if a.get("equivalence_scale"):
            # RU: проверка чувствительности, всегда на региональной черте. EN: a sensitivity test, always on the regional line.
            out["equivalence_scale"] = E.equivalence_test(df, year, g)
            out["equivalence_scale"]["note"] = ("Sensitivity test. TSA is per-capita by law, so say 'would be reclassified under "
                                                "the Bureau's scale', not 'misclassified'. 'Same line' lowers poverty by "
                                                "construction; 'same headcount' shows who changes places.")
    elif name == "simulate":
        out = E.scenario(df, year, _policy(a.get("policy")), _shock(a.get("shock")), group_by=a.get("group_by", "hh_type"))
    elif name == "compare_policies":
        pols = [_policy(p) for p in a["policies"]]
        shock = _shock(a.get("shock"))
        budget = None
        if a.get("equal_budget"):
            budget = E.scenario(df, year, pols[0], shock, group_by=None)["cost"]["per_capita_tenge_year"]
        out = E.compare(df, year, pols, shock, equal_cost_per_capita=budget)
    else:
        raise ValueError(f"unknown tool: {name}")
    return {"result": _clean(out), "caveats": CAVEATS}
