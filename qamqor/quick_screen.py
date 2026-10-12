"""
Qamqor AI — быстрый скрининг / quick screen (v0.3.1).

RU: Вопрос: можно ли по составу семьи, региону и занятости, НЕ зная дохода, предсказать, что
    семья бедна или близка к бедности? Модель учится на 2022–2023 годах и проверяется на
    семьях 2024 года, которых она не видела. Доход в признаки не входит ни в каком виде.
    Модель не решает, кто беден: это первый фильтр перед проверкой дохода.
EN: Question: can household composition, region and employment, WITHOUT income, predict that a
    household is poor or close to poverty? The model is trained on 2022–2023 and tested on 2024
    households it has never seen. Income is not among the features in any form.
    The model does not decide who is poor: it is a first filter before an income check.

Запуск / Run:
    python quick_screen.py out/households.csv results
"""
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import engine as E

warnings.filterwarnings("ignore")
NEAR = 1.25          # RU: «близко к бедности» — доход ниже 125% ПМ / EN: "close to poverty" — income below 125% of the SM
TRAIN_YEARS, TEST_YEAR = (2022, 2023), 2024

FEATURE_SETS = {
    # RU: только то, что видно без опроса о доходах. EN: only what is visible without asking about income.
    "composition_region": ["size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban",
                           "child_share", "elderly_share"],
    # RU: плюс сколько человек в семье работает (сам факт, не сумма). EN: plus how many members work (the fact, not the amount).
    "plus_employment": ["size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban",
                        "child_share", "elderly_share", "n_earners", "earner_share", "dependents_per_earner"],
    # RU: плюс расходы на жильё и коммунальные услуги. EN: plus housing and utility spending.
    "plus_utilities": ["size", "n_child", "n_child_u7", "n_elderly", "n_working_age", "urban",
                       "child_share", "elderly_share", "n_earners", "earner_share", "dependents_per_earner",
                       "utilities_pc"],
}


