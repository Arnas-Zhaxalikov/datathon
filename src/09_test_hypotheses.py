"""Проверка H1 и H2 из docs/hypotheses.md на households_2021_2024.parquet."""
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, LinearRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

sep = lambda t: print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)

df = pd.read_parquet("outputs/households_2021_2024.parquet")

# ---------------------------------------------------------------------------
# H1 — бедность определяется структурой домохозяйства, не доходом.
# Классификатор риска (нижний квинтиль дохода на душу) на структурных
# признаках, train 2021-2023 -> test 2024 (учитывая отсутствие панели —
# это просто разные годовые срезы, не прогноз одного и того же домохозяйства).
# ---------------------------------------------------------------------------
sep("H1 — скоринг риска бедности на структурных признаках")

h1 = df.dropna(subset=["income_pc", "n_child", "emp_ratio", "hh_size", "settlement"]).copy()
h1 = h1[h1.income_pc > 0]

train = h1[h1.year <= 2023].copy()
test = h1[h1.year == 2024].copy()

# порог риска — нижний квинтиль ПО ОБУЧАЮЩЕЙ выборке (не подглядываем в тест)
threshold = train.income_pc.quantile(0.2)
train["at_risk"] = (train.income_pc <= threshold).astype(int)
test["at_risk"] = (test.income_pc <= threshold).astype(int)

features = ["n_child", "emp_ratio", "hh_size"]
X_train = train[features].copy()
X_train["settlement_rural"] = (train.settlement == "село").astype(int)
X_test = test[features].copy()
X_test["settlement_rural"] = (test.settlement == "село").astype(int)

scaler = StandardScaler().fit(X_train)
clf = LogisticRegression(max_iter=1000).fit(scaler.transform(X_train), train.at_risk)
pred = clf.predict_proba(scaler.transform(X_test))[:, 1]
auc = roc_auc_score(test.at_risk, pred)

print(f"Обучение: 2021-2023, n={len(train):,}, порог риска (нижний квинтиль дохода на душу)={threshold:,.0f} тг/мес")
print(f"Тест: 2024, n={len(test):,}, доля 'at_risk' в тесте={test.at_risk.mean():.1%}")
print(f"ROC-AUC на 2024 (год, не видимый при обучении): {auc:.3f}")
print("Коэффициенты (на стандартизованных признаках):")
for name, coef in zip(X_train.columns, clf.coef_[0]):
    print(f"  {name:20} {coef:+.3f}")
print(
    "\nВывод: AUC существенно выше 0.5 => структурные признаки (дети, доля "
    "занятых, размер семьи, село) предсказывают риск бедности в ГОД, "
    "не участвовавший в обучении => H1 подтверждена."
    if auc > 0.65
    else "\nВывод: AUC недостаточно высок, H1 требует пересмотра признаков."
)

# ---------------------------------------------------------------------------
# H2 — город/село объясняет инфраструктурный доступ лучше, чем доход.
# Два отдельных R²: housing/amenity индекс ~ K (село/город) vs ~ доход.
# ---------------------------------------------------------------------------
sep("H2 — город/село vs доход как предиктор инфраструктурного доступа")

h2 = df.dropna(subset=["dep_index", "income_pc", "settlement", "has_land", "area_pc"]).copy()
h2 = h2[(h2.income_pc > 0) & (h2.year == 2024)]

targets = {
    "dep_index (депривация по 42 удобствам, инверсия amenities_42)": "dep_index",
    "has_land (доля участков)": "has_land",
    "area_pc (площадь на душу)": "area_pc",
}

for label, col in targets.items():
    y = h2[col].astype(float)

    x_settlement = pd.get_dummies(h2.settlement, drop_first=True).astype(float)
    r2_settlement = LinearRegression().fit(x_settlement, y).score(x_settlement, y)

    x_income = h2[["income_pc"]].astype(float)
    r2_income = LinearRegression().fit(x_income, y).score(x_income, y)

    winner = "город/село" if r2_settlement > r2_income else "доход"
    print(
        f"{label:55} R²(город/село)={r2_settlement:.4f}  R²(доход)={r2_income:.4f}  "
        f"сильнее: {winner}"
    )

print(
    "\nВывод: если R²(город/село) систематически выше R²(доход) по всем трём "
    "целям => H2 подтверждена — разрез город/село структурно сильнее дохода "
    "как предиктор инфраструктурного доступа."
)
