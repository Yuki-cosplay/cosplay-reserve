# cosplay-reserve

文化活動が技能・設備・関係性を蓄積し、平時には認識されていなかった社会能力が
危機時に別用途へ転化しうるか——を検証するエージェントベースシミュレーション研究。

本実験が答えたのは、**モデル内で**未知の需要仕様に対して供給者の形成・供給の継続・
協調関係の形成が起きるか、そして何が供給量を制約するか、までである。
**実データによる校正は行っていない。現実のコスプレ制作について何かを証明したものではない**（§ライセンスと主張の範囲）。

正典は `SPEC.md`（研究仕様書）。結果は `RESULTS.md`。

## 提出物

| 種別 | ファイル |
|---|---|
| **デモ動画（提出版）** | **[`figures/demo_video/cosplay_reserve_demo.mp4`](figures/demo_video/cosplay_reserve_demo.mp4)** — 167.5秒 / 1920×1080 / 30fps / 音声なし |
| 研究結果 | [`RESULTS.md`](RESULTS.md) |
| 発表スライド | [`slides/cosplay_reserve_final.pptx`](slides/cosplay_reserve_final.pptx) |
| 図 | [`figures/F1`–`F5_*.png`](figures/) |
| 実験結果・解析データ | [`outputs/main_experiment/`](outputs/main_experiment/) |
| 主結果の生データ | [`outputs/main_experiment/transition_recomputed_preregistered.json`](outputs/main_experiment/transition_recomputed_preregistered.json) |

> **デモ動画は `cosplay_reserve_demo.mp4` の 1 本のみである。**
> ナレーションはなく、実ログに基づく Agent の状態遷移を連続して可視化している。
> 表示される数値はすべて `outputs/` と M1 trace の実測値で、
> 見栄えのための丸めや強調は行っていない（`figures/demo_video/README.md` §4 に
> データと視覚補間の境界を列挙してある）。
> 制作過程で生成した旧版・プロトタイプはリポジトリに含めていない。

---

## 主結果

事前登録した転化基準（4条件の同時充足）を満たした run は **0 / 20**。
供給者形成・供給継続・協調関係の形成は **20/20 run で充足**され、唯一の未充足は
**量**（`community_supply_share >= 0.25`）だった。

量を制約していたのは材料・設備・時間ではなく、**要求仕様へ作り替えたあとの制作成功確率**である。

---

## セットアップ

### 必要なもの

| 項目 | バージョン |
|---|---|
| Python | **3.12**（開発は 3.12.10） |
| OS | Windows でも macOS / Linux でも動く（開発は Windows 11） |

依存パッケージ（開発時の実績バージョン）:

| パッケージ | バージョン | 用途 |
|---|---|---|
| numpy | 2.5.2 | RNG ストリーム、数値計算 |
| networkx | 3.6.1 | ネットワーク生成 |
| PyYAML | 6.0.3 | config |
| pandas | 3.0.5 | 集計 |
| matplotlib | 3.11.1 | 図 |
| pytest | 9.1.1 | テスト |
| anthropic | 0.122.0 | **LLM を使う実験のみ必要** |

### インストール

```bash
git clone <this-repo>
cd cosplay-reserve

python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install numpy pandas networkx pyyaml matplotlib pytest anthropic
```

`requirements.txt` は用意していない。上記が動作確認済みの構成である。

### API キーの発行とクレジット購入（LLM を使う実験のみ）

> **⚠️ ここは第三者が必ず躓く。Claude の月額サブスクリプション（Pro / Max）とは
> 課金が完全に別である。サブスクリプションを契約していても API は使えない。**

1. **Anthropic Console** (`console.anthropic.com`) にログインする
2. **クレジットを購入する** — Billing から前払いクレジットを購入する。
   残高ゼロだと API キーがあっても呼び出しは失敗する。
   main experiment の再実行には **約 $18.5** 必要（下記の費用警告を参照）
3. **API キーを発行する** — API Keys から新規作成し、表示された文字列を控える
   （再表示されない）

### 環境変数 `ANTHROPIC_API_KEY` の設定

**Windows (PowerShell) — 現在のセッションのみ**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

**Windows (PowerShell) — 永続化（新しいターミナルから有効）**
```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

**macOS / Linux — 現在のセッションのみ**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**macOS / Linux — 永続化**
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc   # bash なら ~/.bashrc
source ~/.zshrc
```

