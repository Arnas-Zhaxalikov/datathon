"""Проверка расчётного модуля. Запуск: python test_engine.py (или pytest)."""
import engine

ASTANA = 71  # минимум 55 480, черта АСП 38 836

# семья из условия: 4 человека, доход 200 000, один работающий с заработком 200 000
BASE = dict(hh_size=4, n_child=2, n_employed=1, income_monthly=200_000, region=ASTANA)


def test_earner_three_months_without_wage():
    r = engine.check_household(**BASE, earner_wage=200_000, months_without_wage=3)
    assert r["scenarios"]["earner_gap"]["income_pc"] == 37_500
    assert r["scenarios"]["earner_gap"]["during_pc"] == 0


def test_income_drop_15():
    r = engine.check_household(**BASE, earner_wage=200_000, income_drop_pct=15)
    assert r["scenarios"]["income_drop"]["income_pc"] == 42_500


def test_housing_rise_30():
    r = engine.check_household(**BASE, housing_cost=25_000, housing_rise_pct=30)
    assert r["scenarios"]["housing_rise"]["income_pc"] == 48_125
    assert r["scenarios"]["housing_rise"]["extra_cost"] == 7_500


def test_default_housing_assumption_matches_25000():
    r = engine.check_household(**BASE)
    assert r["housing_cost"] == 25_000
    assert {a["field"] for a in r["assumptions"]} == {"earner_wage", "housing_cost"}


def test_no_assumptions_when_everything_given():
    r = engine.check_household(**BASE, earner_wage=200_000, housing_cost=25_000)
    assert r["assumptions"] == []


def test_lines_are_regional():
    assert engine.lines(ASTANA) == (55_480, 55_480 * 0.7)
    assert engine.lines(61)[0] == 44_309
    assert len(engine.REGIONAL_SM) == 20


def test_four_statuses():
    def group(income, **kw):
        return engine.check_household(**{**BASE, "income_monthly": income, **kw})["group"]

    assert group(120_000) == "A"  # 30 000 на человека < 38 836
    assert group(200_000) == "B"  # 50 000: между чертой АСП и минимумом
    assert group(240_000) == "C"  # 60 000 >= 55 480, но -15% даёт 51 000
    assert group(480_000) == "D"  # 120 000, запас выдерживает все три сценария


def test_warning_only_when_scenario_crosses_the_minimum():
    below = engine.check_household(**BASE)  # уже ниже минимума — предупреждений нет
    assert not any(s["crosses"] for s in below["scenarios"].values())
    assert "failing" not in below["outcome"]

    above = engine.check_household(**{**BASE, "income_monthly": 240_000})
    assert above["scenarios"]["income_drop"]["crosses"]
    assert "income_drop" in above["outcome"]["failing"]


def test_outcomes():
    a = engine.check_household(**{**BASE, "income_monthly": 120_000})
    assert a["outcome"] == {"topup_family": round((38_836 - 30_000) * 4)}

    b = engine.check_household(**BASE)
    assert b["outcome"] == {"gap_pc": 5_480, "gap_family": 21_920, "above_asp_pc": 11_164}

    d = engine.check_household(**{**BASE, "income_monthly": 480_000})
    assert d["outcome"] == {"margin_pc": 64_520, "margin_family": 258_080, "failing": []}


def test_invalid_input():
    for bad, code in [
        (dict(region=99), "err_region"),
        (dict(n_child=5), "err_members"),
        (dict(earner_wage=150_000, transfers=100_000), "err_amounts"),
        (dict(hh_size=0), "err_values"),
    ]:
        try:
            engine.check_household(**{**BASE, **bad})
        except engine.InputError as e:
            assert e.code == code, (bad, e.code)
        else:
            raise AssertionError(f"no error for {bad}")


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
