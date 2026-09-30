"""Анализ объединённой таблицы домохозяйств."""
import duckdb, pandas as pd, numpy as np, os

con = duckdb.connect()
M = "outputs/households_2021_2024.parquet"
con.execute(f"create view m as select * from '{M}'")
os.makedirs("outputs/aggregates", exist_ok=True)
pd.set_option("display.width", 220)
sep = lambda t: print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)

sep("1. КОНТРОЛЬ СУММ — среднее на домохозяйство в месяц, тенге")
chk = con.execute("""
  select year,
         count(*) as hh,
         round(avg(income_total)/12) as income_month,
         round(avg(spend_total)/12)  as spend_month,
         round(avg(income_wage)/12)  as wage_month,
         round(100*avg(income_wage)/avg(income_total),1) as wage_share_pct,
         round(avg(hh_size),2) as hh_size
  from m where income_total > 0 and spend_total > 0 group by year order by year""").df()
print(chk.to_string(index=False))
chk.to_csv("outputs/aggregates/m_totals_by_year.csv", index=False)

sep("2. РАЗРЫВ СБЕРЕЖЕНИЙ — норма сбережений, %")
gap = con.execute("""
  select year, settlement,
         count(*) as hh,
         round(median(income_total)/12) as income_med_month,
         round(median(spend_total)/12)  as spend_med_month,
         round(median(savings_rate),1)  as savings_rate_median,
         round(100.0*sum(case when savings_abs < 0 then 1 else 0 end)/count(*),1) as pct_deficit
  from m where income_total > 0 and spend_total > 0
  group by year, settlement order by settlement, year""").df()
print(gap.to_string(index=False))
gap.to_csv("outputs/aggregates/m_savings_gap.csv", index=False)

sep("3. РАЗРЫВ ПО КВИНТИЛЯМ ДОХОДА, 2024")
qt = con.execute("""
  with q as (select *, ntile(5) over (order by income_pc) as quintile
             from m where year = 2024 and income_total > 0 and spend_total > 0)
  select quintile, count(*) as hh,
         round(avg(income_pc)/12) as income_pc_month,
         round(avg(spend_pc)/12)  as spend_pc_month,
         round(median(savings_rate),1) as savings_rate,
         round(avg(hh_size),2) as hh_size,
         round(100.0*sum(case when settlement like 'село%' then 1 else 0 end)/count(*),1) as rural_pct,
         round(avg(amenities_42),1) as amenities
  from q group by quintile order by quintile""").df()
print(qt.to_string(index=False))
qt.to_csv("outputs/aggregates/m_quintiles_2024.csv", index=False)

sep("4. ГОРОД И СЕЛО — полный профиль, 2024")
ur = con.execute("""
  select settlement, count(*) as hh,
         round(avg(hh_size),2) as hh_size, round(avg(n_child),2) as children,
         round(avg(n_elderly),2) as elderly, round(avg(emp_ratio),3) as emp_ratio,
         round(avg(area_total),1) as area_m2, round(avg(area_pc),1) as area_pc,
         round(avg(amenities_42),1) as amenities_42, round(avg(durables_46),1) as durables_46,
         round(avg(income_total)/12) as income_month, round(avg(spend_total)/12) as spend_month,
         round(median(savings_rate),1) as savings_rate,
         round(100.0*avg(case when has_land = 1 then 1.0 else 0 end),1) as has_land_pct,
         round(avg(sat_mean),2) as satisfaction
  from m where year = 2024 group by settlement order by settlement""").df()
print(ur.T.to_string())
ur.to_csv("outputs/aggregates/m_urban_rural_2024.csv", index=False)

sep("5. ЖИЛИЩНАЯ ДЕПРИВАЦИЯ ПО РЕГИОНАМ, 2024")
KATO = {10:"Абай",11:"Акмолинская",15:"Актюбинская",19:"Алматинская",23:"Атырауская",27:"ЗКО",
        31:"Жамбылская",33:"Жетісу",35:"Карагандинская",39:"Костанайская",43:"Кызылординская",
        47:"Мангистауская",55:"Павлодарская",59:"СКО",61:"Туркестанская",62:"Ұлытау",63:"ВКО",
        71:"Астана",75:"Алматы",79:"Шымкент"}
dep = con.execute("""
  select TE, count(*) as hh, round(avg(amenities_42),1) as amenities,
         round(avg(dep_index),1) as deprivation,
         round(avg(income_total)/12) as income_month,
         round(avg(area_pc),1) as area_pc,
         round(100.0*avg(case when settlement like 'село%' then 1.0 else 0 end),1) as rural_pct
  from m where year = 2024 group by TE order by deprivation desc""").df()
dep["region"] = dep.TE.map(KATO)
print(dep[["region","hh","amenities","deprivation","income_month","area_pc","rural_pct"]].to_string(index=False))
dep.to_csv("outputs/aggregates/m_deprivation_by_region.csv", index=False)

sep("6. ТИПЫ ДОМОХОЗЯЙСТВ, 2024")
ht = con.execute("""
  with t as (select *,
       case when hh_size = 1 then 'одиночка / single'
            when n_child = 0 and n_elderly > 0 then 'пожилые без детей / elderly'
            when n_child >= 3 then 'многодетные / 3+ children'
            when n_child > 0 then 'с детьми / with children'
            else 'взрослые без детей / adults only' end as hh_type
       from m where year = 2024 and income_total > 0 and spend_total > 0)
  select hh_type, count(*) as hh, round(avg(hh_size),2) as size,
         round(avg(income_pc)/12) as income_pc_month, round(avg(spend_pc)/12) as spend_pc_month,
         round(median(savings_rate),1) as savings_rate,
         round(avg(amenities_42),1) as amenities, round(avg(sat_mean),2) as satisfaction
  from t group by hh_type order by income_pc_month desc""").df()