設定できたかの確認:
```powershell
# Windows
if ($env:ANTHROPIC_API_KEY) { "設定済み" } else { "未設定" }
```
```bash
# macOS / Linux
[ -n "$ANTHROPIC_API_KEY" ] && echo "設定済み" || echo "未設定"
```

**キーをリポジトリにコミットしないこと。** config にも書かない。

---

## 費用に関する警告

**API を呼ぶスクリプトは 2 つだけである。以下の 2 つ以外は実行しても課金されない。**

| スクリプト | LLM calls | 費用 | 状態 |
|---|---|---|---|
| `experiments/m3_main.py` | 960 | **$18.503645** | 実行済み。結果は `outputs/main_experiment/` にある |
| `experiments/live_penalty_zero.py` | **96** | **$1.808630** | 実行済み。結果は `outputs/live_penalty_zero/` にある |

> **どちらも既に実行済みであり、再実行する必要はない。**
> 生ログはこのリポジトリに収録してあるため、**主結果の検証は API を一度も呼ばずに行える**（§LLM を使わずに検証できる範囲）。
> 再実行する場合は合計 **約 $20.3** が必要になる（`claude-opus-5`、main experiment は 1 run あたり平均 $0.9252）。

> **`experiments/live_penalty_zero.py` は名前から費用が推測しにくいので注意。**
> このスクリプトは `experiments.m3_main` を経由して間接的に Anthropic API を呼ぶ。
> 1 本あたり 48 calls / 約 $0.90、2 本で **96 calls / $1.808630** を消費する。
> 目的は「penalty=0 の replay 結果が実際の挙動と一致するか」の検証であり、
> **その検証は既に完了している**（RESULTS.md §9、±2sd 以内）。

### LLM を使わずに検証できる範囲

**以下はすべて API 不使用・費用ゼロで実行できる。まずここから確認することを強く勧める。**

| 検証できるもの | 費用 |
|---|---|
| **M1 全体**（Agent 生成 / ネットワーク / 学習 / 段階遷移、4条件 × N seed） | $0 |
| **感度分析 replay**（既存ログから production layer を再計算） | $0 |
| **corrected adjudication**（事前登録 D4 による転化の再判定 = **主結果**） | $0 |
| **事前登録監査**（事前登録 / config / run metadata の三者突合） | $0 |
| **seed の構造的 eligibility scan** | $0 |
| **全テスト（216 件）** | $0 |

LLM が必要なのは **`experiments/m3_main.py`（$18.5）** と
**`experiments/live_penalty_zero.py`（$1.8）** の 2 本だけである。
どちらも実行済みで、生ログを収録してあるため再実行は不要。

### CostGuard の設定

API 費用の上限はコードに組み込まれており、**呼び出しの「前」に判定して停止する**。

**config 側**（`configs/base.yaml`）:
```yaml
llm:
  model: claude-opus-5
  max_usd: 1.00                 # 1 run あたりの累積上限
  input_usd_per_mtok: 5.00
  output_usd_per_mtok: 25.00
```

**ハーネス側**（`experiments/m3_main.py`、実験仕様として固定）:
```python
PER_RUN_MAX_USD = 1.25          # 1 run の上限
CAMPAIGN_MAX_USD = 20.00        # campaign 全体の上限
MAX_ATTEMPTS = 3                # 初回 + 再試行2回
```

campaign 上限に達すると、**新しい run を開始せずに停止する**（途中で打ち切られた run を
補完しない）。中断しても各 run の結果ファイルから再開でき、累積費用は完了済み run から復元される。

---

## 再現手順

### 1. M1 — LLM 不使用、費用ゼロ

```bash
# 開発 smoke（4条件 × 5 seed = 20 run）
python -m experiments.m1_smoke --seeds 5

# 主実験相当（4条件 × 20 seed = 80 run）
python -m experiments.m1_smoke --seeds 20 --output outputs
```

**所要時間**: 1 run あたり約 **3.4 秒**（蓄積相 156 step）。
20 run で約 **1.2 分**、80 run で約 **4.5 分**（実測に基づく外挿）。

**出力**: `--summary` で指定した CSV（既定 `outputs/m1_smoke_summary.csv`）。
`--output` を付けると run ごとの成果物も書き出される。

### 2. M3 main experiment — **LLM 使用、約 $18.5**

