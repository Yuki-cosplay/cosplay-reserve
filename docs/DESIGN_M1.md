# Milestone 1 詳細設計

**対象**: SPEC.md §28 Milestone 1（LLMなし、コードのみで機構を成立させる）
**準拠**: SPEC.md **v0.2**（§19 2×2完全要因計画 / §25 二相クロック / §33 改訂履歴）
**前提**: `docs/REVIEW.md` の承認、および §17 の決定事項
**作成日**: 2026-08-15
**最終更新**: 2026-08-15（SPEC v0.2 同期）

> **この文書の位置づけ**
> SPEC.md §32 最終行「Milestone 1を実装可能なレベルまで設計を具体化してください」への回答。
> `docs/REVIEW.md` で示した【実装提案】を具体的なモジュール・データ構造・式に落とす。
> **本文書のパラメータ値はすべて仮置きである。** 実験開始前に事前登録して固定する。

> **v0.2 同期にあたっての注意**
> 初版は SPEC v0.1（3条件 A / B1 / B2 / C）を前提に書かれていた。SPEC §33 により
> `Culture` / `Skill-Matched Random` / `Isolated` / `B1` / `B2` / Erdős–Rényi条件 は**名称ごと廃止**された。
> 本文書からもこれらを完全に除去している。旧名称を実装に持ち込んではならない。

---

## 1. スコープ

### 1.1 M1 に含めるもの（SPEC §28 の指定）

- Agent 生成（seed から決定論的に）
- skills / assets / network
- アクション: `observe` / `ask` / `practice` / `make` / `share`
- 技能学習
- maker stage 遷移
- Metrics 記録と出力
- **4条件（A / B / C / D）の世界生成**（SPEC §19: topology × peer learning）
- 材料の外生補充（§9）
- 感度分析グリッドの実行基盤（§11）

### 1.2 M1 に含めないもの

| 除外するもの | 理由 |
|---|---|
| LLM 呼び出し一切 | SPEC §28「Milestone 1: LLMなし」。蓄積相では M2 以降も使わない（決定 D12、§17） |
| 供給ショック | M3 の範囲（ショック相 1 step = 6時間、SPEC §25） |
| Hospital / Manufacturer / Logistics の実体 | M3 で需要が発生してから必要になる |
| 市場価格の内生的決定 | M3 |
| 金銭・所持金（`money`）・`trade` | **決定 D8**（§17）により M1 の因果モデルから除外。材料は外生補充で代替 |
| Agent の参入・退出 | **決定 D7**（§17）により実装しない。母集団 N=40 固定。拡張フックも設けない |
| 転化判定（Transition） | 需要がないので判定対象が存在しない |
| UI・可視化ダッシュボード | §30 Anti-Goal「不要なUIを先に作る」 |

`make` は M1 でも実装するが、**需要のない自主制作**として扱う。これで十分にループは閉じる（作る→技能獲得→共有）。

---

## 2. モジュール構成

SPEC §27 の構成をベースに、M1 で必要な最小サブセットのみを作成する。

```
cosplay-reserve/
  configs/
    base.yaml                 # 共通パラメータ（4条件で完全に同一）
    condition_a.yaml          # structured × peer learning ON
    condition_b.yaml          # rewired    × peer learning ON
    condition_c.yaml          # structured × peer learning OFF
    condition_d.yaml          # rewired    × peer learning OFF
  src/
    common/
      types.py                # AttributeVector, Method, Project 等の共通型
      rng.py                  # seed 管理・子ストリーム生成
      io.py                   # UTF-8 明示の読み書きヘルパ
    agents/
      agent.py                # Agent データ構造・初期化
      observation.py          # 局所情報の切り出し（神の視点の遮断点）
      decision.py             # M1: 決定論的ルール。M2 で LLM 差し替え
      memory.py               # Memory / MethodLibrary / peer 受容ゲート
    world/
      world.py                # World 状態・step ループ
      production.py           # make の成否判定・属性計算
      resources.py            # 材料の外生補充（inventory_cap 方式）
    culture/
      network.py              # base graph 生成と4条件への配布
      learning.py             # 技能獲得・減衰・scaffolding
      capability.py           # maker_stage 判定
    simulation/
      runner.py               # run のオーケストレーション・メタデータ記録
      metrics.py              # Metrics 算出・出力
      events.py               # Event 型・キュー
  experiments/
    m1_smoke.py               # 4条件 × 複数seed のスモーク実行
    sensitivity_grid.py       # §11 の 15セル感度分析
  outputs/                    # .gitignore 済み
  tests/
```

**config ファイル名について**: 上記の構成は SPEC §27（§33 改訂5 で追従済み）と一致している。旧条件名に基づくファイル名は SPEC 側からも除去済みであり、実装に持ち込んではならない。

**過剰なframework化を避ける**（§30）ため、以下は作らない: 依存性注入コンテナ、プラグイン機構、抽象基底クラスの階層、独自のイベントバス実装。

---

## 3. データ構造（確定版）

`docs/REVIEW.md` §5・§6 の提案を M1 に必要な範囲へ絞り込んだもの。

### 3.0 中立コードネーム方針（`docs/REVIEW.md` I8）

