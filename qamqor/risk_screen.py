"""
Qamqor AI — оценка риска без данных о доходе / the income-free risk screen.

RU: Применяет сохранённую логистическую регрессию (её обучает и сохраняет poverty_challenge.py)
    к одной семье. На вход — только состав семьи, регион и город/село. Дохода, числа работающих
    и ничего, посчитанного из дохода, здесь нет и передать их нельзя.
    Вероятность на экран не выводится: она переводится в место в рейтинге семей 2024 года
    («риск выше, чем у X% людей выборки»). Это фильтр, а не решение: решение о помощи
    принимается по доходу.
EN: Applies the saved logistic regression (trained and saved by poverty_challenge.py) to one
    household. The input is household composition, region and urban/rural only. Income, the
    number of earners and anything derived from income are not here and cannot be passed.
    The probability is not shown: it is turned into a place in the ranking of the 2024
    households ("risk higher than X% of people in the sample"). This is a filter, not a
    decision: eligibility is decided on income.

Пример / Example:
    import risk_screen
    risk_screen.screen(size=6, n_child=4, region="Shymkent city")
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import engine as E
import household_rules as HR

DIR = Path(__file__).resolve().parent / "results" / "poverty_challenge"
MODEL_PATH, SCORES_PATH = DIR / "model_logit.joblib", DIR / "scores_2024.csv"

# RU: признаки модели, кроме региона; порядок важен. EN: the model features besides region; the order matters.
BASE_FEATURES = ["size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban"]
# RU: в названии признака не может быть ничего из этого списка. EN: no feature name may contain any of these.
FORBIDDEN = ("income", "inc_", "earner", "labor", "wage", "pension", "stipend", "benefit", "utilit", "gr1", "gr2")
# RU: Астана, Алматы и Шымкент целиком городские. EN: Astana, Almaty and Shymkent are entirely urban.
CITY_REGIONS = {"71", "75", "79"}
HIGH, ELEVATED = 90.0, 80.0   # RU: границы уровней, место в рейтинге. EN: level bounds, place in the ranking.
# RU: группы для объяснения: признаки, связанные между собой, показываются вместе.
# EN: groups for the explanation: features tied to each other are shown together.
GROUPS = {"children": ("n_child", "n_child_u7"), "household_size": ("size", "n_working_age"),
          "elderly": ("n_elderly",), "urban": ("urban",)}

_STATE: dict | None = None


def feature_names() -> list[str]:
    """RU: полный список признаков модели. EN: the full list of model features."""
    return BASE_FEATURES + [f"region_{name}" for name in sorted(E.REGION_NAMES.values())]


def design(hh: pd.DataFrame) -> pd.DataFrame:
    """RU: таблица признаков из таблицы семей; колонки дохода не читаются. EN: the feature table; no income column is read."""
    X = hh[BASE_FEATURES].astype(float).copy()
    names = hh["region"].astype(str).map(E.REGION_NAMES)
    for name in sorted(E.REGION_NAMES.values()):
        X[f"region_{name}"] = (names == name).astype(float)
    return X[feature_names()]


def load(model_path: Path | None = None, scores_path: Path | None = None) -> dict:
    """RU: загрузить модель и распределение рисков один раз. EN: load the model and the risk distribution once."""
    global _STATE
    import joblib
    mp, sp = Path(model_path or MODEL_PATH), Path(scores_path or SCORES_PATH)
    if not mp.exists() or not sp.exists():
        raise FileNotFoundError("risk model not built, run poverty_challenge.py")
    bundle = joblib.load(mp)
    scores = pd.read_csv(sp).sort_values("risk")
    _STATE = {"bundle": bundle, "risks": scores["risk"].to_numpy(float),
              "cum": np.cumsum(scores["size"].to_numpy(float)), "total": float(scores["size"].sum())}
    return _STATE


def _state() -> dict:
    return _STATE if _STATE is not None else load()


def percentile(risk: float) -> float:
    """RU: доля людей выборки 2024 года с риском строго ниже, %. EN: share of 2024 sample people with strictly lower risk, %."""
    s = _state()
    i = int(np.searchsorted(s["risks"], round(float(risk), 6), side="left"))
    return round(100.0 * (s["cum"][i - 1] if i else 0.0) / s["total"], 1)


def level(pct: float) -> str:
    return "high" if pct >= HIGH else "elevated" if pct >= ELEVATED else "usual"


def predict(X: pd.DataFrame) -> np.ndarray:
    """RU: риск по сохранённой модели, 6 знаков. EN: the saved model's risk, 6 decimals."""
    b = _state()["bundle"]
    return np.round(b["model"].predict_proba(X[b["features"]].to_numpy(float))[:, 1], 6)