```bash
# まず必ず dry-run で計画と費用を確認する（API を呼ばない）
python -m experiments.m3_main --dry-run

# 実行
python -m experiments.m3_main
```

**所要時間**: 実測で約 **1時間40分**（20 run、17:47〜19:28）。
**費用**: **$18.503645**（960 calls）。

**出力**: `outputs/main_experiment/`
- `{A,B,C,D}_seed{2,4,6,7,9}.json` — run ごとの結果（metrics / transition_history / provenance）
- `campaign.json` — 実行順序（事前ランダム化）と cap の記録

### 3. 主結果の再判定（corrected adjudication）— API 0 call

```bash
python -m experiments.recompute_transition
```

**所要時間**: 1 秒未満。**出力**: `outputs/main_experiment/transition_recomputed_preregistered.json`

**これが主結果である**（事前登録 D4 による転化判定）。実行時 config の暫定値による判定は
各 run ファイルに副次的記録として残っている。理由は次節と `RESULTS.md` §5。

### 4. 感度分析 replay — API 0 call

```bash
python -m experiments.sensitivity_replay
```

**所要時間**: 約 **30 秒**（20 run × 4 penalty 値 × CRN Monte Carlo 2000 反復）。
**出力**: `outputs/sensitivity_replay/penalty_sensitivity.json`

既存ログから `p_base` を復元し、`modify_difficulty_penalty` を 0.00 / 0.15 / 0.35 / 0.50 に
変えて production layer だけを再計算する。**LLM を再実行しない**（penalty 差と LLM 応答差が
混ざるのを避けるため）。

### 5. 事前登録監査 — API 0 call

```bash
python -m experiments.audit_preregistration
```

**出力**: `outputs/main_experiment/preregistration_audit.json`
事前登録値 / 実行 config / run metadata の三者を突き合わせる。

### 6. seed の構造的 eligibility scan — API 0 call

```bash
python -m experiments.seed_eligibility --need 5 --max-seed 40 --agents 6
```

**出力**: `outputs/seed_eligibility.json`
LLM の出力も Agent の行動結果も参照しない、測定可能性に基づく事前選定である。

### 7. live run による部分均衡検証 — **LLM 使用、96 calls / $1.808630**

> **警告: このスクリプトは Anthropic API を呼び、課金される。**
> `experiments/live_penalty_zero.py` は `experiments.m3_main` を経由して
> 間接的に API を呼ぶ。名前に `penalty_zero` とあるが、費用はゼロではない。
> **1 本あたり 48 calls / 約 $0.90、2 本で 96 calls / $1.808630。**

**通常は実行する必要がない。** 実行済みの結果が
`outputs/live_penalty_zero/A_seed{2,4}_penalty0.json` に収録してあり、
RESULTS.md §9 の結論はそのファイルから検証できる。

```bash
# 実行済み結果を読むだけなら API 0 call
python -c "import json;d=json.load(open('outputs/live_penalty_zero/A_seed2_penalty0.json'));print(d['community_supply_total'], d['llm_calls'], d['spent_usd'])"
```

あえて再実行する場合:

```bash
python -m experiments.live_penalty_zero --seeds 2,4     # 課金される
```

**目的**: §4 の感度分析 replay は「意思決定を固定したまま production layer だけ
再計算する」部分均衡仮定に依存している。この仮定が成り立つかを、penalty=0 で
実際に LLM を走らせて確認する。結果は replay の予測の **±2sd 以内**であった
（RESULTS.md §9、`docs/PREREGISTRATION_SENSITIVITY.md` に予測を実行前に記録済み）。

---

## config の二層構造（重要）

### `configs/base.yaml` が正典

事前登録された値が入っている。条件別 YAML（`condition_a.yaml` 〜 `condition_d.yaml`）の
差分は **`topology` と `peer_learning_enabled` の2キーのみ**。

転化判定 D4 の現在値（`docs/PREREGISTRATION_H1.md` §D4 と一致）:

```yaml
shock:
  transition:
    community_supply_share: 0.25
    active_supplier_count: 3      # = ceil(shock_agent_count / 2)
    supply_duration_steps: 4      # = 24時間
    coordination_edges: 2
```

### `configs/as_executed/` は実行時の記録（編集禁止）

> **⚠️ main experiment の 20 run は、上記の事前登録値ではなく
> 暫定値 `share >= 0.20` / `duration >= 3` で実行された。**