技能・材料・設備・制作対象・属性のすべてを、**意味を持たない連番コード**で表現する。

| 種別 | 表記 | 研究者向け対応表の所在 |
|---|---|---|
| 技能 | `skill_0` .. `skill_5` | **意図的に定めない**（下記） |
| 材料 | `mat_0` .. `mat_4` | 同上 |
| 設備 | `asset_0` .. `asset_3` | 同上 |
| 制作対象 | `proj_0` .. `proj_5` | 同上 |
| 要求仕様の属性 | `attr_0` .. `attr_6` | **SPEC.md §18 のみ**（列挙順に対応） |

**技能・材料・設備・制作対象に具体的な意味を割り当てない。** M1 には需要が存在しないため、これらは互いに交換可能なスロットであり、意味を持つ必要がない。逆に `sewing` / `3d_printing` のような名前を付けると、(a) LLM 導入時（M2）にプロンプトへ流入して既知知識のリーク経路になり、(b) 実装者が「この技能なら当然マスクを作れるはずだ」という答えを無意識に埋め込む経路になる。

`attr_0` .. `attr_6` だけは、M3 で `RequiredItem` との充足判定に使うため研究者側の対応表が必要になる。その対応表は **SPEC.md §18 にのみ存在する**。コード・config・ログ・出力ファイル・プロンプトには連番コードしか出現させない。`tests/test_no_answer_leak.py` がこれを機械的に強制する。

### 3.1 共通型

```python
# src/common/types.py
from dataclasses import dataclass, field
from enum import Enum

SKILL_NAMES    = ("skill_0", "skill_1", "skill_2", "skill_3", "skill_4", "skill_5")
MATERIAL_NAMES = ("mat_0", "mat_1", "mat_2", "mat_3", "mat_4")
ASSET_NAMES    = ("asset_0", "asset_1", "asset_2", "asset_3")

@dataclass(frozen=True)
class AttributeVector:
    """材料・製品・要求仕様を共通の空間で表現する。名称も意味も持たない。
    M1 では需要がないため主に Project.target_profile として使う。
    M3 で RequiredItem との充足判定に使う。
    【重要】属性に意味を持つ名前を付けない。対応表は SPEC.md §18（研究者向け）にのみ置く。
    コード・ログ・プロンプトには attr_0..attr_6 しか出現させない。"""
    attr_0: float = 0.0
    attr_1: float = 0.0
    attr_2: float = 0.0
    attr_3: float = 0.0
    attr_4: float = 0.0
    attr_5: float = 0.0
    attr_6: float = 0.0

@dataclass(frozen=True)
class Project:
    """制作対象の仕様。カタログは seed から決定論的に生成され、4条件で完全に同一。
    Agent はカタログから選ぶだけで、新しい project_type を作らない（M1 の範囲）。"""
    project_type: str                    # 中立コードネーム: "proj_0" .. "proj_5"
    primary_skill: str                   # SKILL_NAMES のいずれか
    base_difficulty: float               # 0.0-1.0
    required_asset: str | None           # ASSET_NAMES のいずれか、または None
    material_cost: dict[str, float]      # MATERIAL_NAMES -> 消費量
    time_cost: float                     # 1回の make に必要な時間
    target_profile: AttributeVector      # 完成物の属性。M3 の充足判定で使う

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
    hop_count: int               # 発明者からのホップ数。自己発見は 0

    @property
    def is_peer_acquired(self) -> bool:
        """peer learning ゲート（§8）と Metrics の分類に使う唯一の判定基準。"""
        return self.origin_agent_id != self.source_agent_id or self.hop_count > 0

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
    practiced_this_step: set[str]                    # 減衰の免除対象（§6.3）

    assets: dict[str, bool]                          # ASSET_NAMES -> 保有
    time_budget: float                               # 1step（=1週）あたりの可処分時間
    materials: dict[str, float]                      # MATERIAL_NAMES -> 在庫量

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
    completed_projects: list                         # ProjectOutcome の履歴
    rejected_intents: list

    inbox: list                                      # 受信メッセージ
    outbox: list                                     # 送信予定メッセージ

    # 決定 D8: money は M1 の因果モデルに存在しない。フィールドごと持たない。
    # 決定 D7: 参入・退出はない。alive / joined_step のようなフィールドも作らない。
```

**`money` と参入・退出フィールドを「将来のために置いておく」ことをしない。** 未使用フィールドは、後から因果モデルへ紛れ込む経路になる。M3 で必要になった時点で追加する。

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
    self_assets: dict[str, bool]
    self_time_budget: float
    self_materials: dict[str, float]
    self_maker_stage: MakerStage
    self_methods: tuple[Method, ...]

    project_catalog: tuple[Project, ...]              # 全Agent共通。世界の状態ではない

    neighbors: tuple[str, ...]                        # known_agents のみ
    perceived_neighbor_skills: dict[str, dict[str, PerceivedSkill]]
    trust: dict[str, float]

    inbox: tuple                                      # 今step 到着したメッセージ
    recent_events: tuple

    # M3 で追加: observable_market（観測可能な市場情報のみ）
