"""Проверка моста приложения к расчётному ядру. Запуск: python test_core.py (или pytest).

Формулы проверяет qamqor/verify.py; здесь — что анкета из формы доходит до ядра без искажений
и что ответ раскладывается для интерфейса верно.
"""
import core

ASTANA = 71  # ПМ 2024 — 55 386, черта АСП — 38 770
BASE = dict(hh_size=4, n_child=2, n_employed=1, income_monthly=200_000, region=ASTANA)


def tests_by_key(r):
    return {t["key"]: t for t in r["tests"]}


def test_lines_come_from_the_engine():
    r = core.classify_household(**BASE)
    assert (r["sm"], r["asp"]) == (55_386, 38_770)
    assert r["income_pc"] == 50_000 and r["level"] == "D"


def test_three_stress_tests_base_version():
    # наёмный кормилец с заработком 200 000 сохраняет 45% на 3 месяца
    r = core.classify_household(**BASE, earner_wage=200_000, housing_cost=25_000)
    t = tests_by_key(r)
    assert t["fail_earner_loss"]["income_pc"] == round((200_000 * 12 - 200_000 * 3 * 0.55) / 12 / 4)  # 43 125
    assert t["fail_cost_of_living"]["income_pc"] == round(200_000 / 1.1 / 4)                         # 45 455
    assert t["fail_utilities"]["income_pc"] == round((200_000 - 25_000 * 0.3) / 4)                    # 48 125
    assert set(t) == {"fail_earner_loss", "fail_cost_of_living", "fail_utilities"}
    assert r["earner_keeps_pct"] == 45 and r["assumptions"] == []


def test_self_employed_earner_keeps_nothing():
    r = core.classify_household(**BASE, earner_wage=200_000, earner_self_employed=True)
    assert r["earner_keeps_pct"] == 0
    assert tests_by_key(r)["fail_earner_loss"]["income_pc"] == round((200_000 * 12 - 200_000 * 3) / 12 / 4)  # 37 500


def test_assumptions_are_reported():
    r = core.classify_household(**BASE)
    assert {a["field"] for a in r["assumptions"]} == {"earner_wage", "housing_cost"}
    assert r["earner_wage"] == 132_000 and r["housing_cost"] == 25_000


def test_five_levels():
    level = lambda income, **kw: core.classify_household(**{**BASE, "income_monthly": income, **kw})["level"]
    assert level(120_000) == "E"   # 30 000 на человека — ниже черты АСП
    assert level(200_000) == "D"   # 50 000 — между чертой АСП и ПМ
    assert level(240_000) == "C"   # 60 000 — выше ПМ, не проходит два и более теста
    assert level(240_000, earner_wage=100_000) == "B"   # при меньшем заработке кормильца — только рост стоимости жизни
    assert level(480_000) == "A"


def test_warning_only_when_a_test_crosses_the_minimum():
    below = core.classify_household(**BASE)
    assert not any(t["crosses"] for t in below["tests"])
    above = core.classify_household(**{**BASE, "income_monthly": 240_000, "earner_wage": 100_000})
    assert [t["key"] for t in above["tests"] if t["crosses"]] == ["fail_cost_of_living"]
    assert above["outcome"]["failing"] == ["fail_cost_of_living"]


def test_what_if_and_peers():
    r = core.classify_household(**BASE, whatif_child_allowance=20_000)
    assert r["what_if"]["income_pc"] == 60_000 and r["what_if"]["level"] in "ABC"
    assert r["peers"] is None or r["peers"]["households"] >= core.PEERS_MIN_HOUSEHOLDS


def test_summary_matches_the_tool():
    s = core.summary()
    g = core.T.call("gap_overview", {"year": 2024})["result"]["overall"]
    assert {k: v["pct"] for k, v in s["levels"].items()} == {k[0]: v for k, v in g["tiers_pct"].items()}
    assert s["pct_below_sm"] == g["poverty_rate_sm_pct"] and len(s["by_region"]) == 20


def test_invalid_input():
    for bad, code in [(dict(region=99), "err_region"), (dict(n_child=5), "err_no_adult"),
                      (dict(earner_wage=150_000, transfers=100_000), "err_amounts"), (dict(hh_size=0), "err_size")]:
        try:
            core.classify_household(**{**BASE, **bad})
        except core.InputError as e:
            assert e.code == code, (bad, e.code)
        else:
            raise AssertionError(f"no error for {bad}")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
