# Milestone 1 詳細設計

**対象**: SPEC.md §28 Milestone 1（LLMなし、30〜50 Agent、コードのみで機構を成立させる）
**前提**: `docs/REVIEW.md` の承認
**作成日**: 2026-08-15

> **この文書の位置づけ**
> SPEC.md §32 最終行「Milestone 1を実装可能なレベルまで設計を具体化してください」への回答。
> `docs/REVIEW.md` で示した【実装提案】を具体的なモジュール・データ構造・式に落とす。
> **本文書のパラメータ値はすべて仮置きである。** 実験開始前に事前登録して固定する。

---

## 1. スコープ

### 1.1 M1 に含めるもの（SPEC §28 の指定）

- Agent 生成（seed から決定論的に）
- skills / assets / network
- アクション: `observe` / `ask` / `practice` / `make` / `share`
- 技能学習
- maker stage 遷移
- Metrics 記録と出力
- 4条件（A / B1 / B2 / C）の世界生成

### 1.2 M1 に含めないもの

| 除外するもの | 理由 |
|---|---|
| LLM 呼び出し一切 | SPEC §28「Milestone 1: LLMなし」 |
| 供給ショック | M3 の範囲 |
| Hospital / Manufacturer / Logistics の実体 | M3 で需要が発生してから必要になる |
| 市場価格の内生的決定 | M3 |
| 金銭取引（`trade`） | M1 では材料は初期配分のみ。経済は M3 |
| 転化判定（Transition） | 需要がないので判定対象が存在しない |
| UI・可視化ダッシュボード | §30 Anti-Goal「不要なUIを先に作る」 |

`make` は M1 でも実装するが、**需要のない自主制作**として扱う。これで十分にループは閉じる（作る→技能獲得→共有）。

---

## 2. モジュール構成

SPEC §27 の構成をベースに、M1 で必要な最小サブセットのみを作成する。

```
cosplay-reserve/
  configs/
    base.yaml                 # 共通パラメータ
    world_culture.yaml        # 条件A
    world_random_deg.yaml     # 条件B1（次数保存リワイヤリング）
    world_random_er.yaml      # 条件B2（Erdős–Rényi）
    world_isolated.yaml       # 条件C
  src/
    common/
      types.py                # AttributeVector, Material, Method 等の共通型
      rng.py                  # seed 管理・子ストリーム生成
      io.py                   # UTF-8 明示の読み書きヘルパ
    agents/
      agent.py                # Agent データ構造・初期化
      observation.py          # 局所情報の切り出し（神の視点の遮断点）
      decision.py             # M1: 決定論的ルール。M2 で LLM 差し替え
      memory.py               # Memory / MethodLibrary
    world/
      world.py                # World 状態・step ループ
      production.py           # make の成否判定・属性計算
    culture/
      network.py              # 4条件のネットワーク構築
      learning.py             # 技能獲得・減衰・scaffolding
      capability.py           # maker_stage 判定
    simulation/
      runner.py               # run のオーケストレーション・メタデータ記録
      metrics.py              # Metrics 算出・出力
      events.py               # Event 型・キュー
  experiments/
    m1_smoke.py               # 4条件 × 複数seed のスモーク実行
    threshold_sweep.py        # パラメータ感度分析
  outputs/                    # .gitignore 済み
  tests/
```

**過剰なframework化を避ける**（§30）ため、以下は作らない: 依存性注入コンテナ、プラグイン機構、抽象基底クラスの階層、独自のイベントバス実装。

---

## 3. データ構造（確定版）

`docs/REVIEW.md` §5・§6 の提案を M1 に必要な範囲へ絞り込んだもの。

### 3.1 共通型