```

`build_observation(world, agent) -> Observation` が唯一の変換点。ここ以外で Agent が World を参照するコードを書いてはならない。

**`peer_learning_enabled` を Observation に入れてはならない。** これは世界の物理法則であって、Agent が知覚し戦略を変える対象ではない（§8）。

---

## 4. 1ステップの処理シーケンス

1 step = 1週間（蓄積相、SPEC §25）。

```python
def step(world: World) -> None:
    # (0) 外生補充 — 全条件で同一（§9）
    replenish_materials(world)
    reset_time_budgets(world)
    for a in world.agents.values():
        a.practiced_this_step.clear()

    # (1) perceive — 局所情報の切り出し
    observations = {a.id: build_observation(world, a) for a in world.agents.values()}

    # (2) decide — Intent 列の生成（M1: 決定論的ルール / M2以降: LLM）
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
    deliver_messages(world)          # outbox -> 近傍の inbox。peer ゲートは受容時（§8）

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
def decide(obs: Observation, rng) -> list[Intent]:
    """M1: 効用ベースの決定論的ルール（rng は同点処理のみに使用）。
    M2: この関数を LLM 実装に差し替える。シグネチャは変更しない。
    1 step = 1週間あるため、時間予算が尽きるまで貪欲に行動を選ぶ
    （最大 cfg.max_actions_per_step 件）。"""
```

### 5.1 効用の定義（仮置き）

各行動の効用を計算し、時間予算内で最大のものから順に選ぶ。

| 行動 | 効用 | 意図 |
|---|---|---|
| `observe` | `w_obs × (未知の近傍数 / 近傍数)` | 情報が少ないほど観測したくなる |
| `ask` | `w_ask × imitation_tendency × (近傍の推定技能 − 自技能)⁺ × trust` | 自分より上手い相手がいるほど尋ねたくなる |
| `practice` | `w_prac × (1 − max_skill)` | 技能が低いほど練習の限界効用が高い |
| `make` | `w_make × participation_level × expected_success_prob` | 成功見込みが高いほど作りたくなる |
| `share` | `w_share × sharing_tendency × 未共有Methodの数` | 共有性向と手持ち知識に比例 |
| `idle` | `w_idle`（一定の下限値） | 何もしない選択肢 |

重み `w_*` はすべて config。行動には時間コストがあり、残り `time_budget` を超える行動は選択できない。材料が不足する `make` も選択できない（実現可能性はコードが判定する — SPEC §13）。

**重要**: この効用関数は「Agent がループを回すため」に設計されていない。各 Agent は自分の局所状態から自分の効用を最大化するだけであり、ループは結果としてマクロに現れる（SPEC §5 の要求）。

**効用関数は4条件で完全に同一である。** 条件によって重みや選択肢を変えてはならない。C/D の Agent も `ask` と `share` を通常どおり選択する（§8）。

---

## 6. 中核の式

### 6.1 制作の成否

```python
def success_probability(agent, project, methods) -> float:
    skill = agent.skills[project.primary_skill]
    asset_bonus = cfg.asset_bonus if has_required_asset(agent, project) else 0.0

    # scaffolding: 該当Methodを持っていると実効難度が下がる ← ループの閉じ目
    reduction = max((m.difficulty_reduction for m in methods
                     if m.project_type == project.project_type), default=0.0)
    effective_difficulty = project.base_difficulty * (1.0 - reduction)

    raw = skill + asset_bonus - effective_difficulty
    return clamp(sigmoid(raw / TEMPERATURE), 0.02, 0.98)
```

`reduction` の項が **Capability Reproduction Loop を閉じる唯一の環**である。

- **self-scaffolding**（全条件で有効）: 自分が発見した Method が、自分の成功確率を上げる
- **social scaffolding**（A/B のみ）: 他Agentから受け取った Method が、自分の成功確率を上げる

C/D では peer 由来 Method が Library に入らないため（§8）、`methods` に peer 由来のものは存在しない。**この関数自体に条件分岐を書いてはならない。** 分岐は §8 の受容ゲート1箇所のみに置く。

### 6.2 技能獲得（収穫逓減）

```python
def skill_gain(current_skill: float, success: bool, cfg) -> float:
    base = cfg.learn_rate_success if success else cfg.learn_rate_failure
    return base * (1.0 - current_skill)      # 上限 1.0 に漸近
```

失敗からも学ぶ（`learn_rate_failure < learn_rate_success`）。これにより初期段階の完全停滞を防ぐ。

**仮置き**: `learn_rate_success = L = 0.04`, `learn_rate_failure = 0.25 × L`

`L` は感度分析の因子である（§11）。`learn_rate_failure` は `L` に比例して動かし、比率 0.25 を固定する。

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

**決定 D6（§17）により減衰は採用する。** ただし `decay_rate` の値は暫定であり、**この値に依存する主張はしない**。`L / D` 比が均衡技能水準を支配するため、感度分析（§11）で `L/D ∈ {4, 8, 16, 32}` と no-decay baseline を必ず併走させる。

**仮置き**: `decay_rate = D = L / 8 = 0.005` / step（1 step = 1週）

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
# make 成功時に、一定確率で新しい Method が生まれる（自己発見。全条件で有効）
if success and rng.random() < cfg.method_discovery_prob:
    agent.methods[new_id] = Method(
        method_id=new_id, project_type=project.project_type,
        primary_skill=project.primary_skill,
        required_skill_level=agent.skills[project.primary_skill],
        difficulty_reduction=cfg.base_reduction,
        origin_agent_id=agent.id, source_agent_id=agent.id,
        origin_step=world.step, acquired_step=world.step, hop_count=0,
    )

# share は近傍の inbox へ Method を配送する（全条件で有効）
# 受容は §8 のゲートを必ず経由する
```

