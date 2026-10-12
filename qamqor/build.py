"""
Qamqor AI — сборка общей таблицы домохозяйств / building the shared household table.

RU: Склеивает D-008 (состав семьи) и D-004 (доходы каждого человека, расходы на жильё и
    коммунальные услуги) по ключу NOMER в одну таблицу «одна строка = одно домохозяйство за год».
EN: Joins D-008 (household roster) and D-004 (per-person income, housing and utility spending)
    on the NOMER key into one table where one row = one household-year.

Запуск / Run:
    python build.py /path/to/data  /path/to/out

RU: Важные допущения помечены словом ASSUMPTION — их нужно сверить с бланками форм.
EN: Key assumptions are tagged ASSUMPTION — they must be checked against the form blanks.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# RU: 2021 год не берём — в D-008 за 2021 нет года рождения, значит нет числа детей.
# EN: 2021 is skipped — D-008 for 2021 has no birth year, so children cannot be counted.
YEARS = [2022, 2023, 2024]

GR = [f"GR{i}" for i in range(1, 24)]

# ASSUMPTION ------------------------------------------------------------------------------
# RU: Смысл колонок доходов (kv_vopr11) восстановлен по самим данным (возраст, пол, суммы),
#     а не по бланку. Уверенно: GR1, GR2, GR4, GR5. GR8 — вероятно. Остальное — «прочее».
# EN: Meaning of the income columns (kv_vopr11) is inferred from the data itself (age, sex,
#     amounts), not from the blank. Confident: GR1, GR2, GR4, GR5. GR8 — probable. Rest — "other".
INCOME_GROUPS = {
    "wage": ["GR1"],            # RU: зарплата / EN: wages
    "self_emp": ["GR2"],        # RU: самозанятость, бизнес / EN: self-employment, business
    "pension": ["GR4"],         # RU: пенсия / EN: pension
    "stipend": ["GR5"],         # RU: стипендия / EN: scholarship
    "child_benefit": ["GR8"],   # RU: пособия на детей (вероятно) / EN: child benefits (probable)
}
_known = {c for cols in INCOME_GROUPS.values() for c in cols}
INCOME_GROUPS["other"] = [c for c in GR if c not in _known]

CHILD_AGE = 18      # RU: ребёнок — младше 18 / EN: child — under 18
ELDERLY_AGE = 63    # RU: пожилой — 63 и старше / EN: elderly — 63 and over


def _quarters(data: Path, year: int, table: str, usecols=None) -> pd.DataFrame:
    """RU: читает таблицу D-004 за все 4 квартала. EN: reads a D-004 table for all 4 quarters."""
    frames = []
    for q in range(1, 5):
        f = data / "d004" / str(year) / f"{q}kv" / f"{table}.csv"
        frames.append(pd.read_csv(f, dtype=str, usecols=usecols))
    return pd.concat(frames, ignore_index=True)


def build_year(data: Path, year: int):
    # ---- D-008: люди / persons ----------------------------------------------------------
    roster = pd.read_csv(data / "d008" / str(year) / "kontr_k.csv", dtype=str)
    persons = roster[["NOMER", "NOMP", "TE", "K", "POL", "RODSTVO"]].copy()
    persons["age"] = year - pd.to_numeric(roster["GOD_ROJD"], errors="coerce")
    persons["female"] = (persons["POL"] == "2").astype(int)

    # ---- D-004 kv_vopr0: какие кварталы опрошены / which quarters were interviewed -------
    # RU: REZ=2 — квартал без данных (интервью не состоялось). Годовые суммы пересчитываем
    #     на 4 квартала по числу опрошенных кварталов.
    # EN: REZ=2 — a quarter with no data (no interview). Annual sums are scaled to 4 quarters
    #     by the number of interviewed quarters.
    v0 = _quarters(data, year, "kv_vopr0", ["NOMER", "REZ", "KVARTAL"])
    n_q = v0[v0["REZ"] == "1"].groupby("NOMER")["KVARTAL"].nunique().rename("n_quarters")

    # ---- D-004 kv_vopr11: доходы каждого человека / per-person income ---------------------
    inc = _quarters(data, year, "kv_vopr11", ["NOMER", "NOMP", "KVARTAL"] + GR)
    inc[GR] = inc[GR].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    for name, cols in INCOME_GROUPS.items():
        inc[name] = inc[cols].sum(axis=1)
    groups = list(INCOME_GROUPS)
    p_inc = inc.groupby(["NOMER", "NOMP"])[groups].sum().reset_index()
    persons = persons.merge(p_inc, on=["NOMER", "NOMP"], how="left")
    persons[groups] = persons[groups].fillna(0.0)
    persons["labor"] = persons["wage"] + persons["self_emp"]
    persons["income"] = persons[groups].sum(axis=1)
    persons["year"] = year

    # ---- D-004 kv_vopr2: жильё и коммунальные услуги / housing and utilities --------------
    util = _quarters(data, year, "kv_vopr2", ["NOMER", "STOIMK"])
    util["STOIMK"] = pd.to_numeric(util["STOIMK"], errors="coerce").fillna(0.0)
    utilities = util.groupby("NOMER")["STOIMK"].sum().rename("utilities")

    # ---- домохозяйства / households -------------------------------------------------------
    g = persons.groupby("NOMER")
    hh = pd.DataFrame({
        "year": year,
        "region": g["TE"].first(),
        # ASSUMPTION: K=1 — город, K=2 — село (Астана, Алматы, Шымкент целиком K=1).
        #             K=1 urban, K=2 rural (Astana, Almaty, Shymkent are entirely K=1).
        "urban": (g["K"].first() == "1").astype(int),
        "size": g.size(),
        "n_child": g["age"].apply(lambda a: int((a < CHILD_AGE).sum())),
        "n_child_u7": g["age"].apply(lambda a: int((a < 7).sum())),
        "n_elderly": g["age"].apply(lambda a: int((a >= ELDERLY_AGE).sum())),
        "n_earners": g["labor"].apply(lambda x: int((x > 0).sum())),
        "main_earner_labor": g["labor"].max(),
    })
    hh["n_working_age"] = hh["size"] - hh["n_child"] - hh["n_elderly"]
    for name in groups + ["labor", "income"]:
        hh[f"inc_{name}" if name != "income" else "income"] = g[name].sum()
    hh = hh.join(utilities).join(n_q)
    hh["utilities"] = hh["utilities"].fillna(0.0)
    hh["n_quarters"] = hh["n_quarters"].fillna(0).astype(int)

    # RU: убираем семьи без единого опрошенного квартала; остальным приводим суммы к году.
    # EN: drop households with no interviewed quarter; scale the rest to a full year.
    hh = hh[hh["n_quarters"] > 0].copy()
    k = 4.0 / hh["n_quarters"]
    money = ["income", "main_earner_labor", "utilities"] + [c for c in hh.columns if c.startswith("inc_")]
    hh[money] = hh[money].mul(k, axis=0)

    hh.index.name = "hh_id"
    hh["hh_type"] = household_type(hh)
    return hh.reset_index(), persons


def household_type(hh: pd.DataFrame) -> pd.Series:
    """RU: понятный тип семьи для таблиц. EN: a readable household type for tables."""
    adults = hh["size"] - hh["n_child"]
    t = pd.Series("working_age_no_children", index=hh.index)
    t[hh["n_child"].between(1, 3)] = "children_1_3"
    t[hh["n_child"] >= 4] = "children_4plus"                      # многодетные / large families
    t[(hh["n_child"] >= 1) & (adults == 1)] = "single_adult_with_children"
    t[(hh["n_child"] == 0) & (hh["n_elderly"] == hh["size"])] = "pensioners_only"
    return t


def main():
    data = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("out")
    out.mkdir(parents=True, exist_ok=True)
    hh_all, p_all = [], []
    for y in YEARS:
        hh, persons = build_year(data, y)
        hh_all.append(hh)
        p_all.append(persons)
        print(f"{y}: households {len(hh):,}, persons {len(persons):,}")
    pd.concat(hh_all, ignore_index=True).to_csv(out / "households.csv", index=False)
    pd.concat(p_all, ignore_index=True).to_csv(out / "persons.csv", index=False)
    print("saved ->", out)


if __name__ == "__main__":
    main()