```python
# src/common/types.py
from dataclasses import dataclass, field
from enum import Enum

SKILL_NAMES = ("sewing", "crafting", "cad", "printing_3d", "electronics", "repair")

@dataclass(frozen=True)
class AttributeVector:
    """材料・製品・要求仕様を共通の空間で表現する。名称を持たない。
    M1 では需要がないため主に Method.target_profile として使う。
    M3 で RequiredItem との充足判定に使う。"""
    flexibility: float = 0.0
    rigidity: float = 0.0
    filtration: float = 0.0
    durability: float = 0.0
    conductivity: float = 0.0
    sterility: float = 0.0
    precision: float = 0.0

@dataclass(frozen=True)
class Method:
    """共有される手順知識。伝播経路の追跡情報を必ず持つ。
    これにより knowledge_diffusion_speed が副産物として測定可能になる。"""
    method_id: str
    project_type: str            # 中立コードネーム: "proj_0" .. "proj_K"
    primary_skill: str           # SKILL_NAMES のいずれか
    required_skill_level: float
    difficulty_reduction: float  # 0.0-0.6。実効難度をこの割合だけ下げる
    origin_agent_id: str         # 最初の発明者
    source_agent_id: str         # 直接の伝達元
    origin_step: int
    acquired_step: int
    hop_count: int               # 発明者からのホップ数

class MakerStage(str, Enum):
    CONSUMER = "consumer"
    CUSTOMIZER = "customizer"
    MAKER = "maker"
    ADVANCED_MAKER = "advanced_maker"

class ActionType(str, Enum):
    """一般化された行動のみ。答えを含む行動は定義しない。"""
    OBSERVE  = "observe"
    ASK      = "ask"
    PRACTICE = "practice"
    MAKE     = "make"
    SHARE    = "share"
    CONSUME  = "consume"
    IDLE     = "idle"
```

### 3.2 Agent

```python
# src/agents/agent.py
@dataclass
class PerceivedSkill:
    """他Agentの能力は『信念』として持つ。真値は保持しない。"""
    estimate: float
    last_updated_step: int
    observation_count: int

    @property
    def confidence(self) -> float:
        return 1.0 - 0.7 ** self.observation_count

@dataclass
class Agent:
    id: str
    rng_seed: int                                    # マスターseedの子

    skills: dict[str, float]                         # SKILL_NAMES -> 0.0-1.0
    practice_count: dict[str, int]
    success_count: dict[str, int]
    failure_count: dict[str, int]

    assets: dict[str, bool | int]                    # sewing_machine, printer_3d,
                                                     # tools(0-3), workspace
    money: float
    time_budget: float                               # 1step あたりの可処分時間
    materials: dict[str, float]

    participation_level: float
    maker_stage: MakerStage
    sharing_tendency: float
    imitation_tendency: float
    helping_norm: float

    known_agents: set[str]
    trust: dict[str, float]
    perceived_skills: dict[str, dict[str, PerceivedSkill]]  # agent_id -> skill -> 信念

    methods: dict[str, Method]                       # method_id -> Method
    recent_events: list                              # 直近 N step のイベント
    completed_projects: list
    rejected_intents: list

    inbox: list                                      # 受信メッセージ
    outbox: list                                     # 送信予定メッセージ
```

### 3.3 Observation — 神の視点の唯一の遮断点

```python
# src/agents/observation.py
@dataclass(frozen=True)
class Observation:
    """decide() が受け取れる唯一の入力。World への参照を含まない。
    【設計上の要点】このクラスに World や他Agentの実体を入れないことが、
    SPEC §14 Information Locality の構造的な担保になる。
    tests/test_locality.py がこれを機械的に検証する。"""
    step: int
    self_id: str
    self_skills: dict[str, float]
    self_assets: dict[str, bool | int]
    self_time_budget: float
    self_materials: dict[str, float]
    self_maker_stage: MakerStage
    self_methods: tuple[Method, ...]

    neighbors: tuple[str, ...]                        # known_agents のみ
    perceived_neighbor_skills: dict[str, dict[str, PerceivedSkill]]
    trust: dict[str, float]

    inbox: tuple                                      # 今step 到着したメッセージ
    recent_events: tuple

    # M3 で追加: observable_market（観測可能な市場情報のみ）
```

`build_observation(world, agent) -> Observation` が唯一の変換点。ここ以外で Agent が World を参照するコードを書いてはならない。

