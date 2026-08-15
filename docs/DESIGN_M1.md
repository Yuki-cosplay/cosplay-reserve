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

`attr_0` .. `attr_6` だけは、M3 で `RequiredItem` との充足判定に使うため研究者側の対応表が必要になる。その対応表は **SPEC.md §18 にのみ存在する**。

#### 3.0.1 禁止語テスト（T2）の対象範囲 — 確定

中立化の目的は「**Agent（および M2 以降の LLM）へ答えが流入しないこと**」であって、研究者が読む文書を難読化することではない。したがって T2 の検査対象を以下に限定する。

**対象（Agent-facing strings）:**

- system / user prompt（M2 以降）
- Action 名
- Agent へ渡る Item / Material / Skill / Asset / Project の identifier
- `Observation` 上に現れる文字列
- Agent memory（`recent_events` / `inbox` / `completed_projects` 等）へ格納される文字列

**対象外（researcher-facing）:**

- `README.md` / `RESULTS.md` / `SPEC.md` / `docs/`
- `config_resolved.yaml` および config のキー名
- researcher-facing logs（`timeseries.csv`、`metrics`、`metadata.json` 等）
- コードコメント・docstring

**この線引きの帰結**: config のキー名（例: `n_participant_agents`）は T2 の対象外である。一方で、そのキーが**生成する identifier**（`skill_0` 等）は Agent へ渡るため対象内である。研究者が意味を追えるようにしつつ、Agent 側には意味を渡さない、という非対称を意図的に作る。

**それでも config のキー名は中立に保つ**（決定 X4）。`n_cosplay_agents` のような命名は、T2 に引っかからなくても実装者の頭の中に「答え」を持ち込むため使わない。

### 3.1 共通型

**ID 一覧は config が single source of truth（決定 Y4）。** `types.py` に `SKILL_NAMES` のようなタプルを**ハードコードしない**。config のロード時に ID 一覧を生成し、`IdRegistry` として引き回す。二重定義があると、config を変えたのにコード側の定数が古いまま、という不整合が静かに発生する。

```python
# src/common/types.py
from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class IdRegistry:
    """config から生成される ID 一覧。Python 側に定数を持たない（決定 Y4）。
    world.n_skills / n_materials / n_assets / n_project_types から
    skill_0.. / mat_0.. / asset_0.. / proj_0.. を決定論的に生成する。"""
    skill_ids: tuple[str, ...]
    material_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    project_ids: tuple[str, ...]

    @classmethod
    def from_config(cls, cfg) -> "IdRegistry":
        gen = lambda prefix, n: tuple(f"{prefix}_{i}" for i in range(n))
        return cls(gen("skill", cfg.world.n_skills),
                   gen("mat",   cfg.world.n_materials),
                   gen("asset", cfg.world.n_assets),
                   gen("proj",  cfg.world.n_project_types))

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
    primary_skill: str                   # skill_ids のいずれか
    base_difficulty: float               # 0.0-1.0
    required_asset: str | None           # asset_ids のいずれか、または None
    material_cost: dict[str, float]      # material_ids -> 消費量
    target_profile: AttributeVector      # 完成物の属性。M3 の充足判定で使う
    # 決定 Y3: time_cost は持たない。make の時間コストは
    # action_time_cost.make に一本化する。Project 間の差は base_difficulty
    # ・required_asset・material_cost で表現する。

@dataclass(frozen=True)
class Method:
    """共有される手順知識。伝播経路の追跡情報を必ず持つ。
    これにより knowledge_diffusion_speed が副産物として測定可能になる。"""
    method_id: str
    project_type: str            # 中立コードネーム: "proj_0" .. "proj_K"
    primary_skill: str           # skill_ids のいずれか
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
    """一般化された行動のみ。答えを含む行動は定義しない。
    決定 Y5: CONSUME は M1 から削除した。SPEC §12 では将来候補として
    列挙されているが、M1 では効用も時間コストも定義されず使用しない。"""
    OBSERVE  = "observe"
    ASK      = "ask"
    PRACTICE = "practice"
    MAKE     = "make"
    SHARE    = "share"
    IDLE     = "idle"

@dataclass(frozen=True)
class Intent:
    """Agent が「何をしたいか」だけを表す。決定 X1。
    【構造的制約】数量フィールドを持たせない（`docs/REVIEW.md` I21）。
    生産数量・金額・消費時間量・成功可否は一切含めない。
    数量・時間・実現可能性はすべてコード側（Validator と resolve）が決定する。
    これが SPEC §13「LLM decides intent. Code determines feasibility.」の
    型レベルでの担保になる。
    M2 ではこの型をそのまま LLM の structured output schema として再利用する。"""
    action: ActionType
    target_agent_id: str | None = None
    target_project_id: str | None = None
    target_skill_id: str | None = None
    target_method_id: str | None = None
    reason: str = ""              # 研究者向けの記録。世界状態には影響しない
```

