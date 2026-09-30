"""
Сборка единой таблицы домохозяйств из форм D-серии / Building the merged household table from the D-series.

Ключ связи / join key: NOMER (идентификатор домохозяйства внутри года).
Формы / forms: d008 (состав), d006 (жильё), d004 (расходы и доходы), d002 (субъективные оценки).
"""
import duckdb, glob, os, pandas as pd

con = duckdb.connect()
con.execute("PRAGMA memory_limit='4GB'")
PQ, OUT = "data/pq", "outputs"
os.makedirs(OUT, exist_ok=True)

AMEN = " + ".join([f"case when cast(U{i} as varchar)='1' then 1 else 0 end" for i in range(1, 43)])
TDP  = " + ".join([f"case when TDP{i} is not null then 1 else 0 end" for i in range(1, 47)])
# шкалы удовлетворённости: значения >10 — служебные коды («затрудняюсь», «не применимо»)
SAT  = " , ".join([f"case when GR{i} <= 10 then GR{i} end" for i in range(1, 6)])

frames = []
for Y in (2021, 2022, 2023, 2024):
    roster  = glob.glob(f"{PQ}/d008__{Y}__*.parquet")[0]
    housing = glob.glob(f"{PQ}/d006__{Y}__*.parquet")[0]
    subj    = glob.glob(f"{PQ}/d002__{Y}__subject.parquet")[0]
    inc_fs  = glob.glob(f"{PQ}/d004__{Y}__*kv__kv_vopr11.parquet")
    sp_fs   = [f for v in range(1, 8) for f in glob.glob(f"{PQ}/d004__{Y}__*kv__kv_vopr{v}.parquet")]

    has_birth = "GOD_ROJD" in [c[0] for c in con.execute(f"describe select * from '{roster}'").fetchall()]
    age_expr  = f"({Y} - GOD_ROJD)" if has_birth else "cast(null as int)"

    inc_u = " union all ".join(f"select * from '{f}'" for f in inc_fs)
    sp_u  = " union all ".join(f"select NOMER, try_cast(STOIMK as double) as s from '{f}'" for f in sp_fs)
    gr_all = " + ".join([f"coalesce(try_cast(GR{i} as double),0)" for i in range(1, 24)])

    q = f"""
    with R as (
      select NOMER, any_value(TE) as TE, any_value(K) as K,
             any_value(KOL_CHL) as hh_size, count(*) as n_rows,
             sum(case when {age_expr} < 15 then 1 else 0 end)  as n_child,
             sum(case when {age_expr} >= 65 then 1 else 0 end) as n_elderly,
             sum(case when STATUS = 1 then 1 else 0 end)       as n_employed,
             sum(case when POL = 2 then 1 else 0 end)          as n_female,
             any_value(case when RODSTVO = 1 then POL end)     as head_sex,
             any_value(case when RODSTVO = 1 then UROV end)    as head_edu,
             any_value(case when RODSTVO = 1 then STATUS end)  as head_status,
             any_value(case when RODSTVO = 1 then {age_expr} end) as head_age
      from '{roster}' group by NOMER
    ),
    H as (
      select NOMER, try_cast(TIP_J as int) as dwelling_type, try_cast(VLAD1 as int) as tenure,
             try_cast(KOL_K as double) as rooms, try_cast(OB_PL as double) as area_total,
             try_cast(J_PL as double) as area_living, try_cast(ZEM as int) as has_land,
             ({AMEN}) as amenities_42, ({TDP}) as durables_46
      from '{housing}'
    ),
    I as (
      select NOMER, sum({gr_all}) as income_total,
             sum(coalesce(try_cast(GR1 as double),0)) as income_wage,
             sum(coalesce(try_cast(GR4 as double),0)) as income_transfers
      from ({inc_u}) group by NOMER
    ),
    S as (select NOMER, sum(s) as spend_total from ({sp_u}) group by NOMER),
    B as (select NOMER, least(GR1,10) as sat_1, least(GR2,10) as sat_2,
                 list_avg([{SAT}]) as sat_mean from '{subj}')
    select {Y} as year, R.*, H.* exclude (NOMER), I.* exclude (NOMER),
           S.spend_total, B.* exclude (NOMER)
    from R left join H using (NOMER) left join I using (NOMER)
           left join S using (NOMER) left join B using (NOMER)
    """
    df = con.execute(q).df()
    frames.append(df)
    print(f"{Y}: {len(df):,} домохозяйств / households, "
          f"жильё {df.area_total.notna().sum():,}, доходы {df.income_total.notna().sum():,}, "
          f"расходы {df.spend_total.notna().sum():,}, оценки {df.sat_mean.notna().sum():,}")

m = pd.concat(frames, ignore_index=True)

# Производные признаки / derived features
m["income_pc"]     = m.income_total / m.hh_size
m["spend_pc"]      = m.spend_total / m.hh_size
m["savings_abs"]   = m.income_total - m.spend_total
m["savings_rate"]  = 100 * m.savings_abs / m.income_total
m["area_pc"]       = m.area_total / m.hh_size
m["dep_index"]     = 100 * (1 - m.amenities_42 / 42)      # индекс жилищной депривации
m["settlement"]    = m.K.map({1: "город / urban", 2: "село / rural"})
m["emp_ratio"]     = m.n_employed / m.hh_size

con.register("m_df", m)
con.execute(f"copy m_df to '{OUT}/households_2021_2024.parquet' (format parquet, compression zstd)")
m.to_csv(f"{OUT}/households_2021_2024.csv", index=False)
print(f"\nИтого / total: {len(m):,} строк, {m.shape[1]} колонок")
print(f"Файл / file: {OUT}/households_2021_2024.parquet "
      f"({os.path.getsize(f'{OUT}/households_2021_2024.parquet')/1e6:.1f} МБ)")
print("\nКолонки / columns:", list(m.columns))
