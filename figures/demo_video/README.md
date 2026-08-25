# demo_video — 実ログ再生によるデモ動画

`cosplay_reserve_demo.mp4`（1920×1080 / 30fps / **167.5秒** / h264 / **無音**）

旧版は `cosplay_reserve_demo_v1.mp4`（180.0秒）としてローカルに保存（**公開対象外**、§7）。

**この動画は概念アニメーションではなく、確定済みログの再生です。**
描画されるイベントはすべて、`outputs/` 配下のログの1レコードに対応します。

---

## 1. 何を見せているか

| 時刻 | フェーズ | 内容 | 再生元 |
|---|---|---|---|
| 0:00–0:08 | SETUP | participant 30体と固定ネットワーク（格子は薄く敷き、文字は最前面） | `build_world(condition_a, seed=2)` |
| 0:08–0:28 | ACCUMULATION | 週1–60。集団の技能分布と maker_stage が変化 | M1 trace |
| **0:28–0:36** | **ACCUMULATION（等速）** | **個体クローズアップ。対象は `select_closeup()` が決定論的に選定** | M1 trace |
| **0:36–0:42** | **個体 → 集団** | **直前に見た1体の6技能を、participant 30体の分布上に重ねる** | M1 trace |
| 0:42–0:58 | ACCUMULATION | 週65–156 | M1 trace |
| 0:58–1:04 | SHOCK | 未知仕様の提示（`attr_0 >= 0.60` / `attr_2 >= 0.55`） | main experiment |
| 1:04–1:38 | SHOCK | step 1–4（1 step = 8.5秒） | main experiment |
| **1:38–1:41** | **挿入カット** | **1体のバー2本に寄り、閾値への到達を大きく見せる** | main experiment |
| 1:41–2:15 | SHOCK | step 5–8 | main experiment |
| 2:15–2:43 | RESULT | 4条件の内訳と Transition の判定 | corrected adjudication |
| 2:43–2:47 | CLOSING | クロージングカード | corrected adjudication |

尺は `SEG` に定義され、`assert TOTAL == 5025`（= 167.5秒 × 30fps）で固定。
`assert 150*30 <= TOTAL <= 180*30` と `assert RESULT_SEC <= 30` も併せて強制している。

### 閾値の扱い（重要）

**閾値線の位置は動かしていない。** 仕様上、属性は閾値ちょうどまでしか上がらないため、
バーが線を「越える」絵は作らず、**「ぴったり届く」ことを見せる**設計にしている。
到達判定は既存ログの値（`after_attributes` と `required_attributes`）から導出しており、
到達時に閾値線を白へ1フレームだけフラッシュ→緑、バーを緑へ、`✓ required` を付す。

## 2. 使用ログ（再生元）

| フェーズ | ファイル | 再実行の有無 |
|---|---|---|
| SETUP | `configs/condition_a.yaml` → `build_world(seed=2)` | **決定論的な再構築のみ。156 step は回さない** |
| ACCUMULATION | `figures/demo_video/data/m1_trace/A_seed2/{actions,snapshots,method_events}.jsonl` | **M1 は再実行しない**（取得済み trace を読む） |
| SHOCK | `outputs/main_experiment/A_seed2.json` | **M3 は絶対に再実行しない。読み取り専用** |
| RESULT | `outputs/main_experiment/transition_recomputed_preregistered.json` | 読み取り専用 |

**新規 Anthropic API / LLM call = 0。** `make_video.py` は `src.llm` / `anthropic` を import せず、
`step()` / `run_one()` も呼びません。

---

## 3. M1 trace の素性（重要）

蓄積相の per-agent データは、**観測専用の trace logging** で取得したものです。

- 追加したのは `world.trace`（既定 `None`）と、`if trace:` で守られた読み取りのみの hook
- **RNG を消費せず、状態も書き換えず、iteration 順も変えません**
- 保証は「安全に見えるコード」ではなく **hash 全件一致**で与えています:

  > **seed 1–20 × condition A/B/C/D = 80 run で `final_state_sha256` が 80/80 一致**
  > （`figures/demo_video/data/m1_trace/hash_verification.json`、`verdict: PASS`）

- trace 自体の整合性も 80 run 全件で検証済み（step 数 / agent 追跡 / 欠落重複 /
  action vocabulary / action counts / skill 集団統計 / maker_stage 集計 /
  completed_projects / method_count が既存 `timeseries.csv` と一致）

---

## 4. ★データと視覚補間の境界★

### データ（ログの1レコードに対応する）