**`Intent` に数量を入れてはならない。** 「材料を3個使って2個作る」と Agent（M2 以降は LLM）が宣言できてしまうと、実現可能性の判定が LLM 側へ漏れる。Agent が言えるのは「`proj_2` を作りたい」までで、何個の材料を消費し何時間かかるかは Project 定義と config が決める。

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

    is_participant: bool                             # §3.4。生成後は変化しない
                                                     # （M1 では参加の出入りを扱わない）

    skills: dict[str, float]                         # skill_ids -> 0.0-1.0
    practice_count: dict[str, int]
    success_count: dict[str, int]
    failure_count: dict[str, int]
    practiced_this_step: set[str]                    # 減衰の免除対象（§6.3）

    assets: dict[str, bool | int]                    # asset_ids -> 保有（tools のみ 0-3）
    time_budget: float                               # 1step（=1週）あたりの可処分時間
                                                     # 決定 X2-7: M1 では全Agent同一
    materials: dict[str, float]                      # material_ids -> 在庫量

    participation_level: float                       # §3.4。participant/non-participant で
                                                     # 唯一差が付く状態変数
    maker_stage: MakerStage
    sharing_tendency: float
    imitation_tendency: float
    helping_norm: float

    known_agents: set[str]                           # 一般社会接触の近傍（§7.2）
    cultural_peers: set[str]                         # cultural peer-learning edge の近傍（§7.2）
                                                     # known_agents の部分集合
    trust: dict[str, float]
    # 決定（trust 最終仕様）: M1 では trust は**固定値**。更新式を実装しない。
    # peer learning ON/OFF が trust dynamics まで変えてしまうと、
    # 操作した因子が2つになる。M2 以降で必要性を再検討する。
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
    self_assets: dict[str, bool | int]
    self_time_budget: float
    self_materials: dict[str, float]
    self_maker_stage: MakerStage
    self_methods: tuple[Method, ...]

    # 自分の性向。§5.1 の効用計算が参照するため必須
    self_participation_level: float
    self_sharing_tendency: float
    self_imitation_tendency: float
    self_helping_norm: float

    project_catalog: tuple[Project, ...]              # 全Agent共通。世界の状態ではない

    neighbors: tuple[str, ...]                        # known_agents のみ（一般社会接触）
    cultural_peers: tuple[str, ...]                   # neighbors の部分集合（§7.2）
    perceived_neighbor_skills: dict[str, dict[str, PerceivedSkill]]
    trust: dict[str, float]

    inbox: tuple                                      # 今step 到着したメッセージ
    recent_events: tuple

    # M3 で追加: observable_market（観測可能な市場情報のみ）
