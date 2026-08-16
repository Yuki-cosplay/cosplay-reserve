# H1 事前登録（holdout seed 21〜40）

**記録時刻**: 2026-08-16 13:36 JST
**この文書は holdout（seed 21〜40）の結果を見る前に確定した。結果を見た後に primary metric を変更しない。**

## 背景 — なぜ事前登録が必要か

seed 1〜20 の主実験で `maker_count` に天井効果が判明した（全条件 30/30、sd 0.00）。
到達**速度**の指標（`time_to_maker` 系）は、**天井効果を確認した後に追加した**ものである。
したがって seed 1〜20 の結果を confirmatory evidence として扱わない。

**seed 1〜20 の位置づけ**: `ceiling diagnosis / metric selection set`（探索的）

## 事前登録内容

| 項目 | 内容 |
|---|---|
| **primary metric** | **`mean_time_to_maker`** — 各 participant が初めて MAKER 以上へ到達した step の、run 内平均 |
| **secondary metric** | `maker_count_auc`（step 0〜156 の maker_count(participants) の面積） |
| **contrast (peer learning)** | **A vs C**、**B vs D**（paired seed 差分） |
| **contrast (topology)** | A vs B、C vs D（paired seed 差分） |
| **interaction** | (A−B) − (C−D) |
| **seed range** | **21〜40（20 seed）** |
| **条件** | A/B/C/D の4条件、156 週、config・モデル無変更 |
| **config_sha256 (condition A)** | `bab5f05a3b6a4dd2f7afebe64f6039816d2a641f28af678075fc001d4df8ebbc` |
| **model_code_sha256 (src/**/*.py)** | `069df9aff47fb85b6a75efc71b235f8b9f9a489963662fc10cf6bec059b83298` |
| **git commit** | `4a55c42` |

## 判定基準（結果を見る前に定義）

**方向性の予測**: peer learning ON（A, C の A 側 / B, D の B 側）のほうが `mean_time_to_maker` が**小さい**（速い）。

| 判定 | 条件 |
|---|---|
| **supported** | A−C と B−D の paired 差分がいずれも負で、かつ20 seed 中 **15 以上**が負方向 |
| **not supported** | 差分の符号が一貫しない、または効果量が seed 間ばらつき（sd）に埋もれる |
| **inconclusive** | 上記のいずれにも明確に当てはまらない |

**null interpretation**: peer Method transfer という manipulation は成立している（C/D で peer 由来 Method が厳密に 0）が、それが Maker 形成**速度**まで影響していない。すなわち現行設定では H1 は支持されない、と報告する。

**逆転（A > C、すなわち peer ON のほうが遅い）も正当な結果として報告する。**

## 禁止事項

- 結果を見た後に primary metric を変更しない
- モデル・閾値・パラメータを変更しない
- seed を除外しない（全 seed を報告する）

## 既知の制約

`mean_time_to_maker` は per-agent の到達 step ログを持たないため、**集計 `maker_count` の増分から推定**している。`maker_count` は MAKER が可逆（技能減衰で降格しうる）なため単調でない run があり（seed 1〜20 で 54/80 が単調）、非単調な run では推定値に誤差が入る。この制約は `docs/LIMITATIONS_CANDIDATES.md` に記録する。

---

## holdout 結果（2026-08-16 13:39、事前登録後に実行）

| metric | A | B | C | D |
|---|---|---|---|---|
| **mean_time_to_maker** | **12.843** | 12.888 | 13.230 | 13.187 |
| maker_count_auc | 4324.15 | 4322.60 | 4312.45 | 4313.70 |
| peer_methods_final | 51.90 | 49.50 | **0.00** | **0.00** |

paired-seed 差分（負 = peer ON のほうが速い）:

| contrast | mean | sd | n_neg |
|---|---|---|---|
| peer A−C | −0.387 | 0.447 | **15/20** |
| peer B−D | −0.298 | 0.440 | **13/20** |
| topo A−B | −0.045 | 0.358 | 10/20 |
| topo C−D | +0.043 | 0.420 | 9/20 |
| interaction | −0.088 | 0.538 | — |

**判定: not supported（事前登録の基準による）**

- 「supported」の条件は A−C と B−D が**いずれも 15/20 以上**負であること。**B−D が 13/20 で未達**
- 「not supported」の条件「効果量が seed 間ばらつきに埋もれる」に該当（A−C: 効果 0.387 < sd 0.447、B−D: 0.298 < 0.440）

**ただし方向は2つの独立した seed 集合で再現している**（seed 1–20: A−C −0.420 / B−D −0.353、seed 21–40: −0.387 / −0.298）。効果は一貫して peer ON が速い向きだが、**seed 間ばらつきに対して小さい**。

topology 効果と交互作用は**ほぼ 0**（符号も seed 集合間で不安定）。
