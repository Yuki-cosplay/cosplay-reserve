"""M1 の共通型定義（docs/DESIGN_M1.md §3.1）。

【重要】ID 一覧の定数をこのモジュールに置かない（決定 Y4）。
SKILL_NAMES のようなタプルをハードコードすると config と二重定義になり、
config を変えたのにコード側が古いまま、という不整合が静かに発生する。
ID は IdRegistry が config から生成する。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


@dataclass(frozen=True)
class IdRegistry:
    """config から生成される ID 一覧（決定 Y4）。

    skill / material / asset は個数指定から連番を生成し、
    project だけはカタログから導出する（決定 P4）。

    非対称の理由: skill / material / asset は中身を持たない純粋な ID であり、
    個数さえ決まれば ID を作れる。一方 project は primary_skill / base_difficulty
    などの中身を伴う実体であり、カタログに固定値で列挙されている（決定 W1）。
    件数を別途宣言すると、カタログの長さと個数指定という2つの真実の源ができる。
    """

    skill_ids: tuple[str, ...]
    material_ids: tuple[str, ...]
    asset_ids: tuple[str, ...]
    project_ids: tuple[str, ...]

    @classmethod
    def from_config(cls, cfg: dict) -> "IdRegistry":
        def gen(prefix: str, n: int) -> tuple[str, ...]:
            return tuple(f"{prefix}_{i}" for i in range(n))

        world = cfg["world"]
        return cls(
            skill_ids=gen("skill", world["n_skills"]),
            material_ids=gen("mat", world["n_materials"]),
            asset_ids=gen("asset", world["n_assets"]),
            project_ids=tuple(p["project_id"] for p in cfg["projects"]),
        )


@dataclass(frozen=True)
class AttributeVector:
    """材料・製品・要求仕様を共通の空間で表現する。名称も意味も持たない。

    M1 では需要がないため値を使わない。全属性 0.0 とする（決定 W1、§14.2.2）。
    値を入れると根拠のない数字が実験記録に残る。M3 で RequiredItem と
    対にして初めて意味を持つ。

    【重要】属性に意味を持つ名前を付けない。対応表は SPEC.md §18 にのみ置く。
    """

    attr_0: float = 0.0
    attr_1: float = 0.0
    attr_2: float = 0.0
    attr_3: float = 0.0
    attr_4: float = 0.0
    attr_5: float = 0.0
    attr_6: float = 0.0

    @classmethod
    def from_dict(cls, d: dict) -> "AttributeVector":
        return cls(**{k: float(v) for k, v in d.items()})


@dataclass(frozen=True)
class Project:
    """制作対象の仕様。base.yaml に固定値で記述する（決定 W1）。分布から生成しない。

    決定 Y3: time_cost は持たない。make の時間コストは action_time_cost.make に
    一本化する。Project 間の差は base_difficulty / required_asset / material_cost
    で表現する。
    """

    project_id: str
    primary_skill: str
    base_difficulty: float
    required_asset: str | None
    material_cost: dict[str, float]
    target_profile: AttributeVector

    @classmethod
    def from_dict(cls, d: dict) -> "Project":
        return cls(
            project_id=d["project_id"],
            primary_skill=d["primary_skill"],
            base_difficulty=float(d["base_difficulty"]),
            required_asset=d["required_asset"],
            material_cost={k: float(v) for k, v in d["material_cost"].items()},
            target_profile=AttributeVector.from_dict(d["target_profile"]),
        )


@dataclass(frozen=True)
class Method:
    """共有される手順知識。伝播経路の追跡情報を必ず持つ。

    決定 W6: required_skill_level は M1 では持たない。書き込むだけで誰も
    読まないフィールドがあると、後から読む者が「どこかで使われているはず」と
    誤解する。M2 で必要になった時点で追加する。
    """

    method_id: str
    project_id: str
    primary_skill: str
    difficulty_reduction: float
    origin_agent_id: str
    source_agent_id: str
    origin_step: int
    acquired_step: int
    hop_count: int

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
    列挙されているが、M1 では効用も時間コストも定義されず使用しない。
    """

    OBSERVE = "observe"
    ASK = "ask"
    PRACTICE = "practice"
    MAKE = "make"
    SHARE = "share"
    IDLE = "idle"


@dataclass(frozen=True)
class Intent:
    """Agent が「何をしたいか」だけを表す（決定 X1）。

    【構造的制約】数量フィールドを持たせない（docs/REVIEW.md I21）。
    生産数量・金額・消費時間量・成功可否は一切含めない。
    数量・時間・実現可能性はすべてコード側（Validator と resolve）が決定する。
    これが SPEC §13「LLM decides intent. Code determines feasibility.」の
    型レベルでの担保になる。

    M2 ではこの型をそのまま LLM の structured output schema として再利用する。
    """

    action: ActionType
    target_agent_id: str | None = None
    target_project_id: str | None = None
    target_skill_id: str | None = None
    target_method_id: str | None = None
    reason: str = ""


class RejectionReason(str, Enum):
    """Validator が Intent を却下した理由（決定 V6）。

    rejected_intents に記録し、Metrics で分布を集計する（§10.1）。
    却下が特定の理由に偏っている場合、それ自体が
    「何がボトルネックになっているか」の知見になる。
    """

    TIME_BUDGET_EXCEEDED = "time_budget_exceeded"
    INSUFFICIENT_MATERIAL = "insufficient_material"
    MISSING_ASSET = "missing_asset"
    TARGET_NOT_NEIGHBOR = "target_not_neighbor"
    UNKNOWN_PROJECT = "unknown_project"
    METHOD_NOT_OWNED = "method_not_owned"


@dataclass(frozen=True)
class PerceivedSkill:
    """他Agentの能力は『信念』として持つ。真値は保持しない。"""

    estimate: float
    last_updated_step: int
    observation_count: int

    @property
    def confidence(self) -> float:
        return 1.0 - 0.7**self.observation_count
