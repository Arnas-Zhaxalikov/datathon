"""
Qamqor AI — расчётное ядро / the calculation engine.

RU: Статическая микросимуляция: берём таблицу домохозяйств, меняем правило или условия,
    пересчитываем доход каждой семьи и сравниваем с базой. Поведение людей не меняется,
    поэтому это эффект «на следующий день», а не прогноз.
EN: Static microsimulation: take the household table, change a rule or a condition,
    recompute each household's income and compare with the baseline. Behaviour does not
    change, so this is a next-day effect, not a forecast.

RU: Все доли считаются по людям (вес семьи = число её членов). Весов обследования в данных нет.
EN: All shares are person-based (a household's weight = its size). The data has no survey weights.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

import numpy as np
import pandas as pd

# RU: Прожиточный минимум (ПМ) из закона о республиканском бюджете, тенге в месяц.
#     За 2022 год — среднее: 36 018 (янв–март) и 37 389 (с 1 апреля).
# EN: Subsistence minimum (SM) from the republican budget law, tenge per month.
#     2022 is a time-weighted mean of 36,018 (Jan–Mar) and 37,389 (from 1 April).
SUBSISTENCE_MIN = {2022: (3 * 36018 + 9 * 37389) / 12, 2023: 40567, 2024: 43407}

# RU: Фактический ПМ, который Бюро национальной статистики (БНС) считает по ценам. Именно от него
#     считаются официальная бедность и черта АСП (70% регионального ПМ). Он выше бюджетного.
#     Годовые значения по стране: 43 567 (2022), 48 738 (2023), 51 058 (2024) тенге.
# EN: The actual SM that the Bureau of National Statistics (BNS) computes from prices. Official
#     poverty and the TSA line (70% of the regional SM) are based on it. It is higher than the
#     budget-law figure. National annual values: 43,567 (2022), 48,738 (2023), 51,058 (2024) tenge.
ACTUAL_SM_NATIONAL = {2022: 43567, 2023: 48738, 2024: 51058}

# RU: Фактический годовой ПМ по регионам (v0.3). Ключ — код региона (TE), тенге в месяц на человека.
#     Источник — таблицы БНС «Величина прожиточного минимума»: за 2023 и 2024 — годовые значения
#     из выпусков за IV квартал; за 2022 годового регионального значения в выпусках нет, оно
#     восстановлено методом БНС: (9 x среднее за 9 месяцев + октябрь + ноябрь + декабрь) / 12.
#     Проверка: тот же расчёт по стране совпал с опубликованными итогами БНС с точностью до 2 тенге.
#     В v0.2 здесь стояло приближение по соотношениям июля и августа 2024 года.
# EN: Actual annual SM by region (v0.3). Key — region code (TE), tenge per month per person.
#     Source — the BNS "Subsistence minimum" tables: for 2023 and 2024 the annual values from the
#     fourth-quarter editions; for 2022 the editions carry no annual regional value, so it is
#     rebuilt with the BNS method: (9 x nine-month average + October + November + December) / 12.
#     Check: the same calculation for the country matched the published BNS totals to within 2 tenge.
#     v0.2 used an approximation from July and August 2024 ratios here.
REGIONAL_SM = {
    2022: {
        "10": 43273, "11": 43821, "15": 40629, "19": 43721, "23": 42666,
        "27": 40448, "31": 41170, "33": 42776, "35": 41421, "39": 42610,
        "43": 39446, "47": 52366, "55": 43315, "59": 42821, "61": 41099,
        "62": 41652, "63": 44982, "71": 47811, "75": 46060, "79": 41426,
    },
    2023: {
        "10": 47828, "11": 48174, "15": 44463, "19": 48836, "23": 47060,
        "27": 44605, "31": 46601, "33": 47609, "35": 46728, "39": 46440,
        "43": 44211, "47": 61520, "55": 47774, "59": 47845, "61": 44555,
        "62": 48448, "63": 50894, "71": 54415, "75": 51048, "79": 47768,
    },
    2024: {
        "10": 50728, "11": 50136, "15": 46358, "19": 52152, "23": 48292,
        "27": 47161, "31": 48135, "33": 49284, "35": 49063, "39": 48952,
        "43": 45858, "47": 62592, "55": 49322, "59": 50010, "61": 45778,
        "62": 51569, "63": 53792, "71": 55386, "75": 54495, "79": 50146,
    },
}

# RU: Какой ПМ использовать как черту:
#     "regional" — фактический ПМ своего региона (по умолчанию; так устроены АСП и статистика);
#     "actual"   — фактический ПМ, единый по стране;
#     "budget"   — ПМ из закона о бюджете, единый по стране (как в версии 0.1).
#     С v0.3 фактические данные есть за все три года (2022–2024). Если для какого-то года их
#     нет, используется "budget".
# EN: Which SM to use as the line:
#     "regional" — the actual SM of the household's own region (default; this is how TSA and
#                  official statistics work);
#     "actual"   — the actual SM, one value for the country;
#     "budget"   — the budget-law SM, one value for the country (as in version 0.1).
#     From v0.3 actual data exists for all three years (2022–2024). If a year has none,
#     "budget" is used.
LINE_MODE = "regional"


def set_line_mode(mode: str) -> None:
    global LINE_MODE
    if mode not in ("regional", "actual", "budget"):
        raise ValueError("line mode must be 'regional', 'actual' or 'budget'")
    LINE_MODE = mode


def line_mode_used(year: int) -> str:
    """RU: какой режим реально применён для этого года. EN: the mode actually applied for this year."""
    if LINE_MODE in ("regional", "actual") and year not in ACTUAL_SM_NATIONAL:
        return "budget"
    return LINE_MODE


def sm_for_mode(df: pd.DataFrame, year: int, mode: str) -> pd.Series:
    """RU: ПМ для каждой семьи в явно заданном режиме, независимо от LINE_MODE.
       EN: the SM for each household in an explicitly given mode, regardless of LINE_MODE."""
    if mode in ("regional", "actual") and year not in ACTUAL_SM_NATIONAL:
        mode = "budget"
    if mode == "budget":
        return pd.Series(float(SUBSISTENCE_MIN[year]), index=df.index)
    nat = float(ACTUAL_SM_NATIONAL[year])
    if mode == "regional" and "region" in df.columns:
        return df["region"].astype(str).map(REGIONAL_SM[year]).fillna(nat).astype(float)
    return pd.Series(nat, index=df.index)


def sm(df: pd.DataFrame, year: int) -> pd.Series:
    """RU: прожиточный минимум для каждой семьи (тенге в месяц на человека).
       EN: the subsistence minimum for each household (tenge per month per person)."""
    return sm_for_mode(df, year, LINE_MODE)


def _wmean(x, df) -> float:
    w = df["size"].to_numpy(float)
    return float((np.asarray(x, float) * w).sum() / w.sum())


# RU: Черта для адресной социальной помощи (АСП) до 2025 года — 70% ПМ.
# EN: The targeted social assistance (TSA) line before 2025 — 70% of the SM.
TSA_SHARE = 0.70

# RU: Условная численность населения для пересчёта стоимости «на страну». Это иллюстрация.
# EN: Nominal population used to scale costs "to the country". Illustrative only.
POPULATION = 20_000_000

# RU: допуск в тенге, чтобы семья, доведённая ровно до черты, не считалась «ниже черты».
# EN: a tolerance in tenge so a household topped up exactly to the line is not counted "below" it.
EPS = 0.01

TIERS = ["A_tsa_eligible", "B_poor_not_eligible", "C_hidden_vulnerable", "D_resilient"]

# RU: Названия регионов по первым двум цифрам кода КАТО (колонка TE).
# EN: Region names by the first two digits of the KATO code (the TE column).
REGION_NAMES = {
    "10": "Abai", "11": "Akmola", "15": "Aktobe", "19": "Almaty region", "23": "Atyrau",
    "27": "West Kazakhstan", "31": "Zhambyl", "33": "Zhetisu", "35": "Karaganda", "39": "Kostanay",
    "43": "Kyzylorda", "47": "Mangystau", "55": "Pavlodar", "59": "North Kazakhstan",
    "61": "Turkestan", "62": "Ulytau", "63": "East Kazakhstan", "71": "Astana city",
    "75": "Almaty city", "79": "Shymkent city",
}


@dataclass
class StressTests:
    """RU: Стандартные стресс-тесты для поиска «скрытых уязвимых».
       EN: Standard stress tests used to find the "hidden vulnerable"."""
    main_earner_months_lost: float = 3.0   # RU: главный кормилец без заработка N месяцев / EN: main earner loses N months of earnings
    income_drop: float = 0.15              # RU: общий доход падает на 15% / EN: total income falls by 15%
    utilities_rise: float = 0.30           # RU: коммунальные платежи растут на 30% / EN: housing and utility costs rise by 30%


# =========================================================================================
# Базовые расчёты / core measures
# =========================================================================================
def per_capita(df: pd.DataFrame, income: pd.Series | None = None) -> pd.Series:
    """RU: доход на человека в месяц. EN: monthly income per person."""
    inc = df["income"] if income is None else income
    return inc / df["size"] / 12.0


def share(mask, df) -> float:
    """RU: доля людей, для которых условие верно. EN: share of people for whom the condition holds."""
    w = df["size"].to_numpy(float)
    return float((np.asarray(mask, float) * w).sum() / w.sum())


def gini(pc: pd.Series, w: pd.Series) -> float:
    """RU: коэффициент Джини по людям. EN: person-weighted Gini coefficient."""
    x, w = np.asarray(pc, float), np.asarray(w, float)
    o = np.argsort(x)
    x, w = x[o], w[o]
    cw = np.cumsum(w)
    cxw = np.cumsum(x * w)
    lorenz = cxw / cxw[-1]
    p = cw / cw[-1]
    area = np.sum((lorenz[1:] + lorenz[:-1]) / 2 * np.diff(p)) + lorenz[0] * p[0] / 2
    return float(1 - 2 * area)


def weighted_median(x, w) -> float:
    x, w = np.asarray(x, float), np.asarray(w, float)
    o = np.argsort(x)
    c = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(c, 0.5)])


def poverty_gap_cost(df, pc, line) -> float:
    """RU: сколько тенге в год нужно, чтобы поднять всех до черты.
       EN: tenge per year needed to lift everyone up to the line."""
    return float((np.maximum(0.0, line - pc) * df["size"] * 12).sum())


def stress_flags(df: pd.DataFrame, pm, st: StressTests, income=None) -> pd.DataFrame:
    """RU: для каждой семьи — провалит ли она каждый стресс-тест (доход на человека ниже ПМ).
       EN: for each household — whether it fails each stress test (per-capita income below SM)."""
    inc = df["income"] if income is None else income
    n = df["size"] * 12.0
    lost = df["main_earner_labor"] * st.main_earner_months_lost / 12.0
    return pd.DataFrame({
        "fail_earner_loss": (inc - lost) / n < pm - EPS,
        "fail_income_drop": inc * (1 - st.income_drop) / n < pm - EPS,
        "fail_utilities": (inc - df["utilities"] * st.utilities_rise) / n < pm - EPS,
    }, index=df.index)


def classify(df: pd.DataFrame, year: int, st: StressTests | None = None, income=None,
             tsa_line: float | None = None) -> pd.DataFrame:
    """
    RU: Делит семьи на четыре группы.
        A — доход ниже черты АСП (право на помощь по доходу);
        B — ниже прожиточного минимума, но выше черты АСП (бедные, которым помощь не положена);
        C — выше ПМ, но не выдерживают хотя бы один стресс-тест («скрытые уязвимые»);
        D — устойчивые.
    EN: Splits households into four tiers.
        A — income below the TSA line (income-eligible for assistance);
        B — below the subsistence minimum but above the TSA line (poor yet not eligible);
        C — above the SM but failing at least one stress test (the "hidden vulnerable");
        D — resilient.
    """
    st = st or StressTests()
    pm = sm(df, year)
    line = TSA_SHARE * pm if tsa_line is None else tsa_line
    pc = per_capita(df, income)
    f = stress_flags(df, pm, st, income)
    tier = pd.Series("D_resilient", index=df.index)
    tier[f.any(axis=1)] = "C_hidden_vulnerable"
    tier[pc < pm - EPS] = "B_poor_not_eligible"
    tier[pc < line - EPS] = "A_tsa_eligible"
    out = f.copy()
    out["pc_income"] = pc
    out["sm"] = pm
    out["tier"] = tier
    # RU: структурные причины — для объяснения «почему». EN: structural drivers — for the "why".
    inc = df["income"] if income is None else income
    safe = inc.replace(0, np.nan)
    out["drv_many_children"] = df["n_child"] >= 3
    out["drv_no_earner"] = df["n_earners"] == 0
    out["drv_one_earner_many_dependents"] = (df["n_earners"] == 1) & (df["size"] >= 4)
    out["drv_transfer_dependent"] = ((df["inc_pension"] + df["inc_child_benefit"]) / safe).fillna(0) >= 0.5
    out["drv_high_housing_burden"] = (df["utilities"] / safe).fillna(0) >= 0.10
    return out


def summary(df: pd.DataFrame, year: int, st: StressTests | None = None, income=None) -> dict:
    """RU: главные показатели одним словарём. EN: headline indicators in one dict."""
    pm = sm(df, year)
    line = TSA_SHARE * pm
    c = classify(df, year, st, income)
    pc = c["pc_income"]
    res = {
        "year": year,
        "line_mode": line_mode_used(year),
        "persons_in_sample": int(df["size"].sum()),
        "households_in_sample": int(len(df)),
        # RU: при региональном режиме — среднее по людям. EN: in regional mode — the person-weighted mean.
        "subsistence_minimum": round(_wmean(pm, df)),
        "tsa_line": round(_wmean(line, df)),
        "median_income_per_capita": round(weighted_median(pc, df["size"])),
        "poverty_rate_sm_pct": round(100 * share(pc < pm - EPS, df), 2),
        "poverty_rate_tsa_line_pct": round(100 * share(pc < line - EPS, df), 2),
        "gini": round(gini(pc, df["size"]), 4),
        "gap_to_sm_per_capita_year": round(poverty_gap_cost(df, pc, pm) / df["size"].sum()),
        "tiers_pct": {t: round(100 * share(c["tier"] == t, df), 2) for t in TIERS},
    }
    return res


# =========================================================================================
# Три черты / three lines (v0.3)
# =========================================================================================
def three_lines(df: pd.DataFrame, year: int, income=None) -> dict:
    """
    RU: Доля людей ниже трёх черт на одной и той же выборке: черта АСП (70% регионального ПМ),
        ПМ из закона о бюджете и фактический региональный ПМ. Разница между первой и третьей —
        «непокрытая полоса»: люди ниже ПМ, которым помощь по доходу не положена.
        Не зависит от LINE_MODE.
    EN: Share of people below three lines on the same sample: the TSA line (70% of the regional
        SM), the budget-law SM and the actual regional SM. The difference between the first and
        the third is the "uncovered band": people below the SM who are not income-eligible.
        Independent of LINE_MODE.
    """
    pc = per_capita(df, income)
    reg = sm_for_mode(df, year, "regional")
    bud = sm_for_mode(df, year, "budget")
    tsa = 100 * share(pc < TSA_SHARE * reg - EPS, df)
    b = 100 * share(pc < bud - EPS, df)
    r = 100 * share(pc < reg - EPS, df)
    return {
        "year": year,
        "tsa_line_tenge": round(_wmean(TSA_SHARE * reg, df)),
        "budget_sm_tenge": round(float(SUBSISTENCE_MIN[year])),
        "regional_sm_tenge": round(_wmean(reg, df)),
        "below_tsa_line_pct": round(tsa, 2),
        "below_budget_sm_pct": round(b, 2),
        "below_regional_sm_pct": round(r, 2),
        "uncovered_band_pct": round(r - tsa, 2),
        # RU: какая часть людей ниже ПМ не имеет права на АСП по доходу.
        # EN: what part of people below the SM is not income-eligible for TSA.
        "share_of_poor_not_eligible_pct": round(100 * (r - tsa) / r, 1) if r > 0 else 0.0,
    }


# =========================================================================================
# Шкала эквивалентности / equivalence scale (v0.3)
# =========================================================================================
# RU: Шкала БНС: первый член семьи считается за 1, каждый следующий — за 0,8.
#     Это проверка чувствительности. АСП по закону считается на человека, поэтому результат
#     звучит как «были бы отнесены иначе по шкале БНС», а не «АСП ошибается».
#     БНС применяет шкалу к доходам, использованным на потребление; у нас денежный доход.
# EN: The BNS scale: the first household member counts as 1, each further member as 0.8.
#     This is a sensitivity test. TSA is per-capita by law, so the result reads "would be
#     reclassified under the BNS scale", not "misclassified by TSA".
#     BNS applies the scale to income used for consumption; ours is money income.
EQUIV_WEIGHT = 0.8


def equivalent_size(df: pd.DataFrame) -> pd.Series:
    """RU: эквивалентный размер семьи. EN: equivalent household size."""
    return 1.0 + EQUIV_WEIGHT * (df["size"] - 1.0)


def per_equivalent(df: pd.DataFrame, income: pd.Series | None = None) -> pd.Series:
    """RU: доход на эквивалентного члена семьи в месяц. EN: monthly income per equivalent member."""
    inc = df["income"] if income is None else income
    return inc / equivalent_size(df) / 12.0


def _weighted_quantile(x, w, q: float) -> float:
    x, w = np.asarray(x, float), np.asarray(w, float)
    o = np.argsort(x)
    c = np.cumsum(w[o]) / w.sum()
    return float(x[o][min(np.searchsorted(c, q), len(x) - 1)])


def equivalence_test(df: pd.DataFrame, year: int, group_by: str | None = "n_child_group") -> dict:
    """
    RU: Сравнивает два способа считать доход: на человека и на эквивалентного члена семьи.
        Два чтения, и оба нужны:
        1) «та же черта» — эквивалентный доход сравнивается с тем же региональным ПМ. Доход при
           этом не падает ни у кого, поэтому бедных становится меньше по построению (до −20%
           к размеру семьи). Показывает, сколько людей шкала выводит из-под черты.
        2) «та же доля бедных» — черта поднимается так, чтобы общая доля бедных осталась прежней.
           Показывает чистую перестановку: кто входит в число бедных и кто выходит.
    EN: Compares two ways to measure income: per person and per equivalent member.
        Two readings, both needed:
        1) "same line" — equivalised income is compared with the same regional SM. Nobody's
           income falls, so poverty drops by construction. Shows how many people the scale
           lifts above the line.
        2) "same headcount" — the line is raised until the overall poverty share is unchanged.
           Shows the pure re-ranking: who enters poverty and who leaves it.
    """
    pm = sm_for_mode(df, year, "regional")
    pc, pe = per_capita(df), per_equivalent(df)
    poor_pc = pc < pm - EPS
    poor_pe = pe < pm - EPS
    tsa_pc = pc < TSA_SHARE * pm - EPS
    tsa_pe = pe < TSA_SHARE * pm - EPS
    h = share(poor_pc, df)
    # RU: множитель черты, при котором доля бедных по эквивалентному доходу равна h.
    # EN: the line multiplier at which the equivalised poverty share equals h.
    k = _weighted_quantile(pe / pm, df["size"], h) if h > 0 else 1.0
    poor_k = (pe / pm) < k
    res = {
        "year": year,
        "scale": f"1 + {EQUIV_WEIGHT:g} per additional member",
        "below_sm_per_capita_pct": round(100 * h, 2),
        "below_sm_equivalised_same_line_pct": round(100 * share(poor_pe, df), 2),
        "reclassified_out_of_poverty_pct_of_people": round(100 * share(poor_pc & ~poor_pe, df), 2),
        "reclassified_share_of_the_poor_pct": round(100 * share(poor_pc & ~poor_pe, df) / h, 1) if h > 0 else 0.0,
        "below_tsa_line_per_capita_pct": round(100 * share(tsa_pc, df), 2),
        "below_tsa_line_equivalised_same_line_pct": round(100 * share(tsa_pe, df), 2),
        "same_headcount": {
            "line_multiplier": round(k, 4),
            "below_line_pct": round(100 * share(poor_k, df), 2),
            "enter_poverty_pct_of_people": round(100 * share(~poor_pc & poor_k, df), 2),
            "leave_poverty_pct_of_people": round(100 * share(poor_pc & ~poor_k, df), 2),
        },
    }
    if group_by:
        d = df
        if group_by == "n_child_group":
            d = df.assign(n_child_group=np.select(
                [df["n_child"] == 0, df["n_child"] == 1, df["n_child"] == 2, df["n_child"] == 3],
                ["0", "1", "2", "3"], default="4+"))
        elif group_by == "size_group":
            d = df.assign(size_group=np.where(df["size"] >= 7, "7+", df["size"].astype(int).astype(str)))
        elif group_by == "n_elderly_group":
            d = df.assign(n_elderly_group=np.where(df["n_elderly"] >= 2, "2+", df["n_elderly"].astype(int).astype(str)))
        rows = []
        persons = float(df["size"].sum())
        for key, g in d.groupby(group_by):
            i = g.index
            rows.append({
                group_by: REGION_NAMES.get(str(key), str(key)) if group_by == "region" else str(key),
                "persons_pct_of_sample": round(100 * g["size"].sum() / persons, 1),
                "below_sm_per_capita_pct": round(100 * share(poor_pc[i], g), 1),
                "below_sm_equivalised_same_line_pct": round(100 * share(poor_pe[i], g), 1),
                "below_line_same_headcount_pct": round(100 * share(poor_k[i], g), 1),
            })
        res["by_group"] = rows
    return res


# =========================================================================================
# Политики / policies
# =========================================================================================
@dataclass
class Policy:
    """
    RU: Описание меры. kind:
        "tsa"             — доплата до черты (как АСП): line_share * ПМ;
        "tsa_median"      — правило 2025 года: max(median_share * медианный доход, floor_share * ПМ);
        "child_allowance" — amount тенге в месяц на каждого ребёнка в семьях с числом детей >= min_children;
        "none"            — без изменений.
    EN: A measure. kind:
        "tsa"             — top-up to a line (like TSA): line_share * SM;
        "tsa_median"      — the 2025 rule: max(median_share * median income, floor_share * SM);
        "child_allowance" — amount tenge per month per child in families with >= min_children children;
        "none"            — no change.
    """
    kind: str = "none"
    line_share: float = 0.70
    median_share: float = 0.35
    floor_share: float = 0.70
    amount: float = 0.0
    min_children: int = 1
    takeup: float = 1.0          # RU: доля обратившихся из имеющих право / EN: share of eligible who claim
    label: str = ""

    def name(self) -> str:
        if self.label:
            return self.label
        tu = "" if self.takeup >= 1 else f", take-up {self.takeup:.0%}"
        if self.kind == "tsa":
            return f"TSA top-up to {self.line_share:.0%} SM{tu}"
        if self.kind == "tsa_median":
            return f"TSA top-up to max({self.median_share:.0%} median, {self.floor_share:.0%} SM){tu}"
        if self.kind == "child_allowance":
            return f"Child allowance {self.amount:,.0f} tg/mo per child, families with {self.min_children}+ children{tu}"
        return "No change"


@dataclass
class Shock:
    """
    RU: Изменение условий. kind:
        "wages"       — все трудовые доходы падают на size (0.10 = на 10%);
        "earner_loss" — главный кормилец теряет заработок на size месяцев;
        "utilities"   — расходы на жильё и коммунальные услуги растут на size (0.30 = на 30%);
        "prices"      — общий рост цен на size при неизменных доходах (реальный доход падает);
        "none".
    EN: A change in conditions. kind:
        "wages"       — all labour income falls by size (0.10 = 10%);
        "earner_loss" — the main earner loses earnings for size months;
        "utilities"   — housing and utility costs rise by size (0.30 = 30%);
        "prices"      — a general price rise of size with incomes unchanged (real income falls);
        "none".
    """
    kind: str = "none"
    size: float = 0.0

    def name(self) -> str:
        return {
            "wages": f"Labour income -{self.size:.0%}",
            "earner_loss": f"Main earner loses {self.size:g} months of earnings",
            "utilities": f"Housing and utility costs +{self.size:.0%}",
            "prices": f"Prices +{self.size:.0%}",
        }.get(self.kind, "No shock")


def apply_shock(df: pd.DataFrame, shock: Shock | None) -> pd.Series:
    """RU: годовой доход семьи после шока. EN: household annual income after the shock."""
    inc = df["income"].astype(float).copy()
    if shock is None or shock.kind == "none":
        return inc
    if shock.kind == "wages":
        return inc - df["inc_labor"] * shock.size
    if shock.kind == "earner_loss":
        return inc - df["main_earner_labor"] * shock.size / 12.0
    if shock.kind == "utilities":
        return inc - df["utilities"] * shock.size
    if shock.kind == "prices":
        return inc / (1.0 + shock.size)
    raise ValueError(f"unknown shock kind: {shock.kind}")


def policy_line(df, year, policy: Policy, income):
    """RU: черта меры для каждой семьи (или None). EN: the measure's line for each household (or None)."""
    pm = sm(df, year)
    if policy.kind == "tsa":
        return policy.line_share * pm
    if policy.kind == "tsa_median":
        med = weighted_median(per_capita(df, income), df["size"])
        return np.maximum(policy.median_share * med, policy.floor_share * pm)
    return None