`hop_count` と `origin_agent_id` により、**誰の発明が何ホップで何step後に誰へ届いたか**が完全に追跡できる。これが `knowledge_diffusion_speed` の測定基盤になる。

---

## 7. 4条件のネットワーク構築

SPEC §19 の**完全ペアリング要件**を構造で保証する。base graph を1回だけ生成し、deep copy で配布する。

```python
# src/culture/network.py
import copy
import networkx as nx

def build_base_graphs(agents, cfg, rng) -> dict[str, nx.Graph]:
    """【最重要】topology ごとに base graph を1回だけ生成する。
    条件ごとに生成し直してはならない。生成の乱数差で A/C または B/D に
    差が出ることを SPEC §19 が明示的に禁止している。"""

    structured = watts_strogatz_like(agents, k=cfg.mean_degree,
                                     p=cfg.rewire_p, rng=rng)
    structured = add_skill_assortativity(structured, agents,
                                         strength=cfg.assortativity, rng=rng)

    # 次数保存リワイヤリング。次数分布とエッジ数を完全に保存し、
    # 『誰と誰が繋がっているか』だけを壊す → topology の効果を単離できる
    rewired = copy.deepcopy(structured)
    nx.double_edge_swap(rewired,
                        nswap=cfg.swap_multiplier * rewired.number_of_edges(),
                        max_tries=10**6, seed=int(rng.integers(2**31)))

    return {"structured": structured, "rewired": rewired}


CONDITIONS = {
    #            topology       peer_learning_enabled
    "A": ("structured", True),
    "B": ("rewired",    True),
    "C": ("structured", False),
    "D": ("rewired",    False),
}

def graph_for(condition: str, base_graphs, agents) -> nx.Graph:
    """A と C は同一の structured graph、B と D は同一の rewired graph を受け取る。
    deep copy するのは、run 中の変更が他条件へ漏れないようにするためだけであり、
    構造は完全に同一である。tests/test_network_pairing.py が検証する。"""
    topology, _ = CONDITIONS[condition]
    return relabel_to_agent_ids(copy.deepcopy(base_graphs[topology]), agents)
```

**4条件で共通なもの**: Agent の初期状態（技能・設備・材料・性向）、Project カタログ、効用重み、学習率、減衰率、補充設定、step 数、Agent 数。
**条件間で違うもの**: 使用する base graph（structured / rewired）と `peer_learning_enabled` フラグの2つだけ。

**`nx.empty_graph()` を使ってはならない。** SPEC §19 により、C/D は社会的接触を保持した世界である。エッジを削除する条件は M1 に存在しない。

---

## 8. peer learning の遮断点 — 分岐はここ1箇所のみ

SPEC §19 が定める C/D の意味は「ネットワークを除去した世界」ではなく、

> 人は社会的につながっているが、そのつながりが制作能力の再生産経路として機能しない世界

である。したがって遮断するのは **peer Method transfer だけ**である。

### 8.1 全条件で有効なもの（C/D でも維持）

`practice` / `make` / **Method の自己発見** / **self-scaffolding** / `observe` / `ask` / `share` / メッセージ配送 / `perceived_skills` の更新 / `trust` の更新 / 近傍関係そのもの。

`ask` は C/D でも実行され、相手の技能に関する信念（`perceived_skills`）と `trust` を更新する。更新されないのは Method Library だけである。

### 8.2 C/D でのみ無効なもの

他Agent由来 Method の**受容**。これに伴い、peer 由来 Method による social scaffolding も発生しなくなる。

### 8.3 実装 — 単一ゲート

```python
# src/agents/memory.py
def accept_peer_method(agent, method: Method, cfg, rng) -> bool:
    """peer learning の遮断点は、コード全体でこの関数の1箇所のみ。
    ここ以外に peer_learning_enabled を参照する分岐を書いてはならない。
    分岐が散らばると『C/D で何が無効なのか』が追跡不能になる。"""
    if not cfg.peer_learning_enabled:
        return False                      # ← C/D はここで止まる。ask/share 自体は起きている
    if method.project_type in {m.project_type for m in agent.methods.values()}:
        return False
    p = agent.imitation_tendency * agent.trust.get(method.source_agent_id, 0.0)
    return rng.random() < p
```

受容された場合のみ `hop_count + 1`、`source_agent_id = 送信者`、`acquired_step = world.step` として Library へ格納する。

### 8.4 manipulation check

`method_peer_acquisition_per_time`（§10.1）は **C/D で常に厳密に 0** でなければならない。同時に `observe` / `ask` / `share` の実行回数は C/D でも 0 より大きくなければならない。この2つを `tests/test_peer_learning_gate.py` が機械的に検証する。片方でも破れていれば、操作が意図と違うものになっている。

---

## 9. 材料の外生補充（決定 D13）

### 9.1 方式 — inventory_cap