---

## 4. 1ステップの処理シーケンス

```
def step(world: World) -> None:
    # (1) perceive — 局所情報の切り出し
    observations = {a.id: build_observation(world, a) for a in world.agents.values()}

    # (2) decide — Intent の生成（M1: 決定論的ルール / M2以降: LLM）
    intents = {aid: decide(observations[aid], rng=world.child_rng(aid))
               for aid in world.agents}

    # (3) act — Intent を収集するのみ。世界は変えない
    order = world.rng.permutation(sorted(world.agents))   # seed 固定で再現可能

    # (4) resolve — 一括解決。行動順序の有利不利を排除
    results = [resolve(world, aid, intents[aid]) for aid in order]

    # (5) update — 資源・技能・段階・ネットワークの更新
    apply_results(world, results)
    decay_skills(world)
    update_maker_stages(world)
    deliver_messages(world)          # outbox -> 近傍の inbox

    # (6) record
    world.metrics.record(world)
    world.step += 1
```

**同時解決（4）の意味**: 全 Agent の Intent を確定させてから解決する。逐次実行だと、先に動いた Agent が材料を使い切って後続が行動できない等の順序依存が生じる。`order` は資源競合時の解決順序にのみ使い、これもマスターseed由来で再現可能にする。

---

## 5. M1 の意思決定ルール（LLMなし）

M2 で `decide()` を LLM 実装に差し替えられるよう、**シグネチャを M2 と同一にする**。

```python
# src/agents/decision.py
def decide(obs: Observation, rng) -> Intent:
    """M1: 効用ベースの決定論的ルール（rng は同点処理のみに使用）。
    M2: この関数を LLM 実装に差し替える。シグネチャは変更しない。"""
```

### 5.1 効用の定義（仮置き）

各行動の効用を計算し、時間予算内で最大のものを選ぶ。

| 行動 | 効用 | 意図 |
|---|---|---|
| `observe` | `w_obs × (未知の近傍数 / 近傍数)` | 情報が少ないほど観測したくなる |
| `ask` | `w_ask × imitation_tendency × (近傍の推定技能 − 自技能)⁺ × trust` | 自分より上手い相手がいるほど尋ねたくなる |
| `practice` | `w_prac × (1 − max_skill)` | 技能が低いほど練習の限界効用が高い |
| `make` | `w_make × participation_level × expected_success_prob` | 成功見込みが高いほど作りたくなる |
| `share` | `w_share × sharing_tendency × 未共有Methodの数` | 共有性向と手持ち知識に比例 |
| `idle` | `w_idle`（一定の下限値） | 何もしない選択肢 |

重み `w_*` はすべて config。行動には時間コストがあり、`time_budget` を超える行動は選択できない。

**重要**: この効用関数は「Agent がループを回すため」に設計されていない。各 Agent は自分の局所状態から自分の効用を最大化するだけであり、ループは結果としてマクロに現れる（SPEC §5 の要求）。

---

## 6. 中核の式

### 6.1 制作の成否

```python
def success_probability(agent, project, methods) -> float:
    skill = agent.skills[project.primary_skill]
    asset_bonus = 0.2 if has_required_asset(agent, project) else 0.0

    # scaffolding: 該当Methodを持っていると実効難度が下がる ← ループの閉じ目
    reduction = max((m.difficulty_reduction for m in methods
                     if m.project_type == project.type), default=0.0)
    effective_difficulty = project.base_difficulty * (1.0 - reduction)

    raw = skill + asset_bonus - effective_difficulty
    return clamp(sigmoid(raw / TEMPERATURE), 0.02, 0.98)
```

`reduction` の項が **Capability Reproduction Loop を閉じる唯一の環**である。他Agentから受け取った Method が、自分の成功確率を上げる。

### 6.2 技能獲得（収穫逓減）

```python
def skill_gain(current_skill: float, success: bool, cfg) -> float:
    base = cfg.learn_rate_success if success else cfg.learn_rate_failure
    return base * (1.0 - current_skill)      # 上限 1.0 に漸近
```

