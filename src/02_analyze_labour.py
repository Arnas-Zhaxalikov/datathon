import duckdb, pandas as pd, glob, os
con = duckdb.connect(); con.execute("PRAGMA memory_limit='1800MB'")
pd.set_option('display.width', 220)
OUT = "outputs/aggregates"; os.makedirs(OUT, exist_ok=True)
T = {y: f"data/pq/t001__{y}__" + ("2021" if y == 2021 else "baza") + ".parquet" for y in [2021, 2022, 2023, 2024]}

print("==== 1. LABOUR MARKET (T-001) ====")
rows = []
for y, f in T.items():
    r = con.execute(f"""
      select {y} yr, count(*) n,
        100.0*sum(case when ZAN_RABOTA='1' then 1 else 0 end)/count(*) emp_rate,
        100.0*sum(case when PSK_RABOTA='1' then 1 else 0 end)/count(*) searching,
        sum(case when ORB_TRDDOG is not null then 1 else 0 end) contract_base,
        100.0*sum(case when ORB_TRDDOG='2' then 1 else 0 end)/nullif(sum(case when ORB_TRDDOG is not null then 1 else 0 end),0) no_contract,
        100.0*sum(case when ZAN_RABOTA='1' and DH_POLRESP='2' then 1 else 0 end)/sum(case when DH_POLRESP='2' then 1 else 0 end) emp_female,
        100.0*sum(case when ZAN_RABOTA='1' and DH_POLRESP='1' then 1 else 0 end)/sum(case when DH_POLRESP='1' then 1 else 0 end) emp_male
      from '{f}'""").df()
    rows.append(r)
lab = pd.concat(rows); lab.to_csv(f"{OUT}/labour_by_year.csv", index=False)
print(lab.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

print("\n-- employment rate by region and year (pivot, %)")
parts = []
for y, f in T.items():
    d = con.execute(f"select TE reg, 100.0*sum(case when ZAN_RABOTA='1' then 1 else 0 end)/count(*) v from '{f}' group by 1").df()
    d['yr'] = y; parts.append(d)
piv = pd.concat(parts).pivot(index='reg', columns='yr', values='v').round(1)
piv['change'] = (piv[2024] - piv[2021]).round(1)
piv.to_csv(f"{OUT}/employment_by_region.csv")
print(piv.sort_values('change').to_string())

print("\n-- no-contract rate by region (%), base = respondents with the variable filled")
parts = []
for y, f in T.items():
    d = con.execute(f"""select TE reg, 100.0*sum(case when ORB_TRDDOG='2' then 1 else 0 end)/
      nullif(sum(case when ORB_TRDDOG is not null then 1 else 0 end),0) v from '{f}' group by 1""").df()
    d['yr'] = y; parts.append(d)
piv2 = pd.concat(parts).pivot(index='reg', columns='yr', values='v').round(1)
piv2.to_csv(f"{OUT}/informality_by_region.csv")
print(piv2.sort_values(2024, ascending=False).to_string())

print("\n-- education (DH_OBRAZOV) x employment, 2024")
print(con.execute(f"""select DH_OBRAZOV edu, count(*) n,
  100.0*sum(case when ZAN_RABOTA='1' then 1 else 0 end)/count(*) emp_rate
  from '{T[2024]}' group by 1 order by 1""").df().to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

print("\n==== 2. HOUSEHOLD INCOME (D-004 q11) ====")
rows = []
for y in [2021, 2022, 2023, 2024]:
    fs = [f"data/pq/d004__{y}__{q}kv__kv_vopr11.parquet" for q in [1, 2, 3, 4]]
    fs = [f for f in fs if os.path.exists(f)]
    u = " union all ".join(f"select * from '{f}'" for f in fs)
    d = con.execute(f"""select {y} yr, count(distinct NOMER) hh, sum(GR1) wage_inc, sum(GR4) col4,
        sum(try_cast(GR22 as double)) col22 from ({u})""").df()
    rows.append(d)
inc = pd.concat(rows)
inc['wage_per_hh_month'] = inc.wage_inc / inc.hh / 12
inc.to_csv(f"{OUT}/income_by_year.csv", index=False)
print(inc.to_string(index=False, float_format=lambda x: f"{x:,.0f}"))

print("\n==== 3. HOUSEHOLD SPENDING (D-004 q1..q7, all quarters) ====")
rows = []
for y in [2021, 2022, 2023, 2024]:
    tot = {}
    for v in [1, 2, 3, 4, 5, 6, 7]:
        fs = [f"data/pq/d004__{y}__{q}kv__kv_vopr{v}.parquet" for q in [1, 2, 3, 4]]
        fs = [f for f in fs if os.path.exists(f)]
        if not fs: continue
        u = " union all ".join(f"select STOIMK from '{f}'" for f in fs)
        tot[f"q{v}"] = con.execute(f"select sum(try_cast(STOIMK as double)) from ({u})").fetchone()[0]
    tot['yr'] = y
    rows.append(tot)
sp = pd.DataFrame(rows).set_index('yr')
sp['total'] = sp.sum(axis=1)
sp.to_csv(f"{OUT}/spending_by_question.csv")
print((sp / 1e9).round(2).to_string())
print("growth 2021->2024, %:", ((sp.loc[2024] / sp.loc[2021] - 1) * 100).round(1).to_dict())

print("\n==== 4. HOUSING (D-006) ====")
rows = []
for y, f in [(2021, 'data/pq/d006__2021__rio.parquet'), (2022, 'data/pq/d006__2022__rio2022.parquet'),
             (2023, 'data/pq/d006__2023__rio2023.parquet'), (2024, 'data/pq/d006__2024__rio_2024.parquet')]:
    amen = " + ".join([f"case when U{i}='1' then 1 else 0 end" for i in range(1, 43)])
    d = con.execute(f"""select {y} yr, count(*) hh, avg(try_cast(OB_PL as double)) area,
      avg(try_cast(KOL_K as double)) rooms, avg(({amen})) amenities_of_42 from '{f}'""").df()
    rows.append(d)
hz = pd.concat(rows); hz.to_csv(f"{OUT}/housing_by_year.csv", index=False)
print(hz.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))

print("\n==== 5. DATA COMPLETENESS BY FORM-YEAR (share of non-null cells, %) ====")
rows = []
for f in sorted(glob.glob('data/pq/*.parquet')):
    key = os.path.basename(f)[:-8]
    if key.startswith('d004') and '1kv' not in key: continue
    cols = [c[0] for c in con.execute(f"describe select * from '{f}'").fetchall()]
    expr = " + ".join([f'count("{c}")' for c in cols])
    filled, n = con.execute(f"select ({expr})::double, count(*) from '{f}'").fetchone()
    rows.append((key, n, len(cols), round(100 * filled / (n * len(cols)), 1)))
comp = pd.DataFrame(rows, columns=['table', 'rows', 'cols', 'filled_pct'])
comp.to_csv(f"{OUT}/completeness.csv", index=False)
print(comp.sort_values('filled_pct').head(15).to_string(index=False))
print("...")
print(comp.sort_values('filled_pct').tail(8).to_string(index=False))
