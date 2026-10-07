"""Qamqor — расчётный модуль: черты по регионам, статус семьи, три сценария.

Все формулы живут здесь. Интерфейс и языковая модель только показывают
результат; segmentation.py применяет эти же функции к выборке, не дублируя их.

Статусы (по доходу на человека в месяц, относительно минимума СВОЕГО региона):
  A — ниже черты АСП
  B — ниже прожиточного минимума, но не ниже черты АСП
  C — не ниже минимума, но хотя бы один из трёх сценариев опускает ниже
  D — не ниже минимума во всех трёх сценариях

Сценарии (параметры задаёт пользователь, значения по умолчанию — ниже):
  earner_gap   — главный кормилец N месяцев из 12 без заработка:
                 в среднем за год  (доход*12 - заработок*N) / 12 / размер семьи,
                 в месяцы без заработка  (доход - заработок) / размер семьи
  income_drop  — доход падает на X%:  доход*(1 - X/100) / размер семьи
  housing_rise — жильё и коммунальные дорожают на Y%: из дохода вычитается
                 прирост расходов  (доход - расходы*Y/100) / размер семьи
"""
from __future__ import annotations

import numpy as np

SM_YEAR = 2024
NATIONAL_SM = 51058

SM_SOURCE = (
    "фактический ПМ по регионам, 2024, приближённо: соотношения регионов по "
    "данным БНС за июль–август 2024, приведённые к среднегодовому значению "
    "по стране 51 058 тг"
)

# код региона (поле TE в данных, первые две цифры КАТО) -> (название, ПМ в тг/мес на человека)
REGIONS: dict[int, tuple[str, int]] = {
    10: ("Абай", 51345),
    11: ("Акмолинская", 50497),
    15: ("Актюбинская", 47065),
    19: ("Алматинская", 51280),
    23: ("Атырауская", 48240),
    27: ("Западно-Казахстанская", 47909),
    31: ("Жамбылская", 47297),
    33: ("Жетісу", 48865),
    35: ("Карагандинская", 49403),
    39: ("Костанайская", 49170),
    43: ("Кызылординская", 45483),
    47: ("Мангистауская", 62803),
    55: ("Павлодарская", 50154),
    59: ("Северо-Казахстанская", 50778),
    61: ("Туркестанская", 44309),
    62: ("Ұлытау", 51710),
    63: ("Восточно-Казахстанская", 54464),
    71: ("г. Астана", 55480),
    75: ("г. Алматы", 54875),
    79: ("г. Шымкент", 49263),
}
REGIONAL_SM: dict[int, int] = {code: sm for code, (_, sm) in REGIONS.items()}
REGION_NAMES: dict[int, str] = {code: name for code, (name, _) in REGIONS.items()}

ASP_RATIO = 0.7  # черта АСП = 70% прожиточного минимума региона

# Допущения для полей, которые человек не заполнил. Показываются на экране.
WAGE_SHARE_ASSUMPTION = 0.66      # доля зарплаты в доходе (выборка 2024, m_totals_by_year.csv)
HOUSING_SHARE_ASSUMPTION = 0.125  # жильё и коммунальные как доля дохода семьи

DEFAULT_MONTHS_WITHOUT_WAGE = 3
DEFAULT_INCOME_DROP_PCT = 15
DEFAULT_HOUSING_RISE_PCT = 30

SCENARIOS = ("earner_gap", "income_drop", "housing_rise")

# цвет статуса в интерфейсе — по возрастанию дохода, от самого низкого
GROUP_STATUS = {"A": "critical", "B": "serious", "C": "warning", "D": "good"}


