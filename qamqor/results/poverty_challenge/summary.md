# Poverty prediction challenge (H4)

Modelled on the World Bank's Pover-T Tests. Every number below is in `leaderboard.csv` or `summary.json`. Synthetic data without survey weights: shares are sample shares, and poverty is income-based, not consumption-based.

## Thresholds fixed before the run

- H4a: the best simple model reaches AUC of at least 0.75 on the 2024 test and finds more poor people than each children rule when it flags the same share of people.
- H4b: supported if the upper bound of the 95% interval for (complex minus simple) AUC is below 0.01; rejected if the lower bound is 0.01 or more; inconclusive otherwise.
- The best simple and the best complex model are chosen by cross-validated log loss on the training years, not on the test year.

## Label balance

| Year | Households | Poor households, % | Poor people, % | Poor or near (below 125%), people, % |
|---|---|---|---|---|
| 2022 | 11939 | 9.72 | 14.42 | 26.71 |
| 2023 | 11977 | 8.37 | 12.61 | 24.2 |
| 2024 | 11960 | 6.19 | 9.07 | 18.34 |

## Verdicts

| Feature set | Best simple | Best complex | Simple AUC | Complex AUC | AUC difference (95% interval) | Log-loss difference (95% interval) | H4a | H4b | H4 |
|---|---|---|---|---|---|---|---|---|---|
| A | logistic_l1 | blend_logistic_lightgbm | 0.8491 | 0.8535 | 0.0044 (0.0022 to 0.0065) | -0.0023 (-0.0032 to -0.0014) | supported | supported | supported |
| A + n_earners (SENSITIVITY, not for verdicts) | logistic_l1 | blend_logistic_lightgbm | 0.9303 | 0.9327 | 0.0024 (0.0011 to 0.0036) | -0.0019 (-0.0028 to -0.0011) | supported | supported | supported |

Feature set A on the temporal test is the headline. Sets marked as sensitivity never enter the verdicts.

## Leaderboard, feature set A: train 2022–2023, test 2024

| Model | Calibrated | Log loss | AUC | Average precision | Brier | Predicted / actual rate, % | Poor people found in top 20%, % | Poor among flagged, % |
|---|---|---|---|---|---|---|---|---|
| prior probability | no | 0.2376 | 0.5 | 0.0619 | 0.0589 | 9.04 / 6.19 | 20.5 | 9.3 |
| rule: 3+ children |  |  | 0.6997 |  |  |  | flags 32.8% of people: finds 69.7% |  |
| rule: 4+ children |  |  | 0.6346 |  |  |  | flags 14.6% of people: finds 45.2% |  |
| logistic_l2 | no | 0.1858 | 0.8492 | 0.33 | 0.0513 | 9.3 / 6.19 | 62.1 | 28.2 |
| logistic_l2 | yes | 0.1857 | 0.8492 | 0.33 | 0.0512 | 9.3 / 6.19 | 62.1 | 28.2 |
| logistic_l1 | no | 0.1858 | 0.8491 | 0.3302 | 0.0512 | 9.31 / 6.19 | 62.3 | 28.3 |
| logistic_l1 | yes | 0.1857 | 0.8491 | 0.3302 | 0.0512 | 9.3 / 6.19 | 62.3 | 28.3 |
| random_forest | no | 0.192 | 0.8392 | 0.3406 | 0.0519 | 9.29 / 6.19 | 61.8 | 28.0 |
| random_forest | yes | 0.1892 | 0.8392 | 0.3406 | 0.0506 | 9.22 / 6.19 | 61.8 | 28.0 |
| lightgbm | no | 0.1835 | 0.8525 | 0.3646 | 0.0505 | 9.37 / 6.19 | 62.4 | 28.3 |
| lightgbm | yes | 0.1832 | 0.8525 | 0.3646 | 0.0502 | 9.37 / 6.19 | 62.4 | 28.3 |
| blend_logistic_lightgbm | no | 0.1835 | 0.8535 | 0.3545 | 0.0505 | 9.34 / 6.19 | 63.9 | 29.0 |
| blend_logistic_lightgbm | yes | 0.1834 | 0.8535 | 0.3546 | 0.0503 | 9.34 / 6.19 | 64.0 | 29.0 |