```

`build_observation(world, agent) -> Observation` が唯一の変換点。ここ以外で Agent が World を参照するコードを書いてはならない。

**`peer_learning_enabled` を Observation に入れてはならない。** これは世界の物理法則であって、Agent が知覚し戦略を変える対象ではない（§8）。

`is_participant` も Observation に入れない。Agent が自分の「区分」を知って戦略を変えるのではなく、`participation_level` という連続量として効用に効く。

### 3.4 participant / non-participant の定義（決定 X3）

母集団 N=40 を **participant 30 / non-participant 10** で構成する。

#### 3.4.1 差を付けないもの — 一切の初期差を作らない

以下は **participant / non-participant で完全に同一の分布**から生成する。

| 項目 | 扱い |
|---|---|
| `skills`（6技能） | 同一分布 |
| `assets` | 同一分布 |
| `materials` | 同一（全Agent一律の初期在庫） |
| `sharing_tendency` | 同一分布 |
| `imitation_tendency` | 同一分布 |
| `helping_norm` | 同一分布 |
| `time_budget` | 全Agent同一（決定 X2-7） |

`money` は M1 に存在しない（決定 D8）。**Agent 初期状態にも config にも復活させない。**

#### 3.4.2 差を付けるもの — 2点のみ

| | participant | non-participant |
|---|---|---|
| `participation_level` | config の分布から生成。**低participation層を含む** | ≒ 0 |
| cultural peer-learning network | **参加資格あり** | 参加しない |

`participation_level` は「文化活動へどれだけ時間と関心を向けているか」であり、能力でも善意でもない。

#### 3.4.3 non-participant を孤立ノードにしてはならない

**non-participant も一般的な社会接触を持つ。** `known_agents` は空にしない。遮断するのは cultural Method transfer と peer scaffolding だけである。

**理由**: participant と non-participant の差を「participation の差」と「ネットワーク孤立の差」の**二重差**にすると、文化参加の効果と単純な社会接触の効果を分離できなくなる。これは条件C/Dを `nx.empty_graph()` にしてはならない理由（§7）と同じ構造の誤りである。

一般社会接触と cultural peer-learning edge の分離は §7.2 で扱う。

#### 3.4.4 研究上の注記 — 誤読を防ぐための明示

- **participant は「初期技能が高い人」を意味しない。** 初期 `skills` の分布は同一である
- **participant は「利他的な人」を意味しない。** `sharing_tendency` / `helping_norm` の分布は同一である
- `skills` / `assets` / `materials` / behavioral traits の初期分布はすべて同一である
- participation による能力形成が起きるかどうかは、**シミュレーション中に検証される対象**であって前提ではない（SPEC §6）
- **participant / non-participant の差は M1 の主要な因果対照ではない。** 主要対照はあくまで **A/B/C/D（topology × peer learning）の2×2完全要因計画**である
- **この比較から「文化参加の因果効果」を直接主張してはならない。** non-participant は M1 では **context population**（文化圏の外側に人がいる、という背景）として扱う
- **30 / 10 という比率は現実の人口比を表す実証値ではない。** M1 の仮置き構成である。将来的に participant 比率自体が感度分析または実データ校正の対象になりうる

#### 3.4.5 Metrics の併記（§10.1）

すべての集計 Metrics を **`all_agents` と `participants_only` の2系列で併記**する。`nonparticipants_only` も補助指標として保存してよいが、**主要仮説（H1/H2）の判定指標にはしない**。

判定指標を participants_only に置くのは、H1/H2 が「文化圏内部で相互学習構造が能力再生産を変えるか」を問うているためである。all_agents 系列は、context population を含めたときに効果が希釈されるかを見る補助情報として残す。

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

    # (2b) validate — time_budget 内に収まる Intent だけを通す（§5.2）
    #      予算超過以降の Intent は却下し、rejected_intents へ記録する
    intents = {aid: validate(world.agents[aid], intents[aid], world.cfg)
               for aid in world.agents}

    # (3) act — Intent を収集するのみ。世界は変えない
    order = world.rng.permutation(sorted(world.agents))   # seed 固定で再現可能

    # (4) resolve — 一括解決。行動順序の有利不利を排除
    #     make を実行した Project の primary_skill は、成否を問わず
    #     practiced_this_step へ追加される（§6.3）
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

重み `w_*` はすべて config。

**重要**: この効用関数は「Agent がループを回すため」に設計されていない。各 Agent は自分の局所状態から自分の効用を最大化するだけであり、ループは結果としてマクロに現れる（SPEC §5 の要求）。

**効用関数は4条件で完全に同一である。** 条件によって重みや選択肢を変えてはならない。C/D の Agent も `ask` と `share` を通常どおり選択する（§8）。

### 5.2 Validator — 時間・実現可能性の判定はコード側（決定 X1）

`decide()` は「やりたいこと」を順に並べた `list[Intent]` を返すだけで、**時間予算も実現可能性も自分では判定しない**。判定は Validator が行う。

```python
# src/agents/decision.py
def validate(agent, intents: list[Intent], cfg) -> list[Intent]:
    """time_budget 内で順に Intent を評価し、予算を超えた Intent 以降は却下する。
    却下された Intent は agent.rejected_intents へ記録し、学習信号として残す
    （`docs/REVIEW.md` I16）。
    時間コストは cfg.action_time_cost からのみ引く。Project.time_cost は存在しない（決定 Y3）。"""
    remaining, accepted = agent.time_budget, []
    for intent in intents[:cfg.time.max_actions_per_step]:
        cost = cfg.action_time_cost[intent.action.value]
        if cost > remaining or not is_feasible(agent, intent, cfg):
            agent.rejected_intents.append((intent, reason_code))
            break                      # 予算超過以降はすべて却下
        remaining -= cost
        accepted.append(intent)
    return accepted
```

`is_feasible()` が判定するもの: 材料の充足、必要設備の保有、対象 Agent が近傍にいるか、対象 Method を保有しているか。**Agent（M2 以降は LLM）はこれらを宣言できない。**

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
    return clamp(sigmoid(raw / cfg.temperature), 0.02, 0.98)
```

