# figures

`RESULTS.md` 用の図。**すべて既存ログ（`outputs/` 配下）から生成しており、新規実験は行っていない（API 0 call）。**

| ファイル | 内容 |
|---|---|
| `F1_transition_conditions.png` | 転化の4条件のうち3つは全 run で充足され、未充足は量の1条件のみだったこと |
| `F2_penalty_sensitivity.png` | 転化確率が未校正の `modify_difficulty_penalty` に支配され、その効果が実験の主要因子の約 7.4 倍だったこと |
| `F3_adaptation_path.png` | 答えを与えられていない Agent が既存の制作対象を要求仕様まで作り替えて供給に至った実ログ1件 |
| `F4_bottleneck.png` | make 試行 280 件の内訳と時間予算の使用率。律速が資源でも時間でもなく成功確率だったこと |
| `F5_methods.png` | **Methods 図**（結果の図ではない）。事前登録 → seed 事前選別 → 実行 → 事前登録値との突合 → 主結果、という判定基準の決定順序 |

## 生成方法

```bash
python figures/make_figures.py
```

PNG / 300dpi。所要時間は数秒。

## 設計上の約束

- **数値はハードコードしていない。** すべて `outputs/` 配下の JSON から読み取っている
  （`P*` も既存ログから数値解を求めている）。ハードコードすると図とログの乖離を検出できなくなる。
- **日本語フォント**はスクリプト冒頭の `JP_FONTS` で指定している
  （`Meiryo` → `Yu Gothic` → `MS Gothic` → `Noto Sans CJK JP` → `Hiragino Sans` の順に fallback）。
  環境にこれらが無い場合はここを編集すること。
- **各図の下にデータの出所（ファイルパス）を1行入れている。**
- 図中に `RESULTS.md` §11 の禁止表現を入れていない。

## 数値についての注意（図を読むときに必要）

### F1 の「量の条件 2/20」と「転化 0/20」の違い

- **転化（4条件の同時充足）は 0/20 run。** これが主結果である。
- 量の条件（`community_supply_share >= 0.25`）を**1 step でも**充足した run は **2/20**
  （A seed2 / A seed7、いずれもショック直後の t+0）。
- ただしその時点では供給継続の条件（`>= 4 step`）が成立しておらず、
  **share が最も高い時間帯と duration が資格を得る時間帯が重ならない**。
  そのため4条件が同時に成立した run は 0/20 である。

F1 は「1 step でも充足した run 数」を描いているため、量の条件は 2/20 と表示される。
図中にこの注記を入れてある。

### F4 の「材料不足で阻止 0 件」の意味

`_resolve_shock` は `material_feasible` / `asset_feasible` を**記録するだけで make を阻止しない**。
実際、材料在庫が不足した状態での make 試行 8 件のうち **4 件は成功し供給している**。

したがって帰属は「成功可否を材料・設備より先に見る」順序で行っている（`RESULTS.md` §7.3 と同一）。
「材料不足で阻止 0 件」は「**材料不足によって供給に至らなかった試行が 0 件**」という意味であり、
「材料が常に足りていた」という意味ではない。図の下にこの注記を入れてある。

### F2 / F4 の一般化に関する制約

- `penalty = 0.00` は**モデル上の構造的上限ケース**であり、改善すれば到達できる状態ではない
  （`docs/LIMITATIONS_CANDIDATES.md` L16）。F2 に注記を入れてある。
- **モデル内で材料・設備・時間が律速でなかったことは、現実でそれらの介入が有効でないことを
  意味しない**（本モデルに共有プールの競合・調達リードタイムは存在しない）。F4 に注記を入れてある。

## データの出所

| 図 | 出所 |
|---|---|
| F1 | `outputs/main_experiment/transition_recomputed_preregistered.json` |
| F2 | `outputs/sensitivity_replay/penalty_sensitivity.json`、`outputs/main_experiment/*.json`（P\* の数値解） |
| F3 | `outputs/main_experiment/A_seed2.json`（provenance） |
| F4 | `outputs/main_experiment/A_seed{2,4,6,7,9}.json`、`configs/as_executed/main_experiment_20260816.yaml` |
| F5 | 上記 + `outputs/seed_eligibility.json`、`outputs/live_penalty_zero/` |