```python
# src/world/resources.py
def replenish_materials(world) -> None:
    """毎step、各Agentの材料在庫を上限に向けて一定量補充する。
    全条件・全Agentで同一の外生パラメータ。条件間の差を一切作らない。"""
    cfg = world.cfg.materials
    for agent in world.agents.values():
        for m in MATERIAL_NAMES:
            agent.materials[m] = min(cfg.inventory_cap[m],
                                     agent.materials[m] + cfg.replenish_rate[m])
```

### 9.2 なぜ必要か

決定 D8 により `money` を M1 の因果モデルから外した。材料が初期配分のみの枯渇性ストックだと、次の2つが起きる。

1. 在庫が尽きた時点で `make` が停止し、以降の技能蓄積が**初期配分の関数**になる。条件の効果ではなく初期値の効果を測ることになる
2. 枯渇を避けるために Agent が「貯め込む」挙動を設計に入れたくなる。それは非線形性をコードに埋め込むことであり、CLAUDE.md 絶対ルールに抵触する

`inventory_cap` 方式は、材料の可用性を**全条件で同一の定常的な背景条件**にする。上限があるため貯め込みも発生しない。

### 9.3 制約

- `inventory_cap` と `replenish_rate` は `base.yaml` にのみ書く。条件別 YAML で上書きしてはならない
- `tests/test_material_replenishment.py` が、在庫が cap を超えないこと・4条件で補充設定が完全一致することを検証する
- 補充量は感度分析の因子ではない（M1 では固定）。M3 で供給ショックを入れる際に、この外生補充自体が制約要因として再検討対象になる

---

## 10. Metrics と出力

### 10.1 M1 で記録する Metrics

SPEC §22 のうち M1 で算出可能なもの、および v0.2 同期で追加した時間正規化指標。

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
| **`time_allocation_by_action`** | action別の消費時間合計と、総消費時間に対する割合 | 毎step |
| **`skill_gain_per_time`** | Σ(技能獲得量) / Σ(消費時間)。Agent平均と分布 | 毎step |
| **`method_self_discovery_per_time`** | 自己発見 Method 数 / `make` に投入した時間 | 毎step |
| **`method_peer_acquisition_per_time`** | peer 由来受容 Method 数 / (`observe`+`ask`+`share`) に投入した時間 | 毎step |

### 10.2 追加4指標の意図

**時間で正規化しないと、条件間比較が「何をしたか」ではなく「どれだけ時間を使ったか」の比較になる。** 例えばある条件で `make` の割合が高ければ、Method の自己発見数は当然増える。生の件数だけを見ると、それを能力再生産の差と誤読する。

- `time_allocation_by_action` — 条件が Agent の**時間配分**を変えたのかを直接見る。効用関数は4条件で同一だが、`ask` の期待効用は近傍の推定技能に依存するため、配分は内生的に変わりうる
- `skill_gain_per_time` — 投入時間あたりの学習効率。H2「Latent Capability がより速く成長するか」の速度の分母を明示する
- `method_self_discovery_per_time` — 自力での知識生成レート。C/D でもこれは動く。**A/B の優位が単なる自己発見の増加なのか、peer 経路なのかを切り分ける**
- `method_peer_acquisition_per_time` — peer 経路そのもののレート。C/D では定義上 0 であり、§8.4 の manipulation check を兼ねる

**`latent_capacity` は積の形で単一スコア化しない**（`docs/REVIEW.md` §12.3）。構成指標を別々に保存する。

M1 で算出しないもの: `active_supplier_count`, `community_supply_share`, `transition_time`, `coordination_edges`, `coordination_complexity`（いずれも需要の発生が前提）。

### 10.3 出力フォーマット

```
outputs/
  <run_id>/
    metadata.json           # 再現性メタデータ（下記）
    timeseries.csv          # step 単位のスカラー Metrics
    agents_snapshot.jsonl   # 10step 毎の全Agent状態
    method_events.jsonl     # Method の生成・共有・受容・却下の全イベント
    time_allocation.csv     # step × action の消費時間
    network_snapshot.json   # 初期・中間・最終のネットワーク
    config_resolved.yaml    # 継承解決後の実効config
```

**`metadata.json`（SPEC §23 の要求を満たす）**:

```json
{
  "run_id": "20260815T120000_A_seed42",
  "timestamp_utc": "2026-08-15T12:00:00Z",
  "random_seed": 42,
  "condition": "A",
  "topology": "structured",
  "peer_learning_enabled": true,
  "phase": "accumulation",
  "steps": 156,
  "step_hours": 168,
  "milestone": "M1",
  "llm": null,
  "prompt_version": null,
  "config_sha256": "...",
  "base_graph_sha256": "...",
  "code_git_commit": "...",
  "python_version": "3.12.10",
  "package_versions": {"numpy": "2.5.2", "networkx": "3.6.1", "...": "..."},
  "agent_initial_states_sha256": "...",
  "final_state_sha256": "..."
}
```

`base_graph_sha256` は**完全ペアリングの証拠**として残す。A と C、B と D でこの値が一致していなければ、SPEC §19 の要件を満たしていない。

M1 では `llm` と `prompt_version` は `null`。M2 でここが埋まる。`agent_initial_states_sha256` は条件間不変テスト（T5）でも利用する。