`temperature` は `base.yaml` の `learning` ブロックに置く。**コードにハードコードしない。** 値によって成否分布の鋭さが変わるため、config で追跡可能にしておく必要がある。

`reduction` の項が **Capability Reproduction Loop を閉じる唯一の環**である。

- **self-scaffolding**（全条件で有効）: 自分が発見した Method が、自分の成功確率を上げる
- **social scaffolding**（A/B のみ）: 他Agentから受け取った Method が、自分の成功確率を上げる

C/D では peer 由来 Method が Library に入らないため（§8）、`methods` に peer 由来のものは存在しない。**この関数自体に条件分岐を書いてはならない。** 分岐は §8 の受容ゲート1箇所のみに置く。

### 6.2 技能獲得（収穫逓減）

```python
def skill_gain(current_skill: float, success: bool, cfg) -> float:
    # 決定 Y2: config が持つのは learn_rate_success と learn_rate_failure_ratio。
    #          learn_rate_failure は config に直接書かず、必ずここで導出する。
    learn_rate_failure = cfg.learn_rate_success * cfg.learn_rate_failure_ratio
    base = cfg.learn_rate_success if success else learn_rate_failure
    return base * (1.0 - current_skill)      # 上限 1.0 に漸近
```

**導出（決定 Y2、これを正とする）:**

```
learn_rate_failure = learn_rate_success × learn_rate_failure_ratio
既定 learn_rate_failure_ratio = 0.25
```

`learn_rate_failure` を config に直接書いてはならない。二重定義になり、感度分析で `L` を振ったときに比率が崩れる。

失敗からも学ぶ（`learn_rate_failure < learn_rate_success`）。これにより初期段階の完全停滞を防ぐ。

**仮置き**: `learn_rate_success = L = 0.04` → `learn_rate_failure = 0.01`

`L` は感度分析の因子である（§11）。比率 0.25 は固定する。

### 6.3 技能減衰 — H1 を自明化させないための必須要素

```python
def decay_skills(world) -> None:
    """練習しなかった技能は減衰する。
    【理由】減衰がないと技能は単調増加し、H1『Maker人口は増加するか』が
    構成上自明になる。減衰があって初めて『学習の流入が減衰を上回るか』
    という非自明な問いになる。"""
    for agent in world.agents.values():
        for skill in world.ids.skill_ids:
            if skill not in agent.practiced_this_step:
                agent.skills[skill] *= (1.0 - world.cfg.decay_rate)
```

#### make と技能維持 — 確定仕様

`practiced_this_step` へ追加されるのは以下の2つである。

| 行動 | `practiced_this_step` への追加 |
|---|---|
| `practice` を実行した skill | 追加する |
| `make` を実行した Project の `primary_skill` | **成功・失敗を問わず追加する** |

**`make` は成否にかかわらず減衰を免除する。** 制作に失敗しても技能を使用していることに変わりはなく、同じ step で「使ったのに腕が鈍る」のは機構として不自然である。また、成功時のみ免除すると、減衰が「技能の使用有無」ではなく「成功率」に連動してしまい、`success_probability` が二重に効く。

`make` の失敗は `skill_gain(success=False)` による**小さな正の獲得**として扱われ、減衰によるペナルティは受けない。

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

### 7.2 エッジの二層構造 — 一般社会接触と cultural peer-learning edge

§3.4.3 の要求（non-participant を孤立ノードにしない）を満たすため、エッジを概念上2層に分ける。**グラフ object は1つで、層は属性で表現する。**

| 層 | 対応フィールド | 定義 | 何を運ぶか |
|---|---|---|---|
| **一般社会接触** | `Agent.known_agents` | base graph の全エッジ。**全Agent（non-participant を含む）が持つ** | `observe` / `ask` / `share` の到達範囲、`perceived_skills` の更新 |
| **cultural peer-learning edge** | `Agent.cultural_peers` | 両端が participant であるエッジのみ。`known_agents` の部分集合 | Method transfer と peer scaffolding |

```python
def build_edge_layers(graph, agents) -> None:
    """cultural_peers は known_agents の部分集合。エッジ自体は削除しない。"""
    for a in agents.values():
        a.known_agents = set(graph.neighbors(a.id))
        a.cultural_peers = {n for n in a.known_agents
                            if a.is_participant and agents[n].is_participant}
```

**non-participant の `known_agents` は空にならない。** 彼らは観測され、尋ねられ、共有の宛先にもなる。運ばれないのは Method だけである。