| 閾値 | 実行時 | 事前登録 | 一致 |
|---|---|---|---|
| `community_supply_share` | 0.20 | 0.25 | ✗ |
| `active_supplier_count` | 3 | 3 | ✓ |
| `supply_duration_steps` | 3 | 4 | ✗ |
| `coordination_edges` | 2 | 2 | ✓ |

原因は config の同期漏れである（`RESULTS.md` §5、`docs/LIMITATIONS_CANDIDATES.md` L11）。
実行時の config は `configs/as_executed/main_experiment_20260816.yaml` に
**バイト単位で同一のまま保存**してある。**編集しないこと。再実行の起点にも使わないこと。**

### 現在の config で再実行するとどうなるか

> **`configs/base.yaml` は事前登録値へ同期済みである。
> 第三者が現在の config から実行すれば、正式事前登録値による判定が得られる。**

`tests/test_preregistration_sync.py` が config と事前登録値の一致を常時検査している。

### raw metrics は D4 に依存しない

**転化判定（`transitioned` / `transition_step` / `emergence_level`）は D4 に依存するが、
生の測定値は依存しない。**

| D4 に依存する | D4 に依存しない（raw metrics） |
|---|---|
| `transitioned` | `community_supply_total` / `community_supply_share` |
| `transition_step` | `active_supplier_count` / `supply_duration` |
| `emergence_level_provisional` | `coordination_edges` / `modify_count` |
| `met_*` フラグ | `provenance`（make 試行ごとの全記録） |

そのため、**既存ログを改変せずに事前登録値で再判定できた**（手順 3）。
再判定は既存の `TransitionJudge.evaluate()` を再利用しており、判定ロジックを再実装していない。

---

## テスト

```bash
python -m pytest                                  # 全件
python -m pytest tests/test_preregistration_sync.py -v   # 単一ファイル
python -m pytest tests/x.py::test_y               # 単一テスト
```

**216 passed**（API を呼ばない）。主な検証内容:

- 決定論的再現性（同一 seed で同一結果）
- **A/C・B/D のネットワーク同一性**と pre-network 初期状態の4条件一致
- peer learning ON/OFF の遮断点の正しさ
- **Agent-facing strings の answer leak 防止**（禁止語テスト、語境界マッチ、陽性対照12件・陰性対照6件）
- 事前登録値と config の同期
- shock agent 選出が条件・技能に依存しないこと

---

## ドキュメントの地図

| ファイル | 内容 |
|---|---|
| `SPEC.md` | **研究仕様書（正典）。** §0 の研究命題・理論・実験原則は固定 |
| `RESULTS.md` | **研究結果（§1–§12）と製品仮説（§13–§14）。両者を明確に分離してある** |
| `CLAUDE.md` | 作業ルール（絶対ルール、譲れない設計上の制約） |
| `docs/DESIGN_M1.md` | M1 詳細設計。**実装のモジュール構成はこちらが正典** |
| `docs/PREREGISTRATION_H1.md` | 事前登録: H1 主要指標、**D4 転化閾値（正典）**、D5、使用 seed の選定根拠 |
| `docs/PREREGISTRATION_SENSITIVITY.md` | 事前登録: penalty 感度分析と live run 2本（予測値を実行前に記録） |
| `docs/LIMITATIONS_CANDIDATES.md` | **限界 L1–L16。** P0 と freeze 解除事由を含む。結果を読む前に目を通すこと |
| `docs/RESULTS_CANDIDATES.md` | 確定した知見の発生時点での記録 |
| `docs/REVIEW.md` | SPEC §32 設計レビュー。**旧条件名を含む審議記録であり、実装に持ち込まない** |
| `docs/PITCH_PRODUCT_ONEPAGER.md` | 製品仮説の 1 ページ。**研究結果とは水準が異なる** |
| `docs/TIMELOG.md` | 作業時間の記録 |

### 出力の地図

> **GitHub は `outputs/` の中身を英数字順に並べる。** そのため `20260816T…` で
> 始まる 80 個のディレクトリが先頭に来て、主結果より前に表示される。
> **まず `outputs/main_experiment/` を開くこと。** 下表は重要度順に並べてある。