すべてのファイル書き込みで `encoding="utf-8"`、`newline=""` を明示する（Windows 環境対策）。

---

## 11. 感度分析グリッド

### 11.1 因子

技能の均衡水準は `L`（学習率）と `D`（減衰率）の**比**が支配する。片方だけを振っても意味がないため、`L` と `L/D` 比を直交させる。

| 因子 | 水準 |
|---|---|
| `L` = `learn_rate_success` | 0.02 / 0.04 / 0.08 |
| `L/D` 比 | 4 / 8 / 16 / 32 |

`learn_rate_failure = 0.25 × L`（比率固定）。`D = L / (L/D比)`。

### 11.2 15セル

| セル | L | L/D | D = decay_rate |
|---|---|---|---|
| S01 | 0.02 | 4 | 0.005 |
| S02 | 0.02 | 8 | 0.0025 |
| S03 | 0.02 | 16 | 0.00125 |
| S04 | 0.02 | 32 | 0.000625 |
| S05 | 0.04 | 4 | 0.01 |
| S06 | 0.04 | 8 | **0.005（既定値）** |
| S07 | 0.04 | 16 | 0.0025 |
| S08 | 0.04 | 32 | 0.00125 |
| S09 | 0.08 | 4 | 0.02 |
| S10 | 0.08 | 8 | 0.01 |
| S11 | 0.08 | 16 | 0.005 |
| S12 | 0.08 | 32 | 0.0025 |
| S13 | 0.02 | — | **0（no-decay baseline）** |
| S14 | 0.04 | — | **0（no-decay baseline）** |
| S15 | 0.08 | — | **0（no-decay baseline）** |

12セル（3 × 4）＋ 各 `L` の no-decay baseline 3セル ＝ **15セル**。

### 11.3 no-decay baseline を必ず入れる理由

減衰の導入（決定 D6）は、H1 を自明化させないための設計判断である。しかし減衰自体がパラメータであり、**減衰の値によって結論が変わるなら、その結論は減衰の設定の産物である**。`D = 0` を併走させることで、「減衰なしでも成立するか / 減衰がある場合にのみ成立するか」を明示的に報告できる。これは §15.1 の Anti-Goal 回避と同じ趣旨である。

### 11.4 実行規模

15セル × 4条件 × 5 seed = **300 run**。LLM を使わないためコストはゼロ（決定 D12）。

**感度分析は「良い結果が出るセルを探す作業ではない」。** 全15セルの結果を報告し、条件間の関係がパラメータ領域を通じて安定か不安定かを示す。安定でなければ、それが結果である。

---

## 12. seed 設計

| 用途 | seed 数 | run 数 | 備考 |
|---|---|---|---|
| 開発中の smoke | 1〜5 | 4〜20 | 実装反復用。**結果の解釈に使わない** |
| 感度分析（§11） | 5 | 300 | 15セル × 4条件 × 5 |
| 最終主実験 | 20 | 80 | 4条件 × 20。**事前登録してから実行する** |

seed は `master_seed` から `rng.spawn()` で子ストリームを派生させる。Agent ごと・ネットワーク生成・解決順序でストリームを分離し、片方の呼び出し回数変更が他方の乱数列を汚染しないようにする。

**同一 seed における4条件は、同じ `master_seed` から同じ初期状態を生成する。** 条件が変えるのは §7 の2点のみ。

---

## 13. テストファイル一覧

| ファイル | テスト内容 | 対応 |
|---|---|---|
| `tests/test_determinism.py` | 同一seedで2回実行し `final_state_sha256` が一致 | T1 |
| `tests/test_no_answer_leak.py` | Agent向け全文字列に禁止語が含まれない | T2 |
| `tests/test_locality.py` | `Observation` に World 参照・他Agent真値・`peer_learning_enabled` が含まれない | T3 |
| `tests/test_conservation.py` | 材料が負にならない・`inventory_cap` を超えない | T4 |
| `tests/test_condition_invariance.py` | **A/B/C/D の4条件で初期Agent状態・Projectカタログが完全一致** | T5 |
| `tests/test_stage_transition.py` | 固定シナリオで Consumer→Customizer→Maker が発火 | T6 |
| `tests/test_learning_causality.py` | share 無効化で knowledge_diffusion が 0 になる | T7 |
| `tests/test_metrics.py` | 手計算フィクスチャと算出値が一致（追加4指標を含む） | T8 |
| `tests/test_network_pairing.py` | **A と C のエッジ集合が完全一致／B と D が完全一致／A と B の次数列とエッジ数が一致** | T9 |
| `tests/test_peer_learning_gate.py` | **C/D で peer 由来 Method が 0 かつ observe/ask/share の実行回数 > 0** | T11 |
| `tests/test_material_replenishment.py` | **補充設定が4条件で同一、在庫が cap を超えない** | T12 |
| `tests/test_smoke.py` | 20 seed × 4条件が例外なく完走 | T10 |

`test_condition_invariance.py` は、4条件それぞれで World を構築し、**ネットワーク構築前の Agent 状態**の SHA-256 が4つとも一致することを検証する。一致しなければ、条件分岐が Agent 初期化へ漏れている。