失敗からも学ぶ（`learn_rate_failure < learn_rate_success`）。これにより初期段階の完全停滞を防ぐ。

**仮置き**: `learn_rate_success = 0.08`, `learn_rate_failure = 0.02`

### 6.3 技能減衰 — H1 を自明化させないための必須要素

```python
def decay_skills(world) -> None:
    """練習しなかった技能は減衰する。
    【理由】減衰がないと技能は単調増加し、H1『Maker人口は増加するか』が
    構成上自明になる。減衰があって初めて『学習の流入が減衰を上回るか』
    という非自明な問いになる。"""
    for agent in world.agents.values():
        for skill in SKILL_NAMES:
            if skill not in agent.practiced_this_step:
                agent.skills[skill] *= (1.0 - world.cfg.decay_rate)
```

**仮置き**: `decay_rate = 0.005` / step

### 6.4 maker_stage 判定

```python
def judge_maker_stage(agent, cfg) -> MakerStage:
    """決定論的関数。閾値は config。
    段階は上下どちらにも動きうる（技能減衰があるため）。"""
    max_skill = max(agent.skills.values())
    breadth = sum(1 for s in agent.skills.values() if s >= cfg.breadth_threshold)
    n_projects = len(agent.completed_projects)
    n_assets = count_assets(agent)

    if (max_skill >= cfg.adv_skill and breadth >= cfg.adv_breadth
            and n_assets >= cfg.adv_assets and n_projects >= cfg.adv_projects):
        return MakerStage.ADVANCED_MAKER
    if max_skill >= cfg.maker_skill and n_projects >= cfg.maker_projects:
        return MakerStage.MAKER
    if max_skill >= cfg.customizer_skill or n_projects >= 1:
        return MakerStage.CUSTOMIZER
    return MakerStage.CONSUMER
```

**仮置き**: `customizer_skill=0.20`, `maker_skill=0.45`, `maker_projects=3`, `adv_skill=0.70`, `adv_breadth=3`, `adv_assets=3`, `adv_projects=10`, `breadth_threshold=0.35`

### 6.5 Method の生成と共有

```python
# make 成功時に、一定確率で新しい Method が生まれる
if success and rng.random() < cfg.method_discovery_prob:
    agent.methods[new_id] = Method(
        method_id=new_id, project_type=project.type,
        primary_skill=project.primary_skill,
        required_skill_level=agent.skills[project.primary_skill],
        difficulty_reduction=cfg.base_reduction,
        origin_agent_id=agent.id, source_agent_id=agent.id,
        origin_step=world.step, acquired_step=world.step, hop_count=0,
    )

# share は近傍の inbox へ Method を配送する
# 受信側は imitation_tendency と trust で受容判定し、hop_count を +1 して保持
```

`hop_count` と `origin_agent_id` により、**誰の発明が何ホップで何step後に誰へ届いたか**が完全に追跡できる。これが `knowledge_diffusion_speed` の測定基盤になる。

---

## 7. 4条件のネットワーク構築

```python
# src/culture/network.py
def build_network(agents, condition: str, rng) -> nx.Graph:
    """【最重要】Agent 初期化とネットワーク構築を厳密に分離する。
    条件分岐はこの関数の中にのみ存在し、Agent の初期状態には一切触れない。
    tests/test_condition_invariance.py がこれを検証する。"""

    if condition == "culture":
        # A: 文化ネットワーク。クラスタ性と技能同類性を持つ
        g = watts_strogatz_like(agents, k=cfg.mean_degree, p=cfg.rewire_p, rng=rng)
        g = add_skill_assortativity(g, agents, strength=cfg.assortativity, rng=rng)

    elif condition == "random_deg":
        # B1: 次数保存リワイヤリング。次数分布とエッジ数を完全に保存し、
        #     『誰と誰が繋がっているか』だけを壊す。→ 構造の効果を単離できる
        g = build_network(agents, "culture", rng=rng.spawn())
        nx.double_edge_swap(g, nswap=cfg.swap_multiplier * g.number_of_edges(),
                            max_tries=10**6, seed=int(rng.integers(2**31)))

    elif condition == "random_er":
        # B2: Erdős–Rényi。平均次数のみ一致。次数分布も壊す（補助条件）
        g = nx.gnm_random_graph(len(agents), m=expected_edges(agents),
                                seed=int(rng.integers(2**31)))

    elif condition == "isolated":
        # C: 床（sanity check）。学習チャネルをほぼ除去
        g = nx.empty_graph(len(agents))
        # 学習無効化フラグは world.cfg.learning_enabled = False で表現

    return relabel_to_agent_ids(g, agents)
```

