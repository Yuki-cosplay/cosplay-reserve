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

---

# M3 事前登録（Transition Threshold / External Supply Parity Reference / seed）

**記録時刻**: 2026-08-16 15:5x JST
**記録時点の commit**: `51cba70`
**config_sha256 (condition A)**: `9ed5ad771bc60335c0977a4a3ae734dd98f7c55820832e0f73a841431167371f`
**すべて main experiment の LLM 実行前に確定した。**

## D5 — External Supply Parity Reference（人間確定）

```
external_reference_supply_per_step
  = max_make_per_agent_per_step × shock_agent_count
  = (time_budget / action_time_cost.make) × shock_agent_count
  = 3 × shock_agent_count          （n=6 なら 18.0 units/step）
```

**★これは現実の外部メーカー能力の実証値ではない★**
community supply を無次元比較するための**正規化基準**である。

- 「Manufacturer 能力の推定値」と呼んではならない
- README / RESULTS / presentation でも、実証的な外部供給能力であるかのように記述してはならない
- **PIPELINE_VALIDATION の観測結果から決定した値ではない**
- `manufacturer_coverage_ratio` 案は却下（実装しない）

**意味**: shock 対象コミュニティの全 Agent が 1 step の時間予算をすべて make へ投入した場合の理論最大供給能力と同量を、比較用 reference capacity とする。

## unit_demand の定義（人間確定）

`unit_demand = 200` は「**ショック発生時点で不足している総需要量（stock）**」である。per-step flow ではない。

**M3 では `remaining_demand` の減少機構を実装しない。** `unit_demand` を供給停止条件にも transition 判定にも使用しない。

**理由**: SPEC §20 の Transition Threshold は4項目のみであり、需要枯渇はそこに含まれない。n=6 では外部比較基準だけで 8 step に 144 units となり、需要枯渇時点が transition 判定に影響しうるため、これを避ける。

**用途**: ショックの不足規模を示す**文脈情報**としてのみ、metadata と Agent-facing shock specification に保存する。Agent へ提示する際も中立属性表現を維持し、answer leak を起こさない。

## D4 — Transition Threshold（人間確定・main experiment 開始前に固定）

| 閾値 | 値 | 根拠 |
|---|---|---|
| `community_supply_share` | **>= 0.25** | share = community/(community + external_reference) より、share=0.25 ⇔ **community = external_reference / 3**。外部比較基準の少なくとも1/3に相当する供給をコミュニティが追加した状態を「無視できない供給」の操作的定義とする |
| `active_supplier_count` | **>= ceil(n/2)** | 少数の突出した Agent だけでなく、shock 対象コミュニティの**少なくとも半数**が供給主体へ転化した状態を要求する |
| `supply_duration_steps` | **>= 4** | ショック相は 1 step = 6時間。**4 step = 24時間**。「継続的供給」の最小単位を1日と定義する |
| `coordination_edges` | **>= 2** | 単発の二者協力1件ではなく、**最低2本**の協調関係が形成された状態を最小の coordination network 形成と定義する |

> **これら4閾値は、PIPELINE_VALIDATION で観測された share / supplier count / duration / coordination edges の値を根拠として選択したものではない。**
> PIPELINE_VALIDATION run（seed 42）は `confirmatory_evidence: false` / `excluded_from_d4_d5_calibration: true` として除外済みである。

## 使用 seed（構造的 eligibility に基づく事前選定）

> ### ⚠️ 旧 scan は無効（pairing inconsistency）
>
> 最初の scan（固定 seed 5, 7, 11, 13, 14）は **P0 の不整合により無効**である。
> ショック対象 Agent を「蓄積相 156 step 後の技能上位 n 名」で選出していたため、
> peer_learning の有無で技能が分岐し、**同一 seed でも A≠C / B≠D の Agent 集合**になっていた。
> 結果として `structural_coordination_capacity` がペアで一致せず、
> SPEC §19 の完全ペアリングが実質的に破れていた。
>
> 旧 scan は `outputs/seed_eligibility_INVALIDATED_prescan.json` に
> `STATUS: INVALIDATED` として保存し、削除していない。**main experiment には使用しない。**
>
> **修正**: ショック対象 Agent は専用 RNG ストリーム（index 4 `shock_agents`）から
> **条件と独立に、同一 seed につき1回だけ**選出し、同じ ID 集合を A/B/C/D すべてへ配布する。
> 技能で選ばないのは、技能による選出自体が条件依存の選択効果を持ち込むためである。

