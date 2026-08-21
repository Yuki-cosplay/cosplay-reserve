# LIMITATIONS 候補

RESULTS.md の Limitations へ転記する候補を、発生時点で記録する。
**削ること・任意選択したこと自体は許容する。記録しないことは許容しない。**

## L1. assortativity の技能スカラーを「6技能の平均」と定義したこと

**内容**: `add_skill_assortativity()`（`src/culture/network.py`）が参照する技能水準を、6技能の**平均**と定義した。

**任意性**: これは設計上の任意選択である。**`max` や合計を採ると structured topology の構造が変わりうる。** 平均は「全体的な習熟度が近い者同士が繋がる」を、max は「得意分野の水準が近い者同士が繋がる」を表現し、生成されるネットワークは別物になる。

**採用理由**（DESIGN_M1 §7）:
1. max は単一の順序統計量にすぎず、N=40 では「1技能だけ高い者同士が繋がる」構造になる
2. `max_skill` は `judge_maker_stage()` の MAKER 判定に使われており、同じ量を「技能水準」と「段階」の2つの構成概念に流用すると交絡を疑われる

**未検証**: 技能スカラーの定義に対する結果の頑健性は検証していない。A vs B（topology 主効果）の結論は、この定義のもとでのものである。

**記録日**: 2026-08-16

---

## L2. 達成 assortativity が目標未達だった run の扱い

**内容**: `network.assortativity`（0.3）は目標係数であり、`assortativity_swaps × |E|` の上限に達したら未達でも打ち切る。**再試行・上限延長を行わない。**

**帰結**: seed によっては条件A の structured topology が目標より弱い構造になりうる。

**対応**: 達成値を `metadata.json` に全 run 記録する（`assortativity_achieved_structured` / `assortativity_achieved_rewired` / `assortativity_target_reached`）。RESULTS.md で A vs B を論じる際は達成 assortativity の seed 間ばらつきを併記する。

**未達を埋めるための上限延長は禁止**（結果に合わせた調整に接近するため）。

**記録日**: 2026-08-16

---

## L3. 【重要】maker_count に天井効果が発生し、H1 が現行設定では検定不能

**内容**: M1 主実験（20 seed × 4条件 = 80 run、156 週）の結果、**全4条件で participant 30名全員が Maker に到達した（maker_count = 30.00、標準偏差 0.00）**。

| 条件 | maker_count (participants, n=30) | peer 由来 Method 保有数 | skill_mean |
|---|---|---|---|
| A | 30.00 (sd 0.00) | 52.95 | 0.4861 |
| B | 30.00 (sd 0.00) | 52.80 | 0.4860 |
| C | 30.00 (sd 0.00) | **0.00** | 0.4861 |
| D | 30.00 (sd 0.00) | **0.00** | 0.4861 |

主効果はすべて厳密に 0.000（peer learning、topology、交互作用）。

**天井到達の時期**: 条件A seed1 では **step 30 で 30/30 に到達**し、以降 126 step（全体の 81%）は変化しない。

**問題の性質**: これは「差がなかった」という null result **ではない**。従属変数が上限で飽和して分散が 0 になっているため、**そもそも条件効果を観測する余地が構造的に存在しない**。決定 U1 で `advanced_assets` を 3→2 に下げたときと**同じ「構造的な観測不能性」**である。

**重要な区別**（DESIGN_M1 §14.4 / 決定 U1 と同じ枠組み）:
- 「構造的な観測不能性の除去」= 観測装置の較正 → 実験開始前なら許容される
- 「仮説に有利な方向へのパラメータ調整」= 結果の捏造 → 禁止

**決定（2026-08-16、人間承認済み）**: **パラメータを変更しない。** `maker_skill` / stage threshold / `learn_rate` / `decay_rate` / Method 効果その他のモデルパラメータは一切変更しない。**天井効果を解消する目的での閾値変更は禁止する。** 天井効果は認めたうえで、到達**速度**の指標（`mean_time_to_maker`）を primary metric として holdout seed 21〜40 で判定した（L3 分類 **Case C**、`docs/RESULTS_CANDIDATES.md`）。