### 13.1 実行方法

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m pytest tests/test_determinism.py -v
.\.venv\Scripts\python.exe -m pytest tests/test_no_answer_leak.py::test_no_answer_leak_in_agent_facing_strings
```

---

## 14. config スキーマ

### 14.1 base.yaml（4条件で完全に同一）

```yaml
run:
  seed: 42
  phase: accumulation
  steps: 156                    # 蓄積相。52 / 104 / 156 から選択（決定 D11）
  step_hours: 168               # 1 step = 1週間（SPEC §25 蓄積相）
  output_dir: outputs/

world:
  n_cosplay_agents: 30
  n_general_agents: 10          # 合計 N=40 固定（決定 D7。参入・退出なし）
  project_types: 6              # 中立コードネーム proj_0 .. proj_5

network:
  mean_degree: 6
  rewire_p: 0.1
  assortativity: 0.3
  swap_multiplier: 10           # rewired の double_edge_swap 回数 = 10 × エッジ数

materials:                      # 決定 D13。条件別 YAML で上書き禁止
  names: [mat_0, mat_1, mat_2, mat_3, mat_4]
  initial: 5.0                  # 全Agent・全材料の初期在庫
  inventory_cap: 10.0
  replenish_rate: 1.0           # per step

learning:
  learn_rate_success: 0.04      # = L。感度分析の因子（§11）
  learn_rate_failure_ratio: 0.25  # learn_rate_failure = ratio × L
  decay_rate: 0.005             # = D = L / 8。感度分析の因子（§11）
  base_reduction: 0.25          # Method 1件あたりの実効難度低減
  method_discovery_prob: 0.15
  asset_bonus: 0.2

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

time:
  budget_per_step: 3.0          # 1週あたりの可処分時間（抽象単位）
  max_actions_per_step: 6
