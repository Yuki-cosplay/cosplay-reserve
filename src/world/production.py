"""制作の成否判定と設備保有判定（docs/DESIGN_M1.md §6.1 / §6.4）。"""

from __future__ import annotations

import math

from src.agents.agent import Agent
from src.common.types import Method, Project


def _owns(agent: Agent, asset_id: str, cfg: dict) -> bool:
    """設備の保有判定の唯一の実装（決定 U2 / W2）。

    count_assets() と has_required_asset() の両方がこれを呼ぶ。
    2箇所で判定が食い違わないようにするため。
    isinstance ではなく config の type 宣言を参照する。
    """
    v = agent.assets[asset_id]
    if cfg["agent_init"]["assets"][asset_id]["type"] == "bernoulli":
        return v is True
    return v >= 1  # categorical: 0 は未保有


def has_required_asset(agent: Agent, project: Project, cfg: dict) -> bool:
    if project.required_asset is None:
        return True
    return _owns(agent, project.required_asset, cfg)


def has_materials(agent: Agent, project: Project) -> bool:
    return all(agent.materials.get(m, 0.0) >= need for m, need in project.material_cost.items())


def scaffolding_reduction(project: Project, methods: tuple[Method, ...]) -> float:
    """該当 Method を持っていると実効難度が下がる。ループの閉じ目（§6.1）。

    self-scaffolding（全条件）と social scaffolding（A/B のみ）を区別しない。
    C/D では peer 由来 Method が Library に入らないため（§8）、
    この関数に条件分岐を書く必要がない。
    """
    return max(
        (m.difficulty_reduction for m in methods if m.project_id == project.project_id),
        default=0.0,
    )


def success_probability(agent: Agent, project: Project, cfg: dict) -> float:
    learning = cfg["learning"]
    skill = agent.skills[project.primary_skill]
    asset_bonus = learning["asset_bonus"] if has_required_asset(agent, project, cfg) else 0.0

    reduction = scaffolding_reduction(project, tuple(agent.methods.values()))
    effective_difficulty = project.base_difficulty * (1.0 - reduction)

    raw = skill + asset_bonus - effective_difficulty
    p = 1.0 / (1.0 + math.exp(-raw / learning["temperature"]))
    return min(max(p, 0.02), 0.98)


def consume_materials(agent: Agent, project: Project) -> None:
    for m, need in project.material_cost.items():
        agent.materials[m] = max(0.0, agent.materials[m] - need)
