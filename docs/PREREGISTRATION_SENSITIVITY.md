# 事前登録: modify_difficulty_penalty 感度分析

**登録日**: 2026-08-16（**replay 実行前・live run 実行前**）
**人間承認**: 済
**対象**: `docs/LIMITATIONS_CANDIDATES.md` L12 / L13

---

## 0. 目的（Transition を成功させることではない）

> **今回の bottleneck 診断が、実データで校正されていない単一パラメータ
> `modify_difficulty_penalty = 0.35` にどの程度依存するかを確認する。**

B8 の診断（供給量の主要律速は make 成功確率であり、その低下は仕様適応のための
modify が課す難度ペナルティに由来する）は、この 1 パラメータの上に乗っている。
**その依存度を測るのが本分析の唯一の目的である。**

転化の成否は結果として報告するのみで、**目的にしない**。

---

## 1. 感度値（結果を見る前に固定。以後追加・変更しない）

| penalty | 位置づけ |
|---|---|
| **0.00** | **penalty なしの構造的上限。** 仕様適応が成功確率を一切下げない世界 |
| **0.15** | **model sensitivity range（実証値ではない）** |
| **0.35** | **current model.** main experiment が使用した値。**実データ未校正** |
| **0.50** | **model sensitivity range（実証値ではない）** |

**0.15 / 0.50 は実証値ではなく、モデルの感度域を張るための値である。**
**結果を見てから値を追加・変更しない。**

---

## 2. 方式: deterministic replay（API 0 call）

### 2.1 `p_base` の復元式

production layer の該当箇所（`src/world/shock.py:132-137`）:

```python
penalty = 1.0 + shock["modify_difficulty_penalty"] * n_shifts
p = success_probability(agent, project, cfg)          # penalty に依存しない
p = max(0.02, min(0.98, p / penalty))
success = bool(rng.random() < p)
```

`success_probability()` は `skill + asset_bonus − effective_difficulty` のロジスティックであり、
**penalty を参照しない**。provenance には `effective_success_probability`（除算後の `p`）と
`applied_modifications`（`n_shifts`）が両方記録されているため、

> **`p_base = p_eff_logged × (1 + 0.35 × n_shifts)`**

で厳密に復元できる。全 1110 make 試行で復元可能であることを確認済み。

**クリップによる情報損失がないことの確認**:
- 上側クリップ: `p_base ≤ 0.98` かつ `penalty ≥ 1` のため、`n_shifts ≥ 1` では原理的に発動しない
- `n_shifts = 0` では `penalty = 1` なので `p_eff = p_base`（`success_probability` 内で既にクリップ済み）
- 下側クリップ 0.02: `p_base < 0.034` でのみ発動。観測範囲外

復元結果:

| n_shifts | p_base | 件数 |
|---|---|---|
| 0 | 0.9636〜0.9694 | 4 |
| 0 | 0.9800 | 31 |
| 1 | 0.9800 | 6 |
| 2 | 0.9800 | 1069 |

**1110 件中 1106 件（99.6%）が `p_base = 0.98`**（`success_probability` 内部のクリップ上限）。

### 2.2 技能フィードバック経路が不活性であることの証明

replay の最大の懸念は「penalty を変えると成功/失敗が変わり、`apply_skill_gain` 経由で
技能が分岐し、以後の `p_base` が変わる」という帰還ループである。**これは塞がっている。**

| 量 | 値 |
|---|---|
| 蓄積相 156 step 後の該当技能（seed2 / 条件A / shock 対象 6 agent） | 0.9976〜0.9985 |
| `p_base = 0.98` にクリップされるのに必要な raw（temperature 0.15） | 0.5838 |
| 実際の raw | 0.898（**余裕 +0.314**） |
| 1 run で 1 agent が行った make の最大回数 | 15 |
| 15回すべて成功 vs すべて失敗 の技能乖離（`gain = base × (1 − skill)` の収穫逓減込み） | **0.0008** |

**最悪ケースの技能乖離 0.0008 は、クリップまでの余裕 0.314 の約 1/400。**
8 step のショック相では、penalty をどう変えても `p_base` をクリップ下へ押し下げることは
**構造的に不可能**である。したがって replay はこの帰還経路に関して**厳密**である。

（この飽和自体はモデルの限界であり、L12 に記録した。）

### 2.3 現行値での再現検証（実施済み）

`penalty = 0.35` で解析的期待値を計算し、実測供給と突き合わせた（全 20 run）:

| | 実測 | 解析期待値 | 差 |
|---|---|---|---|
| 供給合計 | 606.0 | 612.79 | −6.79（**−1.1%**） |

run 別の差は平均 −0.34、標準偏差 3.30。二項ノイズ `√(52×0.576×0.424) ≈ 3.6` と一致し、
**系統的なズレはない。**

### 2.4 主要指標: 解析的期待値（RNG 不使用）

```
p_base  = p_eff_logged × (1 + 0.35 × n_shifts)
p_eff'  = max(0.02, min(0.98, p_base / (1 + P' × n_shifts)))
E[供給] = Σ_{meets_requirement な試行} p_eff' × unit_yield(=1.0)
```

- `meets_requirement` は属性で判定され penalty 非依存 → ログ値をそのまま使用
- `material_feasible` / `asset_feasible` も penalty 非依存 → そのまま
- `consume_materials` は成功可否と無関係に実行されるため材料状態も分岐しない

### 2.5 副次指標: common random numbers による Monte Carlo

`max community_supply_share` と corrected transition は `active_supplier_count`（整数）と
step 単位の離散実現を要するため期待値では出せない。

- 各 make 試行に `(condition, seed, step, agent_id, 試行連番)` から決定論的に導出した一様乱数 `u` を割り当てる
- **4 つの penalty 値すべてで同じ `u`** を使う（common random numbers）→ penalty 差だけが動く対応比較
- `success = u < p_eff'`、`supplied = 1.0 if success and meets_requirement`
- step ごとに ledger を再構成し、**既存の `TransitionJudge.evaluate()` をそのまま再利用**する
  （corrected adjudication と同一方式。判定ロジックを再実装しない）
- `coordination_edges` は propose / join 由来で penalty 非依存 → `transition_history` のログ値を投入
- 反復数 **R = 2000**（結果を見て変更しない）
- 転化判定の閾値は**正式事前登録 D4**（`share>=0.25 / suppliers>=3 / duration>=4 / edges>=2`）

---

## 3. 評価指標

**Transition TRUE/FALSE を主要指標にしない。**

**主要**:
- `community_supply_total`
- community supply units/step
- make success rate
- D4 required rate **6.0 units/step** との差

**副次**:
- `max community_supply_share`
- corrected transition result

---

## 4. 実行前の予測（★実行前に記録。実行後に変更しない★）

> ### 予測 P1
> **`penalty = 0.00` のとき、条件A の供給は約 6.4 units/step になる。**
>
> 根拠: 仕様適合 make が 6.58 /step（条件A 5 run 実測）、`p_eff = 0.98`
> （`p_base` の 99.6% がクリップ上限のため）→ 6.58 × 0.98 ≈ **6.45 units/step**。
>
> これは **D4 閾値 6.00 units/step をわずかに超える水準**である。

> ### 予測 P2
> したがって `penalty = 0.00` では **share 条件が初めて満たされうる**が、
> **余裕は極めて小さい（約 +7%）**。転化するかどうかは断定しない。

**この予測が当たるか外れるかを、結果と併記して報告する。**

---

## 5. 解釈ルール（結果を見る前に固定）

| 結果 | 結論として述べてよいこと |
|---|---|
| penalty 値で大きく変化する | 「**現在の供給能力診断はこの未校正パラメータに敏感であり、実地 Pilot による calibration が社会実装上必須**」 |
| 広い範囲で同じ傾向 | 「**仕様適応コストが供給能力を左右する重要変数である可能性**」まで |

**いずれの場合も、次のようには書かない**:

> ~~「現実のコスプレ制作では仕様適応が量産を妨げることを証明した」~~

---

## 6. 出力

- `outputs/sensitivity_replay/`（新規ディレクトリ）
- **既存 20 run のログ・`campaign.json`・`transition_recomputed_preregistered.json` は読み取りのみ。変更・上書きしない。**

---

## 7. 追加検証: partial-equilibrium 仮定の実測（live run 2本）

L13 の限界を、限界のまま残さず測定値に変える。

### 7.1 設定（実行前に固定）

| 項目 | 値 |
|---|---|
| 対象 | **条件A、seed 2 および 4** |
| 設定 | `modify_difficulty_penalty = 0.00`（**他は main experiment と完全に同一**） |
| run 数 | **2**（打ち止め） |
| 推定費用 | $1.85（最大 $1.89、retry 1回で $2.84） |
| CostGuard | **per-run $1.25 / campaign $3.00** |
| D4 | 正式事前登録値 `0.25 / 3 / 4 / 2` |

### 7.2 目的