**この分離が必要な理由**: participant と non-participant の差を「participation の差」と「ネットワーク孤立の差」の二重差にすると、文化参加の効果と単純な社会接触の効果が交絡する（§3.4.3）。C/D を `empty_graph` にしない理由とまったく同じ構造である。

**topology のリワイヤリングは一般社会接触層に対して行う。** `cultural_peers` は base graph 確定後に導出されるため、A/C と B/D のペアリング（§7）はそのまま保たれる。

---

## 8. peer learning の遮断点 — 分岐はここ1箇所のみ

SPEC §19 が定める C/D の意味は「ネットワークを除去した世界」ではなく、

> 人は社会的につながっているが、そのつながりが制作能力の再生産経路として機能しない世界

である。したがって遮断するのは **peer Method transfer だけ**である。

### 8.1 全条件で有効なもの（C/D でも維持）

`practice` / `make` / **Method の自己発見** / **self-scaffolding** / `observe` / `ask` / `share` / メッセージ配送 / `perceived_skills` の更新 / 近傍関係そのもの。

`ask` は C/D でも実行され、相手の技能に関する信念（`perceived_skills`）を更新する。**更新されないのは Method Library だけである。**

> **trust は M1 では固定値であり、`ask` でも更新されない。**
> 以前の「`ask` によって `perceived_skills` と `trust` を更新する」という記述は**廃止した**。
> peer learning の ON/OFF が trust dynamics まで変えてしまうと、操作した因子が2つになり、A−C の差を peer 経路だけに帰属できなくなる。trust dynamics の必要性は M2 以降で再検討する。

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
    if method.source_agent_id not in agent.cultural_peers:
        return False                      # ← non-participant はここで止まる（§7.2）
    if method.project_type in {m.project_type for m in agent.methods.values()}:
        return False
    # trust は M1 では固定値。ここで参照はするが、更新はどこでも行わない
    p = agent.imitation_tendency * agent.trust.get(method.source_agent_id, 0.0)
    return rng.random() < p
```

ゲートは2段になるが、**どちらも「受容するか」の判定であり、この関数の外に分岐は出さない**。`cfg.peer_learning_enabled` が条件（A/B/C/D）の操作、`cultural_peers` が母集団構成（participant / non-participant）の表現である。両者は独立しており、C/D では participant 同士でも Method は渡らない。

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
        for m in world.ids.material_ids:
            agent.materials[m] = min(cfg.inventory_cap[m],
                                     agent.materials[m] + cfg.replenish_rate[m])
```

**決定 Y1: `inventory_cap` と `replenish_rate` は material ID ごとの dict である。** config でもスカラーではなく material ID をキーとする dict で書く。材料ごとに希少性を変えられる余地を残しつつ、M1 の既定値は全材料で同一にする。全条件で同一であることは変わらない。

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

### 10.2.1 集計母集団の併記（決定 X3）

**すべての集計 Metrics を2系列で併記する。**

| 系列 | 対象 | 用途 |
|---|---|---|
| `all_agents` | N=40 全員 | context population を含めたときの希釈を見る補助情報 |
| **`participants_only`** | participant 30名 | **H1 / H2 の主要判定指標** |
| `nonparticipants_only` | non-participant 10名 | 補助指標。**主要仮説の判定には使わない** |

`timeseries.csv` は `metric_name` × `population` の形で3系列を保存する。

**主要判定を `participants_only` に置く理由**: H1/H2 は「文化圏内部で相互学習構造が能力再生産を変えるか」を問うている。non-participant は cultural peer-learning edge を持たないため、条件 A/B/C/D の操作がそもそも到達しない。彼らを分母に含めた指標を主要判定に使うと、効果量が母集団構成比（30/10）という**仮置きの数字**に依存してしまう。

**それでも `all_agents` を捨てない理由**: 「文化圏の内側では差が出たが社会全体では無視できる大きさだった」という結果も、報告すべき知見だからである。

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