def _claims(df: pd.DataFrame, takeup: float) -> pd.Series:
    """
    RU: Кто из имеющих право реально обращается. Доля takeup выбирается псевдослучайно, но
        воспроизводимо (по номеру семьи), чтобы результат не менялся от запуска к запуску.
    EN: Who among the eligible actually claims. A takeup share is picked pseudo-randomly but
        reproducibly (from the household id), so results do not change between runs.
    """
    if takeup >= 1.0:
        return pd.Series(True, index=df.index)
    key = df["hh_id"].astype(str) if "hh_id" in df.columns else pd.Series(df.index.astype(str), index=df.index)
    u = (pd.util.hash_pandas_object(key, index=False).to_numpy() % 100_000) / 100_000.0
    return pd.Series(u < takeup, index=df.index)


def apply_policy(df: pd.DataFrame, year: int, policy: Policy | None, income: pd.Series):
    """
    RU: возвращает (годовая выплата каждой семье, черта). Выплата добавляется к доходу.
        Доплата до черты считается от дохода семьи после шока, как при обращении за АСП.
    EN: returns (annual payment per household, line). The payment is added to income.
        The top-up is computed from post-shock household income, as on a TSA application.
    """
    pay = pd.Series(0.0, index=df.index)
    if policy is None or policy.kind == "none":
        return pay, None
    if policy.kind in ("tsa", "tsa_median"):
        line = policy_line(df, year, policy, income)
        pay = np.maximum(0.0, line * 12.0 * df["size"] - income) * _claims(df, policy.takeup)
        return pay, line
    if policy.kind == "child_allowance":
        ok = df["n_child"] >= policy.min_children
        pay = ok * df["n_child"] * policy.amount * 12.0 * _claims(df, policy.takeup)
        return pay.astype(float), None
    raise ValueError(f"unknown policy kind: {policy.kind}")


