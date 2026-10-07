"""Qamqor — сегментация домохозяйств A/B/C/D и стресс-тесты.

Методология (осознанно простая и честно задокументированная, в духе
docs/RULES.md — не выдавать предположение за официальный факт):

Абсолютная черта прожиточного минимума требует официального источника,
которого у нас нет. Вместо того чтобы подставлять непроверенные "официальные"
тенге, используется ОТНОСИТЕЛЬНАЯ черта бедности — стандартная методология
(OECD/Eurostat): 50% медианного дохода на душу по году. Черта АСП — 70% от
неё, как в постановке Qamqor AI.

Группы:
  A — доход на душу ниже черты АСП (уже получает/имеет право на помощь)
  B — ниже прожиточного минимума, но выше черты АСП (бедны, но НЕ видны системе)
  C — выше прожиточного минимума сейчас, но падает ниже него хотя бы в одном
      стресс-сценарии ("скрытые уязвимые")
  D — устойчивы во всех сценариях

Стресс-сценарии (упрощённые, приближённые — см. комментарии у каждого):
  earner_loss   — кормилец теряет доход: минус пропорциональная доля
                  дохода одного занятого члена семьи
  income_drop15 — доход минус 15%
  utility_up30  — коммунальные +30%, смоделировано как снижение
                  располагаемого дохода на 30% от предполагаемой доли
                  коммунальных в расходах (UTILITY_SHARE, допущение)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLDS_PARQUET = ROOT / "outputs" / "households_2021_2024.parquet"

ASP_RATIO = 0.7          # черта АСП = 70% прожиточного минимума (как у Qamqor)
UTILITY_SHARE = 0.25     # допущение: доля коммунальных в расходах бедного домохозяйства
WAGE_SHARE_ASSUMPTION = 0.66  # для анкеты гражданина: доля зарплаты в доходе по умолчанию
                               # (наблюдаемая доля по 2024 году — outputs/aggregates/m_totals_by_year.csv)

GROUP_LABELS = {
    "A": "Получает/имеет право на АСП",
    "B": "Бедны, но не видны системе",
    "C": "Скрыто уязвимы",
    "D": "Устойчивы",
}
GROUP_STATUS = {"A": "serious", "B": "critical", "C": "warning", "D": "good"}


_CACHE: dict = {"df": None, "lines": {}, "classified": {}}


def _load() -> pd.DataFrame:
    """income_total/spend_total в households_2021_2024.parquet — ГОДОВЫЕ суммы
    (подтверждено outputs/aggregates/m_totals_by_year.csv: income_month =
    income_total/12). Все расчёты ниже ведутся в месячных величинах, поэтому
    делим здесь же, один раз, а не в каждой функции по отдельности.

    Файл не меняется во время работы сервера — кэшируем в процессе, иначе
    каждый вызов API заново читает и пересчитывает parquet (~1.3с)."""
    if _CACHE["df"] is None:
        df = pd.read_parquet(HOUSEHOLDS_PARQUET)
        df = df[(df.income_total > 0) & (df.hh_size > 0)].copy()
        df["income_total_month"] = df.income_total / 12
        df["income_wage_month"] = df.income_wage / 12
        df["spend_total_month"] = df.spend_total / 12
        df["income_pc"] = df.income_total_month / df.hh_size
        _CACHE["df"] = df
    return _CACHE["df"]


def poverty_lines(df: pd.DataFrame, year: int) -> dict:
    if year not in _CACHE["lines"]:
        sub = df[df.year == year]
        pm = float(sub.income_pc.median() * 0.5)
        asp = pm * ASP_RATIO
        _CACHE["lines"][year] = {"poverty_line": pm, "asp_threshold": asp}
    return _CACHE["lines"][year]


def _stress_income_pc(row: pd.Series, scenario: str) -> float:
    """row.income_total_month / row.spend_total_month — уже месячные величины
    (см. _load). classify_household передаёт месячные значения напрямую.

    earner_loss теряет долю ЗАРПЛАТНОГО дохода (income_wage_month) одного
    занятого члена семьи, не весь доход — трансферты (пособия и т.п.)
    при потере работы не исчезают. Ранняя версия ошибочно обнуляла income_total
    целиком для однодоходных семей (4933 из 11948 домохозяйств 2024 года) —
    исправлено после проверки распределения n_employed."""
    n_employed = max(row.n_employed, 1)
    if scenario == "earner_loss":
        income = row.income_total_month - row.income_wage_month / n_employed
    elif scenario == "income_drop15":
        income = row.income_total_month * 0.85
    elif scenario == "utility_up30":
        income = row.income_total_month - 0.30 * UTILITY_SHARE * row.spend_total_month
    else:
        raise ValueError(f"unknown scenario: {scenario}")
    return max(income, 0) / row.hh_size


SCENARIOS = ["earner_loss", "income_drop15", "utility_up30"]


def classify(df: pd.DataFrame, year: int) -> pd.DataFrame:
    if year in _CACHE["classified"]:
        return _CACHE["classified"][year]

    sub = df[df.year == year].copy()
    lines = poverty_lines(df, year)
    pm, asp = lines["poverty_line"], lines["asp_threshold"]

    for scenario in SCENARIOS:
        sub[f"stress_{scenario}"] = sub.apply(lambda r: _stress_income_pc(r, scenario), axis=1)
    sub["worst_stress_income_pc"] = sub[[f"stress_{s}" for s in SCENARIOS]].min(axis=1)

    def group_of(row) -> str:
        if row.income_pc < asp:
            return "A"
        if row.income_pc < pm:
            return "B"
        if row.worst_stress_income_pc < pm:
            return "C"
        return "D"

    sub["group"] = sub.apply(group_of, axis=1)
    _CACHE["classified"][year] = sub
    return sub


def national_summary(year: int) -> dict:
    df = _load()
    sub = classify(df, year)
    lines = poverty_lines(df, year)
    total = len(sub)
    counts = sub.group.value_counts().to_dict()
    groups = {
        g: {
            "count": int(counts.get(g, 0)),
            "pct": round(100 * counts.get(g, 0) / total, 1),
            "label": GROUP_LABELS[g],
            "status": GROUP_STATUS[g],
        }
        for g in ("A", "B", "C", "D")
    }
    return {
        "year": year,
        "total_households": total,
        "poverty_line": round(lines["poverty_line"]),
        "asp_threshold": round(lines["asp_threshold"]),
        "groups": groups,
    }


def classify_household(
    *, hh_size: int, n_child: int, n_employed: int, income_monthly: float, settlement: str, year: int = 2024
) -> dict:
    df = _load()
    lines = poverty_lines(df, year)
    pm, asp = lines["poverty_line"], lines["asp_threshold"]

    hh_size = max(hh_size, 1)
    income_pc = income_monthly / hh_size

    fake_row = pd.Series(
        {
            "income_total_month": income_monthly,
            "income_wage_month": income_monthly * WAGE_SHARE_ASSUMPTION,
            "spend_total_month": income_monthly * 0.5,  # нет данных о расходах гражданина — консервативное допущение
            "hh_size": hh_size,
            "n_employed": max(n_employed, 0),
        }
    )
    stress = {s: _stress_income_pc(fake_row, s) for s in SCENARIOS}
    worst = min(stress.values())

    if income_pc < asp:
        group = "A"
    elif income_pc < pm:
        group = "B"
    elif worst < pm:
        group = "C"
    else:
        group = "D"

    return {
        "group": group,
        "label": GROUP_LABELS[group],
        "status": GROUP_STATUS[group],
        "income_pc": round(income_pc),
        "poverty_line": round(pm),
        "asp_threshold": round(asp),
        "pct_of_poverty_line": round(100 * income_pc / pm, 1),
        "stress_scenarios": {s: round(v) for s, v in stress.items()},
        "worst_stress_income_pc": round(worst),
    }


def policy_simulate(*, year: int, new_asp_ratio: float, topup_amount: float) -> dict:
    """Что будет, если изменить черту АСП и/или размер доплаты."""
    df = _load()
    sub = df[df.year == df.year.max() if year not in df.year.unique() else df.year == year].copy()
    lines = poverty_lines(df, year)
    pm = lines["poverty_line"]
    new_asp = pm * new_asp_ratio

    eligible = sub[sub.income_pc < new_asp].copy()
    eligible["income_pc_after"] = eligible.income_pc + topup_amount / eligible.hh_size
    gap_before = ((pm - eligible.income_pc).clip(lower=0) * eligible.hh_size).sum()
    gap_after = ((pm - eligible.income_pc_after).clip(lower=0) * eligible.hh_size).sum()
    gap_closed_pct = round(100 * (1 - gap_after / gap_before), 1) if gap_before > 0 else 0.0

    return {
        "year": year,
        "new_asp_threshold": round(new_asp),
        "topup_amount": topup_amount,
        "eligible_households": len(eligible),
        "eligible_pct": round(100 * len(eligible) / len(sub), 1),
        "poverty_gap_before": round(gap_before),
        "poverty_gap_after": round(gap_after),
        "gap_closed_pct": gap_closed_pct,
    }