**なお peer learning の遮断自体は正しく機能している**（C/D で peer 由来 Method が厳密に 0、A/B で約53）。機構は動いており、飽和しているのは maker_count という指標の側である。

**記録日**: 2026-08-16

---

## L4. 感度分析 15セルを M1 時点で実施していない（P2 へ後回し）

**内容**: `experiments/sensitivity_grid.py`（15セル × 4条件 × 5 seed = 300 run）は実装済みだが、**未実行**。時間制約により P2 とし、M3 完了後に余裕がある場合のみ実施する。

**実施セル**: なし
**未実施セル**: S01〜S15 の全15セル

**RESULTS.md に必ず記載する文言**:
> 本結論は特定のパラメータ設定下でのものであり、learn_rate と decay_rate の比に対する頑健性は未検証である。

**記録日**: 2026-08-16

---

## L5. Method → production success は成立するが、production success → Maker stage への伝播が弱い

**内容**: M1 の因果連鎖を段階ごとに見ると、上流は作動しているが下流で効果が失われる。

| 段階 | 状態 | 証拠 |
|---|---|---|
| peer Method transfer | ✅ 作動 | A/B で約50件、C/D で厳密に 0 |
| Method → 制作成功確率 | ✅ 作動 | +0.161〜+0.223（解析評価） |
| 制作成功 → **Maker stage 到達** | ⚠️ **弱い** | mean_time_to_maker の差 −0.387（sd 0.447 に埋もれる） |

**ボトルネックの所在**: scaffolding 機構そのものではなく、**production success から Maker stage 指標への伝播**にある（L3 分類 Case C）。

**考えられる要因**（検証していない・パラメータ変更もしていない）:
- `maker_projects = 3` が低く、Method の有無にかかわらず短期間で満たされる
- `maker_count` が上限 30 の離散指標であり、step 30 で飽和する（L3）
- 自己発見 Method が peer 由来 Method を大きく上回り（自己発見が支配的）、peer 経路の限界寄与が小さい

**未検証**: 上記要因の切り分けは行っていない。**天井効果を解消する目的での閾値変更は禁止されている。**

**記録日**: 2026-08-16

---

## L6. `mean_time_to_maker` が集計値からの推定であること

**内容**: primary metric の `mean_time_to_maker` は、per-agent の初到達 step ログを持たないため、**集計 `maker_count` の増分から推定**している。

**制約**: `maker_count` は MAKER が可逆（技能減衰で降格しうる、決定 Z1）なため単調でない run がある（seed 1〜20 で 54/80、seed 21〜40 で 53/80 が単調）。**非単調な run では推定値に誤差が入る。**

**影響**: 効果量が seed 間ばらつきに埋もれる規模（−0.39 vs sd 0.45）であるため、この推定誤差は結論に影響しうる。per-agent の到達 step を直接記録する計装は M1 では実施していない。

**記録日**: 2026-08-16

---

## L7. 【P0・freeze解除事由】coordination_edges が原理的に到達不能だった実装欠陥

**発見日**: 2026-08-16（M3 PIPELINE_VALIDATION の解析中）

**根本原因**: `propose` は `ShockState.proposals` に記録されるだけで、他Agentの `Observation` にも `inbox` にも到達していなかった。`join` の前提条件は「対象が近傍であること」かつ「対象が提案済みであること」だが、**Agent には誰が提案したかを知る経路が存在しなかった**。

**帰結**: `coordination_edges` は agent 数を増やしても構造的に常に 0。転化4条件の1つが永久に偽となるため、**転化は原理的に TRUE になりえなかった**。

