"""Проверка оценки без данных о доходе. Запуск: python test_risk.py (или pytest).

Модель обучает и сохраняет qamqor/poverty_challenge.py; здесь — что она загружается, не видит
дохода, ведёт себя разумно и что рейтинг на экране совпадает с пересчётом по сохранённой модели.
"""
import inspect

import pandas as pd

import core

RS = core.T.RS  # qamqor/risk_screen.py
ASTANA, TURKESTAN = 71, 61
BASE = dict(hh_size=4, n_child=2, region=ASTANA)


def test_model_loads_and_features_match_the_saved_list():
    bundle = RS.load()["bundle"]
    assert bundle["features"] == RS.feature_names()
    assert list(RS.design(pd.DataFrame([{"size": 4, "n_child": 2, "n_child_u7": 0, "n_elderly": 0, "n_working_age": 2,
                                         "urban": 1, "region": "71"}])).columns) == bundle["features"]
    assert bundle["model"].named_steps["logisticregression"].coef_.shape[1] == len(bundle["features"])
    assert bundle["version"] and bundle["trained_at"] and bundle["train_years"] == [2022, 2023]


def test_no_income_feature_and_no_number_of_earners():
    features = RS.load()["bundle"]["features"]
    assert "n_earners" not in features
    assert not [f for f in features if any(bad in f.lower() for bad in RS.FORBIDDEN)]
    assert set(features) - {f for f in features if f.startswith("region_")} == {
        "size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban"}
    # дохода нет ни в функции ядра, ни в мосте, ни в запросе сервера
    for fn in (RS.screen, core.risk_screen):
        assert not [p for p in inspect.signature(fn).parameters if "income" in p or "wage" in p or "earn" in p]
    import app
    assert not [f for f in app.RiskScreenRequest.model_fields if "income" in f or "wage" in f or "employed" in f]


def test_income_entered_in_my_family_does_not_change_the_estimate():
    first = core.risk_screen(**BASE)
    for income in (50_000, 200_000, 900_000):
        core.classify_household(**BASE, n_employed=1, income_monthly=income)
        assert core.risk_screen(**BASE) == first


def test_request_with_an_income_field_is_rejected():
    from fastapi.testclient import TestClient
    import app
    client = TestClient(app.app)
    ok = client.post("/api/risk_screen", json=BASE)
    assert ok.status_code == 200 and ok.json() == core.risk_screen(**BASE)
    assert client.post("/api/risk_screen", json={**BASE, "income_monthly": 100_000}).status_code == 422


def test_no_children_is_lower_risk_than_four_or_more_children():
    for region in (ASTANA, TURKESTAN, 47):
        none = core.risk_screen(hh_size=2, n_child=0, region=region)
        many = core.risk_screen(hh_size=6, n_child=4, region=region)
        same_size = core.risk_screen(hh_size=6, n_child=0, region=region)
        assert none["rank_pct"] < many["rank_pct"] and same_size["rank_pct"] < many["rank_pct"], region
        assert many["factors"][0]["key"] == "children" and many["factors"][0]["direction"] == "raises"


def test_every_region_answers():
    regions = [r["code"] for r in core.regions()]
    assert len(regions) == 20
    for code in regions:
        for urban in (True, False, None):
            r = core.risk_screen(hh_size=5, n_child=3, n_child_u7=1, n_elderly=1, region=code, urban=urban)
            assert 0 <= r["rank_pct"] <= 100 and r["level"] in ("high", "elevated", "usual")
            assert {f["key"] for f in r["factors"]} == {"children", "household_size", "elderly", "region", "urban"}


def test_only_factors_the_family_has():
    keys = lambda **kw: {f["key"] for f in core.risk_screen(region=ASTANA, **kw)["factors"]}
    assert keys(hh_size=2, n_child=0) == {"household_size", "region", "urban"}
    assert keys(hh_size=4, n_child=2) == {"children", "household_size", "region", "urban"}
    assert keys(hh_size=2, n_child=0, n_elderly=2) == {"elderly", "household_size", "region", "urban"}
    tool = core.T.call("risk_screen", {"size": 6, "n_child": 4, "region": "Shymkent city"})["result"]
    assert "elderly" not in {f["key"] for f in tool["factors"]} and "average household" in tool["factors_compared_with"]


def test_levels_follow_the_rank():
    assert [RS.level(p) for p in (95, 90, 89.9, 80, 79.9, 10)] == ["high", "high", "elevated", "elevated", "usual", "usual"]


def test_rank_of_100_sample_households_matches_the_saved_model():
    scores = pd.read_csv(RS.SCORES_PATH, dtype={"hh_id": str, "region": str})
    hh = pd.read_csv(core.QAMQOR / "out" / "households.csv", dtype={"hh_id": str, "region": str})
    hh = hh[hh["year"] == 2024].set_index("hh_id")
    sample = scores.sample(100, random_state=7)
    recomputed = RS.predict(RS.design(hh.loc[sample["hh_id"]]))
    assert (recomputed == sample["risk"].to_numpy()).all()
    for (_, s), risk in zip(sample.iterrows(), recomputed):
        h = hh.loc[s["hh_id"]]
        got = core.risk_screen(hh_size=int(h["size"]), n_child=int(h["n_child"]), n_child_u7=int(h["n_child_u7"]),
                               n_elderly=int(h["n_elderly"]), region=int(h["region"]), urban=bool(h["urban"]))
        assert got["rank_pct"] == RS.percentile(s["risk"]) == RS.percentile(risk), s["hh_id"]


def test_invalid_input():
    for bad, code in [(dict(region=99), "err_region"), (dict(n_child_u7=3), "err_risk_members"),
                      (dict(n_elderly=3), "err_risk_members"), (dict(hh_size=0), "err_risk_members")]:
        try:
            core.risk_screen(**{**BASE, **bad})
        except core.InputError as e:
            assert e.code == code, (bad, e.code)
        else:
            raise AssertionError(f"no error for {bad}")


def test_tool_and_graph_explain_the_figure():
    r = core.T.call("risk_screen", {"size": 6, "n_child": 4, "region": "Shymkent city"})
    assert any("filter" in c.lower() for c in r["caveats"])
    for node in r["result"]["explain_nodes"]:
        x = core.T.call("explain", {"node": node})["result"]
        assert x["node"]["id"] == node
    x = core.T.call("explain", {"node": "metric:risk_screen_recall_top20_2024"})["result"]
    assert x["node"]["value"] == r["result"]["model"]["recall_top20_pct"]
    assert any("filter" in c for c in x["caveats"]) and x["sources"][0]["key"] == "screen_model.recall_top20_pct"


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
