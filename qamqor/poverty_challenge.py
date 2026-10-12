"""
Qamqor AI — poverty prediction challenge (modelled on the World Bank "Pover-T Tests", 2018).

Tests one hypothesis with two parts, on income-free features only:
  H4a  an income-free model identifies poor households well, and better than category rules;
  H4b  logistic regression is not meaningfully worse than gradient boosting or an ensemble.

The label is built from income (engine.py), but NO feature is: no income amount and nothing
derived from the income records. n_earners comes from those records, so it appears only in a
separately labelled sensitivity run that never enters the verdicts.

Run:
    python poverty_challenge.py out/households.csv results/poverty_challenge
        [--persons out/persons.csv]   adds feature set B (member aggregates)
        [--raw <RAW_DATA_DIR>]        adds feature set C (D-006 housing items, needs --persons)
"""
from __future__ import annotations

import argparse
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score, roc_curve
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import engine as E
import risk_screen

warnings.filterwarnings("ignore")
SEED = 20261012
TRAIN_YEARS, TEST_YEAR = (2022, 2023), 2024
NEAR = 1.25
SHARES = (0.10, 0.20, 0.30)
N_BOOT = 1000
T0 = time.time()

# Verdict thresholds, fixed before any result is computed.
AUC_MIN = 0.75          # H4a: the best simple model must reach this AUC on the temporal test
MARGIN = 0.01           # H4b: non-inferiority margin for (complex - simple) AUC

SIMPLE = ("logistic_l2", "logistic_l1")
COMPLEX = ("random_forest", "lightgbm", "blend_logistic_lightgbm")
RULES = {"3+ children": 3, "4+ children": 4}

# Feature families for grouped permutation importance.
FAMILIES = {
    "children": ("n_child", "n_child_u7", "child_share", "share_under7", "single_adult_with_children"),
    "age structure": ("n_elderly", "n_working_age", "elderly_share", "size", "age_mean", "age_min", "age_max",
                      "n_adults_18_62", "adults_18_62_share"),
    "head and sex": ("head_age", "head_female", "n_adult_women", "n_adult_men", "adult_women_share", "adult_men_share"),
    "urban/rural": ("urban",),
    "employment (sensitivity only)": ("n_earners",),
}


def say(msg: str) -> None:
    print(f"[{time.time() - T0:5.0f}s] {msg}", flush=True)


# ---------------------------------------------------------------------------------------------
# Data, labels, features
# ---------------------------------------------------------------------------------------------
def load_households(path: str) -> pd.DataFrame:
    hh = pd.read_csv(path, dtype={"hh_id": str, "region": str})
    return hh[hh["year"].isin(TRAIN_YEARS + (TEST_YEAR,))].reset_index(drop=True)


def add_labels(hh: pd.DataFrame) -> pd.DataFrame:
    """poor: income per person below the regional subsistence minimum of that year."""
    hh = hh.copy()
    line = pd.concat([E.sm_for_mode(part, int(y), "regional") for y, part in hh.groupby("year")]).reindex(hh.index)
    pc = E.per_capita(hh)
    hh["poor"] = (pc < line).astype(int)
    hh["poor_or_near"] = (pc < NEAR * line).astype(int)
    return hh


def class_balance(hh: pd.DataFrame) -> list[dict]:
    rows = []
    for y, d in hh.groupby("year"):
        w = d["size"]
        rows.append({"year": int(y), "households": len(d),
                     "poor_households_pct": round(100 * d["poor"].mean(), 2),
                     "poor_people_pct": round(100 * (d["poor"] * w).sum() / w.sum(), 2),
                     "poor_or_near_people_pct": round(100 * (d["poor_or_near"] * w).sum() / w.sum(), 2)})
    return rows


def features_a(hh: pd.DataFrame) -> pd.DataFrame:
    """Set A: household composition and location."""
    X = hh[["size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban"]].astype(float).copy()
    X["child_share"] = hh["n_child"] / hh["size"]
    X["elderly_share"] = hh["n_elderly"] / hh["size"]
    region = pd.get_dummies(hh["region"].map(E.REGION_NAMES).fillna(hh["region"]), prefix="region", dtype=float)
    return pd.concat([X, region], axis=1)


def head_evidence(persons: pd.DataFrame) -> tuple[str, pd.DataFrame]:
    """The RODSTVO code of the household head: the code that appears exactly once in almost every household."""
    key = ["year", "NOMER"]
    n_hh = persons.groupby(key).ngroups
    counts = persons.groupby(key + ["RODSTVO"]).size().rename("n").reset_index()
    ev = counts.groupby("RODSTVO").agg(households_with_code=("n", "size"), exactly_once=("n", lambda s: int((s == 1).sum())),
                                       persons=("n", "sum"))
    ev["exactly_once_pct_of_all_households"] = (100 * ev["exactly_once"] / n_hh).round(2)
    ev = ev.sort_values("exactly_once_pct_of_all_households", ascending=False)
    mean_age = persons.groupby("RODSTVO")["age"].mean().round(1).rename("mean_age")
    return str(ev.index[0]), ev.join(mean_age)


