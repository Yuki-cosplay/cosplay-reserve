"""maker_stage の判定（docs/DESIGN_M1.md §6.4）。"""

from __future__ import annotations

from src.agents.agent import Agent
from src.common.types import MakerStage
from src.world.production import _owns


def count_assets(agent: Agent, cfg: dict) -> int:
    """保有している設備の【種類数】（決定 Z5）。

    categorical 型（0-3 の離散値）は 1 以上であれば 1 種類として数える。
    tools を 3 本持っていても、それは1種類である。
    isinstance による型分岐をせず _owns() に集約する（決定 W2 / U2）。
    """
    return sum(1 for aid in agent.assets if _owns(agent, aid, cfg))


def judge_maker_stage(agent: Agent, cfg: dict) -> MakerStage:
    """決定論的関数。閾値は config。

    決定 Z1: 技能による Customizer 判定の経路を削除した。
    SPEC §4 は各段階を「行動の記述」として定義しており、潜在技能の水準ではない。
    技能が高くても一度も手を動かしていない人は Consumer である。

    「履歴」と「現在の能力」の非対称:
      Customizer      = 行動したことがあるか（n_projects >= 1）  -> 不可逆
      Maker 以上      = 現在その能力があるか（max_skill を要求）  -> 可逆
    """
    th = cfg["stage_thresholds"]
    max_skill = max(agent.skills.values())
    breadth = sum(1 for v in agent.skills.values() if v >= th["breadth_threshold"])
    n_projects = len(agent.completed_projects)
    n_assets = count_assets(agent, cfg)

    if (
        max_skill >= th["advanced_skill"]
        and breadth >= th["advanced_breadth"]
        and n_assets >= th["advanced_assets"]
        and n_projects >= th["advanced_projects"]
    ):
        return MakerStage.ADVANCED_MAKER
    if max_skill >= th["maker_skill"] and n_projects >= th["maker_projects"]:
        return MakerStage.MAKER
    if n_projects >= 1:
        return MakerStage.CUSTOMIZER
    return MakerStage.CONSUMER


def update_maker_stages(agents: dict[str, Agent], cfg: dict) -> None:
    for agent in agents.values():
        agent.maker_stage = judge_maker_stage(agent, cfg)