def scenario(df: pd.DataFrame, year: int, policy: Policy | None = None, shock: Shock | None = None,
             st: StressTests | None = None, group_by: str | None = "hh_type") -> dict:
    """
    RU: Один сценарий: (шок) -> (мера) -> сравнение с базой.
    EN: One scenario: (shock) -> (measure) -> comparison with the baseline.
    """
    base_inc = df["income"].astype(float)
    shocked = apply_shock(df, shock)
    pay, line = apply_policy(df, year, policy, shocked)
    final = shocked + pay
    pm = sm(df, year)
    persons = float(df["size"].sum())
    cost = float(pay.sum())
    got = pay > 0
    res = {
        "year": year,
        "policy": (policy or Policy()).name(),
        "shock": (shock or Shock()).name(),
        "policy_line_tenge_month": None if line is None else round(_wmean(line, df)),
        "baseline": summary(df, year, st, base_inc),
        "after_shock": summary(df, year, st, shocked),
        "after_policy": summary(df, year, st, final),
        "cost": {
            "sample_tenge_year": round(cost),
            "per_capita_tenge_year": round(cost / persons),
            "share_of_household_income_pct": round(100 * cost / base_inc.sum(), 3),
            "illustrative_national_bln_tenge_year": round(cost / persons * POPULATION / 1e9, 1),
        },
        "poverty_gap_closed_pct": None,
        "beneficiaries": {
            "households_pct": round(100 * float(got.mean()), 2),
            "persons_pct": round(100 * share(got, df), 2),
            "avg_payment_per_person_month": round(float(pay[got].sum() / (df.loc[got, "size"].sum() * 12))) if got.any() else 0,
            # RU: доля выплат, дошедшая до тех, кто был ниже ПМ. EN: share of spending reaching those below the SM.
            "spending_to_poor_pct": round(100 * float(pay[per_capita(df, shocked) < pm - EPS].sum() / cost), 1) if cost > 0 else 0.0,
        },
    }
    g1 = res["after_shock"]["gap_to_sm_per_capita_year"]
    g2 = res["after_policy"]["gap_to_sm_per_capita_year"]
    # RU: какая часть «дефицита до ПМ» закрыта мерой. EN: share of the shortfall to the SM closed by the measure.
    res["poverty_gap_closed_pct"] = round(100 * (g1 - g2) / g1, 1) if g1 > 0 else 0.0
    if group_by:
        rows = []
        pc0, pc1, pc2 = per_capita(df, base_inc), per_capita(df, shocked), per_capita(df, final)
        c2 = classify(df, year, st, final)
        for key, g in df.groupby(group_by):
            i = g.index
            rows.append({
                group_by: REGION_NAMES.get(str(key), str(key)) if group_by == "region" else str(key),
                "persons_pct_of_sample": round(100 * g["size"].sum() / persons, 1),
                "subsistence_minimum": round(_wmean(pm[i], g)),
                "poor_baseline_pct": round(100 * share(pc0[i] < pm[i] - EPS, g), 1),
                "poor_after_shock_pct": round(100 * share(pc1[i] < pm[i] - EPS, g), 1),
                "poor_after_policy_pct": round(100 * share(pc2[i] < pm[i] - EPS, g), 1),
                "hidden_vulnerable_after_policy_pct": round(100 * share(c2.loc[i, "tier"] == "C_hidden_vulnerable", g), 1),
                "receives_payment_pct": round(100 * share(got[i], g), 1),
                "share_of_spending_pct": round(100 * float(pay[i].sum() / cost), 1) if cost > 0 else 0.0,
            })
        res["by_group"] = rows
    return res