def _factors(x: np.ndarray) -> list[dict]:
    """RU: вклад признаков в логарифм шансов относительно средней семьи обучения: коэффициент × отклонение.
       EN: feature contributions to the log-odds against the average training household: coefficient × deviation."""
    b = _state()["bundle"]
    scaler, lr = b["model"].named_steps["standardscaler"], b["model"].named_steps["logisticregression"]
    contrib = dict(zip(b["features"], lr.coef_[0] * (x - scaler.mean_) / scaler.scale_))
    groups = {**GROUPS, "region": tuple(f for f in b["features"] if f.startswith("region_"))}
    out = [{"key": k, "contribution": round(float(sum(contrib[f] for f in cols)), 3)} for k, cols in groups.items()]
    for f in out:
        f["direction"] = "raises" if f["contribution"] > 0.02 else "lowers" if f["contribution"] < -0.02 else "neutral"
    return sorted(out, key=lambda f: -abs(f["contribution"]))


def screen(size: int, n_child: int = 0, n_child_u7: int = 0, n_elderly: int = 0, region: str = "",
           urban: bool | None = None) -> dict:
    """
    RU: Оценка одной семьи. region — название как в engine.REGION_NAMES или код. urban=None: город
        для Астаны, Алматы и Шымкента, иначе тоже город (и это возвращается как допущение).
    EN: Screens one household. region is a name as in engine.REGION_NAMES or a code. urban=None:
        urban for Astana, Almaty and Shymkent, otherwise urban too (returned as an assumption).
    """
    code = str(region) if str(region) in E.REGION_NAMES else {v: k for k, v in E.REGION_NAMES.items()}.get(str(region))
    if code is None:
        raise ValueError(f"unknown region: {region!r}")
    size, n_child, n_child_u7, n_elderly = int(size), int(n_child), int(n_child_u7), int(n_elderly)
    HR.check(size, n_child, n_child_u7, n_elderly)   # RU: невозможную семью не считаем. EN: an impossible household is not computed.
    assumed_urban = urban is None and code not in CITY_REGIONS
    is_urban = True if code in CITY_REGIONS or urban is None else bool(urban)
    row = pd.DataFrame([{"size": size, "n_child": n_child, "n_child_u7": n_child_u7, "n_elderly": n_elderly,
                         "n_working_age": size - n_child - n_elderly, "urban": int(is_urban), "region": code}])
    X = design(row)
    b = _state()["bundle"]
    risk = float(predict(X)[0])
    pct = percentile(risk)
    return {
        "risk_rank_pct": pct,
        "rank_text": f"risk higher than {pct}% of people in the {b['test_year']} sample",
        "level": level(pct),
        "levels": {"high": f"top {100 - HIGH:g}%", "elevated": f"top {100 - ELEVATED:g}% but not top {100 - HIGH:g}%", "usual": "the rest"},
        # RU: только факторы, которые есть у этой семьи: без детей нет фактора «дети», без пожилых — «пожилые».
        # EN: only factors this household has: no children, no "children" factor; no elderly, no "elderly" factor.
        "factors": [f for f in _factors(X.to_numpy(float)[0])
                    if not (f["key"] == "children" and n_child == 0) and not (f["key"] == "elderly" and n_elderly == 0)],
        "factors_compared_with": f"the average household of the {b['train_years'][0]}-{b['train_years'][-1]} sample",
        "inputs": {**row.drop(columns="region").iloc[0].astype(int).to_dict(), "region": E.REGION_NAMES[code],
                   "urban_assumed": assumed_urban},
        "model": {"kind": "logistic regression", "version": b["version"], "trained_at": b["trained_at"],
                  "train_years": b["train_years"], "test_year": b["test_year"], "test_auc": b["test_auc"],
                  "recall_top20_pct": b["recall_top20_pct"]},
        "explain_nodes": ["metric:risk_screen_recall_top20_2024", "metric:risk_screen_auc_2024", "caveat:risk_screen_filter"],
    }