| パス | 内容 |
|---|---|
| **`outputs/main_experiment/transition_recomputed_preregistered.json`** | **主結果**（事前登録 D4 による再判定、Transition 0/20） |
| `outputs/main_experiment/{A..D}_seed{2,4,6,7,9}.json` | main experiment の run 20本（**副次的記録**の転化判定を含む）。再取得に $18.5 |
| `outputs/main_experiment/preregistration_audit.json` | 三者突合監査（22 項目） |
| `outputs/main_experiment/campaign.json` | 実行計画（`order_seed` からの決定論的な実行順と費用上限） |
| `outputs/sensitivity_replay/penalty_sensitivity.json` | penalty 感度分析（P\* = 0.042573） |
| `outputs/live_penalty_zero/A_seed{2,4}_penalty0.json` | live run 2本（replay 手法の妥当性検証）。再取得に $1.8 |
| `outputs/seed_eligibility.json` | seed の事前選定（構造のみに基づく） |
| `outputs/seed_eligibility_INVALIDATED_prescan.json` | 無効化した旧 scan（**削除せず保存**、使用禁止） |
| `outputs/m1_main_summary.csv` / `m1_holdout_summary.csv` | M1 160 run の `final_state_sha256` 一覧（決定論の照合表） |
| `outputs/holdout/` | M1 holdout（seed 21–40）の per-run 出力。§11 の H1 非支持所見の一次証拠 |
| `outputs/20260816T*_{A..D}_seed*/` | **M1 蓄積相の per-run 出力（読み飛ばして可）。** 80 ディレクトリ。集計は上の summary CSV にある |
| `outputs/m1_smoke_summary.csv` | 開発時 smoke（4条件 × 5 seed）。**研究結果ではない。** `m1_main_summary.csv` の真部分集合で同一スキーマ |

### `outputs/` の収録方針

`.gitignore` は **許可リスト方式**である（`outputs/*` で全除外し、公開対象だけを
`!` で戻す）。既定が除外なので、**今後の run は名指しで許可しない限り追跡されない**。

意図的に収録していないもの:

| ファイル | 除外理由 |
|---|---|
| `outputs/m3_shock.json` | `run_type: PIPELINE_VALIDATION` / `excluded_from_main_experiment: true`。**暫定 D4/D5 での結果**であり、主結果と取り違えられる危険がある |
| `outputs/m2_smoke.json` | M2 疎通確認の中間生成物 |
| `outputs/demo_m1_recording.csv` | デモ収録用。研究上の主張を支えない |
| `figures/demo_video/data/**` | 可視化専用の trace 約 880MB。`python -m experiments.m1_trace_and_verify --seeds 20` で $0 再生成できる |

### 「モデルに答えを教えていない」ことの検証手順

本研究の中心的な主張は、**PPE への転化が指令ではなく創発として起きた**という点にある
（SPEC §8）。これは「Agent に答えを教えていない」ことが前提であり、
主張する側が「信じてください」と言うだけでは足りない。
以下の 3 段で、**読者が自分で検証できる**ようにしてある。

#### 1. プロンプト本文はリポジトリに入っている

`src/llm/prompts.py` に原文がある（`SHOCK_SYSTEM_PROMPT`、1507 文字）。
sha256 だけを記録して本文を隠しているのではない。読んで確認できる。

#### 2. その本文が実際に使われたことを sha256 で照合できる

各 run ファイルの `prompt_sha256` は、`experiments/m3_main.py` の
`_prompt_hash()` が `PROMPT_VERSION + SHOCK_SYSTEM_PROMPT` から計算した値である。
手元で再計算すると記録と一致する:

```bash
python -c "import hashlib, json, glob; from src.llm.prompts import PROMPT_VERSION, SHOCK_SYSTEM_PROMPT; h = hashlib.sha256((PROMPT_VERSION + SHOCK_SYSTEM_PROMPT).encode('utf-8')).hexdigest(); logged = {json.load(open(f, encoding='utf-8'))['prompt_sha256'] for f in glob.glob('outputs/main_experiment/[ABCD]_seed*.json') + glob.glob('outputs/live_penalty_zero/*.json')}; print('recomputed:', h); print('logged    :', logged); print('MATCH' if logged == {h} else 'MISMATCH')"
```

```
recomputed: 6cf3be8a88f218f5f43d09dfe2884dffc65f69e0f3c698d9e92c1a6c419c51ff
logged    : {'6cf3be8a88f218f5f43d09dfe2884dffc65f69e0f3c698d9e92c1a6c419c51ff'}
MATCH
```