def prepare(hh: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for y, d in hh.groupby("year"):
        d = d.copy()
        pm = E.sm_for_mode(d, int(y), "regional")
        d["ratio"] = E.per_capita(d) / pm
        d["poor"] = (d["ratio"] < 1.0).astype(int)
        d["poor_or_near"] = (d["ratio"] < NEAR).astype(int)
        d["sm"] = pm
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    d["child_share"] = d["n_child"] / d["size"]
    d["elderly_share"] = d["n_elderly"] / d["size"]
    d["earner_share"] = d["n_earners"] / d["size"]
    d["dependents_per_earner"] = (d["size"] - d["n_earners"]) / d["n_earners"].clip(lower=1)
    # RU: расходы на ЖКУ на человека в долях регионального ПМ, чтобы годы были сравнимы.
    # EN: utility spending per person as a share of the regional SM, so years are comparable.
    d["utilities_pc"] = d["utilities"] / d["size"] / 12.0 / d["sm"]
    return d


def design(d: pd.DataFrame, cols) -> pd.DataFrame:
    X = d[cols].astype(float).copy()
    reg = pd.get_dummies(d["region"].astype(str), prefix="region", dtype=float)
    return pd.concat([X, reg.reindex(columns=[f"region_{k}" for k in sorted(E.REGION_NAMES)], fill_value=0.0)], axis=1)


def flag_top(score: np.ndarray, w: np.ndarray, share: float) -> np.ndarray:
    """RU: отметить семьи с наибольшим риском, пока не наберётся share людей. EN: flag the highest-risk households up to `share` of people."""
    o = np.argsort(-score, kind="stable")
    c = np.cumsum(w[o]) / w.sum()
    f = np.zeros(len(score), bool)
    f[o[c <= share + 1e-12]] = True
    return f


def rates(flag, y, w) -> dict:
    tp = (w * (flag & (y == 1))).sum()
    return {"flagged_pct_of_people": round(100 * (w * flag).sum() / w.sum(), 1),
            "found_pct": round(100 * tp / (w * (y == 1)).sum(), 1),          # RU: доля найденных / EN: recall
            "correct_pct": round(100 * tp / max((w * flag).sum(), 1e-9), 1)}  # RU: доля верных среди отмеченных / EN: precision


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("out/households.csv")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("results")
    d = prepare(pd.read_csv(src, dtype={"hh_id": str, "region": str}))
    tr = d[d.year.isin(TRAIN_YEARS)].reset_index(drop=True)
    te = d[d.year == TEST_YEAR].reset_index(drop=True)
    wtr, wte = tr["size"].to_numpy(float), te["size"].to_numpy(float)
    R = {"version": "0.3.4", "train_years": list(TRAIN_YEARS), "test_year": TEST_YEAR,
         "train_households": int(len(tr)), "test_households": int(len(te)),
         "near_poverty_threshold": NEAR, "targets": {}, "models": [], "rules": {}}
    scores = {}
    for target in ("poor", "poor_or_near"):
        ytr, yte = tr[target].to_numpy(), te[target].to_numpy()
        prev = float((wte * yte).sum() / wte.sum())
        R["targets"][target] = {"share_of_people_test_pct": round(100 * prev, 2),
                                "share_of_people_train_pct": round(100 * float((wtr * ytr).sum() / wtr.sum()), 2)}
        for fs, cols in FEATURE_SETS.items():
            Xtr, Xte = design(tr, cols), design(te, cols)
            for mname, mdl in [
                ("logistic", make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, C=1.0))),
                ("boosting", HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15,
                                                            l2_regularization=1.0, random_state=0)),
            ]:
                if mname == "logistic":
                    mdl.fit(Xtr, ytr, logisticregression__sample_weight=wtr)
                else:
                    mdl.fit(Xtr, ytr, sample_weight=wtr)
                p = mdl.predict_proba(Xte)[:, 1]
                scores[(target, fs, mname)] = p
                row = {"target": target, "features": fs, "model": mname,
                       "auc": round(roc_auc_score(yte, p, sample_weight=wte), 3),
                       "average_precision": round(average_precision_score(yte, p, sample_weight=wte), 3),
                       "mean_predicted_pct": round(100 * float((wte * p).sum() / wte.sum()), 1),
                       "actual_pct": round(100 * prev, 1),
                       "flag_same_share_as_target": rates(flag_top(p, wte, prev), yte, wte),
                       "flag_top_20pct": rates(flag_top(p, wte, 0.20), yte, wte),
                       "flag_top_30pct": rates(flag_top(p, wte, 0.30), yte, wte)}
                R["models"].append(row)
        # RU: простые правила для сравнения. EN: simple rules for comparison.
        R["rules"][target] = {
            "3+ children": rates((te.n_child >= 3).to_numpy(), yte, wte),
            "4+ children": rates((te.n_child >= 4).to_numpy(), yte, wte),
            "no earner": rates((te.n_earners == 0).to_numpy(), yte, wte),
            "one earner and 4+ members": rates(((te.n_earners == 1) & (te["size"] >= 4)).to_numpy(), yte, wte),
        }

    # ---- что важно для модели / what drives the model ------------------------------------
    cols = FEATURE_SETS["plus_employment"]
    base = ["size", "n_child", "n_elderly", "n_earners", "urban"]
    Xb_tr = design(tr, base)
    lr = LogisticRegression(max_iter=5000, C=10.0).fit(Xb_tr, tr["poor"], sample_weight=wtr)
    R["odds_ratios_poor"] = {c: round(float(np.exp(b)), 2) for c, b in zip(Xb_tr.columns, lr.coef_[0]) if c in base}
    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=15, l2_regularization=1.0,
                                        random_state=0).fit(design(tr, cols), tr["poor"], sample_weight=wtr)
    Xte = design(te, cols)
    reg_cols = [c for c in Xte.columns if c.startswith("region_")]
    rng = np.random.default_rng(0)
    base_auc = roc_auc_score(te["poor"], gb.predict_proba(Xte)[:, 1], sample_weight=wte)
    groups = {"children (count, under 7, share)": ["n_child", "n_child_u7", "child_share"],
              "employment (earners, share, dependents per earner)": ["n_earners", "earner_share", "dependents_per_earner"],
              "household size and working-age adults": ["size", "n_working_age"],
              "elderly (count, share)": ["n_elderly", "elderly_share"],
              "region": reg_cols, "urban or rural": ["urban"]}
    imp = {}
    for g, cs in groups.items():
        drops = []
        for _ in range(10):
            Xp = Xte.copy()
            perm = rng.permutation(len(Xp))
            Xp[cs] = Xp[cs].to_numpy()[perm]
            drops.append(base_auc - roc_auc_score(te["poor"], gb.predict_proba(Xp)[:, 1], sample_weight=wte))
        imp[g] = round(float(np.mean(drops)), 3)
    R["auc_drop_when_shuffled_poor"] = dict(sorted(imp.items(), key=lambda kv: -kv[1]))

    # ---- состязание способов адресности при равном бюджете / targeting contest ------------
    # RU: Бюджет — стоимость доплаты до 100% ПМ при идеальной проверке дохода. Модель дохода не
    #     видит, поэтому отмеченные семьи получают одинаковую сумму на человека.
    # EN: The budget is the cost of a top-up to 100% of the SM under a perfect income test. The
    #     model never sees income, so flagged households get the same amount per person.
    E.set_line_mode("regional")
    df = te.copy()
    pm = E.sm(df, TEST_YEAR)
    pc0 = E.per_capita(df)
    gap0 = E.poverty_gap_cost(df, pc0, pm)
    budget = gap0                                           # tenge per year, whole sample
    poor0 = (pc0 < pm - E.EPS).to_numpy()

    def outcome(pay: pd.Series, label: str, extra=None) -> dict:
        final = df["income"] + pay
        pc1 = E.per_capita(df, final)
        r = {"method": label,
             "people_receiving_pct": round(100 * E.share(pay > 0, df), 1),
             "payment_per_person_month": round(float(pay[pay > 0].sum() / (df.loc[pay > 0, "size"].sum() * 12))) if (pay > 0).any() else 0,
             "spending_reaching_the_poor_pct": round(100 * float(pay[poor0].sum() / pay.sum()), 1),
             "poor_who_receive_pct": round(100 * float((wte * (poor0 & (pay > 0).to_numpy())).sum() / (wte * poor0).sum()), 1),
             "shortfall_closed_pct": round(100 * (gap0 - E.poverty_gap_cost(df, pc1, pm)) / gap0, 1),
             "below_sm_after_pct": round(100 * E.share(pc1 < pm - E.EPS, df), 2)}
        if extra:
            r.update(extra)
        return r

    def flat(flag: np.ndarray) -> pd.Series:
        f = pd.Series(flag, index=df.index)
        return f * df["size"] * (budget / float(df.loc[f, "size"].sum()))

    contest = [outcome(np.maximum(0.0, pm * 12.0 * df["size"] - df["income"]), "income test, everyone claims"),
               outcome(np.maximum(0.0, pm * 12.0 * df["size"] - df["income"]) * E._claims(df, 0.6) / 1.0, "income test, 60% claim (same line, budget not fully used)")]
    kids = df["n_child"] >= 1
    contest.append(outcome(kids * df["n_child"] * (budget / float(df.loc[kids, "n_child"].sum())), "allowance for every child"))
    k4 = df["n_child"] >= 4
    contest.append(outcome(k4 * df["n_child"] * (budget / float(df.loc[k4, "n_child"].sum())), "allowance for children in families with 4+"))
    curve = {}
    for fs in ("composition_region", "plus_employment"):
        p = scores[("poor", fs, "boosting")]
        best = None
        curve[fs] = []
        for share in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50):
            r = outcome(flat(flag_top(p, wte, share)), f"model ({fs}), flat payment to the top {share:.0%} by risk")
            curve[fs].append({"flagged_share_pct": round(100 * share), "shortfall_closed_pct": r["shortfall_closed_pct"],
                              "spending_reaching_the_poor_pct": r["spending_reaching_the_poor_pct"],
                              "poor_who_receive_pct": r["poor_who_receive_pct"]})
            if best is None or r["shortfall_closed_pct"] > best["shortfall_closed_pct"]:
                best = r
        contest.append(best)
    contest.append(outcome(pd.Series(budget / float(df["size"].sum()), index=df.index) * df["size"], "same amount to everyone"))
    R["targeting_contest_2024"] = {"budget_per_capita_tenge_year": round(budget / float(df["size"].sum())),
                                   "results": contest, "model_curve": curve}

    # ---- кого модель пропускает / whom the model misses -----------------------------------
    p = scores[("poor", "plus_employment", "boosting")]
    f = flag_top(p, wte, 0.20)
    miss = poor0 & ~f
    hit = poor0 & f
    def prof(m):
        g = te[m]
        w = g["size"]
        return {"people_pct_of_poor": round(100 * float(wte[m].sum() / wte[poor0].sum()), 1),
                "mean_children": round(float((g.n_child * w).sum() / w.sum()), 2),
                "mean_size": round(float((g["size"] * w).sum() / w.sum()), 2),
                "mean_earners": round(float((g.n_earners * w).sum() / w.sum()), 2),
                "no_children_pct": round(100 * float((w * (g.n_child == 0)).sum() / w.sum()), 1),
                "two_or_more_earners_pct": round(100 * float((w * (g.n_earners >= 2)).sum() / w.sum()), 1),
                "median_income_to_sm_ratio": round(float(g.ratio.median()), 2)}
    R["missed_vs_found_poor_top20"] = {"found": prof(hit), "missed": prof(miss)}
    # RU: риск по десяти равным группам. EN: risk by ten equal groups of people.
    o = np.argsort(-p)
    c = np.cumsum(wte[o]) / wte.sum()
    dec = np.minimum((c * 10).astype(int), 9)
    R["actual_poverty_by_risk_decile"] = [
        {"risk_decile": int(k + 1), "below_sm_pct": round(100 * float((wte[o][dec == k] * te["poor"].to_numpy()[o][dec == k]).sum() / wte[o][dec == k].sum()), 1),
         "poor_or_near_pct": round(100 * float((wte[o][dec == k] * te["poor_or_near"].to_numpy()[o][dec == k]).sum() / wte[o][dec == k].sum()), 1)}
        for k in range(10)]

    out.mkdir(parents=True, exist_ok=True)
    (out / "quick_screen.json").write_text(json.dumps(R, ensure_ascii=False, indent=2, default=float), encoding="utf-8", newline="\n")
    te.assign(risk_poor=np.round(p, 4))[["hh_id", "region", "urban", "size", "n_child", "n_elderly", "n_earners", "ratio", "poor", "poor_or_near", "risk_poor"]] \
        .round({"ratio": 3}).to_csv(out / "quick_screen_scores_2024.csv", index=False, lineterminator="\n")
    print("saved ->", out / "quick_screen.json")


if __name__ == "__main__":
    main()