**これはパラメータ調整ではない。** 結果を改善するための閾値変更ではなく、評価指標が定義上到達不能だった欠陥の修正である（freeze 規約の P0「実行不能」「条件交絡」に該当）。

**修正**: `Observation.neighbor_proposals` を追加し、`build_observation` 内で `known_agents` に限定して絞り込む。global proposal list は渡さない。

**修正時刻**: 2026-08-16 15:0x JST / **修正前 commit**: `e53c908`

**結果への影響**: PIPELINE_VALIDATION run（seed 42）の `coordination_edges=0` は、この欠陥下での観測値である。**本実験の根拠にも D4 の calibration にも使用しない**（既に除外指定済み）。

---

## L8. D5（baseline_supply_per_step）に外部の実証的根拠が存在しない

**内容**: `community_supply_share` の分母を決める `baseline_supply_per_step`（既存供給能力）について、**現実データに基づく値が存在しない**。COVID期のメイカー活動に対応する定量データは存在しないか極めて限定的である（`docs/REVIEW.md` §12.1【要承認3】と同じ理由）。

**帰結**: `community_supply_share` の絶対値は D5 の選び方に完全に依存する。閾値 0.25 が「無視できない供給」を意味するかどうかは、D5 が何を表すかで変わる。

**候補「3 × agent数」の問題点**: モデル上の最大 make 回数から導いた値であり、**外部供給の意味と一致しない**。詳細は報告参照。

**推奨**: D5 を固定定数として確定するのではなく、**感度分析の因子**として扱い、`community_supply_total`（絶対量）を主指標、`community_supply_share` を副指標とする。

**記録日**: 2026-08-16

---

## L9. 【P0】ショック対象 Agent 選出が条件依存だった（pairing inconsistency）

**発見日**: 2026-08-16（seed eligibility report の査読中、人間が検出）

**根本原因**: ショック対象 Agent を「蓄積相 156 step 後の participant 技能上位 n 名」で選出していた。peer_learning の有無で技能が分岐するため、**同一 seed でも A≠C / B≠D の Agent 集合**になっていた。

`base_graph_sha256` と pre-network 初期状態ハッシュは4条件で一致していたが、**選出された Agent 集合が違うため誘導部分グラフが異なり**、`structural_coordination_capacity` が A/C・B/D で一致しなかった（例: seed 1 で A=0 / C=1、seed 2 で A=4 / C=1）。

**帰結**: SPEC §19 の完全ペアリング（A/C・B/D が同一 Graph object 由来）が、**構造量の測定レベルで実質的に破れていた**。この状態で得た seed 固定（5, 7, 11, 13, 14）は無効。

**修正**: 専用 RNG ストリーム（index 4 `shock_agents`）を末尾に追加し、**条件と独立に同一 seed につき1回だけ**選出して同じ ID 集合を A/B/C/D へ配布する。末尾追加のため index 0〜3 の子ストリームは不変で、既存 run の再現性は保たれる（テストで検証）。

**選出規則を「技能上位」から無作為へ変更した理由**: 技能で選ぶこと自体が条件依存の選択効果を持ち込む。無作為選出は条件間で構造的に同一になる。

**無効化した scan**: `outputs/seed_eligibility_INVALIDATED_prescan.json`（削除せず `STATUS: INVALIDATED` で保存）

**記録日**: 2026-08-16

---

## L10. External Supply Parity Reference により share の上限が 0.5 に固定されること

**内容**: D5 = `3 × shock_agent_count` は community の理論最大供給能力と同量であるため、`community_supply_share` の上限は **agent 数によらず 0.5 に固定**される。

**帰結**: share はコミュニティ供給の**規模**ではなく「理論最大能力に対する達成率」を測る指標になる。閾値 0.25 は「理論最大の半分を達成」と等価である。

**これは設計上の選択であり欠陥ではない**（人間確定 2026-08-16）。ただし RESULTS.md で share を論じる際は、**この上限が構造的に 0.5 であること**を明示し、絶対的な供給規模の比較には `community_supply_total` を併用すること。