def features_b(hh: pd.DataFrame, persons: pd.DataFrame, head_code: str) -> pd.DataFrame:
    """Set B: A plus aggregates over household members (age, sex, the head). No income columns are read."""
    p = persons[["NOMER", "year", "RODSTVO", "age", "female"]].copy()
    p["NOMER"] = p["NOMER"].astype(str)
    adult = p["age"] >= 18
    p["adult_woman"], p["adult_man"] = (adult & (p["female"] == 1)).astype(int), (adult & (p["female"] == 0)).astype(int)
    p["adult_18_62"], p["under7"] = p["age"].between(18, 62).astype(int), (p["age"] < 7).astype(int)
    g = p.groupby(["year", "NOMER"])
    agg = g.agg(age_mean=("age", "mean"), age_min=("age", "min"), age_max=("age", "max"), n_adult_women=("adult_woman", "sum"),
                n_adult_men=("adult_man", "sum"), n_adults_18_62=("adult_18_62", "sum"), n_under7=("under7", "sum"), n=("age", "size"))
    head = p[p["RODSTVO"].astype(str) == head_code].groupby(["year", "NOMER"]).agg(head_age=("age", "first"), head_female=("female", "first"))
    agg = agg.join(head)
    for c in ("n_adult_women", "n_adult_men", "n_adults_18_62"):
        agg[c.replace("n_", "", 1) + "_share" if c != "n_adults_18_62" else "adults_18_62_share"] = agg[c] / agg["n"]
    agg["share_under7"] = agg["n_under7"] / agg["n"]
    agg = agg.drop(columns=["n", "n_under7"]).reset_index().rename(columns={"NOMER": "hh_id"})
    B = hh[["year", "hh_id"]].merge(agg, on=["year", "hh_id"], how="left").drop(columns=["year", "hh_id"])
    B.index = hh.index
    B["single_adult_with_children"] = ((hh["size"] - hh["n_child"] == 1) & (hh["n_child"] >= 1)).astype(float)
    B = B.fillna(B.median(numeric_only=True))
    return pd.concat([features_a(hh), B.astype(float)], axis=1)


def features_c(hh: pd.DataFrame, base: pd.DataFrame, raw: Path) -> pd.DataFrame:
    """Set C: B plus D-006 housing and asset items (rio*.csv), joined on NOMER. Optional."""
    frames = []
    for y in sorted(hh["year"].unique()):
        parts = [pd.read_csv(f, dtype=str) for f in sorted((raw / "d006" / str(y)).glob("rio*.csv"))]
        if not parts:
            continue
        d = parts[0]
        for extra in parts[1:]:
            d = d.merge(extra[[c for c in extra.columns if c == "NOMER" or c not in d.columns]], on="NOMER", how="outer")
        d = d.drop_duplicates("NOMER")
        d["year"] = y
        frames.append(d)
    if not frames:
        raise FileNotFoundError(f"no d006/<year>/rio*.csv under {raw}")
    d6 = pd.concat(frames, ignore_index=True).rename(columns={"NOMER": "hh_id"})
    items = d6.drop(columns=["hh_id", "year"])
    items = items.loc[:, items.isna().mean() <= 0.60]                 # drop columns more than 60% empty
    items = items.loc[:, items.nunique(dropna=True) > 1]
    cat = [c for c in items if items[c].nunique(dropna=True) <= 12]
    num = items[[c for c in items if c not in cat]].apply(pd.to_numeric, errors="coerce")
    num = num.loc[:, num.notna().mean() > 0.40]
    X6 = pd.concat([pd.get_dummies(items[cat], prefix=[f"d006_{c}" for c in cat], dtype=float),
                    num.fillna(num.median()).add_prefix("d006_")], axis=1)
    X6[["hh_id", "year"]] = d6[["hh_id", "year"]]
    C = hh[["year", "hh_id"]].merge(X6, on=["year", "hh_id"], how="left").drop(columns=["year", "hh_id"]).fillna(0.0)
    C.index = hh.index
    return pd.concat([base, C], axis=1)


def family_of(col: str) -> str:
    if col.startswith("region_"):
        return "region"
    if col.startswith("d006_"):
        return "housing"
    return next((f for f, cols in FAMILIES.items() if col in cols), "other")


# ---------------------------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------------------------
def make_model(name: str, weighted: bool):
    cw = "balanced" if weighted else None
    if name == "logistic_l2":
        return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=3000, class_weight=cw))
    if name == "logistic_l1":
        return make_pipeline(StandardScaler(), LogisticRegression(penalty="l1", C=0.5, solver="liblinear", class_weight=cw))
    if name == "random_forest":   # 500 trees: the Pover-T benchmark
        return RandomForestClassifier(n_estimators=500, min_samples_leaf=5, n_jobs=-1, random_state=SEED, class_weight=cw)
    if name == "lightgbm":
        from lightgbm import LGBMClassifier
        return LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40, subsample=0.8,
                              subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=SEED, verbose=-1,
                              class_weight=cw, n_jobs=-1)
    raise ValueError(name)