print(ht.to_string(index=False))
ht.to_csv("outputs/aggregates/m_household_types_2024.csv", index=False)

sep("7. КОРРЕЛЯЦИИ МЕЖДУ ПРИЗНАКАМИ (README обещает ослабление примерно вдвое)")
df = con.execute("select * from m where year = 2024").df()
pairs = [
    ("area_total","hh_size","площадь жилья ~ размер домохозяйства"),
    ("area_total","n_child","площадь жилья ~ число детей"),
    ("amenities_42","income_total","благоустройство ~ доход"),
    ("durables_46","income_total","предметы ДП ~ доход"),
    ("income_total","spend_total","доход ~ расход"),
    ("income_pc","sat_mean","доход на душу ~ удовлетворённость"),
    ("amenities_42","sat_mean","благоустройство ~ удовлетворённость"),
    ("head_edu","income_total","образование главы ~ доход"),
    ("emp_ratio","income_pc","доля занятых ~ доход на душу"),
]
rows = []
for a, b, label in pairs:
    d = df[[a, b]].dropna()
    r = d[a].corr(d[b])
    rows.append({"pair": label, "n": len(d), "pearson_r": round(r, 3),
                 "spearman": round(d[a].corr(d[b], method="spearman"), 3)})
cor = pd.DataFrame(rows)
print(cor.to_string(index=False))
cor.to_csv("outputs/aggregates/m_correlations_2024.csv", index=False)

sep("8. РЕГРЕССИЯ: что объясняет доход на душу, 2024")
d = df[["income_pc","head_edu","emp_ratio","amenities_42","durables_46","hh_size","K","n_child"]].dropna()
d = d[(d.income_pc > 0) & (d.income_pc < d.income_pc.quantile(0.99))]
y = np.log(d.income_pc.values)
X = np.column_stack([np.ones(len(d)), d.head_edu, d.emp_ratio, d.amenities_42,
                     d.durables_46, d.hh_size, (d.K == 2).astype(float), d.n_child])
names = ["константа", "образование главы", "доля занятых", "благоустройство",
         "предметы ДП", "размер домохозяйства", "село", "число детей"]
beta, *_ = np.linalg.lstsq(X, y, rcond=None)
resid = y - X @ beta
s2 = resid @ resid / (len(y) - X.shape[1])
se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
tv = beta / se
r2 = 1 - (resid @ resid) / ((y - y.mean()) @ (y - y.mean()))
ols = pd.DataFrame({"переменная": names, "коэффициент": beta.round(4),
                    "ст.ошибка": se.round(4), "t": tv.round(1)})
print(ols.to_string(index=False))
print(f"\nn = {len(d):,},  R² = {r2:.3f}   (зависимая переменная: log дохода на душу)")
print("Стандартные ошибки на синтетике занижены (README организатора) — значимость трактовать осторожно.")
ols.to_csv("outputs/aggregates/m_ols_income_2024.csv", index=False)

sep("9. ДИНАМИКА НОРМЫ СБЕРЕЖЕНИЙ, 2021–2024")
dyn = con.execute("""
  select year,
         round(median(case when settlement like 'город%' then savings_rate end),1) as urban,
         round(median(case when settlement like 'село%'  then savings_rate end),1) as rural,
         round(median(savings_rate),1) as all_hh
  from m where income_total > 0 and spend_total > 0 group by year order by year""").df()
print(dyn.to_string(index=False))
dyn.to_csv("outputs/aggregates/m_savings_dynamics.csv", index=False)
print("\nГотово. Агрегаты в outputs/aggregates/")

sep("10. ПРОВЕРКА РАЗРЫВА: полнота расходов")
print("""Расходы собраны по вопросам 1-7, где есть денежное поле STOIMK.
Продовольствие записано в вопросах 9-10 в натуральных и смешанных единицах и в STOIMK не попадает.
Ниже — верхняя граница: все числовые поля вопросов 9-10 засчитаны как тенге.""")
import glob as _g
parts = []
for v in (9, 10):
    for f in _g.glob("data/pq/d004__2024__*kv__kv_vopr{}.parquet".format(v)):
        cols = [c[0] for c in con.execute(f"describe select * from '{f}'").fetchall()]
        grs = [c for c in cols if c.startswith("GR")]
        expr = " + ".join([f"coalesce(try_cast({c} as double),0)" for c in grs])
        parts.append(f"select NOMER, ({expr}) as v from '{f}'")
con.execute("create or replace view food as select NOMER, sum(v) as food_v from (" +
            " union all ".join(parts) + ") group by NOMER")
sens = con.execute("""
  select count(*) as hh,
    round(avg(m.income_total)/12) as income_month,
    round(avg(m.spend_total)/12)  as spend_q1_q7_month,
    round(avg(coalesce(food.food_v,0))/12) as food_upper_bound_month,
    round(median(m.savings_rate),1) as savings_rate_now,
    round(median(100.0*(m.income_total - m.spend_total - coalesce(food.food_v,0))
                 / m.income_total),1) as savings_rate_with_food
  from m left join food using (NOMER)
  where m.year = 2024 and m.income_total > 0 and m.spend_total > 0""").df()
print(sens.to_string(index=False))
sens.to_csv("outputs/aggregates/m_gap_sensitivity.csv", index=False)
print("""
ВЫВОД
Даже при самой щедрой оценке продовольствия норма сбережений остаётся около 57%.
Реальный показатель для Казахстана — порядка 10-15%. Значит, разрыв не поведенческий:
блоки доходов и расходов в синтетике откалиброваны независимо, и их совместное
распределение не воспроизведено. Это ограничение достоверности не указано в README.""")