# =========================================================================================
# Равный бюджет / equal budget
# =========================================================================================
def solve_budget(df: pd.DataFrame, year: int, policy: Policy, target_cost_per_capita: float,
                 shock: Shock | None = None, tol: float = 1.0) -> Policy:
    """
    RU: Подбирает параметр меры (черту для "tsa", размер для "child_allowance") так, чтобы
        стоимость на душу населения в год совпала с заданной. Метод деления пополам.
    EN: Tunes the measure's parameter (the line for "tsa", the amount for "child_allowance")
        so that the cost per capita per year matches the target. Bisection.
    """
    shocked = apply_shock(df, shock)
    persons = float(df["size"].sum())
    pm = float(sm(df, year).mean())

    def cost(v):
        p = Policy(**{**asdict(policy), ("line_share" if policy.kind == "tsa" else "amount"): v})
        return float(apply_policy(df, year, p, shocked)[0].sum()) / persons

    if policy.kind == "tsa":
        lo, hi = 0.0, 5.0
    elif policy.kind == "child_allowance":
        lo, hi = 0.0, 20 * pm
    else:
        raise ValueError("solve_budget supports 'tsa' and 'child_allowance'")
    for _ in range(80):
        mid = (lo + hi) / 2
        if cost(mid) < target_cost_per_capita:
            lo = mid
        else:
            hi = mid
        if abs(cost(mid) - target_cost_per_capita) < tol:
            break
    key = "line_share" if policy.kind == "tsa" else "amount"
    return Policy(**{**asdict(policy), key: (lo + hi) / 2, "label": ""})