**記録日**: 2026-08-16

---

## L11. 【P0・freeze解除事由】事前登録 D4 が runtime config へ同期されないまま main experiment を実行した

**発見日**: 2026-08-16（main experiment 20/20 完了報告を人間が査読した際に指摘）

**問題**: 人間承認済みの正式事前登録 D4 は
`share >= 0.25` / `suppliers >= ceil(n/2) = 3` / `duration >= 4` / `edges >= 2`
であるのに対し、20 run は
`share >= 0.20` / `suppliers >= 3` / `duration >= 3` / `edges >= 2`
で実行された。**share と duration の2項目が不一致**。

**根本原因**: commit `573be42` で導入された PIPELINE_VALIDATION 用の暫定値
（config 内に `★D4 未決（要人間決定）★ … 暫定値。` と自己申告されていた）が、
D4 を確定した commit `2de6b52` で更新されなかった。
同 commit は `configs/base.yaml` の **D5 ブロックだけを書き換え、直下の D4 ブロックを素通り**している
（`git show 2de6b52 -- configs/base.yaml` の diff 末尾に旧 D4 コメントが context 行として残っている）。
確定値は `docs/PREREGISTRATION_H1.md` §D4 と `experiments/m3_main.py` の docstring にのみ記録され、
**runtime が実際に読む config には到達しなかった**。

**なぜ検出されなかったか**: 実行後の逸脱チェックが
「20 run で同じ値だったか」という**内部整合性**しか検査しておらず、
「事前登録値と一致しているか」という**外部基準との照合**を行っていなかった。
`config_sha256` は seed 由来で 20 種類、`prompt_sha256` は 1 種類、
`D4_transition` は全 run 同一 — これらはすべて通過してしまう。
`m3_main.py` に D4 のモジュール定数が存在せず、
`test_frozen_spec_matches_approved_values` も D4 を一切 assert していなかった。

**分類**: config synchronization error（+ frozen-spec test の検査漏れ）。
preregistration document は正しい値を保持しており、runtime 実装ロジックにも報告にも誤りはない。

**結果への影響**: runtime 判定では 6/20 run が転化 TRUE。
事前登録値で既存ログを再判定（corrected adjudication）すると **0/20 run**。
6 run すべてが FALSE へ変わる。律速は全 run で `community_supply_share`
（観測 max 0.154〜0.250 に対し閾値 0.25）。

**対応**:
- runtime 判定（a）は各 run ファイルに保持し、削除・上書きしない
- 事前登録値による再判定（b）を `outputs/main_experiment/transition_recomputed_preregistered.json` へ**新規**保存
- 再判定は既存の `TransitionJudge.evaluate()` を再利用（判定ロジックを再実装していない）。
  runtime 閾値で replay すると 20 run × 8 step の `met_*` / `all_met` / `transition_step` が
  ログと完全一致することを自己検証済み
- 検証を `experiments/audit_preregistration.py`（事前登録 / config / run metadata の三者突合）と
  `tests/test_preregistration_sync.py` へ変更
- **(b) を最終主結果とすることを人間が確定した（2026-08-16）。**
  事前登録値による corrected adjudication（転化 **0/20**）が主結果である。
  runtime config の暫定値による判定（転化 6/20）は、**事前登録との不一致を示す副次的記録**として
  各 run ファイルに保持する。削除も上書きもしないが、結果の主張には使用しない。

**config の是正（2026-08-16、人間承認済み）**:

1. 実行時 config を `configs/as_executed/main_experiment_20260816.yaml` へ**歴史的記録として保存**した
   （commit `0976cf2` の `configs/base.yaml` とバイト単位で同一。冒頭に不一致の経緯を明記）。
   **編集禁止・再実行の起点に使わないこと。**
