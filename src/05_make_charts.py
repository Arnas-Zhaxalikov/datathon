"""Генерация графиков для презентации. Запускать из корня репозитория после шагов 01-04.

Тема задаётся переменной окружения CHART_THEME: dark (по умолчанию, под изометрические
слайды) или light. Палитра каждой темы проверена валидатором на различимость при
дальтонизме: попарное расстояние не ниже 22 при протанопии против порога 15."""
import glob
import os

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

THEME = os.environ.get("CHART_THEME", "light")

PALETTE = {
    "dark":  dict(blue="#4A8CD4", ochre="#C07F33", purple="#9179C9", surface="#12192B",
                  ink="#F2F5F8", ink2="#B8C4D6", muted="#8494AB", grid="#26324C"),
    "light": dict(blue="#2C6CB0", ochre="#C0762A", purple="#6B5CA5", surface="#FFFFFF",
                  ink="#16223A", ink2="#4A5568", muted="#8A9099", grid="#DEDFDA"),
}[THEME]

FIG = "outputs/figures" if THEME == "light" else "outputs/figures_dark"
os.makedirs(FIG, exist_ok=True)

BLUE, OCHRE, PURPLE = PALETTE["blue"], PALETTE["ochre"], PALETTE["purple"]
SURFACE = PALETTE["surface"]
INK, INK2, MUTED, GRID = PALETTE["ink"], PALETTE["ink2"], PALETTE["muted"], PALETTE["grid"]

plt.rcParams.update({
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans",
    "font.size": 19,
    "text.color": INK,
    "axes.labelcolor": INK2,
    "axes.edgecolor": GRID,
    "axes.linewidth": 1.0,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "xtick.labelsize": 18,
    "ytick.labelsize": 18,
    "legend.frameon": False,
    "legend.fontsize": 18,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})

con = duckdb.connect()
con.execute("create view m as select * from 'outputs/households_2021_2024.parquet'")
T = {y: glob.glob(f"data/pq/t001__{y}__*.parquet")[0] for y in (2021, 2022, 2023, 2024)}
YEARS = [2021, 2022, 2023, 2024]

KATO = {10: "Абай", 11: "Акмолинская", 15: "Актюбинская", 19: "Алматинская", 23: "Атырауская",
        27: "ЗКО", 31: "Жамбылская", 33: "Жетісу", 35: "Карагандинская", 39: "Костанайская",
        43: "Кызылординская", 47: "Мангистауская", 55: "Павлодарская", 59: "СКО",
        61: "Туркестанская", 62: "Ұлытау", 63: "ВКО", 71: "Астана", 75: "Алматы", 79: "Шымкент"}


def grid_y(ax):
    ax.yaxis.grid(True, color=GRID, linewidth=1.0, linestyle="-")
    ax.set_axisbelow(True)


def grid_x(ax):
    ax.xaxis.grid(True, color=GRID, linewidth=1.0, linestyle="-")
    ax.set_axisbelow(True)