Model against the rules at the same share of people flagged (logistic_l1):

| Rule | People flagged, % | Rule finds, % | Model finds, % |
|---|---|---|---|
| 3+ children | 32.8 | 69.7 | 79.5 |
| 4+ children | 14.6 | 45.2 | 51.8 |

## Leaderboard, feature set A + n_earners (SENSITIVITY, not for verdicts): train 2022–2023, test 2024

| Model | Calibrated | Log loss | AUC | Average precision | Brier | Predicted / actual rate, % | Poor people found in top 20%, % | Poor among flagged, % |
|---|---|---|---|---|---|---|---|---|
| prior probability | no | 0.2376 | 0.5 | 0.0619 | 0.0589 | 9.04 / 6.19 | 20.5 | 9.3 |
| rule: 3+ children |  |  | 0.6997 |  |  |  | flags 32.8% of people: finds 69.7% |  |
| rule: 4+ children |  |  | 0.6346 |  |  |  | flags 14.6% of people: finds 45.2% |  |
| logistic_l2 | no | 0.1405 | 0.9302 | 0.5708 | 0.04 | 8.89 / 6.19 | 81.1 | 36.8 |
| logistic_l2 | yes | 0.1405 | 0.9302 | 0.5708 | 0.0399 | 8.9 / 6.19 | 81.1 | 36.8 |
| logistic_l1 | no | 0.1405 | 0.9303 | 0.571 | 0.04 | 8.9 / 6.19 | 81.1 | 36.8 |
| logistic_l1 | yes | 0.1405 | 0.9303 | 0.571 | 0.0399 | 8.89 / 6.19 | 81.1 | 36.8 |
| random_forest | no | 0.1464 | 0.9238 | 0.5505 | 0.041 | 8.98 / 6.19 | 80.9 | 36.7 |
| random_forest | yes | 0.1466 | 0.9238 | 0.5505 | 0.0413 | 9.04 / 6.19 | 80.9 | 36.7 |
| lightgbm | no | 0.1385 | 0.9323 | 0.5906 | 0.0395 | 8.93 / 6.19 | 82.6 | 37.4 |
| lightgbm | yes | 0.1387 | 0.9323 | 0.5906 | 0.0396 | 8.97 / 6.19 | 82.6 | 37.4 |
| blend_logistic_lightgbm | no | 0.1384 | 0.9327 | 0.5858 | 0.0393 | 8.91 / 6.19 | 81.8 | 37.1 |
| blend_logistic_lightgbm | yes | 0.1385 | 0.9327 | 0.5858 | 0.0394 | 8.93 / 6.19 | 81.9 | 37.1 |

Model against the rules at the same share of people flagged (logistic_l1):

| Rule | People flagged, % | Rule finds, % | Model finds, % |
|---|---|---|---|
| 3+ children | 32.8 | 69.7 | 92.3 |
| 4+ children | 14.6 | 45.2 | 72.3 |

## Odds ratios, logistic regression, feature set A (training years)

One more unit of the feature multiplies the odds of being below the minimum by this factor, other features held fixed. Associations, not causes.