def compare(df: pd.DataFrame, year: int, policies: list[Policy], shock: Shock | None = None,
            equal_cost_per_capita: float | None = None, st: StressTests | None = None) -> dict:
    """
    RU: Сравнивает меры рядом. Если задан equal_cost_per_capita, сначала подгоняет каждую
        меру под один и тот же бюджет — иначе «побеждает» та, что просто дороже.
    EN: Puts measures side by side. If equal_cost_per_capita is given, each measure is first
        tuned to the same budget — otherwise the more expensive one "wins" by size alone.
    """
    out = []
    for p in policies:
        if equal_cost_per_capita is not None and p.kind in ("tsa", "child_allowance"):
            p = solve_budget(df, year, p, equal_cost_per_capita, shock)
        r = scenario(df, year, p, shock, st)
        out.append(r)
    return {"year": year, "shock": (shock or Shock()).name(),
            "equal_cost_per_capita": equal_cost_per_capita, "results": out}


# =========================================================================================
# Неопределённость / uncertainty
# =========================================================================================
def bootstrap(df: pd.DataFrame, fn, B: int = 200, seed: int = 7) -> dict:
    """
    RU: Доверительный интервал 95% перевыборкой семей. fn(df) -> число или словарь чисел.
        На синтетических данных интервалы занижены (см. README организаторов, п. 6).
    EN: 95% confidence interval by resampling households. fn(df) -> a number or dict of numbers.
        On synthetic data these intervals are too narrow (organizers' README, item 6).
    """
    rng = np.random.default_rng(seed)
    base = fn(df)
    keys = list(base) if isinstance(base, dict) else None
    draws = []
    n = len(df)
    for _ in range(B):
        s = df.iloc[rng.integers(0, n, n)].reset_index(drop=True)
        v = fn(s)
        draws.append([v[k] for k in keys] if keys else v)
    a = np.asarray(draws, float)
    lo, hi = np.percentile(a, [2.5, 97.5], axis=0)
    if keys:
        return {k: {"value": base[k], "ci95": [round(float(lo[i]), 3), round(float(hi[i]), 3)]} for i, k in enumerate(keys)}
    return {"value": base, "ci95": [round(float(lo), 3), round(float(hi), 3)]}