def save(fig, name):
    fig.savefig(f"{FIG}/{name}.png", bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print(f"{FIG}/{name}.png")


# 1. Динамика занятости
lab = pd.concat([con.execute(f"""
    select {y} as yr,
      100.0*sum(case when ZAN_RABOTA=1 then 1 else 0 end)/count(*) as emp,
      100.0*sum(case when ZAN_RABOTA=1 and DH_POLRESP=1 then 1 else 0 end)
        / sum(case when DH_POLRESP=1 then 1 else 0 end) as men,
      100.0*sum(case when ZAN_RABOTA=1 and DH_POLRESP=2 then 1 else 0 end)
        / sum(case when DH_POLRESP=2 then 1 else 0 end) as women
    from '{f}'""").df() for y, f in T.items()])

fig, ax = plt.subplots(figsize=(7.6, 4.3))
ax.plot(lab.yr, lab.men, "-o", color=BLUE, linewidth=2, markersize=8, label="Мужчины")
ax.plot(lab.yr, lab.women, "-o", color=OCHRE, linewidth=2, markersize=8, label="Женщины")
for x, y, c in [(lab.yr.iloc[-1], lab.men.iloc[-1], BLUE), (lab.yr.iloc[-1], lab.women.iloc[-1], OCHRE)]:
    ax.annotate(f"{y:.1f}%".replace(".", ","), (x, y), xytext=(10, -4), textcoords="offset points",
                fontsize=20, fontweight="bold", color=INK)
ax.set_xticks(YEARS)
ax.set_ylim(58, 76)
ax.set_ylabel("% занятых")
ax.legend(loc="lower left")
grid_y(ax)
ax.set_title("Уровень занятости по полу", fontsize=23, color=INK, loc="left", pad=14)
save(fig, "employment_sex")

# 2. Занятость по возрасту и полу
age = con.execute(f"""
    select case when vosr<25 then '15–24' when vosr<35 then '25–34' when vosr<45 then '35–44'
                when vosr<55 then '45–54' when vosr<65 then '55–64' else '65+' end as ag,
           DH_POLRESP as sex,
           100.0*sum(case when ZAN_RABOTA=1 then 1 else 0 end)/count(*) as emp
    from '{T[2024]}' where vosr >= 15 group by 1,2 order by 1,2""").df()
p = age.pivot(index="ag", columns="sex", values="emp")
x = np.arange(len(p))
fig, ax = plt.subplots(figsize=(7.6, 4.3))
ax.bar(x - 0.21, p[1], 0.40, color=BLUE, label="Мужчины")
ax.bar(x + 0.21, p[2], 0.40, color=OCHRE, label="Женщины")
ax.set_xticks(x)
ax.set_xticklabels(p.index)
ax.set_ylabel("% занятых")
ax.set_ylim(0, 100)
ax.legend(loc="upper right")
grid_y(ax)
ax.set_title("Занятость по возрасту, 2024", fontsize=23, color=INK, loc="left", pad=14)
save(fig, "employment_age")

# 3. Изменение занятости по регионам
parts = []
for y, f in T.items():
    d = con.execute(f"select TE, 100.0*sum(case when ZAN_RABOTA=1 then 1 else 0 end)/count(*) as v from '{f}' group by 1").df()
    d["yr"] = y
    parts.append(d)
reg = pd.concat(parts).pivot(index="TE", columns="yr", values="v").dropna()
reg["ch"] = reg[2024] - reg[2021]
reg = reg.sort_values("ch")
names = [KATO.get(int(i), str(i)) for i in reg.index]
fig, ax = plt.subplots(figsize=(7.4, 6.4))
ax.barh(names, reg.ch, height=0.68, color=[OCHRE if v < 0 else BLUE for v in reg.ch])
ax.axvline(0, color=INK2, linewidth=1.2)
for i, v in enumerate(reg.ch):
    ax.annotate(f"{v:+.1f}".replace(".", ","), (v, i), xytext=(7 if v >= 0 else -7, 0), textcoords="offset points",
                va="center", ha="left" if v >= 0 else "right", fontsize=17, color=INK2)
ax.set_xlabel("изменение, п.п.")
ax.set_xlim(-7.5, 8.5)
grid_x(ax)
ax.set_title("Занятость: изменение 2021 → 2024", fontsize=23, color=INK, loc="left", pad=14)
save(fig, "employment_region")

# 4. Неформальная занятость: регионы и аномалия
inf = pd.concat([con.execute(f"""
    select TE, 100.0*sum(case when ORB_TRDDOG=2 then 1 else 0 end)
      / nullif(sum(case when ORB_TRDDOG is not null then 1 else 0 end),0) as v from '{f}' group by 1""").df()
    .assign(yr=y) for y, f in T.items()])
a19 = inf[inf.TE == 19].sort_values("yr")
rest = inf[(inf.yr == 2024) & (inf.TE != 19)].sort_values("v", ascending=False).head(8)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.3),
                              gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.42})
ax1.plot(a19.yr, a19.v, "-o", color=OCHRE, linewidth=2, markersize=9)
ax1.annotate("40,7%", (a19.yr.iloc[-1], a19.v.iloc[-1]), xytext=(-64, -6),
             textcoords="offset points", fontsize=22, fontweight="bold", color=INK)
ax1.set_xticks(YEARS)
ax1.set_ylim(0, 46)
ax1.set_ylabel("% без договора")
grid_y(ax1)
ax1.set_title("Алматинская область", fontsize=22, color=INK, loc="left", pad=12)
n2 = [KATO.get(int(i), str(i)) for i in rest.TE]
ax2.barh(n2[::-1], rest.v.values[::-1], height=0.66, color=BLUE)
for i, v in enumerate(rest.v.values[::-1]):
    ax2.annotate(f"{v:.1f}".replace(".", ","), (v, i), xytext=(6, 0), textcoords="offset points",
                 va="center", fontsize=17, color=INK2)
