"""Observation — 神の視点の唯一の遮断点（docs/DESIGN_M1.md §3.3）。

【設計上の要点】このクラスに World や他Agentの実体を入れないことが、
SPEC §14 Information Locality の構造的な担保になる。
tests/test_locality.py がこれを機械的に検証する。

Observation に入れてはならないもの:
  - World への参照、他Agentの真値
  - peer_learning_enabled（世界の物理法則であり、Agent が知覚し戦略を変える対象ではない）
  - is_participant（区分ではなく participation_level という連続量として効用に効く）
  - cultural_peers（決定 Z2。M1 の決定ルールが参照せず、non-participant では
    常に空集合になるため区分が漏洩する）
"""

from __future__ import annotations

from dataclasses import dataclass

from src.common.types import MakerStage, Method, PerceivedSkill, Project

# tests/test_locality.py が参照する禁止フィールド名（構造で担保する）
FORBIDDEN_OBSERVATION_FIELDS = frozenset(
    {
        "world",
        "agents",
        "graph",
        "cfg",
        "peer_learning_enabled",
        "is_participant",
        "cultural_peers",
    }
)


@dataclass(frozen=True)
class Observation:
    """decide() が受け取れる唯一の入力。World への参照を含まない。"""

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

    project_catalog: tuple[Project, ...]

    neighbors: tuple[str, ...]  # known_agents のみ（一般社会接触）
    perceived_neighbor_skills: dict[str, dict[str, PerceivedSkill]]
    trust: dict[str, float]

    inbox: tuple
    recent_events: tuple

    # P0修正（M3）: 近傍が出した提案。(proposer_id, project_id) の組。
    # known_agents に含まれる Agent の提案のみを載せる。global proposal list は渡さない。
    # 蓄積相では常に空（build_observation に proposals を渡さないため）。
    # デフォルト付きのため、必ず全ての非デフォルトフィールドより後ろに置くこと。
    neighbor_proposals: tuple[tuple[str, str], ...] = ()

    # M3 で追加: observable_market（観測可能な市場情報のみ）


def build_observation(world, agent, proposals: dict[str, str] | None = None) -> Observation:
    """World -> Observation の唯一の変換点。

    ここ以外で Agent が World を参照するコードを書いてはならない。

    proposals は {proposer_id: project_id} の全体辞書。**ここで近傍に絞り込む。**
    絞り込みをこの1箇所に集約するのは、build_observation が神の視点の唯一の
    遮断点だからである（§3.3）。呼び出し側で絞ると漏洩経路が分散する。
    """
    visible_proposals: tuple[tuple[str, str], ...] = ()
    if proposals:
        visible_proposals = tuple(
            (pid, proj)
            for pid, proj in sorted(proposals.items())
            if pid in agent.known_agents and pid != agent.id
        )
    return Observation(
        step=world.step,
        self_id=agent.id,
        self_skills=dict(agent.skills),
        self_assets=dict(agent.assets),
        self_time_budget=agent.time_budget,
        self_materials=dict(agent.materials),
        self_maker_stage=agent.maker_stage,
        self_methods=tuple(agent.methods.values()),
        self_participation_level=agent.participation_level,
        self_sharing_tendency=agent.sharing_tendency,
        self_imitation_tendency=agent.imitation_tendency,
        self_helping_norm=agent.helping_norm,
        project_catalog=world.projects,
        neighbors=tuple(sorted(agent.known_agents)),
        perceived_neighbor_skills={
            k: dict(v) for k, v in agent.perceived_skills.items()
        },
        trust=dict(agent.trust),
        inbox=tuple(agent.inbox),
        recent_events=tuple(agent.recent_events),
        neighbor_proposals=visible_proposals,
    )