**条件C の扱い**: `docs/REVIEW.md` §12.1【要承認2】の通り、C は床（機構の動作確認）であり、H2 の根拠には使わない。主対照は B1。

---

## 8. config スキーマ

### 8.1 base.yaml（共通）

```yaml
run:
  seed: 42
  steps: 480                    # 【要承認1】が承認された場合は蓄積相の step 数
  step_hours: 168               # 仮: 1 step = 1週間（蓄積相）
  output_dir: outputs/

world:
  n_cosplay_agents: 30
  n_general_agents: 10
  project_types: 6              # 中立コードネーム proj_0 .. proj_5

network:
  mean_degree: 6
  rewire_p: 0.1
  assortativity: 0.3
  swap_multiplier: 10           # B1 のリワイヤリング回数 = 10 × エッジ数

learning:
  learn_rate_success: 0.08
  learn_rate_failure: 0.02
  decay_rate: 0.005
  base_reduction: 0.25          # Method 1件あたりの実効難度低減
  method_discovery_prob: 0.15

stage_thresholds:
  customizer_skill: 0.20
  maker_skill: 0.45
  maker_projects: 3
  advanced_skill: 0.70
  advanced_breadth: 3
  advanced_assets: 3
  advanced_projects: 10
  breadth_threshold: 0.35

decision_weights:
  observe: 0.30
  ask: 0.50
  practice: 0.40
  make: 0.70
  share: 0.35
  idle: 0.10

action_time_cost:
  observe: 0.1
  ask: 0.2
  practice: 0.5
  make: 1.0
  share: 0.2
```

### 8.2 条件別 YAML — 差分はネットワークのみ

```yaml
# configs/world_culture.yaml
extends: base.yaml
condition: culture
learning_enabled: true
```

```yaml
# configs/world_random_deg.yaml
extends: base.yaml
condition: random_deg      # ← ここだけが違う
learning_enabled: true
```

```yaml
# configs/world_isolated.yaml
extends: base.yaml
condition: isolated
learning_enabled: false    # 学習チャネルの除去
```

**条件間の差分がこの2行だけであることが、比較の妥当性の担保になる。** 学習率やAgent数を条件ごとに変えてはならない。

---

## 9. Metrics と出力

### 9.1 M1 で記録する Metrics（SPEC §22 のうち M1 で算出可能なもの）

| Metric | 算出方法 | 頻度 |
|---|---|---|
| `maker_count` | maker_stage が MAKER 以上の Agent 数 | 毎step |
| `maker_stage_distribution` | 各段階の人数 | 毎step |
| `skill_distribution` | 技能別の平均・中央値・分散・分位点 | 毎step |
| `asset_distribution` | 設備保有数の分布 | 毎step |
| `network_density` | `nx.density(g)` | 毎step |
| `skill_reachability` | 「必要技能を持つAgentに何ホップで到達できるか」の平均 | 10step毎 |
| `resource_reachability` | 同上（材料・設備） | 10step毎 |
| `knowledge_diffusion_speed` | Method の `origin_step → acquired_step` 差の分布、hop_count の分布 | 毎step |
| `method_count_total` | 世界に存在する Method の総数（重複なし） | 毎step |
| `method_adoption_rate` | 各 Method の保有Agent数 / 全Agent数 | 毎step |
| `latent_capacity_components` | 分散資源量 / ネットワーク連結度 / （再構成能力は M3） | 毎step |