ax2.set_xlabel("% без договора")
ax2.set_xlim(0, 16)
ax2.set_xticks([0, 4, 8, 12, 16])
grid_x(ax2)
ax2.set_title("Остальные регионы, 2024", fontsize=22, color=INK, loc="left", pad=12)
save(fig, "informality_anomaly")

# 5. Город и село
ur = con.execute("""
    select case when K=1 then 'Город' else 'Село' end as s,
      avg(area_total) as area, avg(amenities_42) as amen, avg(hh_size) as size,
      100.0*avg(case when has_land=1 then 1.0 else 0 end) as land
    from m where year=2024 group by 1 order by 1""").df().set_index("s")
panels = [("Площадь жилья, м²", "area", 0, 95), ("Удобств из 42", "amen", 0, 16),
          ("Размер домохозяйства", "size", 0, 4.4), ("Есть земля, %", "land", 0, 100)]
fig, axes = plt.subplots(1, 4, figsize=(12.6, 3.7))
for ax, (title, col, lo, hi) in zip(axes, panels):
    vals = [ur.loc["Город", col], ur.loc["Село", col]]
    ax.bar(["Город", "Село"], vals, width=0.58, color=[BLUE, OCHRE])
    for i, v in enumerate(vals):
        ax.annotate(f"{v:,.1f}".replace(",", " ").replace(".", ","), (i, v), xytext=(0, 7),
                    textcoords="offset points", ha="center", fontsize=20, fontweight="bold", color=INK)
    ax.set_ylim(lo, hi)
    ax.set_title(title, fontsize=20, color=INK2, pad=12)
    ax.tick_params(axis="y", labelleft=False, length=0)
    ax.spines["left"].set_visible(False)
save(fig, "urban_rural")

# 6. Типы домохозяйств
ht = con.execute("""
    with t as (select *, case
        when hh_size=1 then 'Одиночки'
        when n_child=0 and n_elderly>0 then 'Пожилые без детей'
        when n_child>=3 then 'Многодетные, 3+'
        when n_child>0 then 'С детьми'
        else 'Взрослые без детей' end as ty
      from m where year=2024 and income_total>0)
    select ty, avg(income_pc)/12 as inc, avg(sat_mean) as sat, count(*) as n
    from t group by 1 order by inc desc""").df()
emph = ht.ty.isin(["С детьми", "Многодетные, 3+"])
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.6, 4.2),
                              gridspec_kw={"width_ratios": [1.5, 1], "wspace": 0.12})
ax1.barh(ht.ty[::-1], ht.inc[::-1], height=0.66,
         color=[OCHRE if e else BLUE for e in emph[::-1]])
for i, v in enumerate(ht.inc[::-1]):
    ax1.annotate(f"{v:,.0f}".replace(",", " "), (v, i), xytext=(7, 0), textcoords="offset points",
                 va="center", fontsize=18, fontweight="bold", color=INK)
ax1.set_xlabel("тыс. тенге в месяц")
ax1.set_xlim(0, 200000)
ax1.set_xticks([0, 50000, 100000, 150000, 200000])
ax1.set_xticklabels(["0", "50", "100", "150", "200"])
grid_x(ax1)
ax1.set_title("Доход на душу, 2024", fontsize=22, color=INK, loc="left", pad=14)
ax2.barh(ht.ty[::-1], ht.sat[::-1], height=0.66,
         color=[OCHRE if e else BLUE for e in emph[::-1]])
for i, v in enumerate(ht.sat[::-1]):
    ax2.annotate(f"{v:.2f}".replace(".", ","), (v, i), xytext=(7, 0), textcoords="offset points",
                 va="center", fontsize=18, color=INK2)
ax2.set_xlim(6.8, 8.2)
ax2.set_xticks([7.0, 7.5, 8.0])
ax2.set_xticklabels(["7,0", "7,5", "8,0"])
ax2.set_xlabel("удовлетворённость, 1–10")
ax2.tick_params(axis="y", labelleft=False, length=0)
ax2.spines["left"].set_visible(False)
grid_x(ax2)
ax2.set_title("Удовлетворённость", fontsize=22, color=INK, loc="left", pad=14)
save(fig, "household_types")

# 7. Квинтили по доходу
qt = con.execute("""
    with q as (select *, ntile(5) over (order by income_pc) as qu
               from m where year=2024 and income_total>0)
    select qu, avg(income_pc)/12 as inc, avg(hh_size) as size, avg(n_child) as child
    from q group by 1 order by 1""").df()
labels = [f"Q{i}" for i in qt.qu]
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.0),
                              gridspec_kw={"wspace": 0.26})
