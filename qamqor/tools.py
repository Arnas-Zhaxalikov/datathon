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

RU: Пятый инструмент, explain, ничего не считает: он читает граф правил и происхождения цифр
    (results/graph.json, собирается скриптом build_graph.py) и отвечает, откуда взято число,
    по какому правилу оно получено и какие у него оговорки.
EN: The fifth tool, explain, computes nothing: it reads the graph of rules and provenance
    (results/graph.json, built by build_graph.py) and answers where a number comes from, by
    which rule it was obtained and which caveats apply.

    tools.call("explain", {"node": "threshold:tsa_line_70pct"})
    tools.call("explain", {"node": "sm:2024:Astana city", "depth": 2})
    tools.call("explain", {"node": "Astana", "year": 2023})   # часть названия / part of a name
"""
from __future__ import annotations

import difflib
import json
from pathlib import Path

import pandas as pd

import engine as E

_DATA: pd.DataFrame | None = None
_GRAPH: dict | None = None
GRAPH_PATH = Path(__file__).resolve().parent / "results" / "graph.json"

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
    {
        "name": "explain",
        "description": "Where a number comes from and which rule produced it. Reads the graph of rules and provenance; "
                       "computes nothing. Returns the node (label, value, unit, year), its neighbours by relation "
                       "(has_sm, defines, decides, moves, has_metric, computed_from, limited_by, changes), the path to "
                       "the data forms, the sources (data form, results.json key, verify.py check) and the caveats. "
                       "Node ids: 'metric:poverty_rate_sm_2024', 'threshold:tsa_line_70pct', 'threshold:regional_sm', "
                       "'threshold:budget_sm', 'sm:2024:Astana city', 'region:Turkestan', 'tier:E_below_tsa_line', "
                       "'stress:earner_loss', 'policy:tsa_topup', 'policy:child_allowance', 'form:D-004', "
                       "'caveat:no_weights'. A part of a name also works; if nothing matches, close ids are suggested. "
                       "Use for 'where does this figure come from' and, after check_household, for 'why is this "
                       "household not eligible': explain the TSA line and the subsistence minimum of its region.",
        "input_schema": {"type": "object", "properties": {
            "node": {"type": "string", "description": "Node id or a part of its id or label, case-insensitive."},
            "depth": {"type": "integer", "enum": [1, 2], "description": "1 (default): direct neighbours; 2: also their neighbours."},
            "year": {"type": "integer", "enum": [2022, 2023, 2024],
                     "description": "Optional. Prefers nodes of this year and hides neighbours of other years."}},
            "required": ["node"]},
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


def load_graph(path: str | Path | None = None) -> None:
    """RU: загрузить граф один раз. EN: load the graph once."""
    global _GRAPH
    path = Path(path) if path else GRAPH_PATH
    if not path.exists():
        raise FileNotFoundError("graph.json not built, run build_graph.py")
    raw = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in raw["nodes"]}
    out, into = {i: [] for i in nodes}, {i: [] for i in nodes}
    for e in raw["edges"]:
        out[e["from"]].append(e)
        into[e["to"]].append(e)
    _GRAPH = {"nodes": nodes, "out": out, "in": into}


# RU: связи, по которым идём от узла к формам данных. EN: the relations followed from a node to the data forms.
_TO_SOURCES = ("has_metric", "computed_from", "changes", "moves", "decides")


def _find(nodes: dict, query: str, year: int | None) -> tuple[dict | None, list[str]]:
    """RU: узел по id или части названия; иначе до 5 похожих id. EN: a node by id or part of a name; else up to 5 close ids."""
    q = " ".join(str(query).lower().split())
    by_id = {i.lower(): n for i, n in nodes.items()}
    if q in by_id:
        return by_id[q], []
    hits = [n for n in nodes.values() if q and (q in n["id"].lower() or q in n["label"].lower())]
    if year is not None and any(n["year"] == year for n in hits):
        hits = [n for n in hits if n["year"] == year]
    if hits:
        # RU: сначала совпадение по id, потом самый короткий id. EN: id matches first, then the shortest id.
        hits.sort(key=lambda n: (q not in n["id"].lower(), len(n["id"]), n["id"]))
        return hits[0], [n["id"] for n in hits[1:6]]
    names = {**{n["label"].lower(): i for i, n in nodes.items()}, **{i.lower(): i for i in nodes},
             **{i.lower().split(":", 1)[1]: i for i in nodes}}
    close = difflib.get_close_matches(q, list(names), n=10, cutoff=0.4)
    return None, list(dict.fromkeys(names[c] for c in close))[:5]


def _explain(a: dict) -> dict:
    if _GRAPH is None:
        try:
            load_graph()
        except FileNotFoundError as e:
            return {"error": str(e)}
    nodes, out, into = _GRAPH["nodes"], _GRAPH["out"], _GRAPH["in"]
    year = int(a["year"]) if a.get("year") else None
    depth = 2 if int(a.get("depth") or 1) >= 2 else 1
    node, other = _find(nodes, a.get("node", ""), year)
    if node is None:
        return {"error": f"node not found: {a.get('node')!r}", "suggestions": other,
                "hint": "Call explain again with one of the suggested ids, or with a type prefix such as "
                        "metric:, threshold:, sm:, region:, tier:, stress:, policy:, form:, caveat:."}
    brief = lambda n: {k: n[k] for k in ("id", "type", "label", "value") if k in n}
    shown = lambda n: year is None or n["year"] in (None, year)

    def around(i):
        return [(e, "out", nodes[e["to"]]) for e in out[i]] + [(e, "in", nodes[e["from"]]) for e in into[i]]

    neighbors, seen = [], {node["id"]}
    layer = [node["id"]]
    for dist in range(1, depth + 1):
        nxt = []
        for i in layer:
            for e, direction, n in around(i):
                if n["id"] in seen or not shown(n):
                    continue
                seen.add(n["id"])
                nxt.append(n["id"])
                row = {"relation": e["relation"], "direction": direction, "node": brief(n)}
                if e.get("note"):
                    row["note"] = e["note"]
                if dist == 2:
                    row.update(distance=2, via=i)
                neighbors.append(row)
        layer = nxt
    # RU: кратчайший путь к формам данных по связям «откуда взято». EN: the shortest path to the data forms along provenance edges.
    parent, queue, forms = {node["id"]: None}, [node["id"]], []
    while queue:
        i = queue.pop(0)
        if nodes[i]["type"] == "data_form":
            forms.append(i)
            continue
        for e in out[i]:
            if e["relation"] in _TO_SOURCES and e["to"] not in parent:
                parent[e["to"]] = (i, e["relation"])
                queue.append(e["to"])
    paths = []
    for f in forms:
        steps, i = [f], f
        while parent[i]:
            i, rel = parent[i]
            steps[:0] = [i, f"-{rel}->"]
        paths.append(steps)
    on_path = [i for i in dict.fromkeys(s for p in paths for s in p[::2])] or [node["id"]]
    sources = []
    for i in on_path:
        n = nodes[i]
        if n["type"] == "data_form":
            sources.append({"data_form": n["id"], "label": n["label"], "note": n["note"]})
        elif n.get("source"):
            sources.append({"node": n["id"], **n["source"], **({"verified_by": n["verified_by"]} if n.get("verified_by") else {})})
    reach = list(dict.fromkeys([node["id"]] + on_path + [r["node"]["id"] for r in neighbors if "distance" not in r]))
    caveats = list(dict.fromkeys(nodes[e["to"]]["label"] for i in reach for e in out[i] if e["relation"] == "limited_by"))
    if node["type"] == "caveat":
        caveats.insert(0, node["label"])
    result = {"node": node, "neighbors": neighbors, "path_to_sources": paths, "sources": sources, "caveats": caveats}
    if other:
        result["other_matches"] = other
    return result


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
    if name == "explain":
        return {"result": _explain(a), "caveats": CAVEATS}
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
