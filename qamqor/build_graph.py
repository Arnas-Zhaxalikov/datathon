"""
Qamqor AI — граф правил и происхождения цифр / the graph of rules and provenance.

RU: Собирает results/graph.json: узлы (регионы, черты, уровни, стресс-тесты, меры, метрики,
    формы данных, оговорки) и связи между ними. Граф ничего не считает и не добавляет новых
    цифр: каждое число взято из results.json, quick_screen.json или CSV прожиточных минимумов,
    и у каждого узла-цифры записано, откуда оно (поле source). Если нужного поля в JSON нет,
    узел пропускается. Языковая модель в сборке не участвует.
EN: Builds results/graph.json: nodes (regions, thresholds, tiers, stress tests, policies,
    metrics, data forms, caveats) and the edges between them. The graph computes nothing and adds
    no new figures: every number is taken from results.json, quick_screen.json or the subsistence
    minimum CSV, and every numeric node records where it came from (the source field). If a field
    is missing in the JSON, the node is skipped. No language model takes part in the build.

Запуск / Run:
    python build_graph.py results/results.json ref/regional_sm_annual_2022_2024.csv results/graph.json
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import engine as E

YEARS = (2022, 2023, 2024)
YEAR = 2024
RESULTS, SCREEN, SM_CSV = "results/results.json", "results/quick_screen.json", "ref/regional_sm_annual_2022_2024.csv"
PCT = "% of people in the sample"
TSA_ID = f"threshold:tsa_line_{round(100 * E.TSA_SHARE)}pct"
LEGAL = "legal check needed: TSA also has non-income conditions and its rule changed in 2025"


def lookup(data, key: str):
    """RU: значение по пути вида a.b[year=2024].c или a[0].b; KeyError, если пути нет.
    EN: the value at a path like a.b[year=2024].c or a[0].b; KeyError if the path is absent."""
    for name, sel in re.findall(r"([^.\[\]]+)|\[([^\]]*)\]", key):
        if name:
            data = data[name]
        elif "=" in sel:
            k, v = sel.split("=", 1)
            data = next(r for r in data if str(r.get(k)) == v)
        else:
            data = data[int(sel)]
    return data


class Graph:
    def __init__(self, files: dict):
        self.files, self.nodes, self.edges = files, {}, []

    def node(self, id, type, label, value=None, unit=None, year=None, note="", source=None, verified_by=None):
        n = {"id": id, "type": type, "label": label, "value": value, "unit": unit, "year": year, "note": note}
        if source:
            n["source"] = source
        if verified_by:
            n["verified_by"] = verified_by
        self.nodes[id] = n
        return id

    def figure(self, id, type, label, file, key, unit=PCT, year=YEAR, note="", verified_by=None):
        """RU: узел-цифра из JSON; нет поля — нет узла. EN: a numeric node from JSON; no field, no node."""
        try:
            value = lookup(self.files[file], key)
        except (KeyError, IndexError, StopIteration, TypeError):
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        note = f"{Path(file).name}: {key}" + (f". {note}" if note else "")
        return self.node(id, type, label, value, unit, year, note, {"file": file, "key": key}, verified_by)

    def edge(self, a, b, relation, note=None):
        """RU: связь добавляется, только если оба узла есть. EN: an edge is added only if both nodes exist."""
        if a in self.nodes and b in self.nodes:
            self.edges.append({"from": a, "to": b, "relation": relation, **({"note": note} if note else {})})


def build(results_path: str, sm_path: str) -> dict:
    files = {RESULTS: json.load(open(results_path, encoding="utf-8"))}
    screen_path = Path(results_path).with_name("quick_screen.json")
    if screen_path.exists():
        files[SCREEN] = json.load(open(screen_path, encoding="utf-8"))
    R = files[RESULTS]
    g = Graph(files)
    y = f"[year={YEAR}]"

    # ---- формы данных и оговорки / data forms and caveats ---------------------------------
    used = "feeds the household-year table (build.py)"
    unused = "not used by the engine"
    for code, label, note in [
        ("D-008", "Form D-008: household roster (members, age)", used),
        ("D-004", "Form D-004: income of each person, housing and utility spending", used),
        ("D-002", "Form D-002", unused), ("D-006", "Form D-006: housing conditions", unused),
        ("T-001", "Form T-001: labour force survey", unused),
        ("D-003", "Form D-003: food spending", "absent from the data set"),
    ]:
        g.node(f"form:{code}", "data_form", label, note=note)
    for key, label in [
        ("synthetic_data", "Synthetic data: figures are illustrative"),
        ("no_weights", "No survey weights: shares are shares of the sample; no national counts or sums"),
        ("no_food_spending", "No food spending (form D-003): no food price shock and no consumption-based poverty"),
        ("income_not_consumption", "Poverty here is measured by money income, not by consumption"),
        ("official_poverty_consumption", "Official poverty statistics are based on consumption, so levels are not comparable"),
        ("repeated_cross_sections", "Repeated cross-sections without a panel: households differ between years"),
        ("unused_forms", "Only forms D-008 and D-004 feed the calculations; D-002, D-006 and T-001 are not linked"),
        ("static_model", "Static model: no behavioural response; full take-up unless stated"),
        ("earner_type_approximated", "The main earner's employment type is approximated by the wage share of the household's labour income"),
        ("regional_sm_source", "Regional subsistence minimums are Bureau of National Statistics annual values; "
                               "the 2022 regional values are rebuilt from monthly data with the Bureau's method"),
    ]:
        g.node(f"caveat:{key}", "caveat", label)
    g.edge("caveat:no_food_spending", "form:D-003", "refers_to")
    for code in ("D-002", "D-006", "T-001"):
        g.edge("caveat:unused_forms", f"form:{code}", "refers_to")

    # ---- регионы и прожиточные минимумы / regions and subsistence minimums ------------------
    with open(sm_path, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["region_code"] in E.REGION_NAMES]
    for r in rows:
        # RU: название региона — как в ядре (в CSV «Astana», в ядре «Astana city»). EN: the engine's region name.
        r["region"] = E.REGION_NAMES[r["region_code"]]
    for r in rows:
        name = r["region"]
        key = f"gap_by_region_2024[region={name}].below_sm_regional_line_pct"
        rid = g.figure(f"region:{name}", "region", name, RESULTS, key, "% of people in the region's sample below its subsistence minimum",
                       note=f"region code {r['region_code']}", verified_by=f"verify.py: 2024 {name}")
        if rid is None:
            g.node(f"region:{name}", "region", name, note=f"region code {r['region_code']}")
        for yr in YEARS:
            g.node(f"sm:{yr}:{name}", "threshold", f"Subsistence minimum, {name}, {yr}", int(r[f"sm_{yr}"]),
                   "tenge per person per month", yr, f"{Path(SM_CSV).name}: region_code {r['region_code']}, column sm_{yr}",
                   {"file": SM_CSV, "key": f"region_code={r['region_code']}, column sm_{yr}"},
                   "verify.py reads the lines from this CSV; verify_graph.py: equals results.json regional_sm_by_year")
            g.edge(f"region:{name}", f"sm:{yr}:{name}", "has_sm")
            g.edge(f"sm:{yr}:{name}", "caveat:regional_sm_source", "limited_by")

    # ---- черты / thresholds -----------------------------------------------------------------
    share = f"{E.TSA_SHARE:g}"
    g.figure(TSA_ID, "threshold", f"TSA line: {E.TSA_SHARE:.0%} of the subsistence minimum of the household's region",
             RESULTS, f"three_lines_by_year{y}.tsa_line_tenge", "tenge per person per month, average over people in the sample",
             note=f"rule: income per person below {share} x regional subsistence minimum (engine.TSA_SHARE). {LEGAL}")
    g.figure("threshold:regional_sm", "threshold", "Regional subsistence minimum: the poverty line of the household's own region",
             RESULTS, f"three_lines_by_year{y}.regional_sm_tenge", "tenge per person per month, average over people in the sample")
    g.figure("threshold:budget_sm", "threshold", "Budget-law subsistence minimum: one national value",
             RESULTS, f"national_sm_by_year.{YEAR}.budget_law", "tenge per person per month")
    for r in rows:
        g.edge(f"sm:{YEAR}:{r['region']}", TSA_ID, "defines", f"coefficient {share}")
        g.edge(f"sm:{YEAR}:{r['region']}", "threshold:regional_sm", "defines", "coefficient 1")

    # ---- уровни A–E: ключи в точности как в engine.TIERS / tiers: keys exactly as in engine.TIERS
    tier_text = {"A": "above the regional subsistence minimum, passes all stress tests",
                 "B": "above the regional subsistence minimum, fails one stress test",
                 "C": "above the regional subsistence minimum, fails two or more stress tests",
                 "D": f"below the regional subsistence minimum but not below the TSA line ({E.TSA_SHARE:.0%} of it)",
                 "E": f"below the TSA line ({E.TSA_SHARE:.0%} of the regional subsistence minimum): income-eligible for TSA"}
    for t in E.TIERS:
        g.figure(f"tier:{t}", "tier", f"Level {E.level(t)}: {tier_text[E.level(t)]}", RESULTS,
                 f"gap_by_year_regional_line{y}.tiers_pct.{t}", verified_by=f"verify.py: 2024 level {E.level(t)}")
    for t in E.TIERS:
        if E.level(t) in "DE":
            g.edge(TSA_ID, f"tier:{t}", "decides")
        if E.level(t) in "ABCD":
            g.edge("threshold:regional_sm", f"tier:{t}", "decides")

    # ---- стресс-тесты / stress tests --------------------------------------------------------
    for t in E.TESTS:
        try:
            label = lookup(R, f"stress_tests.base.labels.{t}")
        except KeyError:
            continue
        sid = g.figure("stress:" + t.removeprefix("fail_"), "stress_test", "Stress test: " + label, RESULTS,
                       f"levels_by_stress_version_2024[version=base].above_sm_and_failing_pct.{t}",
                       "% of people in the sample above the subsistence minimum who fail this test",
                       note="base version; parameters in results.json: stress_tests.base")
        for tier in E.AT_RISK:
            g.edge(sid, f"tier:{tier}", "moves", "a household above the minimum that fails one test is level B, two or more level C")
        g.edge(sid, "caveat:static_model", "limited_by")
    g.edge("stress:earner_loss", "caveat:earner_type_approximated", "limited_by")

    # ---- метрики 2024 года / the 2024 metrics -----------------------------------------------
    M = [  # id, label, key, unit, verified_by
        ("poverty_rate_sm_2024", "Share of people below the regional subsistence minimum, 2024",
         f"gap_by_year_regional_line{y}.poverty_rate_sm_pct", PCT, "verify.py: 2024 below regional SM"),
        ("poverty_rate_sm_2024_ci_low", "Share below the regional subsistence minimum, 2024: lower bound of the 95% interval",
         "uncertainty_2024.poverty_rate_sm_pct.ci95[0]", PCT, None),
        ("poverty_rate_sm_2024_ci_high", "Share below the regional subsistence minimum, 2024: upper bound of the 95% interval",
         "uncertainty_2024.poverty_rate_sm_pct.ci95[1]", PCT, None),
        ("below_tsa_line_2024", "Share of people below the TSA line, 2024",
         f"three_lines_by_year{y}.below_tsa_line_pct", PCT, "verify.py: 2024 below TSA line"),
        ("below_budget_sm_2024", "Share of people below the budget-law subsistence minimum, 2024",
         f"three_lines_by_year{y}.below_budget_sm_pct", PCT, "verify.py: 2024 below budget-law SM"),
        ("uncovered_band_2024", "Uncovered band: below the regional subsistence minimum but not below the TSA line, 2024",
         f"three_lines_by_year{y}.uncovered_band_pct", PCT, "verify.py: tools gap_overview 2024: three_lines"),
        ("poor_not_eligible_2024", "Share of people below the subsistence minimum who are not income-eligible for TSA, 2024",
         f"three_lines_by_year{y}.share_of_poor_not_eligible_pct", "% of people below the regional subsistence minimum",
         "verify.py: tools gap_overview 2024: three_lines"),
        ("at_risk_b_c_2024", "Levels B and C together: above the subsistence minimum but failing a stress test, 2024, base tests",
         f"gap_by_year_regional_line{y}.at_risk_pct", PCT, "verify.py: 2024 levels B and C, share of people"),
        ("at_risk_b_c_2024_weak", "Levels B and C together, 2024, weak stress tests",
         "levels_by_stress_version_2024[version=weak].at_risk_pct", PCT, None),
        ("at_risk_b_c_2024_strong", "Levels B and C together, 2024, strong stress tests",
         "levels_by_stress_version_2024[version=strong].at_risk_pct", PCT, None),
        ("median_income_per_capita_2024", "Median income per person, 2024",
         f"gap_by_year_regional_line{y}.median_income_per_capita", "tenge per person per month", None),
        ("gap_to_sm_per_capita_2024", "Shortfall to the subsistence minimum per person of the sample, 2024",
         f"gap_by_year_regional_line{y}.gap_to_sm_per_capita_year", "tenge per person of the sample per year", None),
        ("equivalised_below_sm_2024", "Share below the subsistence minimum with the Bureau's equivalence scale, same line, 2024",
         "equivalence_2024.below_sm_equivalised_same_line_pct", PCT, "verify.py: 2024 equivalised income, same line"),
        ("equal_budget_per_capita_2024", "Equal budget used to compare the measures, 2024",
         "compare_equal_budget_2024.equal_cost_per_capita", "tenge per person of the sample per year", None),
    ]
    core_caveats = ["synthetic_data", "no_weights", "income_not_consumption", "official_poverty_consumption"]
    for key, label, path, unit, ver in M:
        mid = g.figure(f"metric:{key}", "metric", label, RESULTS, path, unit, verified_by=ver)
        if mid is None:
            continue
        for code in ("D-008", "D-004"):
            g.edge(mid, f"form:{code}", "computed_from")
        for c in core_caveats:
            g.edge(mid, f"caveat:{c}", "limited_by")
    # RU: узел без числа: сами доли по регионам записаны в узлах region. EN: no value here: the regional shares sit on the region nodes.
    by_region = g.node("metric:poverty_rate_sm_by_region_2024", "metric", "Share of people below the regional subsistence minimum by region, 2024",
                       unit="% of people in the region's sample", year=YEAR, note="results.json: gap_by_region_2024; the values are on the region nodes",
                       source={"file": RESULTS, "key": "gap_by_region_2024"})
    for code in ("D-008", "D-004"):
        g.edge(by_region, f"form:{code}", "computed_from")
    for c in core_caveats + ["repeated_cross_sections"]:
        g.edge(by_region, f"caveat:{c}", "limited_by")
    for r in rows:
        g.edge(f"region:{r['region']}", by_region, "has_metric")
    rate = "metric:poverty_rate_sm_2024"
    for a, b in [(rate, "caveat:repeated_cross_sections"), (rate, "caveat:unused_forms"), (rate, "caveat:no_food_spending"),
                 ("metric:equivalised_below_sm_2024", "caveat:static_model")]:
        g.edge(a, b, "limited_by")
    for a, b in [(TSA_ID, "metric:below_tsa_line_2024"), ("threshold:regional_sm", rate),
                 ("threshold:budget_sm", "metric:below_budget_sm_2024"),
                 ("tier:E_below_tsa_line", "metric:below_tsa_line_2024"), ("tier:E_below_tsa_line", rate),
                 ("tier:D_below_sm", rate), ("tier:D_below_sm", "metric:uncovered_band_2024"),
                 ("tier:D_below_sm", "metric:poor_not_eligible_2024"),
                 ("tier:C_fails_two_or_more", "metric:at_risk_b_c_2024"), ("tier:B_fails_one_test", "metric:at_risk_b_c_2024"),
                 ("tier:A_resilient", "metric:median_income_per_capita_2024"),
                 (rate, "metric:poverty_rate_sm_2024_ci_low"), (rate, "metric:poverty_rate_sm_2024_ci_high"),
                 (rate, "metric:equivalised_below_sm_2024"), (rate, "metric:gap_to_sm_per_capita_2024"),
                 ("metric:at_risk_b_c_2024", "metric:at_risk_b_c_2024_weak"), ("metric:at_risk_b_c_2024", "metric:at_risk_b_c_2024_strong")]:
        g.edge(a, b, "has_metric")

    # ---- меры при равном бюджете / the measures at an equal budget ---------------------------
    # RU: только АСП и детские пособия из движка; для других программ узлов нет: их правила нужно сверять с законом.
    # EN: only TSA and child allowances from the engine; no nodes for other programmes: their rules need a legal check.
    seen: dict[str, int] = {}
    for i, r in enumerate(R.get("compare_equal_budget_2024", {}).get("results", [])):
        base = "tsa_topup" if r.get("policy", "").startswith("TSA") else "child_allowance" if r.get("policy", "").startswith("Child") else None
        if base is None:
            continue
        seen[base] = seen.get(base, 0) + 1
        pid = g.figure(f"policy:{base}" + (f"_{seen[base]}" if seen[base] > 1 else ""), "policy", "Measure: " + r["policy"], RESULTS,
                       f"compare_equal_budget_2024.results[{i}].after_policy.poverty_rate_sm_pct",
                       "% of people in the sample below the regional subsistence minimum after the measure",
                       note="measure tuned to the equal budget; cost in the same record: cost.per_capita_tenge_year"
                            + (f". {LEGAL}" if base == "tsa_topup" else ""))
        g.edge(pid, rate, "changes")
        g.edge(pid, "metric:equal_budget_per_capita_2024", "has_metric")
        g.edge(pid, "caveat:static_model", "limited_by")

    # ---- скрининг без дохода, если посчитан / the no-income screen, if it was run -------------
    if SCREEN in files:
        models = files[SCREEN].get("models", [])
        i = next((i for i, m in enumerate(models) if (m.get("target"), m.get("features"), m.get("model")) ==
                  ("poor", "composition_region", "logistic")), None)
        if i is not None:
            for key, field, label, unit in [
                ("quick_screen_auc_2024", "auc", "No-income screen (logistic, composition and region): AUC on 2024", "AUC, 0..1"),
                ("quick_screen_top20_found_2024", "flag_top_20pct.found_pct",
                 "No-income screen: share of people below the minimum found among the 20% with the highest risk, 2024",
                 "% of people below the regional subsistence minimum"),
            ]:
                mid = g.figure(f"metric:{key}", "metric", label, SCREEN, f"models[{i}].{field}", unit)
                for code in ("D-008", "D-004"):
                    g.edge(mid, f"form:{code}", "computed_from")
                for c in ("synthetic_data", "no_weights", "repeated_cross_sections"):
                    g.edge(mid, f"caveat:{c}", "limited_by")
                g.edge(rate, mid, "has_metric")

    return {"nodes": list(g.nodes.values()), "edges": g.edges,
            "meta": {"engine_version": R.get("version"), "year": YEAR, "nodes": len(g.nodes), "edges": len(g.edges),
                     "sources": sorted(files) + [SM_CSV], "tiers": E.TIERS, "tsa_share": E.TSA_SHARE,
                     "built_by": "build_graph.py, without a language model"}}


if __name__ == "__main__":
    graph = build(sys.argv[1], sys.argv[2])
    out = Path(sys.argv[3])
    out.write_text(json.dumps(graph, ensure_ascii=False, indent=1), encoding="utf-8")
    types = {}
    for n in graph["nodes"]:
        types[n["type"]] = types.get(n["type"], 0) + 1
    print(f"wrote {out}: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges; by type: {types}")