def oof_predict(name: str, weighted: bool, X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Out-of-fold probabilities from stratified 5-fold CV inside the training data."""
    out = np.zeros(len(y))
    for tr, va in StratifiedKFold(5, shuffle=True, random_state=SEED).split(X, y):
        out[va] = make_model(name, weighted).fit(X[tr], y[tr]).predict_proba(X[va])[:, 1]
    return out


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def platt(oof: np.ndarray, y: np.ndarray):
    """Platt scaling fitted on out-of-fold training predictions; returns a function for new scores."""
    lr = LogisticRegression(C=1e6, max_iter=1000).fit(logit(oof).reshape(-1, 1), y)
    return lambda p: lr.predict_proba(logit(p).reshape(-1, 1))[:, 1]


def fit_ladder(Xtr: pd.DataFrame, ytr: np.ndarray, Xte: pd.DataFrame) -> dict:
    """For each model: pick class weights by CV log loss, fit on all training data, calibrate, predict the test set."""
    A, B = Xtr.to_numpy(float), Xte.to_numpy(float)
    out = {}
    for name in ("logistic_l2", "logistic_l1", "random_forest", "lightgbm"):
        cand = {w: oof_predict(name, w, A, ytr) for w in (False, True)}
        weighted = min(cand, key=lambda w: log_loss(ytr, np.clip(cand[w], 1e-6, 1 - 1e-6)))
        oof = cand[weighted]
        model = make_model(name, weighted).fit(A, ytr)
        raw = model.predict_proba(B)[:, 1]
        cal = platt(oof, ytr)
        out[name] = {"model": model, "class_weights": weighted, "oof_raw": oof, "oof_cal": cal(oof), "raw": raw, "cal": cal(raw),
                     "cv_log_loss": log_loss(ytr, np.clip(cal(oof), 1e-6, 1 - 1e-6)), "cv_auc": roc_auc_score(ytr, oof)}
        say(f"    {name}: class weights {'on' if weighted else 'off'}, CV AUC {out[name]['cv_auc']:.3f}")
    a, b = out["logistic_l2"], out["lightgbm"]
    blend = {k: (a[k] + b[k]) / 2 for k in ("oof_raw", "oof_cal", "raw", "cal")}
    blend.update(model=None, class_weights=None, cv_log_loss=log_loss(ytr, np.clip(blend["oof_cal"], 1e-6, 1 - 1e-6)),
                 cv_auc=roc_auc_score(ytr, blend["oof_raw"]))
    out["blend_logistic_lightgbm"] = blend
    return out


# ---------------------------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------------------------
def flag_top(score: np.ndarray, w: np.ndarray, share: float) -> np.ndarray:
    """Flag households with the highest risk until they hold `share` of all people."""
    order = np.argsort(-score, kind="stable")
    cum = np.cumsum(w[order]) / w.sum()
    flag = np.zeros(len(score), bool)
    flag[order[: int(np.searchsorted(cum, share, side="left")) + 1]] = True
    return flag


def policy(flag: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    """People-weighted: share flagged, share of poor people found, share of flagged people who are poor."""
    return {"flagged_pct_of_people": round(100 * w[flag].sum() / w.sum(), 1),
            "recall_pct": round(100 * (w * y)[flag].sum() / max((w * y).sum(), 1e-9), 1),
            "precision_pct": round(100 * (w * y)[flag].sum() / max(w[flag].sum(), 1e-9), 1)}


def metrics(p: np.ndarray, y: np.ndarray, w: np.ndarray) -> dict:
    pc = np.clip(p, 1e-6, 1 - 1e-6)
    m = {"log_loss": round(log_loss(y, pc, labels=[0, 1]), 4), "auc": round(roc_auc_score(y, p), 4) if 0 < y.sum() < len(y) else None,
         "average_precision": round(average_precision_score(y, p), 4) if y.sum() else None, "brier": round(brier_score_loss(y, p), 4),
         "mean_predicted_pct": round(100 * p.mean(), 2), "actual_pct": round(100 * y.mean(), 2)}
    for s in SHARES:
        r = policy(flag_top(p, w, s), y, w)
        m[f"recall_at_{int(100 * s)}_pct"], m[f"precision_at_{int(100 * s)}_pct"] = r["recall_pct"], r["precision_pct"]
    return m


def rule_rows(d: pd.DataFrame, y: np.ndarray, w: np.ndarray) -> dict:
    return {name: policy((d["n_child"] >= k).to_numpy(), y, w) | {"auc": round(roc_auc_score(y, (d["n_child"] >= k).astype(int)), 4)}
            for name, k in RULES.items()}


def paired_bootstrap(y: np.ndarray, p_complex: np.ndarray, p_simple: np.ndarray) -> dict:
    """Difference (complex - simple) in AUC and log loss over resamples of test households."""
    rng = np.random.default_rng(SEED)
    d_auc, d_ll = [], []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(y), len(y))
        if y[i].min() == y[i].max():
            continue
        d_auc.append(roc_auc_score(y[i], p_complex[i]) - roc_auc_score(y[i], p_simple[i]))
        d_ll.append(log_loss(y[i], np.clip(p_complex[i], 1e-6, 1 - 1e-6)) - log_loss(y[i], np.clip(p_simple[i], 1e-6, 1 - 1e-6)))
    ci = lambda v: [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]
    return {"auc_diff": round(roc_auc_score(y, p_complex) - roc_auc_score(y, p_simple), 4), "auc_diff_ci95": ci(d_auc),
            "log_loss_diff": round(log_loss(y, np.clip(p_complex, 1e-6, 1 - 1e-6)) - log_loss(y, np.clip(p_simple, 1e-6, 1 - 1e-6)), 4),
            "log_loss_diff_ci95": ci(d_ll), "resamples": len(d_auc)}


def verdict_h4b(ci: list[float]) -> str:
    if ci[1] < MARGIN:
        return "supported"
    return "rejected" if ci[0] >= MARGIN else "inconclusive"


# ---------------------------------------------------------------------------------------------
# Interpretation
# ---------------------------------------------------------------------------------------------
def odds_ratios(X: pd.DataFrame, y: np.ndarray) -> list[dict]:
    """Slide-ready odds ratios with 95% intervals. Shares and size are left out: they are functions of the counts."""
    import statsmodels.api as sm
    drop = {"size", "child_share", "elderly_share", "share_under7", "adult_women_share", "adult_men_share", "adults_18_62_share",
            "n_adults_18_62", "age_mean"}
    regions = [c for c in X if c.startswith("region_")]
    ref = max(regions, key=lambda c: X[c].sum())                      # the largest region is the reference
    cols = [c for c in X if c not in drop and c != ref and not c.startswith("d006_")]
    res = sm.Logit(y, sm.add_constant(X[cols])).fit(disp=0, maxiter=200)
    ci = res.conf_int()
    return [{"feature": c, "odds_ratio": round(float(np.exp(res.params[c])), 3), "ci95_low": round(float(np.exp(ci.loc[c, 0])), 3),
             "ci95_high": round(float(np.exp(ci.loc[c, 1])), 3), "p_value": round(float(res.pvalues[c]), 4)}
            for c in cols] + [{"feature": f"reference region: {ref.removeprefix('region_')}", "odds_ratio": 1.0,
                               "ci95_low": None, "ci95_high": None, "p_value": None}]


def grouped_importance(predict, X: pd.DataFrame, y: np.ndarray, repeats: int = 5) -> dict:
    """Permutation importance on the test set: AUC lost when all columns of one feature family are shuffled together."""
    rng = np.random.default_rng(SEED)
    base = roc_auc_score(y, predict(X.to_numpy(float)))
    fams: dict[str, list[int]] = {}
    for j, c in enumerate(X.columns):
        fams.setdefault(family_of(c), []).append(j)
    out = {}
    for fam, idx in fams.items():
        drops = []
        for _ in range(repeats):
            Z = X.to_numpy(float).copy()
            Z[:, idx] = Z[rng.permutation(len(Z))][:, idx]
            drops.append(base - roc_auc_score(y, predict(Z)))
        out[fam] = round(float(np.mean(drops)), 4)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def missed_profile(d: pd.DataFrame, X: pd.DataFrame, p: np.ndarray) -> dict:
    """Poor people the model finds vs misses at the top-20% cut-off."""
    flag, poor, w = flag_top(p, d["size"].to_numpy(float), 0.20), d["poor"].to_numpy(bool), d["size"].to_numpy(float)
    out = {}
    for name, m in (("found", poor & flag), ("missed", poor & ~flag)):
        ww = w[m]
        avg = lambda v: round(float((np.asarray(v, float)[m] * ww).sum() / ww.sum()), 2)
        row = {"people_pct_of_poor": round(100 * ww.sum() / w[poor].sum(), 1), "mean_children": avg(d["n_child"]),
               "mean_size": avg(d["size"]), "mean_elderly": avg(d["n_elderly"]), "urban_pct": round(100 * avg(d["urban"]), 1)}
        for c in ("head_age", "head_female"):
            if c in X:
                row["mean_" + c] = avg(X[c])
        mix = pd.Series(ww, index=d.loc[m, "region"].map(E.REGION_NAMES)).groupby(level=0).sum().sort_values(ascending=False)
        row["top_regions_pct"] = {k: round(100 * v / ww.sum(), 1) for k, v in mix.head(3).items()}
        out[name] = row
    return out


# ---------------------------------------------------------------------------------------------
# Validation schemes
# ---------------------------------------------------------------------------------------------
def run_temporal(hh: pd.DataFrame, X: pd.DataFrame, target: str = "poor") -> dict:
    tr, te = hh["year"].isin(TRAIN_YEARS).to_numpy(), (hh["year"] == TEST_YEAR).to_numpy()
    cols = [c for c in X if X.loc[tr, c].nunique() > 1]
    ytr, yte = hh.loc[tr, target].to_numpy(), hh.loc[te, target].to_numpy()
    ladder = fit_ladder(X.loc[tr, cols], ytr, X.loc[te, cols])
    return {"ladder": ladder, "cols": cols, "ytr": ytr, "yte": yte, "test": hh[te], "Xte": X.loc[te, cols], "Xtr": X.loc[tr, cols],
            "w": hh.loc[te, "size"].to_numpy(float), "prior": float(ytr.mean())}


def run_leave_region_out(hh: pd.DataFrame, X: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Each 2024 region is held out once and scored by models trained on the other 19 (probabilities not calibrated)."""
    d = hh[hh["year"] == TEST_YEAR]
    Xd, y, w = X.loc[d.index], d["poor"].to_numpy(), d["size"].to_numpy(float)
    preds = {m: np.zeros(len(d)) for m in ("logistic_l2", "logistic_l1", "random_forest", "lightgbm")}
    for code in sorted(d["region"].unique()):
        te = (d["region"] == code).to_numpy()
        cols = [c for c in Xd if Xd.loc[~te, c].nunique() > 1]
        for m in preds:
            preds[m][te] = make_model(m, weights[m]).fit(Xd.loc[~te, cols].to_numpy(float), y[~te]).predict_proba(
                Xd.loc[te, cols].to_numpy(float))[:, 1]
    preds["blend_logistic_lightgbm"] = (preds["logistic_l2"] + preds["lightgbm"]) / 2
    rows = []
    for m, p in preds.items():
        rows.append({"model": m, "region": "ALL (pooled)", **metrics(p, y, w)})
        for code in sorted(d["region"].unique()):
            te = (d["region"] == code).to_numpy()
            rows.append({"model": m, "region": E.REGION_NAMES.get(code, code), "households": int(te.sum()), **metrics(p[te], y[te], w[te])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------------------------
def charts(out: Path, T: dict, simple: str, cx: str, rules: dict, loro: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 13, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})
    blue, orange, grey = "#2a78d6", "#eb6834", "#8a8f98"
    y, w, d = T["yte"], T["w"], T["test"]
    ps, pcx = T["ladder"][simple]["cal"], T["ladder"][cx]["cal"]

    fig, ax = plt.subplots(figsize=(7, 6))
    for p, name, c in ((ps, simple, blue), (pcx, cx, orange)):
        f, t, _ = roc_curve(y, p)
        ax.plot(f, t, color=c, lw=2.2, label=f"{name} (AUC {roc_auc_score(y, p):.3f})")
    for name, k in RULES.items():
        flag = (d["n_child"] >= k).to_numpy()
        ax.scatter(flag[y == 0].mean(), flag[y == 1].mean(), color="black", zorder=3)
        ax.annotate(name, (flag[y == 0].mean(), flag[y == 1].mean()), textcoords="offset points", xytext=(8, -12))
    ax.plot([0, 1], [0, 1], color=grey, ls="--", lw=1)
    ax.set(xlabel="False positive rate (households)", ylabel="True positive rate (households)", title="ROC, test year 2024")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(out / "roc.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    for p, name, c in ((T["ladder"][simple]["raw"], f"{simple}, before calibration", grey), (ps, f"{simple}, calibrated", blue),
                       (pcx, f"{cx}, calibrated", orange)):
        q = pd.qcut(pd.Series(p).rank(method="first"), 10, labels=False)
        ax.plot(pd.Series(p).groupby(q).mean() * 100, pd.Series(y).groupby(q).mean() * 100, marker="o", color=c, label=name)
    lim = ax.get_xlim()[1]
    ax.plot([0, lim], [0, lim], color=grey, ls="--", lw=1)
    ax.set(xlabel="Predicted poverty rate, %", ylabel="Actual poverty rate, %", title="Calibration by risk decile, 2024")
    ax.legend(frameon=False)
    fig.tight_layout(); fig.savefig(out / "calibration.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 6))
    grid = np.linspace(0.02, 0.6, 30)
    for p, name, c in ((ps, simple, blue), (pcx, cx, orange)):
        ax.plot(grid * 100, [policy(flag_top(p, w, s), y, w)["recall_pct"] for s in grid], color=c, lw=2.2, label=name)
    for name, r in rules.items():
        ax.scatter(r["flagged_pct_of_people"], r["recall_pct"], color="black", zorder=3)
        ax.annotate(f"rule: {name}", (r["flagged_pct_of_people"], r["recall_pct"]), textcoords="offset points", xytext=(8, -14))
    ax.plot([0, 60], [0, 60], color=grey, ls="--", lw=1, label="random")
    ax.set(xlabel="Share of people flagged, %", ylabel="Share of poor people found, %", title="Poor people found vs people flagged, 2024")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(out / "recall_vs_flagged.png"); plt.close(fig)

    r = loro[(loro["model"] == simple) & (loro["region"] != "ALL (pooled)")].sort_values("recall_at_20_pct")
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.barh(r["region"], r["recall_at_20_pct"], color=blue)
    for v, name in zip(r["recall_at_20_pct"], r["region"]):
        ax.text(v + 1, name, f"{v:.0f}", va="center", fontsize=11)
    ax.set(xlabel="Poor people found among the 20% with the highest risk in the region, %",
           title=f"Leave-one-region-out, 2024 ({simple})")
    fig.tight_layout(); fig.savefig(out / "recall_at_20_by_region.png"); plt.close(fig)


# ---------------------------------------------------------------------------------------------
# One feature set: all models, both schemes, verdicts
# ---------------------------------------------------------------------------------------------
def evaluate_set(tag: str, hh: pd.DataFrame, X: pd.DataFrame, board: list, with_loro: bool = True) -> dict:
    say(f"feature set {tag}: {X.shape[1]} columns; temporal split")
    T = run_temporal(hh, X)
    y, w, d = T["yte"], T["w"], T["test"]
    prior = np.full(len(y), T["prior"])
    board.append({"feature_set": tag, "scheme": "temporal", "model": "prior probability", "calibrated": False, **metrics(prior, y, w)})
    rules = rule_rows(d, y, w)
    for name, r in rules.items():
        board.append({"feature_set": tag, "scheme": "temporal", "model": f"rule: {name}", "calibrated": False, "auc": r["auc"],
                      "rule_flagged_pct_of_people": r["flagged_pct_of_people"], "rule_recall_pct": r["recall_pct"],
                      "rule_precision_pct": r["precision_pct"]})
    for m, L in T["ladder"].items():
        for cal in (False, True):
            board.append({"feature_set": tag, "scheme": "temporal", "model": m, "calibrated": cal, "class_weights": L["class_weights"],
                          "cv_log_loss": round(L["cv_log_loss"], 4), "cv_auc": round(L["cv_auc"], 4),
                          **metrics(L["cal" if cal else "raw"], y, w)})
    # The best model of each kind is chosen on the training data (CV log loss), never on the test set.
    simple = min(SIMPLE, key=lambda m: T["ladder"][m]["cv_log_loss"])
    cx = min(COMPLEX, key=lambda m: T["ladder"][m]["cv_log_loss"])
    ps, pcx = T["ladder"][simple]["cal"], T["ladder"][cx]["cal"]
    ms, mc = metrics(ps, y, w), metrics(pcx, y, w)
    same_share = {}
    for name, r in rules.items():
        got = policy(flag_top(ps, w, r["flagged_pct_of_people"] / 100), y, w)
        same_share[name] = {"people_flagged_pct": r["flagged_pct_of_people"], "rule_recall_pct": r["recall_pct"],
                            "model_recall_pct": got["recall_pct"], "rule_precision_pct": r["precision_pct"],
                            "model_precision_pct": got["precision_pct"]}
    boot = paired_bootstrap(y, pcx, ps)
    h4a = ms["auc"] >= AUC_MIN and all(v["model_recall_pct"] > v["rule_recall_pct"] for v in same_share.values())
    h4b = verdict_h4b(boot["auc_diff_ci95"])
    res = {"columns": X.shape[1], "best_simple": simple, "best_complex": cx, "simple_metrics": ms, "complex_metrics": mc,
           "class_weights": {m: L["class_weights"] for m, L in T["ladder"].items()}, "rules": rules, "model_vs_rules_same_share": same_share,
           "complex_minus_simple": boot, "H4a": "supported" if h4a else "not supported", "H4b": h4b,
           "H4": "supported" if h4a and h4b == "supported" else "not supported" if not h4a or h4b == "rejected" else "inconclusive",
           "T": T}
    say(f"  best simple {simple}: AUC {ms['auc']}, log loss {ms['log_loss']}, recall@20% {ms['recall_at_20_pct']}")
    say(f"  best complex {cx}: AUC {mc['auc']}, log loss {mc['log_loss']}, recall@20% {mc['recall_at_20_pct']}")
    if with_loro:
        say(f"  leave-one-region-out on {TEST_YEAR} (20 folds)")
        weights = {m: bool(L["class_weights"]) for m, L in T["ladder"].items() if L["class_weights"] is not None}
        loro = run_leave_region_out(hh, X, weights)
        for _, r in loro.iterrows():
            board.append({"feature_set": tag, "scheme": "leave-one-region-out" + ("" if r["region"] == "ALL (pooled)" else ": " + r["region"]),
                          "calibrated": False, **{k: v for k, v in r.items() if k != "region" and pd.notna(v)}})
        res["loro"] = loro
    return res


def near_label_check(hh: pd.DataFrame, X: pd.DataFrame) -> dict:
    """Secondary label (below 125% of the minimum): logistic regression only, temporal split."""
    tr, te = hh["year"].isin(TRAIN_YEARS).to_numpy(), (hh["year"] == TEST_YEAR).to_numpy()
    y, yt = hh.loc[tr, "poor_or_near"].to_numpy(), hh.loc[te, "poor_or_near"].to_numpy()
    p = make_model("logistic_l2", False).fit(X[tr].to_numpy(float), y).predict_proba(X[te].to_numpy(float))[:, 1]
    return metrics(p, yt, hh.loc[te, "size"].to_numpy(float))


# ---------------------------------------------------------------------------------------------
# The saved screen model (used by the app and the risk_screen tool)
# ---------------------------------------------------------------------------------------------
def save_screen_model(hh: pd.DataFrame, out: Path, board: list) -> dict:
    """Logistic regression on income-free features, trained on the training years and saved with joblib.
    scores_2024.csv holds its risk for every 2024 household: the distribution used to turn a risk into a rank."""
    import datetime
    import joblib
    import sklearn
    X = risk_screen.design(hh)
    features = list(X.columns)
    assert not [f for f in features if any(bad in f.lower() for bad in risk_screen.FORBIDDEN)], "an income-derived feature"
    tr, te = hh["year"].isin(TRAIN_YEARS).to_numpy(), (hh["year"] == TEST_YEAR).to_numpy()
    model = make_model("logistic_l2", False).fit(X[tr].to_numpy(float), hh.loc[tr, "poor"].to_numpy())
    risk = np.round(model.predict_proba(X[te].to_numpy(float))[:, 1], 6)
    y, w = hh.loc[te, "poor"].to_numpy(), hh.loc[te, "size"].to_numpy(float)
    m = metrics(risk, y, w)
    info = {"version": "risk-screen 1.0", "trained_at": datetime.date.today().isoformat(), "train_years": list(TRAIN_YEARS),
            "test_year": TEST_YEAR, "features": features, "test_auc": m["auc"], "recall_top20_pct": m["recall_at_20_pct"],
            "recall_top10_pct": m["recall_at_10_pct"], "sklearn_version": sklearn.__version__}
    joblib.dump({"model": model, **info}, out / "model_logit.joblib")
    hh.loc[te, ["hh_id", "region", "size"]].assign(region_name=hh.loc[te, "region"].map(E.REGION_NAMES), risk=risk, label=y).to_csv(
        out / "scores_2024.csv", index=False)
    board.append({"feature_set": "screen model (saved, income-free)", "scheme": "temporal", "model": "logistic_l2",
                  "calibrated": False, "class_weights": False, **m})
    return {**info, "metrics": m, "model_file": "model_logit.joblib", "scores_file": "scores_2024.csv"}


# ---------------------------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------------------------
def md_table(head: list[str], rows: list[list]) -> list[str]:
    f = lambda v: "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)
    return ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(f(v) for v in r) + " |" for r in rows] + [""]


def write_summary(out: Path, S: dict, board: pd.DataFrame) -> None:
    L = ["# Poverty prediction challenge (H4)", "",
         "Modelled on the World Bank's Pover-T Tests. Every number below is in `leaderboard.csv` or `summary.json`. "
         "Synthetic data without survey weights: shares are sample shares, and poverty is income-based, not consumption-based.", "",
         "## Thresholds fixed before the run", "",
         f"- H4a: the best simple model reaches AUC of at least {AUC_MIN} on the 2024 test and finds more poor people than each "
         "children rule when it flags the same share of people.",
         f"- H4b: supported if the upper bound of the 95% interval for (complex minus simple) AUC is below {MARGIN}; rejected if "
         f"the lower bound is {MARGIN} or more; inconclusive otherwise.",
         "- The best simple and the best complex model are chosen by cross-validated log loss on the training years, not on the test year.", "",
         "## Label balance", ""]
    L += md_table(["Year", "Households", "Poor households, %", "Poor people, %", "Poor or near (below 125%), people, %"],
                  [[r["year"], r["households"], r["poor_households_pct"], r["poor_people_pct"], r["poor_or_near_people_pct"]] for r in S["class_balance"]])
    L += ["## Verdicts", ""]
    L += md_table(["Feature set", "Best simple", "Best complex", "Simple AUC", "Complex AUC", "AUC difference (95% interval)",
                   "Log-loss difference (95% interval)", "H4a", "H4b", "H4"],
                  [[k, v["best_simple"], v["best_complex"], v["simple_metrics"]["auc"], v["complex_metrics"]["auc"],
                    f"{v['complex_minus_simple']['auc_diff']} ({v['complex_minus_simple']['auc_diff_ci95'][0]} to {v['complex_minus_simple']['auc_diff_ci95'][1]})",
                    f"{v['complex_minus_simple']['log_loss_diff']} ({v['complex_minus_simple']['log_loss_diff_ci95'][0]} to {v['complex_minus_simple']['log_loss_diff_ci95'][1]})",
                    v["H4a"], v["H4b"], v["H4"]] for k, v in S["feature_sets"].items()])
    L += ["Feature set A on the temporal test is the headline. Sets marked as sensitivity never enter the verdicts.", ""]
    for tag in S["feature_sets"]:
        b = board[(board["feature_set"] == tag) & (board["scheme"] == "temporal")]
        L += [f"## Leaderboard, feature set {tag}: train 2022–2023, test 2024", ""]
        rows = []
        for _, r in b.iterrows():
            if str(r["model"]).startswith("rule"):
                rows.append([r["model"], "", "", r["auc"], "", "", "", f"flags {r['rule_flagged_pct_of_people']}% of people: finds {r['rule_recall_pct']}%", ""])
            else:
                rows.append([r["model"], "yes" if r["calibrated"] else "no", r["log_loss"], r["auc"], r["average_precision"], r["brier"],
                             f"{r['mean_predicted_pct']} / {r['actual_pct']}", r["recall_at_20_pct"], r["precision_at_20_pct"]])
        L += md_table(["Model", "Calibrated", "Log loss", "AUC", "Average precision", "Brier", "Predicted / actual rate, %",
                       "Poor people found in top 20%, %", "Poor among flagged, %"], rows)
        v = S["feature_sets"][tag]
        L += [f"Model against the rules at the same share of people flagged ({v['best_simple']}):", ""]
        L += md_table(["Rule", "People flagged, %", "Rule finds, %", "Model finds, %"],
                      [[k, r["people_flagged_pct"], r["rule_recall_pct"], r["model_recall_pct"]] for k, r in v["model_vs_rules_same_share"].items()])
    H = S["headline"]
    L += [f"## Odds ratios, logistic regression, feature set {H['feature_set']} (training years)", "",
          "One more unit of the feature multiplies the odds of being below the minimum by this factor, other features held fixed. "
          "Associations, not causes.", ""]
    L += md_table(["Feature", "Odds ratio", "95% interval", "p"],
                  [[r["feature"], r["odds_ratio"], "" if r["ci95_low"] is None else f"{r['ci95_low']}–{r['ci95_high']}", r["p_value"]] for r in H["odds_ratios"]])
    L += ["## What drives the predictions: AUC lost when a feature family is shuffled (2024)", ""]
    fams = list(H["importance_simple"])
    L += md_table(["Feature family", H["best_simple"], H["best_complex"]],
                  [[f, H["importance_simple"][f], H["importance_complex"].get(f)] for f in fams])
    L += [f"Same ranking in both models: {'yes' if H['same_driver_ranking'] else 'no'}.", "",
          "## Poor people the model finds and misses at the top-20% cut-off", ""]
    keys = [k for k in H["missed_vs_found"]["found"] if k != "top_regions_pct"]
    L += md_table(["", "Found", "Missed"], [[k, H["missed_vs_found"]["found"][k], H["missed_vs_found"]["missed"][k]] for k in keys]
                  + [["top regions, % of the group", json.dumps(H["missed_vs_found"]["found"]["top_regions_pct"]),
                      json.dumps(H["missed_vs_found"]["missed"]["top_regions_pct"])]])
    L += ["## Leave-one-region-out, 2024", "",
          f"Each region is scored by a model trained on the other 19. Pooled AUC of {H['best_simple']}: {H['loro_pooled_auc_simple']}; "
          f"of {H['best_complex']}: {H['loro_pooled_auc_complex']}. Regions where {H['best_simple']} does worst:", ""]
    L += md_table(["Region", "AUC", "Poor people found in the region's top 20%, %", "Actual rate, households, %"],
                  [[r["region"], r["auc"], r["recall_at_20_pct"], r["actual_pct"]] for r in H["loro_worst_regions"]])
    M = S["screen_model"]
    L += ["## The saved screen model", "",
          f"`{M['model_file']}`: logistic regression on household size, children, children under 7, elderly, working-age adults, "
          f"urban or rural and region. No income and no number of earners. Trained on {M['train_years'][0]}–{M['train_years'][-1]}, "
          f"version {M['version']}. On {M['test_year']}: AUC {M['test_auc']}; it finds {M['recall_top20_pct']}% of people below the "
          f"minimum among the 20% with the highest risk and {M['recall_top10_pct']}% among the top 10%. `{M['scores_file']}` holds its "
          "risk for every 2024 household; the app turns a risk into a place in that ranking.", ""]
    L += ["## Not run", ""] + [f"- {x}" for x in S["not_run"]] + [""] if S["not_run"] else []
    L += ["## Caveats", "", "- Synthetic data: results show directions, not national estimates.",
          "- Poverty is income-based; official statistics use consumption.", "- No survey weights.",
          "- `n_earners` is derived from income records and is used only in the sensitivity run.",
          "- Leave-one-region-out probabilities are not calibrated, so compare AUC and recall there, not log loss.", ""]
    (out / "summary.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("households")
    ap.add_argument("out")
    ap.add_argument("--persons")
    ap.add_argument("--raw")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    np.random.seed(SEED)

    print("Verdict thresholds (fixed before the run):")
    print(f"  H4a supported if best SIMPLE AUC >= {AUC_MIN} on the 2024 test AND it finds more poor people than each children rule at the same share flagged.")
    print(f"  H4b supported if the 95% upper bound of (complex - simple) AUC < {MARGIN}; rejected if the lower bound >= {MARGIN}; else inconclusive.")
    print("  H4 supported only if both are. Best models are chosen by CV log loss on the training years.\n")

    hh = add_labels(load_households(a.households))
    balance = class_balance(hh)
    for r in balance:
        say(f"{r['year']}: {r['households']} households, poor {r['poor_households_pct']}% of households, {r['poor_people_pct']}% of people")

    sets, not_run = {"A": features_a(hh)}, []
    if a.persons and Path(a.persons).exists():
        persons = pd.read_csv(a.persons, dtype={"NOMER": str, "RODSTVO": str})
        head_code, ev = head_evidence(persons)
        print("\nRODSTVO evidence (the head is the code that appears exactly once in almost every household):")
        print(ev.head(8).to_string(), f"\n-> head code: {head_code}\n")
        ev.to_csv(out / "rodstvo_head_evidence.csv")
        sets["B"] = features_b(hh, persons, head_code)
        if a.raw:
            try:
                sets["C"] = features_c(hh, sets["B"], Path(a.raw))
            except Exception as e:  # noqa: BLE001  (set C is optional)
                not_run.append(f"Feature set C (D-006 housing items): {e}")
        else:
            not_run.append("Feature set C (D-006 housing items): pass --raw <RAW_DATA_DIR>.")
    else:
        not_run += ["Feature set B (member aggregates, the household head): out/persons.csv is missing; build it with "
                    "`python build.py <RAW_DATA_DIR> out` and pass --persons out/persons.csv.",
                    "Feature set C (D-006 housing items): needs the raw data folder (--raw) and set B."]
    base = "B" if "B" in sets else "A"
    sens_tag = f"{base} + n_earners (SENSITIVITY, not for verdicts)"

    board: list[dict] = []
    results = {tag: evaluate_set(tag, hh, X, board) for tag, X in sets.items()}
    sens = evaluate_set(sens_tag, hh, pd.concat([sets[base], hh[["n_earners"]].astype(float)], axis=1), board, with_loro=False)

    # ---- interpretation on the headline set (A) ------------------------------------------------
    say("interpretation: odds ratios, grouped permutation importance, missed vs found")
    R = results["A"]
    T, simple, cx = R["T"], R["best_simple"], R["best_complex"]
    lad = T["ladder"]
    predict = lambda name: (lambda Z: (lad["logistic_l2"]["model"].predict_proba(Z)[:, 1] + lad["lightgbm"]["model"].predict_proba(Z)[:, 1]) / 2
                            if name == "blend_logistic_lightgbm" else lad[name]["model"].predict_proba(Z)[:, 1])
    imp_s, imp_c = grouped_importance(predict(simple), T["Xte"], T["yte"]), grouped_importance(predict(cx), T["Xte"], T["yte"])
    loro = R["loro"]
    reg = loro[(loro["model"] == simple) & (loro["region"] != "ALL (pooled)")].sort_values("auc")
    pooled = lambda m: float(loro[(loro["model"] == m) & (loro["region"] == "ALL (pooled)")]["auc"].iloc[0])
    interp_set = base
    Xi = sets[interp_set]
    tr = hh["year"].isin(TRAIN_YEARS)
    headline = {"feature_set": "A", "best_simple": simple, "best_complex": cx,
                "odds_ratios_feature_set": interp_set, "odds_ratios": odds_ratios(Xi[tr], hh.loc[tr, "poor"].to_numpy()),
                "importance_simple": imp_s, "importance_complex": imp_c,
                "same_driver_ranking": list(imp_s)[:3] == list(imp_c)[:3],
                "missed_vs_found": missed_profile(T["test"], T["Xte"], lad[simple]["cal"]),
                "loro_pooled_auc_simple": pooled(simple), "loro_pooled_auc_complex": pooled(cx),
                "loro_worst_regions": reg.head(5)[["region", "auc", "recall_at_20_pct", "actual_pct"]].to_dict("records")}

    # ---- outputs -------------------------------------------------------------------------------
    say("saving the screen model (logistic regression, income-free features)")
    screen = save_screen_model(hh, out, board)
    lb = pd.DataFrame(board)
    lb.to_csv(out / "leaderboard.csv", index=False)
    strip = lambda r: {k: v for k, v in r.items() if k not in ("T", "loro")}
    S = {"version": "poverty_challenge 1.0", "seed": SEED, "train_years": list(TRAIN_YEARS), "test_year": TEST_YEAR,
         "thresholds": {"h4a_min_auc": AUC_MIN, "h4b_margin_auc": MARGIN, "bootstrap_resamples": N_BOOT},
         "class_balance": balance, "feature_sets": {**{k: strip(v) for k, v in results.items()}, sens_tag: strip(sens)},
         "headline": headline, "screen_model": screen, "secondary_label_poor_or_near_logistic_set_A": near_label_check(hh, sets["A"]), "not_run": not_run}
    (out / "summary.json").write_text(json.dumps(S, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    write_summary(out, S, lb)
    charts(out, T, simple, cx, R["rules"], loro)
    say(f"saved -> {out}")

    b24, ms, mc, bt = balance[-1], R["simple_metrics"], R["complex_metrics"], R["complex_minus_simple"]
    print("\n".join(["", "SUMMARY",
        f" 1. Label: {b24['poor_people_pct']}% of people ({b24['poor_households_pct']}% of households) are below the regional minimum in {TEST_YEAR}: imbalanced.",
        f" 2. Set A, best simple model: {simple}: AUC {ms['auc']}, log loss {ms['log_loss']}, finds {ms['recall_at_20_pct']}% of poor people in the top 20%.",
        f" 3. Set A, best complex model: {cx}: AUC {mc['auc']}, log loss {mc['log_loss']}, finds {mc['recall_at_20_pct']}% in the top 20%.",
        f" 4. Complex minus simple AUC: {bt['auc_diff']} (95% interval {bt['auc_diff_ci95'][0]} to {bt['auc_diff_ci95'][1]}); log loss {bt['log_loss_diff']} ({bt['log_loss_diff_ci95'][0]} to {bt['log_loss_diff_ci95'][1]}).",
        " 5. Rules at the same share flagged: " + "; ".join(f"{k}: rule {v['rule_recall_pct']}% vs model {v['model_recall_pct']}%" for k, v in R["model_vs_rules_same_share"].items()) + ".",
        f" 6. H4a (predictability): {R['H4a']}. H4b (simplicity): {R['H4b']}. H4: {R['H4']}.",
        " 7. Other feature sets: " + ("; ".join(f"{k}: simple AUC {v['simple_metrics']['auc']}, complex {v['complex_metrics']['auc']}, H4 {v['H4']}" for k, v in results.items() if k != 'A') or "not run (see summary.md, 'Not run')") + ".",
        f" 8. Sensitivity only ({sens_tag}): simple AUC {sens['simple_metrics']['auc']}, complex {sens['complex_metrics']['auc']}.",
        f" 9. Leave-one-region-out pooled AUC: {simple} {headline['loro_pooled_auc_simple']}, {cx} {headline['loro_pooled_auc_complex']}; weakest region: {headline['loro_worst_regions'][0]['region']}.",
        "10. Caveats: synthetic data; income-based, not consumption-based poverty; no survey weights; n_earners only in the sensitivity run."]))


if __name__ == "__main__":
    main()
