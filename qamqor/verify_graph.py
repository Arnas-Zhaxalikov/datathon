"""
Qamqor AI — проверка графа и инструмента explain / a check of the graph and the explain tool.

RU: Проверяет, что граф не добавил и не исказил ни одной цифры: каждый числовой узел равен
    значению по своему ключу в results.json или quick_screen.json (допуск 0), прожиточные
    минимумы равны и CSV, и results.json; все связи ведут к существующим узлам, изолированных
    узлов нет; explain отвечает на типовые запросы и не падает на несуществующем узле.
    Пути к значениям разбираются здесь отдельно, без кода build_graph.py.
EN: Checks that the graph added or distorted no figure: every numeric node equals the value at
    its key in results.json or quick_screen.json (zero tolerance), the subsistence minimums equal
    both the CSV and results.json; every edge points to existing nodes and no node is isolated;
    explain answers the typical queries and does not fail on a missing node.
    The value paths are resolved here separately, without the build_graph.py code.

Запуск / Run:
    python verify_graph.py results/graph.json results/results.json ref/regional_sm_annual_2022_2024.csv
"""
import json
import sys
from pathlib import Path

import pandas as pd

import engine as E
import tools

G = json.load(open(sys.argv[1], encoding="utf-8"))
R = json.load(open(sys.argv[2], encoding="utf-8"))
sm = pd.read_csv(sys.argv[3], dtype={"region_code": str})
screen = Path(sys.argv[2]).with_name("quick_screen.json")
FILES = {"results/results.json": R}
if screen.exists():
    FILES["results/quick_screen.json"] = json.load(open(screen, encoding="utf-8"))
challenge = Path(sys.argv[2]).parent / "poverty_challenge" / "summary.json"
if challenge.exists():
    FILES["results/poverty_challenge/summary.json"] = json.load(open(challenge, encoding="utf-8"))
ok, n_checks = True, 0


def chk(name, good, detail=""):
    global ok, n_checks
    ok &= bool(good)
    n_checks += 1
    print(f"{'OK  ' if good else 'DIFF'} {name}" + ("" if good else f": {detail}"))


def at(data, key):
    """RU: значение по пути a.b[k=v].c[0]. EN: the value at a path a.b[k=v].c[0]."""
    part, parts, depth = "", [], 0
    for ch in key:
        if ch == "[":
            if part:
                parts.append(part)
            part, depth = "[", 1
        elif ch == "]":
            parts.append(part[1:] + "]")
            part, depth = "", 0
        elif ch == "." and not depth:
            if part:
                parts.append(part)
            part = ""
        else:
            part += ch
    if part:
        parts.append(part)
    for p in parts:
        if not p.endswith("]"):
            data = data[p]
        elif "=" in p:
            k, v = p[:-1].split("=", 1)
            (data,) = [r for r in data if str(r[k]) == v]
        else:
            data = data[int(p[:-1])]
    return data


nodes = {n["id"]: n for n in G["nodes"]}
chk("node ids are unique", len(nodes) == len(G["nodes"]))
chk("node types are the eight agreed ones",
    {n["type"] for n in G["nodes"]} <= {"region", "threshold", "tier", "stress_test", "policy", "metric", "data_form", "caveat"})
chk("every node has the agreed fields", all({"id", "type", "label", "value", "unit", "year", "note"} <= set(n) for n in G["nodes"]))

# ---- числа / the numbers ---------------------------------------------------------------------
numeric = [n for n in G["nodes"] if n["value"] is not None]
bad = [n["id"] for n in numeric if not n.get("source") or not n["note"]]
chk(f"every numeric node names its source ({len(numeric)} nodes)", not bad, bad)
from_json = [n for n in numeric if n["source"]["file"] in FILES]
bad = [(n["id"], n["value"], at(FILES[n["source"]["file"]], n["source"]["key"])) for n in from_json
       if n["value"] != at(FILES[n["source"]["file"]], n["source"]["key"])]
chk(f"numeric nodes equal the value at their key in the results files, tolerance 0 ({len(from_json)} nodes)", not bad, bad)
from_csv = [n for n in numeric if n["source"]["file"] not in FILES]
chk("the other numeric nodes are subsistence minimums from the CSV", all(n["id"].startswith("sm:") for n in from_csv))
rows = sm[sm.region_code.isin(E.REGION_NAMES)]
bad = []
for _, r in rows.iterrows():
    name = E.REGION_NAMES[r.region_code]
    for y in (2022, 2023, 2024):
        v = nodes.get(f"sm:{y}:{name}", {}).get("value")
        if not (v == r[f"sm_{y}"] == R["regional_sm_by_year"][str(y)][name]):
            bad.append((name, y, v))