class InputError(ValueError):
    """Некорректный ввод. code — ключ сообщения, текст подставляет интерфейс."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def lines(region: int) -> tuple[int, float]:
    """Прожиточный минимум региона и черта АСП, тг в месяц на человека."""
    if region not in REGIONAL_SM:
        raise InputError("err_region")
    sm = REGIONAL_SM[region]
    return sm, sm * ASP_RATIO


def scenario_incomes(*, income, earner_wage, housing_cost, hh_size, months, drop_pct, rise_pct) -> dict:
    """Доход на человека в месяц в каждом сценарии.

    Чистая арифметика: работает и для одной семьи (числа), и для всей
    выборки сразу (pandas.Series) — поэтому формулы записаны один раз.
    """
    return {
        "earner_gap": np.maximum(income * 12 - earner_wage * months, 0) / 12 / hh_size,
        "earner_gap_during": np.maximum(income - earner_wage, 0) / hh_size,
        "income_drop": income * (1 - drop_pct / 100) / hh_size,
        "housing_rise": np.maximum(income - housing_cost * rise_pct / 100, 0) / hh_size,
    }


def group_of(income_pc, worst_pc, sm, asp):
    """Статус A/B/C/D. Тоже работает и для числа, и для Series."""
    return np.select(
        [income_pc < asp, income_pc < sm, worst_pc < sm],
        ["A", "B", "C"],
        default="D",
    )


def check_household(
    *,
    hh_size: int,
    n_child: int,
    n_employed: int,
    income_monthly: float,
    region: int,
    earner_wage: float | None = None,
    transfers: float | None = None,
    housing_cost: float | None = None,
    months_without_wage: int = DEFAULT_MONTHS_WITHOUT_WAGE,
    income_drop_pct: float = DEFAULT_INCOME_DROP_PCT,
    housing_rise_pct: float = DEFAULT_HOUSING_RISE_PCT,
) -> dict:
    """Статус одной семьи, три сценария и вывод по статусу.

    earner_wage, transfers, housing_cost — необязательные; для пустых берётся
    допущение, и оно возвращается в "assumptions", чтобы интерфейс его показал.
    Суммы — тенге в месяц.
    """
    sm, asp = lines(region)

    if hh_size < 1 or income_monthly < 0:
        raise InputError("err_values")
    if n_child < 0 or n_employed < 0 or n_child > hh_size or n_employed > hh_size:
        raise InputError("err_members")
    if any(v is not None and v < 0 for v in (earner_wage, transfers, housing_cost)):
        raise InputError("err_values")
    if (earner_wage or 0) + (transfers or 0) > income_monthly:
        raise InputError("err_amounts")
    if not 0 <= months_without_wage <= 12 or not 0 <= income_drop_pct <= 100 or housing_rise_pct < 0:
        raise InputError("err_values")

    assumptions = []
    if earner_wage is None:
        if n_employed == 0:
            earner_wage = 0.0
            assumptions.append({"field": "earner_wage", "basis": "no_workers", "value": 0})
        elif transfers is not None:
            earner_wage = (income_monthly - transfers) / n_employed
            assumptions.append(
                {"field": "earner_wage", "basis": "minus_transfers", "value": round(earner_wage), "workers": n_employed}
            )
        else:
            earner_wage = income_monthly * WAGE_SHARE_ASSUMPTION / n_employed
            assumptions.append(
                {
                    "field": "earner_wage",
                    "basis": "wage_share",
                    "value": round(earner_wage),
                    "share_pct": round(WAGE_SHARE_ASSUMPTION * 100),
                    "workers": n_employed,
                }
            )
    if housing_cost is None:
        housing_cost = income_monthly * HOUSING_SHARE_ASSUMPTION
        assumptions.append(
            {
                "field": "housing_cost",
                "basis": "income_share",
                "value": round(housing_cost),
                "share_pct": HOUSING_SHARE_ASSUMPTION * 100,
            }
        )

    income_pc = income_monthly / hh_size
    sc = {
        k: float(v)
        for k, v in scenario_incomes(
            income=income_monthly,
            earner_wage=earner_wage,
            housing_cost=housing_cost,
            hh_size=hh_size,
            months=months_without_wage,
            drop_pct=income_drop_pct,
            rise_pct=housing_rise_pct,
        ).items()
    }
    worst_key = min(SCENARIOS, key=lambda k: sc[k])
    worst_pc = sc[worst_key]
    group = str(group_of(income_pc, worst_pc, sm, asp))

    # сценарий «опускает ниже минимума», только если до него семья была не ниже
    crosses = {k: income_pc >= sm and sc[k] < sm for k in SCENARIOS}

    if group == "A":
        outcome = {"topup_family": round((asp - income_pc) * hh_size)}
    elif group == "B":
        outcome = {
            "gap_pc": round(sm - income_pc),
            "gap_family": round((sm - income_pc) * hh_size),
            "above_asp_pc": round(income_pc - asp),
        }
    else:
        outcome = {
            "margin_pc": round(income_pc - sm),
            "margin_family": round((income_pc - sm) * hh_size),
            "failing": [k for k in SCENARIOS if crosses[k]],
        }

    return {
        "year": SM_YEAR,
        "region": {"code": region, "name": REGION_NAMES[region]},
        "sm": sm,
        "asp": round(asp),
        "group": group,
        "status": GROUP_STATUS[group],
        "hh_size": hh_size,
        "n_child": n_child,
        "income_monthly": round(income_monthly),
        "income_pc": round(income_pc),
        "pct_of_sm": round(100 * income_pc / sm, 1),
        "earner_wage": round(earner_wage),
        "housing_cost": round(housing_cost),
        "assumptions": assumptions,
        "scenarios": {
            "earner_gap": {
                "income_pc": round(sc["earner_gap"]),
                "during_pc": round(sc["earner_gap_during"]),
                "months": months_without_wage,
                "crosses": crosses["earner_gap"],
            },
            "income_drop": {
                "income_pc": round(sc["income_drop"]),
                "pct": income_drop_pct,
                "crosses": crosses["income_drop"],
            },
            "housing_rise": {
                "income_pc": round(sc["housing_rise"]),
                "pct": housing_rise_pct,
                "extra_cost": round(housing_cost * housing_rise_pct / 100),
                "crosses": crosses["housing_rise"],
            },
        },
        "worst": {"key": worst_key, "income_pc": round(worst_pc)},
        "outcome": outcome,
    }