減衰の導入（決定 D6）は、H1 を自明化させないための設計判断である。しかし減衰自体がパラメータであり、**減衰の値によって結論が変わるなら、その結論は減衰の設定の産物である**。`D = 0` を併走させることで、「減衰なしでも成立するか / 減衰がある場合にのみ成立するか」を明示的に報告できる。これは §15.2 の Anti-Goal 回避と同じ趣旨である。

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
| `tests/test_no_answer_leak.py` | **§3.0.1 で定義した Agent-facing strings のみ**に禁止語が含まれない | T2 |
| `tests/test_agent_init.py` | **§15.1 の初期条件7項目を検証**（Consumer ≥ 90%、participation の分散、下位20%の低participation層、participant/non-participant の分布同一性、pre-network 完了、4条件一致、time_budget 一律） | T13 |
| `tests/test_locality.py` | `Observation` に World 参照・他Agent真値・`peer_learning_enabled` が含まれない | T3 |
| `tests/test_conservation.py` | 材料が負にならない・`inventory_cap` を超えない | T4 |
| `tests/test_condition_invariance.py` | **A/B/C/D の4条件で pre-network 初期Agent状態・Projectカタログが完全一致**（決定 Y6） | T5 |
| `tests/test_stage_transition.py` | 固定シナリオで Consumer→Customizer→Maker が発火 | T6 |
| `tests/test_learning_causality.py` | share 無効化で knowledge_diffusion が 0 になる | T7 |
| `tests/test_metrics.py` | 手計算フィクスチャと算出値が一致（追加4指標を含む） | T8 |
| `tests/test_network_pairing.py` | **A と C のエッジ集合が完全一致／B と D が完全一致／A と B の次数列とエッジ数が一致** | T9 |
| `tests/test_peer_learning_gate.py` | **C/D で peer 由来 Method が 0 かつ observe/ask/share の実行回数 > 0** | T11 |
| `tests/test_material_replenishment.py` | **補充設定が4条件で同一、在庫が cap を超えない** | T12 |
| `tests/test_smoke.py` | 20 seed × 4条件が例外なく完走 | T10 |

`test_condition_invariance.py` は、4条件それぞれで World を構築し、**ネットワーク構築前の Agent 状態**の SHA-256 が4つとも一致することを検証する。一致しなければ、条件分岐が Agent 初期化へ漏れている。

**決定 Y6: `agent_initial_states_sha256` は pre-network 状態から算出する。** ハッシュ対象に **network 由来フィールド（`known_agents` / `cultural_peers` / `trust` / `perceived_skills`）を含めない**。post-network 状態でハッシュを取ると、A と B は近傍が違うため必ず不一致になり、T5 が成立しなくなる。`metadata.json` に記録するのも pre-network のハッシュである。

**`trust` を除外する理由**: M1 では固定値だが、初期化時に近傍ごとの dict として展開されるため、近傍構造に依存する。値そのものは条件不変でも、キー集合が条件によって変わる。

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
  # 決定 X4: cosplay 由来の識別子は使わない
  n_participant_agents: 30
  n_nonparticipant_agents: 10   # 合計 N=40 固定（決定 D7。参入・退出なし）
                                # 30/10 は仮置き構成。現実の人口比ではない（§3.4.4）
  n_skills: 6                   # -> skill_0 .. skill_5
  n_materials: 5                # -> mat_0 .. mat_4
  n_assets: 4                   # -> asset_0 .. asset_3
  n_project_types: 6            # -> proj_0 .. proj_5
                                # 決定 Y4: ID 一覧はここから生成する。
                                # types.py に定数を二重定義しない

network:
  mean_degree: 6
  rewire_p: 0.1
  assortativity: 0.3
  swap_multiplier: 10           # rewired の double_edge_swap 回数 = 10 × エッジ数

agent_init:                     # 決定 X2。participant / non-participant で同一（§3.4.1）
  skills:                       # 6技能ごとに個別指定（同一値でも明示的に並べる）
    skill_0: {dist: beta, a: 1.5, b: 8.0}
    skill_1: {dist: beta, a: 1.5, b: 8.0}
    skill_2: {dist: beta, a: 1.2, b: 9.0}
    skill_3: {dist: beta, a: 1.2, b: 9.0}
    skill_4: {dist: beta, a: 1.0, b: 10.0}
    skill_5: {dist: beta, a: 1.5, b: 8.0}
  assets:                       # 設備ごとの保有確率
    asset_0: {dist: bernoulli, p: 0.35}
    asset_1: {dist: bernoulli, p: 0.15}
    asset_2: {dist: categorical, values: [0, 1, 2, 3],   # tools は 0-3 の離散分布
              probs: [0.30, 0.40, 0.20, 0.10]}
    asset_3: {dist: bernoulli, p: 0.25}
  traits:
    participation_level:        # participant のみこの分布から生成
      dist: beta                # non-participant は §3.4.2 により ≒ 0
      a: 2.0
      b: 3.0
    nonparticipant_participation_level: 0.0
    sharing_tendency:    {dist: beta, a: 2.5, b: 2.5}
    imitation_tendency:  {dist: beta, a: 2.5, b: 2.5}
    helping_norm:        {dist: beta, a: 2.5, b: 2.5}
  trust_fixed: 0.5              # M1 では固定値。更新式は実装しない
  time_budget: 3.0              # 決定 X2-7: 全Agent同一