| 表示 | 出どころ |
|---|---|
| 蓄積相の各 Agent の action | `actions.jsonl` の `action` |
| observe / ask の有向線 | `actions.jsonl` の `target_agent_id` |
| 技能バー・技能ヒストグラム | `snapshots.jsonl` の `skills` |
| maker_stage の人口構成 | `snapshots.jsonl` の `maker_stage` |
| completed projects / methods | `snapshots.jsonl` の各 total |
| ショック相の属性 before/after | `provenance[].before_attributes` / `after_attributes` |
| MODIFY の属性と増分 | `modify_history[agent][]` の `attr` / `delta` |
| SUPPLY / MAKE FAILED / REQ NOT MET | `provenance[]` の `supplied_units` / `make_success` / `meets_requirement` |
| COORDINATION の線 | `provenance[].coordination_relation.edges_involving_self` |
| RESULT の各値 | `transition_recomputed_preregistered.json` |

### 視覚補間（simulation event ではない）

コード上 `visual_only_*` 接頭辞で分離しています。

| 関数 | 内容 |
|---|---|
| `visual_only_grid()` | Agent の**画面座標**。**シミュレーションに位置の概念は存在しません** |
| `visual_only_ui_skill()` | Agent 下の小バー。6技能の**単純平均**。**★研究指標ではない★** `RESULTS.md` / `SPEC.md` のどの指標とも対応しません。画面にも `bars = UI aggregate (not a research metric)` と表示しています |
| `visual_only_ease()` | 表示用イージング |
| step 内の表示順 | ショック相で「変形 → 結果」の順に見せていますが、**ログの粒度は step 単位**です。画面に「step 内の表示順は視覚補間（ログは step 粒度）」と表示しています |

### 意図的に描いていないもの

| 対象 | 理由 |
|---|---|
| **share の相手（線）** | trace に `target_agent_id` が**存在しない**（`known_agents` へのブロードキャストのため）。相手を描くと**存在しない関係を創作**することになります。姿勢とラベル `share` のみで表現し、画面に「share の相手は trace に記録されていないため表示していない」と明記 |
| **M1 の propose / join** | **M1 に実装されていません**（ショック相専用の action） |
| **M3 の observe / practice / share / idle の個体別表示** | main experiment のログに**個体別記録がありません**（集計値のみ） |
| **propose / join の「成立の瞬間」** | イベント時刻が**復元不能**です。`COORDINATION ACTIVE` として**成立済みの累積状態のみ**を表示し、画面に「成立の瞬間は復元不能のため演出しない」と明記 |
| **品名・用途** | SPEC §18 に従い、属性 `attr_N` の数値のみを表示します |
| **ネットワークが生成される演出** | M1 中ネットワークは**固定**です。最初から背景に表示します |

---

## 5. 重要値の assert

`load_all()` が読み込み時に検証します。1件でも食い違えば生成が止まります。

```python
assert req == cfg_req                      # 要求属性が config と一致
assert len(parts) == 30                    # participant 30体
assert sorted(snaps) == list(range(156))   # 蓄積相 156 step が完備
assert abs(supplied - community_supply_total) < 1e-9   # 供給合計がログと一致
assert set(shock_agent_ids) <= pset        # shock agent は participant
assert a2["corrected_transition"] is False # A_seed2 の判定がログと一致
assert n_trans == 0                        # 20 run の corrected transition が 0/20
```

---

## 6. 再現方法

### 前提: M1 trace の生成（初回のみ・API 0 call・約105秒）

trace 本体（80 run で約 882MB）は `.gitignore` で除外しています。再生成してください。

```bash
python -m experiments.m1_trace_and_verify --seeds 20
```

これは 80 run を実行し、**既存正典 `outputs/m1_main_summary.csv` と hash を全件突合**します。
`final_state_sha256` が 1件でも不一致なら **FAIL で停止**します（不一致の trace は動画に使いません）。

trace の整合性も確認できます:

```bash
python -m experiments.verify_m1_trace
```

### 動画の生成

```bash
# 各フェーズ5秒の確認用（静止画も出る）
python figures/demo_video/make_video.py --sample

# 最終版（167.5秒）
python figures/demo_video/make_video.py
```

出力: `figures/demo_video/cosplay_reserve_demo.mp4`

### 必要なパッケージ

`matplotlib` / `numpy` / `imageio` / `imageio-ffmpeg`（ffmpeg 本体は `imageio-ffmpeg` が同梱）。
日本語フォントは `Meiryo` → `Yu Gothic` → `MS Gothic` の順に fallback します。
**monospace フォントには日本語グリフが無いため、英数字と日本語は描画時に分離**しています。

---

## 7. 生成物

