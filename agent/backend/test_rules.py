"""Проверка правил состава семьи на сервере. Запуск: python test_rules.py (или pytest).

Правила — qamqor/household_rules.py; те же правила в браузере — agent/web/validate.js
(их проверяет agent/web/test_web.js). Здесь: оба запроса сервера и инструменты ассистента
отклоняют невозможную семью, не выполняя расчёта.
"""
from fastapi.testclient import TestClient

import app
import core

HR = core.HR
client = TestClient(app.app)
ASTANA = 71
OK = dict(hh_size=4, n_child=2, n_child_u7=1, n_elderly=1, n_employed=1)


def classify(**family):
    f = {**OK, **family}
    return client.post("/api/classify", json={**f, "income_monthly": 300_000, "region": ASTANA})


def screen(**family):
    f = {k: v for k, v in {**OK, **family}.items() if k != "n_employed"}
    return client.post("/api/risk_screen", json={**f, "region": ASTANA})


def rejected(response, code, field):
    """422, понятный текст, код и поле; результата расчёта в ответе нет."""
    d = response.json().get("detail")
    assert response.status_code == 422, (response.status_code, response.text)
    assert isinstance(d, dict) and d["code"] == code and d["field"] == field and len(d["message"]) > 20, d
    assert "level" not in response.json() and "rank_pct" not in response.json()


def test_valid_family_is_accepted():
    assert classify().status_code == 200 and screen().status_code == 200


def test_rule_1_size_at_least_one():
    for r in (classify(hh_size=0, n_child=0, n_child_u7=0, n_elderly=0, n_employed=0), screen(hh_size=0, n_child=0, n_child_u7=0, n_elderly=0)):
        rejected(r, "err_size", "size")


def test_rule_2_at_least_one_adult():
    for r in (classify(hh_size=2, n_child=2, n_child_u7=0, n_elderly=0, n_employed=0), screen(hh_size=2, n_child=2, n_child_u7=0, n_elderly=0)):
        rejected(r, "err_no_adult", "n_child")
    assert screen(hh_size=2, n_child=1, n_child_u7=0, n_elderly=0).status_code == 200      # один взрослый и ребёнок — можно


def test_rule_3_children_plus_elderly_within_size():
    for r in (classify(hh_size=4, n_child=2, n_elderly=3), screen(hh_size=4, n_child=2, n_elderly=3)):
        rejected(r, "err_children_elderly", "n_elderly")
    assert screen(hh_size=4, n_child=2, n_elderly=2).status_code == 200                     # дети и двое пожилых — можно


def test_rule_4_children_under_7_within_children():
    for r in (classify(n_child_u7=3), screen(n_child_u7=3)):
        rejected(r, "err_child_u7", "n_child_u7")
    assert screen(n_child_u7=2).status_code == 200


def test_rule_5_working_members_are_adults():
    rejected(classify(hh_size=4, n_child=2, n_employed=3), "err_employed", "n_employed")
    assert classify(hh_size=4, n_child=2, n_employed=2).status_code == 200
    assert classify(hh_size=3, n_child=0, n_child_u7=0, n_elderly=3, n_employed=3).status_code == 200   # работающие 63+ считаются


def test_rule_6_no_working_members_is_fine():
    r = classify(hh_size=2, n_child=0, n_child_u7=0, n_elderly=2, n_employed=0)                # семья пенсионеров
    assert r.status_code == 200 and r.json()["level"] in "ABCDE"


def test_three_people_three_children_is_rejected():
    rejected(classify(hh_size=3, n_child=3, n_child_u7=0, n_elderly=0, n_employed=1), "err_no_adult", "n_child")
    rejected(screen(hh_size=3, n_child=3, n_child_u7=0, n_elderly=0), "err_no_adult", "n_child")


def test_two_people_one_child_two_working_is_rejected():
    rejected(classify(hh_size=2, n_child=1, n_child_u7=0, n_elderly=0, n_employed=2), "err_employed", "n_employed")


def test_rules_module_reports_every_broken_rule():
    assert HR.violations(4, 2, 1, 1, 1) == []
    assert HR.violations(3, 3, 0, 0, 1) == ["no_adult", "employed"]
    assert HR.violations(3, 3, 4, 1, 0) == ["no_adult", "children_elderly", "child_u7"]
    assert HR.violations(0) == ["size"]


def test_assistant_tools_refuse_an_impossible_family():
    """Инструменты не считают: бросают ошибку с просьбой уточнить состав — её получает ассистент."""
    cases = [
        ("risk_screen", {"size": 3, "n_child": 3, "region": "Astana city"}, "no_adult"),
        ("risk_screen", {"size": 4, "n_child": 2, "n_child_u7": 3, "region": "Astana city"}, "child_u7"),
        ("risk_screen", {"size": 4, "n_child": 2, "n_elderly": 3, "region": "Astana city"}, "children_elderly"),
        ("check_household", {"region": "Astana city", "members": [{"age": 9}, {"age": 5}, {"age": 2}]}, "no_adult"),
        ("check_household", {"region": "Astana city", "members": [{"age": 40, "labor_month": 200_000}, {"age": 9, "labor_month": 50_000}]}, "employed"),
    ]
    for tool, args, code in cases:
        try:
            core.T.call(tool, args)
        except HR.CompositionError as e:
            assert e.code == code and "clarify" in str(e), (tool, e.code)
        else:
            raise AssertionError(f"{tool} computed an impossible household: {args}")
    ok = core.T.call("check_household", {"region": "Astana city", "members": [{"age": 70, "pension_month": 90_000}, {"age": 68}]})
    assert ok["result"]["level"] in "ABCDE"                                                 # семья пенсионеров без работающих


def test_assistant_is_told_to_ask_instead_of_computing():
    import claude_agent
    assert "Невозможная семья" in claude_agent.SYSTEM_PROMPT and "попроси уточнить состав" in claude_agent.SYSTEM_PROMPT


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