materials:                      # 決定 D13。条件別 YAML で上書き禁止
  initial:                      # 決定 Y1: すべて material ID ごとの dict
    {mat_0: 5.0, mat_1: 5.0, mat_2: 5.0, mat_3: 5.0, mat_4: 5.0}
  inventory_cap:
    {mat_0: 10.0, mat_1: 10.0, mat_2: 10.0, mat_3: 10.0, mat_4: 10.0}
  replenish_rate:               # per step
    {mat_0: 1.0, mat_1: 1.0, mat_2: 1.0, mat_3: 1.0, mat_4: 1.0}

learning:
  learn_rate_success: 0.04      # = L。感度分析の因子（§11）
  learn_rate_failure_ratio: 0.25  # 決定 Y2: learn_rate_failure = L × ratio。
                                  # learn_rate_failure を直接書かない
  decay_rate: 0.005             # = D = L / 8。感度分析の因子（§11）
  base_reduction: 0.25          # Method 1件あたりの実効難度低減
  method_discovery_prob: 0.15
  asset_bonus: 0.2
  temperature: 0.15             # success_probability の sigmoid 温度。
                                # コードにハードコードしない

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

action_time_cost:               # 決定 Y3: make の時間コストはここだけ。
  observe: 0.1                  # Project.time_cost は存在しない
  ask: 0.2
  practice: 0.5
  make: 1.0
  share: 0.2
  idle: 0.0                     # 決定 Y5

time:
  max_actions_per_step: 6       # time_budget は agent_init.time_budget（決定 X2-7）