ax1.bar(labels, qt.inc, width=0.6, color=BLUE)
for i, v in enumerate(qt.inc):
    ax1.annotate(f"{v:,.0f}".replace(",", " "), (i, v), xytext=(0, 7), textcoords="offset points",
                 ha="center", fontsize=18, color=INK2)
ax1.set_ylabel("")
ax1.set_ylim(0, 245000)
ax1.set_yticks([0, 50000, 100000, 150000, 200000])
ax1.set_yticklabels(["0", "50", "100", "150", "200"])
grid_y(ax1)
ax1.set_title("Доход на душу, тыс. тг/мес", fontsize=22, color=INK, loc="left", pad=14)
ax2.bar(labels, qt["size"], width=0.6, color=OCHRE)
for i, v in enumerate(qt["size"]):
    ax2.annotate(f"{v:.2f}".replace(".", ","), (i, v), xytext=(0, 7), textcoords="offset points",
                 ha="center", fontsize=18, fontweight="bold", color=INK)
ax2.set_ylabel("")
ax2.set_ylim(0, 5.9)
grid_y(ax2)
ax2.set_title("Человек в домохозяйстве", fontsize=22, color=INK, loc="left", pad=14)
save(fig, "quintiles")

# 8. Разрыв доходов и расходов
tot = con.execute("""
    select year, avg(income_total)/12 as inc, avg(spend_total)/12 as sp
    from m where income_total>0 and spend_total>0 group by year order by year""").df()
parts = []
for v in (9, 10):
    for f in glob.glob(f"data/pq/d004__2024__*kv__kv_vopr{v}.parquet"):
        cols = [c[0] for c in con.execute(f"describe select * from '{f}'").fetchall()]
        grs = [c for c in cols if c.startswith("GR")]
        expr = " + ".join([f"coalesce(try_cast({c} as double),0)" for c in grs])
        parts.append(f"select NOMER, ({expr}) as v from '{f}'")
con.execute("create or replace view food as select NOMER, sum(v) as fv from (" +
            " union all ".join(parts) + ") group by NOMER")
sav = con.execute("""
    select median(savings_rate) as now_,
           median(100.0*(m.income_total - m.spend_total - coalesce(food.fv,0))/m.income_total) as with_food
    from m left join food using (NOMER)
    where m.year=2024 and m.income_total>0 and m.spend_total>0""").df().iloc[0]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.8, 4.2),
                              gridspec_kw={"width_ratios": [1.3, 1], "wspace": 0.28})
ax1.plot(tot.year, 100 * tot.inc / tot.inc.iloc[0], "-o", color=BLUE, linewidth=2, markersize=8, label="Доходы")
ax1.plot(tot.year, 100 * tot.sp / tot.sp.iloc[0], "-o", color=OCHRE, linewidth=2, markersize=8, label="Расходы")
ax1.annotate("+54%", (tot.year.iloc[-1], 100 * tot.inc.iloc[-1] / tot.inc.iloc[0]),
             xytext=(-52, 4), textcoords="offset points", fontsize=20, fontweight="bold", color=INK)
ax1.annotate("+43%", (tot.year.iloc[-1], 100 * tot.sp.iloc[-1] / tot.sp.iloc[0]),
             xytext=(-52, -20), textcoords="offset points", fontsize=20, fontweight="bold", color=INK)
ax1.set_ylim(96, 162)
ax1.set_xticks(YEARS)
ax1.set_ylabel("")
ax1.legend(loc="upper left")
grid_y(ax1)
ax1.set_title("Индекс, 2021 = 100", fontsize=22, color=INK, loc="left", pad=14)
bars = ["наш расчёт", "+ еда,\nмаксимум", "Казахстан,\nфакт"]
vals = [sav.now_, sav.with_food, 12.5]
fig_colors = [OCHRE, OCHRE, BLUE]
ax2.bar(bars, vals, width=0.58, color=fig_colors)
for i, v in enumerate(vals):
    ax2.annotate(f"{v:.1f}%".replace(".", ","), (i, v), xytext=(0, 7), textcoords="offset points",
                 ha="center", fontsize=20, fontweight="bold", color=INK)
ax2.set_ylabel("")
ax2.set_ylim(0, 82)
grid_y(ax2)
ax2.set_title("Норма сбережений, %", fontsize=22, color=INK, loc="left", pad=14)
save(fig, "savings_gap")

