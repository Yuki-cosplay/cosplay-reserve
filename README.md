# cosplay-reserve

文化活動が技能・設備・関係性を蓄積し、平時には認識されていなかった社会能力が
危機時に別用途へ転化しうるか——を検証するエージェントベースシミュレーション研究。

本実験が答えたのは、**モデル内で**未知の需要仕様に対して供給者の形成・供給の継続・
協調関係の形成が起きるか、そして何が供給量を制約するか、までである。
**実データによる校正は行っていない。現実のコスプレ制作について何かを証明したものではない**（§ライセンスと主張の範囲）。

正典は `SPEC.md`（研究仕様書）。結果は `RESULTS.md`。

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

> **M3 main experiment の再実行には約 $18.5 かかる。**
> 実測値: 20 run / 960 calls / **$18.503645**（`claude-opus-5`、1 run あたり平均 $0.9252）。
> live run 2本は追加で $1.808630。

### LLM を使わずに検証できる範囲

**以下はすべて API 不使用・費用ゼロで実行できる。まずここから確認することを強く勧める。**

| 検証できるもの | 費用 |
|---|---|
| **M1 全体**（Agent 生成 / ネットワーク / 学習 / 段階遷移、4条件 × N seed） | $0 |
| **感度分析 replay**（既存ログから production layer を再計算） | $0 |
| **corrected adjudication**（事前登録 D4 による転化の再判定 = **主結果**） | $0 |
| **事前登録監査**（事前登録 / config / run metadata の三者突合） | $0 |
| **seed の構造的 eligibility scan** | $0 |
| **全テスト（202 件）** | $0 |

LLM が必要なのは **M3 main experiment（$18.5）** と **live run（$1.8）** だけである。

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

**202 passed**（API を呼ばない）。主な検証内容:

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

| パス | 内容 |
|---|---|
| `outputs/main_experiment/{A..D}_seed{...}.json` | main experiment の run（**副次的記録**の転化判定を含む） |
| `outputs/main_experiment/transition_recomputed_preregistered.json` | **主結果**（事前登録 D4 による再判定） |
| `outputs/main_experiment/preregistration_audit.json` | 三者突合監査 |
| `outputs/sensitivity_replay/penalty_sensitivity.json` | penalty 感度分析 |
| `outputs/live_penalty_zero/A_seed{2,4}_penalty0.json` | live run 2本（replay 手法の妥当性検証） |
| `outputs/seed_eligibility_INVALIDATED_prescan.json` | 無効化した旧 scan（**削除せず保存**、使用禁止） |

`outputs/` は `.gitignore` されている。

---

## ライセンスと、本研究が現実について主張していないこと

ライセンス: 未定（`LICENSE` ファイルは未作成）。研究用途での参照は自由だが、
再配布・商用利用については著者に確認すること。

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