**`latent_capacity` は積の形で単一スコア化しない**（`docs/REVIEW.md` §12.3）。構成指標を別々に保存する。

M1 で算出しないもの: `active_supplier_count`, `community_supply_share`, `transition_time`, `coordination_edges`, `coordination_complexity`（いずれも需要の発生が前提）。

### 9.2 出力フォーマット

```
outputs/
  <run_id>/
    metadata.json           # 再現性メタデータ（下記）
    timeseries.csv          # step 単位のスカラー Metrics
    agents_snapshot.jsonl   # 10step 毎の全Agent状態
    method_events.jsonl     # Method の生成・共有・受容の全イベント
    network_snapshot.json   # 初期・中間・最終のネットワーク
    config_resolved.yaml    # 継承解決後の実効config
```

**`metadata.json`（SPEC §23 の要求を満たす）**:

```json
{
  "run_id": "20260815T120000_culture_seed42",
  "timestamp_utc": "2026-08-15T12:00:00Z",
  "random_seed": 42,
  "condition": "culture",
  "milestone": "M1",
  "llm": null,
  "prompt_version": null,
  "config_sha256": "...",
  "code_git_commit": "...",
  "python_version": "3.12.10",
  "package_versions": {"numpy": "2.5.2", "networkx": "3.6.1", "...": "..."},
  "agent_initial_states_sha256": "...",
  "final_state_sha256": "..."
}
```

M1 では `llm` と `prompt_version` は `null`。M2 でここが埋まる。`agent_initial_states_sha256` は条件間不変テスト（T5）でも利用する。

すべてのファイル書き込みで `encoding="utf-8"`、`newline=""` を明示する（Windows 環境対策）。

---

## 10. テストファイル一覧

| ファイル | テスト内容 | REVIEW対応 |
|---|---|---|
| `tests/test_determinism.py` | 同一seedで2回実行し `final_state_sha256` が一致 | T1 |
| `tests/test_no_answer_leak.py` | Agent向け全文字列に禁止語が含まれない | T2 |
| `tests/test_locality.py` | `Observation` に World 参照・他Agent真値が含まれない | T3 |
| `tests/test_conservation.py` | 材料・所持金が負にならない | T4 |
| `tests/test_condition_invariance.py` | A/B1/B2/C で初期Agent状態が完全一致 | T5 |
| `tests/test_stage_transition.py` | 固定シナリオで Consumer→Customizer→Maker が発火 | T6 |
| `tests/test_learning_causality.py` | share 無効化で knowledge_diffusion が 0 になる | T7 |
| `tests/test_metrics.py` | 手計算フィクスチャと算出値が一致 | T8 |
| `tests/test_network_conditions.py` | B1 が次数分布とエッジ数を保存している | I5 |
| `tests/test_smoke.py` | 20 seed × 4条件が例外なく完走 | T10 |