```

### 14.2 条件別 YAML — 差分は2行のみ

```yaml
# configs/condition_a.yaml
extends: base.yaml
condition: A
topology: structured
peer_learning_enabled: true
```

```yaml
# configs/condition_b.yaml
extends: base.yaml
condition: B
topology: rewired
peer_learning_enabled: true
```

```yaml
# configs/condition_c.yaml
extends: base.yaml
condition: C
topology: structured          # ← A と同一の base graph を deep copy して使う
peer_learning_enabled: false
```

```yaml
# configs/condition_d.yaml
extends: base.yaml
condition: D
topology: rewired             # ← B と同一の base graph を deep copy して使う
peer_learning_enabled: false
```

**条件間の差分がこの2キーだけであることが、比較の妥当性の担保になる。** 学習率・減衰率・Agent数・材料補充・効用重み・step数を条件ごとに変えてはならない。`config_resolved.yaml` の差分を取って2キー以外の差がないことを、`test_condition_invariance` が検証する。

---

## 15. Milestone 1 完了の判定条件

**以下すべてを満たしたとき、M1 完了とする。**

| # | 条件 |
|---|---|
| C1 | 4条件 × 20 seed（最終主実験と同一設定）のスモーク実行が例外なく完走する |
| C2 | 決定論性テスト（T1）が通る |
| C3 | 禁止語テスト（T2）が通る |
| C4 | 局所性テスト（T3）が通る |
| C5 | 条件間不変テスト（T5）が通る |
| C6 | 保存則テスト（T4）が通る |
| C7 | 固定シナリオで `Consumer → Customizer → Maker` の遷移が発火する（T6） |
| C8 | §10.1 の全 Metrics が算出され、`outputs/` へ出力される |
| C9 | `metadata.json` が §10.3 の全項目を含む |
| C10 | 第三者が README を読んで同一の出力を再現できる |
| C11 | **ネットワーク完全ペアリングテスト（T9）が通り、A/C と B/D の `base_graph_sha256` が一致する** |
| C12 | **peer learning ゲートテスト（T11）が通る**（C/D で peer 取得 0、かつ observe/ask/share は発生） |
| C13 | **感度分析15セル（§11）が完走し、全セルの結果が出力される** |

### 15.1 完了条件に**含めない**もの — 明示

以下は M1 の完了条件に**含めない**。

> ❌ 条件A の maker_count が条件C より多いこと
> ❌ 条件A の knowledge_diffusion が条件B より速いこと
> ❌ Latent Capability に条件間の差が出ること
> ❌ topology または peer learning の主効果・交互作用が有意であること

**理由**: これらを完了条件にすると、そうなるまでパラメータを調整することになる。それは SPEC §30 の Anti-Goal「結果が出るように後からパラメータを恣意的調整する」そのものである。

**条件間の差の有無は、Milestone 4 における観測結果であって、M1 の合格基準ではない。** M1 が保証すべきは「機構が動き、Metrics が測定可能であること」だけである。

差が出なかった場合、および **A < B** のように事前の予想と逆転した場合（SPEC §19）、それは H1・H2 に対する正当な知見であり、報告すべき結果である。パラメータ調整の理由にはしない。

---

## 16. 実装順序（推奨）

| 段階 | 内容 | 完了の目安 |
|---|---|---|
| S1 | `common/types.py`, `common/rng.py`, `common/io.py` | 型が定義され、seed の子ストリーム生成が動く |
| S2 | `agents/agent.py` + 初期化 + `test_condition_invariance` | 同一seedから4条件のAgentが完全一致で生成される |
| S3 | `culture/network.py` + `test_network_pairing` | A/C・B/D の完全ペアリングと次数保存が検証される |
| S4 | `agents/observation.py` + `test_locality` | Observation に World 参照がないことが保証される |
| S5 | `agents/decision.py`（決定論ルール） | Intent 列が返る |
| S6 | `world/resources.py` + `test_material_replenishment` | 補充が全条件同一で動く |
| S7 | `world/production.py` + `culture/learning.py` | make の成否と技能獲得が動く |
| S8 | `agents/memory.py`（受容ゲート）+ `test_peer_learning_gate` | C/D の遮断が1箇所で成立する |
| S9 | `culture/capability.py` + `test_stage_transition` | 段階遷移が発火する |
| S10 | `world/world.py`（stepループ）+ `test_determinism` | 決定論性が保証される |
| S11 | `simulation/metrics.py` + `test_metrics` | 追加4指標を含む Metrics が出力される |
| S12 | `simulation/runner.py` + `metadata.json` | 再現性メタデータが揃う |
| S13 | `experiments/m1_smoke.py` + `test_smoke` | C1 達成 |
| S14 | `experiments/sensitivity_grid.py` | C13 達成 |
| S15 | `test_no_answer_leak`, `test_conservation` | 残りの完了条件を満たす |

**S2・S3・S4 を早期に置く理由**: 条件間不変性・ネットワークペアリング・情報局所性は、後から追加するのが最も困難な性質である。実装が進んでから「実は神の視点を使っていた」「A と C のグラフが別物だった」と発覚すると、広範囲の書き直しになる。テストを先に用意し、構造で担保する。

---

## 17. 決定済み事項（承認済み）

`docs/REVIEW.md` §12.2 の未決事項のうち、M1 に関わるもの。**以下は承認済みであり、M1 の実装前提とする。**

| # | 事項 | 決定 | 補足 |
|---|---|---|---|
| **D6** | 技能減衰 | **採用する** | `decay_rate` は**暫定値であり、この値に依存する主張はしない**。感度分析（§11）の対象とし、no-decay baseline を必ず併走させる |
| **D7** | Agent の参入・退出 | **実装しない** | 母集団 **N=40 固定**。将来のための拡張フック（`alive` フラグ等）も**設けない** |
| **D8** | 収入・生計 | **`money` を M1 の因果モデルから外す** | フィールドごと持たない。材料は外生補充（D13）で代替。M3 で経済を導入する際に再設計する |
| **D11** | 蓄積期間 | **52 / 104 / 156 週を config 切替。既定 156** | SPEC §25 の蓄積相に対応 |
| **D12** | 蓄積相の LLM | **使わない** | 蓄積相は M2 以降も決定論的コードで回す。LLM はショック相の局所判断に限定する。これによりコストは M1 でゼロ、感度分析300runもゼロ |
| **D13** | 材料補充 | **`inventory_cap` 方式。全条件同一、config 化** | §9。条件別 YAML での上書きを禁止 |

M1 実装をブロックする未決事項は**残っていない**。

---

## 18. 残件（M1 をブロックしないもの）

| # | 内容 | 期限 |
|---|---|---|
| ~~R1~~ | ~~SPEC §27 と CLAUDE.md の config ファイル名が廃止済み条件名のまま~~ | ✅ **解決済み**（2026-08-15、SPEC §33 改訂5） |
| R2 | Emergence Level E0〜E4 の操作的定義（`docs/REVIEW.md` §12.3） | M3 着手前 |
| R3 | D1（API費用上限の実額）・D2（モデルティア）・D3（run 数の事前登録） | M2 着手前 |
| R4 | D4（転化閾値）・D5（Manufacturer 生産能力）・D9（品質未達供給の扱い） | M3 着手前 |
| R5 | D10（Phase 2 の未知ショック生成主体） | Phase 2 着手前 |

---

## 19. M2 への引き継ぎ設計

M1 の時点で、M2（LLM導入）への差し替え点を明確にしておく。

| M2 で差し替える箇所 | M1 での状態 | 差し替え方法 |
|---|---|---|
| `agents/decision.py::decide()` | 決定論的効用ルール | 同一シグネチャの LLM 実装に置換。M1 実装は `decide_rule_based()` として残し、ベースラインとして再利用 |
| `Observation` | M1 の全フィールド | フィールドを追加するのみ。削除・意味変更はしない |
| `Intent` | M1 の全フィールド | 変更しない。LLM の構造化出力スキーマとしてそのまま使う |
| Event 発火 | M1 では記録のみ | M2 で LLM 呼び出しのトリガーになる |
| 時間解像度 | 蓄積相 1 step = 1週 | M3 でショック相 1 step = 6時間を追加。蓄積相の実装は変更しない |

**M1 の決定論的結果を保存しておくことが、M2 の統制条件になる。** 「LLM を入れて何が変わったか」を差分として測れる（`docs/REVIEW.md` §3.2e）。

決定 D12 により、**蓄積相には M2 以降も LLM を入れない**。M2 の LLM 導入対象はショック相の局所判断である。