2. `configs/base.yaml` の D4 を**正式事前登録値 0.25 / 3 / 4 / 2 へ同期**し、
   `★D4 未決（要人間決定）★ … 暫定値。` のコメントを削除した。
   **第三者が現在の `configs/base.yaml` から実行すれば、正式事前登録値による判定になる。**
3. `tests/test_preregistration_sync.py` の xfail 2件を解消し、通常 PASS へ移行した
   （config↔事前登録の一致 / run metadata↔as_executed の一致 / as_executed が事前登録と
   異なることの固定 / 主結果ファイルが事前登録値であることの確認）。

**既存 20 run の metadata と output は一切変更していない。** run metadata の `D4_transition` は
実行時の値（0.20/3/3/2）のまま保持され、`as_executed` と一致することをテストが保証する。

**API 再実行は行っていない。** corrected adjudication は既存ログのみを用いた再判定であり、
LLM 呼び出し数は 0 である。

**記録日**: 2026-08-16

---

## L12. 技能が蓄積相で飽和し、ショック相の success_probability の技能項が情報を持たない

**発見日**: 2026-08-16（`modify_difficulty_penalty` 感度分析の replay 可否検証中）

**内容**: 蓄積相 156 step 後、供給経路の主要技能は **0.9976〜0.9985** に飽和している
（seed 2 / 条件A / shock 対象 6 agent で実測）。その結果、`success_probability()` が返す
`p_base` は **全 make 試行 1110 件の 99.6%（1106件）で上限 0.98 にクリップ**されている。

| n_shifts | p_base | 件数 |
|---|---|---|
| 0 | 0.9636〜0.9694 | 4 |
| 0 | 0.9800（クリップ上限） | 31 |
| 1 | 0.9800 | 6 |
| 2 | 0.9800 | 1069 |

`p_base = 0.98` に必要な raw は 0.5838（temperature 0.15）であるのに対し、実際の raw は 0.898
（**余裕 +0.314**）。一方、1 run で1 agent が行う make の最大回数は 15 回であり、
収穫逓減 `gain = base × (1 − skill)` を考慮すると、15回すべて成功した場合とすべて失敗した場合の
技能乖離は **0.0008**（余裕 0.314 の約 1/400）にすぎない。

**帰結**: **`success_probability` の技能項は、ショック相において情報を持っていない。**
したがって「技能を上げる介入が効かない」という B8 の診断は、
**現実についての発見ではなく、モデルの構成上の帰結である。**

**同型の先行事例**: この飽和は M1 の `maker_count` 天井効果（全条件 30/30、L3）と同型である。
**本モデルには、蓄積量が上限に達したあとの差異が観測されにくい構造がある。**
L3 は Case C（中間機構は動くが下流への伝播が弱い）として記録済みであり、
L12 はその構造がショック相にも及んでいることを示す。

**結果への影響**:
- `modify_difficulty_penalty` の感度分析において、`penalty = 0.00` のケースは
  「ほぼ全 agent が `p_eff = 0.98`」となる。これは意図した構造的上限だが、
  **技能分布の違いが上限側でまったく効かない**ことも同時に意味する。
- A/B/C/D の条件間比較でショック相の供給量に差が出にくい一因である可能性がある
  （**未検証。断定しない**）。

**是正の候補（いずれも未実施・未承認）**: 蓄積相 step 数の短縮（52 / 104 週は config 済み）、
`learn_rate` / `decay_rate` の見直し、`success_probability` のクリップ上限の再検討。
**ただし結果を見た後のパラメータ調整は禁止（SPEC §30）**であり、実施する場合は
事前登録を伴う独立した実験として行うこと。

**記録日**: 2026-08-16

---

## L13. penalty 感度分析は partial-equilibrium（意思決定を固定した感度）である

**内容**: `modify_difficulty_penalty` の感度分析は、既存 main experiment の provenance から
`p_base` を復元し、production layer のみを再計算する deterministic replay で行う（API 0 call）。
この設計では **Agent の意思決定を main experiment のログに固定する。**