### 10.1 実行方法

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest tests/test_determinism.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_no_answer_leak.py::test_no_answer_leak_in_agent_facing_strings
```

---

## 11. Milestone 1 完了の判定条件

**以下すべてを満たしたとき、M1 完了とする。**

| # | 条件 |
|---|---|
| C1 | 4条件 × 20 seed のスモーク実行が例外なく完走する |
| C2 | 決定論性テスト（T1）が通る |
| C3 | 禁止語テスト（T2）が通る |
| C4 | 局所性テスト（T3）が通る |
| C5 | 条件間不変テスト（T5）が通る |
| C6 | 保存則テスト（T4）が通る |
| C7 | 固定シナリオで `Consumer → Customizer → Maker` の遷移が発火する（T6） |
| C8 | §9.1 の全 Metrics が算出され、`outputs/` へ出力される |
| C9 | `metadata.json` が §9.2 の全項目を含む |
| C10 | 第三者が README を読んで同一の出力を再現できる |

### 11.1 完了条件に**含めない**もの — 明示

以下は M1 の完了条件に**含めない**。

> ❌ 条件A の maker_count が条件C より多いこと
> ❌ 条件A の knowledge_diffusion が条件B より速いこと
> ❌ Latent Capability に条件間の差が出ること

**理由**: これらを完了条件にすると、そうなるまでパラメータを調整することになる。それは SPEC §30 の Anti-Goal「結果が出るように後からパラメータを恣意的調整する」そのものである。

**条件間の差の有無は、Milestone 4 における観測結果であって、M1 の合格基準ではない。** M1 が保証すべきは「機構が動き、Metrics が測定可能であること」だけである。

差が出なかった場合、それは H1・H2 に対する**否定的な知見**であり、報告すべき結果である。パラメータ調整の理由にはしない。

---

## 12. 実装順序（推奨）

| 段階 | 内容 | 完了の目安 |
|---|---|---|
| S1 | `common/types.py`, `common/rng.py`, `common/io.py` | 型が定義され、seed の子ストリーム生成が動く |
| S2 | `agents/agent.py` + 初期化 + `test_condition_invariance` | 同一seedから4条件のAgentが完全一致で生成される |
| S3 | `culture/network.py` + `test_network_conditions` | B1 が次数保存していることが検証される |
| S4 | `agents/observation.py` + `test_locality` | Observation に World 参照がないことが保証される |
| S5 | `agents/decision.py`（決定論ルール） | Intent が返る |
| S6 | `world/production.py` + `culture/learning.py` | make の成否と技能獲得が動く |
| S7 | `culture/capability.py` + `test_stage_transition` | 段階遷移が発火する |
| S8 | `world/world.py`（stepループ）+ `test_determinism` | 決定論性が保証される |
| S9 | `simulation/metrics.py` + `test_metrics` | Metrics が出力される |
| S10 | `simulation/runner.py` + `metadata.json` | 再現性メタデータが揃う |
| S11 | `experiments/m1_smoke.py` + `test_smoke` | C1 達成 |
| S12 | `test_no_answer_leak`, `test_conservation` | 残りの完了条件を満たす |

**S2 と S4 を早期に置く理由**: 条件間不変性と情報局所性は、後から追加するのが最も困難な性質である。実装が進んでから「実は神の視点を使っていた」と発覚すると、広範囲の書き直しになる。テストを先に用意し、構造で担保する。

---

## 13. M2 への引き継ぎ設計

M1 の時点で、M2（LLM導入）への差し替え点を明確にしておく。

| M2 で差し替える箇所 | M1 での状態 | 差し替え方法 |
|---|---|---|
| `agents/decision.py::decide()` | 決定論的効用ルール | 同一シグネチャの LLM 実装に置換。M1 実装は `decide_rule_based()` として残し、ベースラインとして再利用 |
| `Observation` | M1 の全フィールド | フィールドを追加するのみ。削除・意味変更はしない |
| `Intent` | M1 の全フィールド | 変更しない。LLM の構造化出力スキーマとしてそのまま使う |
| Event 発火 | M1 では記録のみ | M2 で LLM 呼び出しのトリガーになる |

**M1 の決定論的結果を保存しておくことが、M2 の統制条件になる。** 「LLM を入れて何が変わったか」を差分として測れる（`docs/REVIEW.md` §3.2e）。

---

## 14. 未決事項（M1 着手前に決定が必要）

`docs/REVIEW.md` §12.2 のうち、M1 に直接影響するもの。

| # | 事項 | 本設計での仮置き | 決定が必要な理由 |
|---|---|---|---|
| D6 | 技能減衰の有無と率 | あり / `decay_rate = 0.005` | 減衰がないと H1 が自明化する（§6.3）。**推奨: 入れる** |
| D7 | Agent の参入・退出 | なし（母集団固定） | 母集団が動くと Metrics の解釈が変わる |
| D8 | 収入・生計の扱い | 初期資金のみ、収入なし | M1 では `trade` を実装しないため影響は小。M3 で要決定 |
| — | 蓄積相の step 数 | 480 step（≒9年相当、1step=1週） | 【要承認1】の承認内容に依存 |

**D6・D7・D8 の決定をもって、M1 の実装に着手できる。**