# =========================================================================================
# Одна семья / a single household (сторона гражданина / citizen side)
# =========================================================================================
def region_code(region: str | None) -> str | None:
    """
    RU: код региона по коду или названию. «Almaty» без уточнения — это город.
    EN: region code from a code or a name. A bare "Almaty" means the city.
    """
    if region is None:
        return None
    r = str(region).strip()
    if r in REGION_NAMES:
        return r
    low = r.lower()
    for code, name in REGION_NAMES.items():
        if name.lower() == low:
            return code
    # RU: сначала города, потом области. EN: cities first, then regions.
    for suffix in (" city", " region", ""):
        for code, name in REGION_NAMES.items():
            if name.lower() == low + suffix:
                return code
    return None


def check_household(members: list[dict], utilities_month: float = 0.0, year: int = 2024,
                    st: StressTests | None = None, region: str | None = None) -> dict:
    """
    RU: Профиль одной семьи по её описанию. members — список словарей:
        {"age": 34, "labor_month": 250000, "pension_month": 0, "other_month": 0}
    EN: Profile of one household from a description. members — a list of dicts:
        {"age": 34, "labor_month": 250000, "pension_month": 0, "other_month": 0}
    """
    st = st or StressTests()
    code = region_code(region)
    labor = [12 * float(m.get("labor_month", 0)) for m in members]
    pension = 12 * sum(float(m.get("pension_month", 0)) for m in members)
    other = 12 * sum(float(m.get("other_month", 0)) for m in members)
    ages = [float(m.get("age", 30)) for m in members]
    row = pd.DataFrame([{
        "size": len(members), "n_child": sum(a < 18 for a in ages), "n_elderly": sum(a >= 63 for a in ages),
        "n_earners": sum(x > 0 for x in labor), "main_earner_labor": max(labor) if labor else 0.0,
        "inc_labor": sum(labor), "inc_pension": pension, "inc_child_benefit": 0.0,
        "income": sum(labor) + pension + other, "utilities": 12 * float(utilities_month),
        "region": code if code else "",
    }])
    c = classify(row, year, st).iloc[0]
    pc = float(c["pc_income"])
    pm = float(c["sm"])
    line = TSA_SHARE * pm
    return {
        "year": year,
        "region": REGION_NAMES.get(code, "not given: national value used") if line_mode_used(year) == "regional" else "national line",
        "line_mode": line_mode_used(year),
        "household_size": len(members),
        "income_per_capita_month": round(pc),
        "subsistence_minimum": round(pm),
        "tsa_line": round(line),
        "tier": c["tier"],
        "tsa_income_eligible": bool(pc < line - EPS),
        "tsa_topup_month_whole_family": round(max(0.0, line - pc) * len(members)),
        "margin_above_sm_month_per_capita": round(pc - pm),
        "stress_tests": {
            f"main earner loses {st.main_earner_months_lost:g} months of earnings": bool(c["fail_earner_loss"]),
            f"income falls {st.income_drop:.0%}": bool(c["fail_income_drop"]),
            f"housing and utility costs rise {st.utilities_rise:.0%}": bool(c["fail_utilities"]),
        },
        "drivers": [k[4:] for k in c.index if k.startswith("drv_") and bool(c[k])],
        "note": "Static estimate from stated income; TSA also has non-income conditions not modelled here.",
    }