**帰結**: penalty が実際に異なれば、Agent は modify 回数や make / practice / share の
行動配分を変えた可能性があるが、**それは捉えていない。**

> 得られるのは「**意思決定が同じままなら、penalty がどれだけ供給量を動かすか**」であり、
> 「**penalty が違う世界での供給量**」ではない。

**この設計を選んだ理由**: LLM を再実行すると penalty 差と LLM 応答差が混ざり、
どちらが供給量を動かしたのか帰属できなくなる。分離を優先した。

**この限界を限界のまま残さないための対応**: 条件A・seed 2 / 4 について
`penalty = 0.00` の live run を **2本だけ**実行し、replay 予測値との差を
**「意思決定応答の効果」として定量化する**（事前登録は `docs/PREREGISTRATION_SENSITIVITY.md`）。
**n=2 のため、この2 run から条件間比較や仮説検証は行わない。**

**記録日**: 2026-08-16

---

## L14. D5 正規化により、shock_agent_count の効果が share から相殺されやすい

**記録日**: 2026-08-16（API 不使用のコード構造確認による）

### 代数的な部分（厳密に成立）

`community_supply_share = C / (C + B)`、`B = external_reference_supply_per_step`。

`src/world/demand.py:65-80` より、**B は n に厳密に比例する**:

```
B = (time_budget // action_time_cost.make) × shock_agent_count = 3 × n
```

ここで 1 agent・1 step あたりの平均供給量を `q = C / (n × T)`（T = step 数）と置くと、
`C = n q T`、`B = 3 n T` であるから

```
share = nqT / (nqT + 3nT) = q / (q + 3)
```

となり **n が代数的に消える**。この恒等式は数値的にも確認済み（誤差 < 1e-12）:

| penalty | C (units/step) | q = C/6 | C/(C+18) | q/(q+3) |
|---|---|---|---|---|
| 0.00 | 6.5109 | 1.0851 | 0.265632 | 0.265632 |
| 0.35 | 3.8299 | 0.6383 | 0.175444 | 0.175444 |

### ★ただし `C = n q T` と置けるのは、q が n に依存しない場合に限る★

コード構造を確認した結果、**q の n 非依存性は production 層では成立するが、
decision 層では保証されない。**

**n 非依存が構造的に成立する経路**:

| 経路 | 確認結果 |
|---|---|
| 材料 | `agent.materials` は **agent ごとの私有在庫**。`replenish_materials` は agent ごとに独立補充、`consume_materials` は当該 agent のみ減算。**共有プールなし → 競合なし**（`src/world/resources.py:17-26`） |
| 設備 | `_owns(agent, asset_id, cfg)` は `agent.assets[asset_id]` を見る **agent ごとの保有**。共有プールなし（`src/world/production.py:11-19`） |
| 時間予算 | agent ごと、step ごとにリセット |
| 成功確率 | `success_probability` は当該 agent の技能・method・設備のみに依存 |
| `unit_yield` | 定数 1.0 |
| `active_supplier_count` | **production へ帰還しない**。`TransitionJudge.evaluate()` が読むだけで、供給量に非線形な影響を与えない |
| coordination | `state.coordination_edges()` も judge が読むだけで、`_resolve_shock` の成功確率計算に入らない |

**n 依存が残る経路（3件、いずれも decision 層）**:

1. **`neighbor_proposals`**: `build_observation` は全体の proposal 辞書を `agent.known_agents`
   で絞り込む（`src/agents/observation.py:81-86`）。ショック相で行動するのは
   `llm_agent_ids` の n 名のみ（`shock_step` のループが `for aid in sorted(llm_agent_ids)`）
   であるため、**n が増えるほど各 agent に見える提案が増え、LLM の意思決定が変わりうる。**