bad += [n["id"] for n in G["nodes"] if n["type"] == "region" and n["value"] is None]
chk(f"subsistence minimums equal the CSV and results.json regional_sm_by_year ({3 * len(rows)} nodes)",
    not bad and len(from_csv) == 3 * len(rows), bad)
chk("tier nodes use the keys of engine.TIERS", [n["id"] for n in G["nodes"] if n["type"] == "tier"] == ["tier:" + t for t in E.TIERS])
chk("one stress-test node per engine test", sum(n["type"] == "stress_test" for n in G["nodes"]) == len(E.TESTS))

# ---- связи / the edges -----------------------------------------------------------------------
bad = [e for e in G["edges"] if e["from"] not in nodes or e["to"] not in nodes]
chk(f"every edge points to existing nodes ({len(G['edges'])} edges)", not bad, bad)
linked = {e["from"] for e in G["edges"]} | {e["to"] for e in G["edges"]}
chk(f"no isolated nodes ({len(nodes)} nodes)", set(nodes) <= linked, sorted(set(nodes) - linked))
chk("meta counts match", (G["meta"]["nodes"], G["meta"]["edges"]) == (len(nodes), len(G["edges"])))

# ---- инструмент explain / the explain tool ----------------------------------------------------
tools.load_graph(sys.argv[1])
x = tools.call("explain", {"node": "sm:2024:Astana city"})["result"]
chk("explain('sm:2024:Astana city') returns 55386", x["node"]["value"] == 55386, x["node"]["value"])
chk("explain('sm:2024:Astana city') points to the ref CSV",
    any(s.get("file", "").startswith("ref/") and s["file"].endswith(".csv") for s in x["sources"]), x["sources"])
tsa = f"threshold:tsa_line_{round(100 * E.TSA_SHARE)}pct"
x = tools.call("explain", {"node": "tier:" + E.TIERS[-1]})["result"]
near = [r["node"] for r in x["neighbors"] if r["relation"] == "decides"]
chk(f"explain('tier:{E.TIERS[-1]}') returns the threshold of {E.TSA_SHARE:.0%} of the subsistence minimum",
    [n["id"] for n in near] == [tsa] and f"{E.TSA_SHARE:.0%}" in near[0]["label"], near)
x = tools.call("explain", {"node": tsa})["result"]
chk("explain(TSA line) lists the 2024 regional minimums that define it, the tiers it decides, data forms and caveats",
    sum(r["relation"] == "defines" for r in x["neighbors"]) == len(rows)
    and {r["node"]["id"] for r in x["neighbors"] if r["relation"] == "decides"} == {"tier:D_below_sm", "tier:E_below_tsa_line"}
    and {s["data_form"] for s in x["sources"] if "data_form" in s} == {"form:D-004", "form:D-008"} and x["caveats"])
x = tools.call("explain", {"node": "metric:poverty_rate_sm_2024"})["result"]
chk("explain(metric) returns the results.json key, the verify.py check and the data forms",
    x["sources"][0].get("key") and "verify.py" in x["sources"][0].get("verified_by", "") and len(x["path_to_sources"]) == 2, x["sources"])
x = tools.call("explain", {"node": "astana", "year": 2023})["result"]
chk("explain accepts a part of a name and a year", x["node"]["id"] == "sm:2023:Astana city", x["node"]["id"])
d1 = tools.call("explain", {"node": "region:Turkestan"})["result"]["neighbors"]
d2 = tools.call("explain", {"node": "region:Turkestan", "depth": 2})["result"]["neighbors"]
chk("depth 2 adds neighbours of neighbours", len(d2) > len(d1) and all(r.get("distance") == 2 for r in d2[len(d1):]))
try:
    x = tools.call("explain", {"node": "tier:A_tsa_eligible"})["result"]
    chk("explain on a missing node returns suggestions without an exception",
        "error" in x and 0 < len(x["suggestions"]) <= 5 and all(s in nodes for s in x["suggestions"]) and x["hint"], x)
    x = tools.call("explain", {"node": "zzzz qqqq"})["result"]
    chk("explain on nonsense returns an error message without an exception", "error" in x and len(x["suggestions"]) <= 5, x)
except Exception as e:  # noqa: BLE001
    chk("explain on a missing node returns suggestions without an exception", False, repr(e))
tools._GRAPH, saved = None, tools.GRAPH_PATH
tools.GRAPH_PATH = Path(sys.argv[1]).with_name("no_such_graph.json")
x = tools.call("explain", {"node": "x"})["result"]
tools.GRAPH_PATH = saved
chk("without graph.json explain says how to build it", x.get("error") == "graph.json not built, run build_graph.py", x)

print(f"{n_checks} checks: " + ("ALL OK" if ok else "SOME DIFFER"))
sys.exit(0 if ok else 1)
