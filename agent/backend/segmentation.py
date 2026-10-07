"""Qamqor — расчёт по выборке домохозяйств и анкета одной семьи.

Формулы статусов и сценариев — в engine.py; здесь они только применяются:
к каждой строке выборки (со своим региональным минимумом) и к введённой
семье. Итог по стране — сумма по регионам, поэтому статус семьи на вкладках
«Моя семья» и «Обзор по стране» считается одинаково.

Прожиточный минимум — фактический по регионам за 2024 год (engine.REGIONAL_SM),
поэтому расчёт доступен только за 2024-й: для других лет минимумов нет.

«Относительная черта бедности» (50% медианного дохода на человека по выборке)
оставлена отдельным справочным показателем и как прожиточный минимум
не используется.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import engine

ROOT = Path(__file__).resolve().parents[2]
HOUSEHOLDS_PARQUET = ROOT / "outputs" / "households_2021_2024.parquet"

UTILITY_SHARE = 0.25  # допущение для выборки: доля жилья и коммунальных в расходах домохозяйства
PEERS_MIN_N = 30      # меньше — сравнение с выборкой не показывается (docs/RULES.md, малые подвыборки)

_CACHE: dict = {"df": None}


def _require_year(year: int) -> None:
    if year != engine.SM_YEAR:
        raise engine.InputError("err_year")


def _load() -> pd.DataFrame:
    """Выборка 2024 года со статусом каждого домохозяйства.

    income_total/spend_total в parquet — ГОДОВЫЕ суммы (подтверждено
    outputs/aggregates/m_totals_by_year.csv), все расчёты ниже месячные,
    поэтому делим на 12 здесь, один раз.

    Файл не меняется во время работы сервера — результат кэшируется в процессе.
    """
    if _CACHE["df"] is None:
        df = pd.read_parquet(HOUSEHOLDS_PARQUET)
        df = df[
            (df.year == engine.SM_YEAR)
            & (df.income_total > 0)
            & (df.hh_size > 0)
            & df.TE.isin(engine.REGIONAL_SM.keys())
        ].copy()
        df["region"] = df.TE.astype(int)
        df["n_child"] = df.n_child.fillna(0).astype(int)
        income = df.income_total / 12
        df["income_month"] = income
        df["income_pc"] = income / df.hh_size
        df["sm"] = df.region.map(engine.REGIONAL_SM)
        df["asp"] = df.sm * engine.ASP_RATIO

        # заработок кормильца — зарплата домохозяйства на одного работающего;
        # жильё и коммунальные — доля расходов (отдельной графы в данных нет)
        sc = engine.scenario_incomes(
            income=income,
            earner_wage=(df.income_wage.fillna(0) / 12) / df.n_employed.fillna(0).clip(lower=1),
            housing_cost=UTILITY_SHARE * df.spend_total.fillna(0) / 12,
            hh_size=df.hh_size,
            months=engine.DEFAULT_MONTHS_WITHOUT_WAGE,
            drop_pct=engine.DEFAULT_INCOME_DROP_PCT,
            rise_pct=engine.DEFAULT_HOUSING_RISE_PCT,
        )
        worst = pd.concat([sc[k] for k in engine.SCENARIOS], axis=1).min(axis=1)
        df["group"] = engine.group_of(df.income_pc, worst, df.sm, df.asp)
        df["below_sm"] = df.income_pc < df.sm
        _CACHE["df"] = df
    return _CACHE["df"]


def regions() -> list[dict]:
    return [
        {"code": code, "name": name, "sm": sm, "asp": round(sm * engine.ASP_RATIO)}
        for code, (name, sm) in engine.REGIONS.items()
    ]


def national_summary(year: int = engine.SM_YEAR) -> dict:
    _require_year(year)
    df = _load()
    total = len(df)
    counts = df.group.value_counts().to_dict()
    groups = {
        g: {
            "count": int(counts.get(g, 0)),
            "pct": round(100 * counts.get(g, 0) / total, 1),
            "status": engine.GROUP_STATUS[g],
        }
        for g in ("A", "B", "C", "D")
    }
    by_region = [
        {
            "code": code,
            "name": engine.REGION_NAMES[code],
            "sm": engine.REGIONAL_SM[code],
            "n": int(len(sub)),
            "pct_below_sm": round(float(100 * sub.below_sm.mean()), 1),
        }
        for code, sub in df.groupby("region")
    ]
    return {
        "year": year,
        "total_households": total,
        "sm_min": min(engine.REGIONAL_SM.values()),
        "sm_max": max(engine.REGIONAL_SM.values()),
        "asp_ratio_pct": round(engine.ASP_RATIO * 100),
        "pct_below_sm": round(float(100 * df.below_sm.mean()), 1),
        "relative_poverty_line": round(float(df.income_pc.median() * 0.5)),
        "groups": groups,
        "by_region": by_region,
    }


def _peers(region: int, n_child: int) -> dict | None:
    """Доля семей ниже минимума среди семей с тем же числом детей в регионе."""
    df = _load()
    sub = df[(df.region == region) & (df.n_child == n_child)]
    if len(sub) < PEERS_MIN_N:
        return None
    return {"n": int(len(sub)), "n_child": n_child, "pct_below_sm": round(float(100 * sub.below_sm.mean()), 1)}


def classify_household(
    *,
    year: int = engine.SM_YEAR,
    whatif_extra_wage: float = 0,
    whatif_child_allowance: float = 0,
    **household,
) -> dict:
    """Анкета одной семьи: статус и сценарии (engine.check_household),
    блок «а что, если» и сравнение с выборкой."""
    _require_year(year)
    if whatif_extra_wage < 0 or whatif_child_allowance < 0:
        raise engine.InputError("err_values")

    result = engine.check_household(**household)

    result["what_if"] = None
    added_wage = whatif_extra_wage
    added_allowance = whatif_child_allowance * household["n_child"]
    if added_wage > 0 or added_allowance > 0:
        # семья та же: меняется только доход (и число работающих), заработок
        # кормильца и расходы на жильё остаются прежними
        after = engine.check_household(
            **{
                **household,
                "income_monthly": household["income_monthly"] + added_wage + added_allowance,
                "n_employed": min(household["n_employed"] + (1 if added_wage > 0 else 0), household["hh_size"]),
                "earner_wage": result["earner_wage"],
                "housing_cost": result["housing_cost"],
                "transfers": None,
            }
        )
        result["what_if"] = {
            "added_wage": round(added_wage),
            "added_allowance": round(added_allowance),
            "income_monthly": after["income_monthly"],
            "income_pc": after["income_pc"],
            "pct_of_sm": after["pct_of_sm"],
            "group": after["group"],
            "status": after["status"],
        }

    result["peers"] = _peers(household["region"], household["n_child"])
    return result


def policy_simulate(*, year: int, new_asp_ratio: float, topup_amount: float) -> dict:
    """Что будет, если изменить черту АСП (долю от минимума региона) и/или размер доплаты."""
    _require_year(year)
    df = _load()
    new_asp = df.sm * new_asp_ratio

    eligible = df[df.income_pc < new_asp]
    income_pc_after = eligible.income_pc + topup_amount / eligible.hh_size
    gap_before = ((eligible.sm - eligible.income_pc).clip(lower=0) * eligible.hh_size).sum()
    gap_after = ((eligible.sm - income_pc_after).clip(lower=0) * eligible.hh_size).sum()
    gap_closed_pct = round(100 * (1 - gap_after / gap_before), 1) if gap_before > 0 else 0.0

    return {
        "year": year,
        "new_asp_ratio": new_asp_ratio,
        "topup_amount": topup_amount,
        "eligible_households": int(len(eligible)),
        "eligible_pct": round(100 * len(eligible) / len(df), 1),
        "poverty_gap_before": round(float(gap_before)),
        "poverty_gap_after": round(float(gap_after)),
        "gap_closed_pct": gap_closed_pct,
    }