つまり **`src/llm/prompts.py` にある本文が、そのまま 22 本すべての run を動かした**
ことが確認できる。あとから差し替えることはできない。

#### 3. そのプロンプトで動いた Agent の理由文を、同じ matcher で検査できる

`provenance[].intent.reason` には **LLM が生成した意思決定の理由文**が平文で入っている
（22 本で 1229 件、ユニーク 276 種、最長 94 文字、非 ASCII 0）。
禁止語の判定は `tests/forbidden.py` の `find_forbidden()` が正典であり、
テストと同じ実装を読者も呼び出せる:

```bash
python -c "import json, glob; from tests.forbidden import find_forbidden, ASCII_TERMS, JA_TERMS; rs = [p['intent']['reason'] for f in glob.glob('outputs/main_experiment/[ABCD]_seed*.json') + glob.glob('outputs/live_penalty_zero/*.json') for p in json.load(open(f, encoding='utf-8'))['provenance'] if isinstance(p.get('intent', {}).get('reason'), str)]; hits = [(r, find_forbidden(r)) for r in rs if find_forbidden(r)]; print(f'terms={len(ASCII_TERMS)+len(JA_TERMS)} strings={len(rs)} hits={len(hits)}')"
```

```
terms=17 strings=1229 hits=0
```

run ファイルの**全文字列値 17,672 件**（キー名 161 種を含む）に広げても
**ヒット 0 件**である。理由文の語彙はすべて一般英単語と中立識別子
（`proj_2` / `skill_0` / `asset_0` / `mat_2` / `attr_2`）で構成されている。

`find_forbidden()` の検出力そのものは `tests/test_forbidden_matcher.py` の
陽性コントロールが保証している（「ヒット 0 件」が matcher の故障によるものでないこと）。

> **注意: これらの文章を「創発の証拠」として読まないこと**（SPEC §30 Anti-Goals）。
> 転化判定は SPEC §21 の閾値化された条件のみで行っており、LLM の文章は判定に
> 一切使っていない。理由文を収録しているのは、**その事実を第三者が確認できるように
> するため**であって、文章の説得力を成果として提示するためではない。

---

## ライセンスと、本研究が現実について主張していないこと

### ライセンス: Apache License 2.0

本リポジトリは **Apache License 2.0** で提供する。全文は [`LICENSE`](LICENSE) にある
（帰属表示は [`NOTICE`](NOTICE)）。

```
Copyright 2026 Igari

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

**`outputs/` 配下の実験ログと解析結果も、コード・ドキュメントと同じ
Apache License 2.0 の下にある。** 別ライセンスを適用している部分はない。
生ログ（`outputs/main_experiment/` 等）、解析後データ
（`transition_recomputed_preregistered.json` 等）、図（`figures/`）、
デモ動画（`figures/demo_video/cosplay_reserve_demo.mp4`）、スライド
（`slides/`）を含め、リポジトリ全体が同一条件である。

再利用にあたっては、Apache-2.0 §4 に従い `LICENSE` と `NOTICE` を保持すること。
学術的な引用の際は、実行時 config が `configs/as_executed/` に固定されているので、
どの時点の結果を参照したかを commit hash とあわせて示せる。

問い合わせは**このリポジトリの GitHub Issues** へ。

> **本研究はモデル内実験であり、実データによるキャリブレーションを行っていない。
> 現実のコスプレイヤーが危機時に供給できることを証明したものではなく、
> 現実の供給量を予測できるものでもない。**
>
> 「コスプレコミュニティが他の趣味コミュニティより強い」「コスプレイヤーが他人より利他的である」
> といった命題は**検証対象であってモデルの前提ではない**（SPEC §6）。
> A/B/C/D の比較は仮説的モデル内部の factorial experiment であり、
> structured topology は現実のネットワークの再現ではない（SPEC §19）。
> モデル内で材料・設備・時間が律速でなかったことは、**現実でそれらの介入が無効であることを
> 意味しない**（本モデルには共有プールの競合も調達リードタイムも存在しない）。
> 主要因子（topology × peer learning）の効果は seed 間ばらつきに埋もれており、
> **n=5/セルは結論を出せる規模ではない**。
>
> 詳細は `RESULTS.md` §11「What the Model Does NOT Support」と
> `docs/LIMITATIONS_CANDIDATES.md` を参照すること。