replay（意思決定固定）の予測値 **X** と、live run（意思決定が応答しうる）の実測値 **Y** を
突き合わせ、その差を **「意思決定応答の効果」** として定量化する。

| 差 | 解釈 |
|---|---|
| 小さい | partial-equilibrium 近似が妥当 |
| 大きい | Agent は penalty に応じて行動配分を変えている |

### 7.3 replay による予測値（★live run 実行前に確定。実行後に変更しない★）

**確定日**: 2026-08-16（replay 実行後・live run 実行**前**）
出典: `outputs/sensitivity_replay/penalty_sensitivity.json`（条件A、`penalty = 0.00`）

#### 供給量の予測

| seed | replay 予測 `community_supply_total` (X) | units/step | live 実測 (Y) | 差 (Y − X) |
|---|---|---|---|---|
| **2** | **49.980** | 6.247 | （live 後に記入） | |
| **4** | **54.880** | 6.860 | （live 後に記入） | |

参考（変更禁止の既存事実）: `penalty = 0.35` の実測は seed 2 = 27.0、seed 4 = 32.0。

#### replay による転化判定（正式 D4、CRN Monte Carlo R=2000）

| seed | 転化確率 | mean max share | 予測 |
|---|---|---|---|
| **2** | **0.9855** | 0.2579 | **転化する見込み** |
| **4** | **1.0000** | 0.2780 | **転化する見込み** |

**ただしこれは「penalty=0 なら転化するか」を確かめる実験ではない**（§7.4）。
転化の有無は結果として報告するのみ。

#### 予測の基礎量（penalty=0.00 での replay）

| seed | make 試行 | 仕様適合試行 | p_eff | 二項 sd |
|---|---|---|---|---|
| 2 | 52 | 51 | 0.98 | 1.000 |
| 4 | 65 | 56 | 0.98 | 1.048 |

### 7.3.1 live / replay 差の許容基準（★実行前に固定★）

live run は**単一の確率的実現**であり、replay 予測は**期待値**である。
したがって両者は、意思決定応答がゼロであっても二項ノイズの分だけずれる。
このノイズを超えるかどうかで判定する。

判定量: **D = Y − X**（live 実測 − replay 予測、`community_supply_total`）

基準となるノイズ幅: 仕様適合試行数 n_q、`p_eff = 0.98` としたときの
`sd = √(n_q × 0.98 × 0.02)`

| seed | sd | **±2 sd（許容帯）** |
|---|---|---|
| 2 | 1.000 | **±2.00** |
| 4 | 1.048 | **±2.10** |

| 判定 | 条件 | 結論 |
|---|---|---|
| **一致** | 両 seed とも `|D| ≤ 2 sd` | **partial-equilibrium 近似は妥当**。replay の感度分析結果はそのまま解釈してよい |
| **不一致** | いずれかで `|D| > 2 sd` | **Agent は penalty に応じて行動配分を変えている。** replay 結果は「意思決定固定下の値」としてのみ解釈し、L13 を限界から**測定済みのバイアス**へ格上げする |

**符号の解釈**（不一致の場合のみ）:
- `D > 0`: penalty 低下に対し Agent は make を増やす方向に応答 → replay は**過小評価**
- `D < 0`: penalty 低下に対し Agent は modify や他行動へ配分を移す → replay は**過大評価**

**n=2 のため、この判定は「近似の妥当性」についてのみ行う。**
効果量の推定も、条件間比較も、仮説検証も行わない。

### 7.3.2 CostGuard（★実行前に固定★）

| 項目 | 値 |
|---|---|
| per-run 上限 | **$1.25** |
| campaign 上限 | **$3.00** |
| 推定費用 | $1.85（実測単価 $0.9252/run × 2） |
| 最大推定 | $1.89（最大単価 $0.9464/run × 2） |
| retry 1回時の最大 | $2.84 |
| 最大試行回数 | **3**（初回 + 再試行2回） |
| 想定残高 | 約 $6.00 → 最悪 $2.84 消費で残 $3.16 |

### 7.4 位置づけと禁止事項

**これは「penalty=0 なら転化するか」を確かめる実験ではない。replay 手法の妥当性を検証する実験である。**
転化が起きても起きなくても結果として報告するのみで、**この 2 run から条件間比較や仮説検証は行わない（n=2）。**

**禁止**:
- 結果を見てから penalty 値を変更しない
- 追加 run を実行しない。**2 run で打ち止め**
- この 2 run を主結果や条件比較に使わない
- **本実験（20 run）の結果・config・metadata を一切変更しない**