### 確定 seed（P0修正後の再スキャン）

| 項目 | 内容 |
|---|---|
| **固定 seed** | **2, 4, 6, 7, 9** |
| scan した seed 範囲 | 1 〜 9 |
| scan 総数 | **9** |
| ineligible seed | 1, 3, 5, 8 |
| eligibility 判定規則 | **structured(A,C) と rewired(B,D) の双方で `structurally_available_pairs >= 2`** |
| shock_agent_count | 6 |

| seed | shock_agent_ids（A/B/C/D 共通） | structured (A=C) | rewired (B=D) | graph A/C | graph B/D | eligible |
|---|---|---|---|---|---|---|
| 1 | `agent_0, agent_23, agent_25, agent_29, agent_5, agent_8` | 1 | 3 | `eb94db93a6` | `4a789dc592` | ✗ |
| 2 | `agent_1, agent_16, agent_25, agent_27, agent_5, agent_9` | 3 | 3 | `245427cb1e` | `7e7ecb5c90` | **✓** |
| 3 | `agent_13, agent_18, agent_27, agent_3, agent_35, agent_36` | 1 | 0 | `8557bc5b31` | `3be606ea64` | ✗ |
| 4 | `agent_1, agent_11, agent_18, agent_19, agent_21, agent_32` | 5 | 2 | `ef94a13460` | `ba909369ba` | **✓** |
| 5 | `agent_10, agent_16, agent_18, agent_22, agent_24, agent_31` | 1 | 2 | `73f960676f` | `814b833686` | ✗ |
| 6 | `agent_10, agent_13, agent_26, agent_33, agent_4, agent_8` | 2 | 2 | `fa8cd0a3dc` | `352dd17bd7` | **✓** |
| 7 | `agent_0, agent_19, agent_22, agent_37, agent_8, agent_9` | 3 | 2 | `fd67df54c6` | `23da7f988d` | **✓** |
| 8 | `agent_10, agent_11, agent_15, agent_22, agent_31, agent_6` | 0 | 2 | `b48aafb17d` | `7226bb5332` | ✗ |
| 9 | `agent_19, agent_27, agent_28, agent_3, agent_33, agent_35` | 3 | 2 | `3672ad3777` | `1665156089` | **✓** |

**ペアリング同一性はすべての seed で検証済み**（`tests/test_shock_agent_pairing.py`）:
`shock_agent_ids(A)==(B)==(C)==(D)`、`capacity(A)==capacity(C)`、`capacity(B)==capacity(D)`、
`graph_hash(A)==graph_hash(C)`、`graph_hash(B)==graph_hash(D)`、
`induced_subgraph_hash` も同様に一致、pre-network 初期状態ハッシュも4条件一致。

### seed 選定に使用していないもの

**LLM の Intent / community supply / supplier count / transition 結果 / emergence level /
その他 Agent 行動結果を一切参照していない。** 参照したのはネットワーク構造と、
条件非依存の Agent 選出のみである。蓄積相を回す必要すらなくなった。

**これは outcome selection ではなく、測定可能性に基づく pre-experiment eligibility check である。**

## 一般化範囲の制約（重要）

main experiment の推論対象は、

> **「coordination_edges >= 2 が structured / rewired の双方で構造的に測定可能なネットワーク realization」**

に**限定される**。

- 結果を「**すべての network realization で成立する**」と一般化してはならない
- ineligible seed を除外したこと自体は、LLM outcome を観測する**前**の構造的 eligibility 判定であり
  outcome-based cherry picking ではない
- ただし **conditional sample であることを必ず明示する**
- **9 seed 中 4 seed（44%）が ineligible** であった事実も併記する

## main experiment 規模（人間承認待ち）

| 項目 | 値 |
|---|---|
| shock_agent_count | 6 |
| shock_steps | 8 |
| conditions | A / B / C / D |
| eligible seeds | 5, 7, 11, 13, 14 |
| **総 run 数** | **20** |
| calls/run | 48 |
| **総 call 数** | **960** |
| 実測単価 | $0.019035/call |
| **総費用** | **$18.27** |