| ファイル | 内容 | git |
|---|---|---|
| **`cosplay_reserve_demo.mp4`** | **提出版（167.5秒）。このリポジトリで公開している唯一のデモ動画** | 追跡 |
| `make_video.py` | 生成スクリプト | 追跡 |
| `make_prototype.py` | 初期プロトタイプ（設計検討用） | 追跡 |
| `README.md` | 本ファイル | 追跡 |
| `data/m1_trace/hash_verification.json` | 80 run の hash 検証レポート | 追跡 |
| `data/m1_trace/*/**.jsonl` | M1 trace 本体（約882MB） | **除外**（再生成可能） |
| `cosplay_reserve_demo_v1.mp4` | 修正前の旧版（180.0秒） | **除外**（下記） |
| `prototype/` | 確認用サンプル（各フェーズ5秒 + 静止画 + 検証フレーム） | **除外**（下記） |

### 旧版とプロトタイプを公開していない理由

`cosplay_reserve_demo_v1.mp4` と `prototype/` は**ローカルには残してあるが、
git の追跡対象から外してある**（`.gitignore` に指定済み）。

- **旧版**: `cosplay_reserve_demo.mp4` と `_v1` が並んでいると、
  `_v1` を「最新改訂版」と読み違える。提出物のうち最も重要な成果物で
  どちらが本番か分からない状態を避けるため。
- **`prototype/`**: 設計検討とレイアウト検証の中間生成物であり、成果物ではない。

なお両者は commit `b38705b` で一度追跡されているため、**blob は git 履歴に残っている**。
`git rm --cached` は履歴を書き換えないので、履歴を辿れば取得できる。
履歴書き換え（`filter-repo` 等）は、既存の commit hash がすべて変わるため行っていない。

---

## 8. この動画が主張していないこと

`RESULTS.md` §11 と同じ制約が適用されます。

- **現実のコスプレイヤーが危機時に供給できることを示したものではありません。** モデル内の記録の再生です
- **現実の供給量を予測するものではありません**
- **Transition 0/20 は失敗ではありません。** 4条件のうち3条件は全 run で満たされ、
  届かなかったのは量の1条件だけです
- **「share が 0/20」ではありません。** share を1 step でも満たしたのは **2/20 run**、
  0/20 は **4条件が同時に成立した run の数**です。動画の RESULT ではこの2つを
  別のブロックに分けて表示しています
- ショック相で6体が同じ経路を通るのは**実ログ**です。動画では
  「6体が独立に同一の最小コスト経路へ収束（実ログ）」と表示しています
  （`RESULTS.md` §6.3: 供給に使われた制作対象は2種、606件中579件が同一）

---

## 9. 最終版で実施した修正の記録

以下の `P0-*` / `P1-*` / `P2-*` は、制作時のレビュー指摘に付けた通し番号である
（レビュー指示書そのものは制作管理資料であり、このリポジトリには含めていない）。
記録として残しているのは、**見送った項目を伏せないため**である。

### COMMUNITY SUPPLY の値（レビュー指摘側の脱落を記録）

レビュー時の参照リストは `6 → 11 → 14 → 15 → 17 → 21 → 27`（7値）だったが、
**実データは 8 step 分あり `6 → 8 → 11 → 14 → 15 → 17 → 21 → 27`（8値）である。**

```
step 1: +6  累計 6      step 5: +1  累計 15
step 2: +2  累計 8      step 6: +2  累計 17
step 3: +3  累計 11     step 7: +4  累計 21
step 4: +3  累計 14     step 8: +6  累計 27
```

**ログを正とし、動画の表示は変更していない。** 供給値の計算式は修正前後で1文字も
変わっておらず（`git diff` に該当差分なし）、表示は旧版と同一である。
**レビュー指摘側で step 2 の `8` が脱落していたものとして記録する**（人間判断 2026-08-21）。

### 実施 / 見送り

| 項目 | 状態 |
|---|---|
| P0-1 RESULT の文字重なり | 実施（サブタイトルと要約行を排他描画） |
| P0-2 RESULT 46s → 28s | 実施 |
| P0-3 タイトルの重なり・右3割の空白 | 実施（格子 alpha 0.18・縦分離・水平中央寄せ） |
| P1-4(a) バー拡大 240px | **部分実施**。グリッド内は 158px。240px は3列レイアウトで情報を削らずには入らないため、**挿入カットの 1032px で代替**（人間承認済み） |
| P1-4(b) 到達時の状態変化 | 実施（閾値線は不動、判定はログ値から導出） |
| P1-4(c) 「届いた」ラベル | 実施（`✓ required`） |
| P1-4(d) 挿入カット | 実施（3.5s） |
| P1-5(a) クローズアップ差し替え | 実施（`select_closeup()` による決定論的選定） |
| P1-5(b) 尺調整 | 実施 |
| P1-5(c) 累積チャート | **見送り**（人間承認済み） |
| P1-6 凡例の重なり | 実施 |
| P2-7 音声 | **見送り**（人間承認済み。無音のまま） |
| §6.2 カット数 | 「個体 → 集団」フェーズの追加で 9 → 11 回 |