# 9. Межформенные корреляции
df24 = con.execute("select * from m where year=2024").df()
pairs = [
    ("Доля занятых ~ доход на душу", "emp_ratio", "income_pc", "структурные"),
    ("Площадь жилья ~ размер домохозяйства", "area_total", "hh_size", "структурные"),
    ("Доход ~ расход", "income_total", "spend_total", "уровневые"),
    ("Площадь жилья ~ число детей", "area_total", "n_child", "структурные"),
    ("Предметы ДП ~ доход", "durables_46", "income_total", "уровневые"),
    ("Благоустройство ~ доход", "amenities_42", "income_total", "уровневые"),
    ("Образование главы ~ доход", "head_edu", "income_total", "уровневые"),
    ("Благоустройство ~ удовлетворённость", "amenities_42", "sat_mean", "уровневые"),
]
rows = []
for label, a, b, kind in pairs:
    d = df24[[a, b]].dropna()
    rows.append({"label": label, "r": d[a].corr(d[b]), "kind": kind})
cor = pd.DataFrame(rows).sort_values("r")
fig, ax = plt.subplots(figsize=(8.8, 4.6))
colors = [BLUE if k == "структурные" else OCHRE for k in cor.kind]
ax.hlines(cor.label, 0, cor.r, color=colors, linewidth=2)
ax.plot(cor.r, cor.label, "o", markersize=10, color="none", markeredgewidth=0)
for (lab_, r, k), c in zip(cor.itertuples(index=False), colors):
    ax.plot([r], [lab_], "o", markersize=10, color=c)
    ax.annotate(f"{r:.3f}".replace(".", ","), (r, lab_), xytext=(11 if r >= 0 else -11, 0),
                textcoords="offset points", va="center", ha="left" if r >= 0 else "right",
                fontsize=17, color=INK2)
ax.axvline(0, color=INK2, linewidth=1.2)
ax.set_xlim(-0.02, 0.44)
ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4])
ax.set_xticklabels(["0", "0,1", "0,2", "0,3", "0,4"])
ax.set_xlabel("коэффициент корреляции Пирсона")
grid_x(ax)
handles = [plt.Line2D([], [], color=BLUE, marker="o", linewidth=2, markersize=9,
                      label="Структура домохозяйства"),
           plt.Line2D([], [], color=OCHRE, marker="o", linewidth=2, markersize=9,
                      label="Уровень жизни")]
ax.legend(handles=handles, loc="lower right")
ax.set_title("Работают структурные признаки, уровневые — нет", fontsize=23, color=INK, loc="left", pad=14)
save(fig, "correlations")

# 10. Заполненность таблиц
comp = pd.read_csv("outputs/aggregates/completeness.csv").sort_values("filled_pct").head(10)
fig, ax = plt.subplots(figsize=(8.4, 4.9))
ax.barh(comp.table[::-1], comp.filled_pct[::-1], height=0.68,
        color=[OCHRE if v < 50 else BLUE for v in comp.filled_pct[::-1]])
for i, v in enumerate(comp.filled_pct[::-1]):
    ax.annotate(f"{v:.0f}%", (v, i), xytext=(6, 0), textcoords="offset points",
                va="center", fontsize=17, color=INK2)
ax.set_xlim(0, 100)
ax.set_xlabel("% непустых ячеек")
ax.tick_params(axis="y", labelsize=12)
grid_x(ax)
ax.set_title("Заполненность: анкеты с ветвлениями — на треть", fontsize=22, color=INK, loc="left", pad=14)
save(fig, "completeness")

# 11. Предприятия в форме 1-Т
firms = []
for y in YEARS:
    f = glob.glob(f"data/pq/1t_god__{y}__*.parquet")[0]
    firms.append({"yr": y, "n": con.execute(f"select count(distinct ID) from '{f}'").fetchone()[0]})
fr = pd.DataFrame(firms)
fig, ax = plt.subplots(figsize=(7.2, 4.0))
ax.bar(fr.yr.astype(str), fr.n, width=0.58, color=[BLUE, BLUE, BLUE, OCHRE])
for i, v in enumerate(fr.n):
    ax.annotate(f"{v:,}".replace(",", " "), (i, v), xytext=(0, 7), textcoords="offset points",
                ha="center", fontsize=20, color=INK)
ax.set_ylabel("предприятий в выборке")
ax.set_ylim(0, 98000)
grid_y(ax)
ax.set_title("Охват формы 1-Т меняется: обвал в 2024", fontsize=22, color=INK, loc="left", pad=14)
save(fig, "firms_by_year")

print(f"\nГотово: {len(os.listdir(FIG))} файлов в {FIG}/ (тема {THEME})")