| Feature | Odds ratio | 95% interval | p |
|---|---|---|---|
| n_child | 2.572 | 2.456–2.694 | 0.0 |
| n_child_u7 | 0.885 | 0.819–0.957 | 0.0021 |
| n_elderly | 0.545 | 0.49–0.606 | 0.0 |
| n_working_age | 0.674 | 0.634–0.717 | 0.0 |
| urban | 1.119 | 0.999–1.253 | 0.0527 |
| region_Abai | 1.485 | 1.079–2.044 | 0.0152 |
| region_Akmola | 0.797 | 0.576–1.104 | 0.1726 |
| region_Aktobe | 0.815 | 0.604–1.1 | 0.1807 |
| region_Almaty city | 1.322 | 0.981–1.782 | 0.0666 |
| region_Almaty region | 1.287 | 0.935–1.771 | 0.122 |
| region_Astana city | 1.354 | 0.997–1.838 | 0.0523 |
| region_Atyrau | 0.82 | 0.599–1.122 | 0.2141 |
| region_East Kazakhstan | 0.706 | 0.474–1.05 | 0.0859 |
| region_Karaganda | 0.664 | 0.478–0.922 | 0.0144 |
| region_Kostanay | 0.485 | 0.336–0.699 | 0.0001 |
| region_Kyzylorda | 0.837 | 0.625–1.122 | 0.234 |
| region_Mangystau | 2.869 | 2.194–3.752 | 0.0 |
| region_North Kazakhstan | 0.694 | 0.482–1.0 | 0.0499 |
| region_Shymkent city | 2.374 | 1.776–3.174 | 0.0 |
| region_Turkestan | 1.737 | 1.327–2.273 | 0.0001 |
| region_Ulytau | 0.608 | 0.399–0.926 | 0.0206 |
| region_West Kazakhstan | 0.736 | 0.543–0.999 | 0.049 |
| region_Zhambyl | 1.689 | 1.28–2.228 | 0.0002 |
| region_Zhetisu | 1.879 | 1.382–2.556 | 0.0001 |
| reference region: Pavlodar | 1.0 |  |  |

## What drives the predictions: AUC lost when a feature family is shuffled (2024)

| Feature family | logistic_l1 | blend_logistic_lightgbm |
|---|---|---|
| children | 0.2808 | 0.2652 |
| region | 0.0295 | 0.0302 |
| age structure | 0.0035 | 0.004 |
| urban/rural | 0.0004 | 0.0004 |

Same ranking in both models: yes.

## Poor people the model finds and misses at the top-20% cut-off

|  | Found | Missed |
|---|---|---|
| people_pct_of_poor | 62.3 | 37.7 |
| mean_children | 4.13 | 2.02 |
| mean_size | 6.6 | 4.77 |
| mean_elderly | 0.36 | 0.35 |
| urban_pct | 50.0 | 53.0 |
| top regions, % of the group | {"Mangystau": 18.5, "Turkestan": 15.5, "Shymkent city": 9.7} | {"Zhambyl": 12.6, "Kyzylorda": 7.4, "West Kazakhstan": 7.4} |

## Leave-one-region-out, 2024

Each region is scored by a model trained on the other 19. Pooled AUC of logistic_l1: 0.8255; of blend_logistic_lightgbm: 0.8254. Regions where logistic_l1 does worst:

| Region | AUC | Poor people found in the region's top 20%, % | Actual rate, households, % |
|---|---|---|---|
| Almaty city | 0.7485 | 50.8 | 4.5 |
| East Kazakhstan | 0.7566 | 50.0 | 2.59 |
| Kostanay | 0.7577 | 52.8 | 1.79 |
| Aktobe | 0.7715 | 49.3 | 4.32 |
| Zhambyl | 0.7905 | 41.5 | 12.04 |

## Not run

- Feature set B (member aggregates, the household head): out/persons.csv is missing; build it with `python build.py <RAW_DATA_DIR> out` and pass --persons out/persons.csv.
- Feature set C (D-006 housing items): needs the raw data folder (--raw) and set B.

## Caveats

- Synthetic data: results show directions, not national estimates.
- Poverty is income-based; official statistics use consumption.
- No survey weights.
- `n_earners` is derived from income records and is used only in the sensitivity run.
- Leave-one-region-out probabilities are not calibrated, so compare AUC and recall there, not log loss.