```

**`consume` は config に現れない**（決定 Y5）。SPEC §12 では将来候補として列挙されているが、M1 では効用も時間コストも定義せず、`ActionType` からも削除している。

### 14.1.1 初期化パラメータの校正について（決定 X2）

`agent_init` の分布パラメータは **§15.1 の初期条件（Consumer ≥ 90% 等）を満たすように選ぶ**。この校正には次の制約を課す。

- **本実験の結果を見て調整してはならない。**
- 校正は**本実験とは独立した固定 seed、または解析的確認により一度だけ**行う
- 採用した分布パラメータは**実験開始前に固定し、事前登録する**
- 校正に使った seed は、本実験の seed 集合（§12）と重複させない

これは SPEC §30 Anti-Goal「結果が出るように後からパラメータを恣意的調整する」を、初期化分布についても適用したものである。**初期条件の校正と、仮説に関わるパラメータの調整は、明確に別物として扱う。**

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
| C14 | **Agent 初期化テスト（T13）が通る**（§15.1 の7要件） |
| C15 | **Metrics が `all_agents` / `participants_only` / `nonparticipants_only` の3系列で出力される**（§10.2.1） |

### 15.1 Agent 初期化の最低要件（決定 X2）— `tests/test_agent_init.py` が検証

| # | 要件 | 検証方法 |
|---|---|---|
| 1 | **初期状態で Consumer が全Agentの 90% 以上** | `maker_stage_distribution` の初期値 |
| 2 | participant の `participation_level` が**分散を持つ**（全員同値でない） | 標準偏差 > 閾値 |
| 3 | participant 下位20% に**低participation層が存在する** | 20パーセンタイル値 < 閾値 |
| 4 | `skills` / `assets` / `materials` / behavioral traits が **participant と non-participant で同一分布** | 生成元の config キーが同一であることを構造的に検証（統計検定ではなく、同じ分布オブジェクトから引いていることを保証する） |
| 5 | **Agent 生成が network 生成前に完了している** | 生成順序の構造的検証 |
| 6 | **A/B/C/D で pre-network initial state が完全一致** | `agent_initial_states_sha256` の一致（T5 と共通、決定 Y6） |
| 7 | `time_budget` が **M1 では全Agent同一** | 全Agentで同値 |

#### 「Consumer 90% 以上」の位置づけ — 誤読を防ぐための明示

**これは現実のコスプレ人口の構成についての主張ではない。** M1 で `Consumer → Customizer → Maker` の stage transition を観測するための**実験初期条件**である。

全員が最初から Maker であれば遷移は観測できず、M1 の目標（SPEC §28「特に Consumer→Customizer→Maker の遷移」）が達成できない。天井効果を避けるために低い位置から始める、というだけの技術的要請である。

この数値を根拠に「コスプレ参加者の大半は消費者である」といった主張をしてはならない。

### 15.2 完了条件に**含めない**もの — 明示

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
| S1 | `common/types.py`（`IdRegistry` / `Intent` / `Project` / `Method` 等）, `common/rng.py`, `common/io.py`, config ローダ | 型が定義され、config から ID 一覧が生成され、seed の子ストリーム生成が動く |
| S2 | `agents/agent.py` + 初期化 + `test_agent_init` + `test_condition_invariance` | §15.1 の7要件を満たし、同一seedから4条件のAgentが pre-network で完全一致で生成される |
| S3 | `culture/network.py`（base graph + `build_edge_layers`）+ `test_network_pairing` | A/C・B/D の完全ペアリング、次数保存、`cultural_peers ⊆ known_agents` が検証される |
| S4 | `agents/observation.py` + `test_locality` | Observation に World 参照・`peer_learning_enabled`・`is_participant` がないことが保証される |
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

### 17.1 S1〜S4 の実装前に確定した事項（2026-08-15 査読）

| # | 事項 | 決定 | 反映先 |
|---|---|---|---|
| **X1** | `Intent` 型 | **確定**。`action` / `target_agent_id` / `target_project_id` / `target_skill_id` / `target_method_id` / `reason` のみ。**数量フィールドを持たせない**（生産数量・金額・消費時間量を含めない）。`decide() -> list[Intent]`、Validator が time_budget 内で順に評価し予算超過以降を却下。M2 で LLM structured output schema として再利用 | §3.1、§5.2 |
| **X2** | Agent 初期化 | **`base.yaml` に `agent_init` を追加**し全分布パラメータを config 化。最低要件7項目（§15.1）。**初期化分布を本実験結果を見て調整してはならない**。校正は独立した固定seedまたは解析的確認で一度だけ行い実験前に固定 | §14.1、§14.1.1、§15.1 |
| **X3** | participant / non-participant | **技能・設備・材料・向社会性に一切差を付けない**。差は `participation_level` と cultural peer-learning network の参加資格のみ。**non-participant を孤立ノードにしない**。M1 の主要因果対照ではない（context population） | §3.4、§7.2、§10.2.1 |
| **X4** | 識別子の中立化 | `n_cosplay_agents` → **`n_participant_agents`**、`n_general_agents` → **`n_nonparticipant_agents`**。T2 の対象は **Agent-facing strings のみ**に限定 | §3.0.1、§14.1 |
| **Y1** | 材料パラメータ | `inventory_cap` / `replenish_rate` を **material ID ごとの dict に統一**。全条件で同一 | §9.1、§14.1 |
| **Y2** | 学習率 | **`learn_rate_failure_ratio` を正とする**。`learn_rate_failure = learn_rate_success × ratio`、既定 0.25。config に `learn_rate_failure` を直接書かない | §6.2、§14.1 |
| **Y3** | make の時間コスト | **`action_time_cost.make` へ一本化**。`Project.time_cost` は**削除**。Project 差は `base_difficulty` 等で表現 | §3.1、§5.2、§14.1 |
| **Y4** | ID 定数 | `SKILL_NAMES` / `ASSET_NAMES` / `MATERIAL_NAMES` / `PROJECT_IDS` を **Python 定数として二重定義しない**。config を single source of truth とし、ロード時に `IdRegistry` を生成 | §3.1、§14.1 |
| **Y5** | `ActionType.CONSUME` | **M1 から削除**。SPEC §12 では将来候補だが M1 では使用しない。`idle` の `action_time_cost = 0.0` | §3.1、§14.1 |
| **Y6** | 初期状態ハッシュ | `agent_initial_states_sha256` は **pre-network 状態**から算出。network 由来フィールド（`known_agents` / `cultural_peers` / `trust` / `perceived_skills`）をハッシュ対象に含めない。A/B/C/D で同一であることをテスト | §13、§10.3 |
| **trust** | trust の扱い | **M1 では固定値。更新式を実装しない。** 「`ask` によって trust を更新する」という旧記述は**全文書で廃止**。`accept_peer_method()` は固定 trust 値を参照してよい。dynamics は M2 以降で再検討 | §3.2、§8.1、§8.3 |
| **temperature** | `success_probability` の温度 | **`base.yaml` の `learning` ブロックへ追加**。コードにハードコードしない | §6.1、§14.1 |
| **make と技能維持** | 減衰免除 | **成功・失敗を問わず**、`make` を実行した Project の `primary_skill` を `practiced_this_step` へ追加し、その step の減衰対象から除外する | §6.3 |

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