2. **`select_shock_agents`**: 30 名の participant から n 名を一様無作為抽出する。
   n が変われば選ばれる agent 集合が変わり、技能・設備・材料の実現値が変わる。
   **期待値としては n 非依存だが、実現値としては保証されない。**
3. **誘導部分グラフの密度**: 選出された n 名の間の隣接ペア数は n に対して組合せ的に増える。
   propose / join の機会が変わり、時間配分が make から移動しうる。

### したがって L14 の記述は次に限定する

> **「人数そのものの効果は、D5 正規化（B = 3n）によって share から相殺されやすい。」**

**「n は完全に消える」と書いてはならない。** 消えるのは代数的な部分だけであり、
`q` が n に依存しないことは production 層でのみ構造的に保証され、decision 層では保証されない。

**未検証**: 実際に n を変えて q が動くかは測定していない（本確認は API 不使用の構造確認のみ）。
n を変えた実験は実施しておらず、実施する場合は事前登録を伴う独立した実験とする。

---

## L15. community_supply_share と parity utilization ratio は別量である

**記録日**: 2026-08-16

**内容**: 2つの比を混同してはならない。

| 指標 | 定義 | current model (C=3.830, B=18) |
|---|---|---|
| `community_supply_share`（**転化判定に使う正式指標**） | `C / (C + B)` | **0.1754** |
| parity utilization ratio（**分析上の補助指標**） | `C / B` | **0.2128** |

D4 の閾値を両方の尺度で書くと:

```
community_supply_share = 0.25
  ⇔ C / (C + 18) = 0.25
  ⇔ C = 6.0
  ⇔ parity utilization ratio = 6 / 18 = 0.3333
```

**禁止する表現**:
- ~~「share = コミュニティが理論最大供給能力の何 % で稼働しているか」~~
- ~~「share = 21%」~~（21.3% は parity utilization ratio であって share ではない）

**RESULTS.md での正式な書き方**:

> current model の期待供給率は External Supply Parity Reference の**約 21%** に相当し、
> D4 の share 閾値 0.25 を満たすには**約 33% 相当**が必要だった。

**「稼働率」という語を使う場合は、必ず "Parity Reference 比" であることを明記する。**
D5 は現実の外部メーカー能力の実証値ではなく正規化基準であるため（L8 / L10）、
現実の設備稼働率と誤認されてはならない。

penalty 別の両指標:

| penalty | C (units/step) | share = C/(C+B) | parity utilization = C/B |
|---|---|---|---|
| 0.00 | 6.511 | 0.2656 | 0.3617 |
| 0.15 | 5.008 | 0.2177 | 0.2782 |
| 0.35 (current) | 3.830 | **0.1754** | **0.2128** |
| 0.50 | 3.255 | 0.1532 | 0.1809 |

---

## L16. penalty = 0.00 の位置づけ（解釈の固定）

**記録日**: 2026-08-16

**正式な位置づけ**:

> **`penalty = 0.00` は、modify による追加の成功確率ペナルティをゼロと仮定した
> モデル上の構造的上限ケースである。**

この上限ケースでのみ、期待供給率 **6.511 units/step** が必要供給率 **6.0 units/step** を
**約 8.5% 上回った**。

**RESULTS.md での正式な書き方**:

> **仕様適応による追加ペナルティをゼロと仮定する上限ケースでのみ、D4 の量的条件を超えた。**

**禁止する表現**（いずれも書いてはならない）:
- ~~penalty を下げれば転化する~~
- ~~熟練を高めれば転化する~~
- ~~penalty = 0 が現実に達成可能である~~
- ~~penalty = 0 が物理的に絶対不可能である~~

**「物理的にありえない」と断定してはならない。** `modify_difficulty_penalty` は実データで
校正されていない（L13 / 感度分析の前提）。現実の値が 0 に近いか遠いかは**未知**であり、
その決定は実地 Pilot（Specification Adaptation Challenge）の測定課題である。
