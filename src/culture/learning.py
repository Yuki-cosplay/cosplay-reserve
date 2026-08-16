"""技能獲得と減衰（docs/DESIGN_M1.md §6.2 / §6.3）。"""

from __future__ import annotations

from src.agents.agent import Agent


def learn_rate_failure(cfg: dict) -> float:
    """決定 Y2: config が持つのは learn_rate_success と learn_rate_failure_ratio。

    learn_rate_failure を config に直接書かない。二重定義になり、
    感度分析で L を振ったときに比率が崩れる。
    """
    learning = cfg["learning"]
    return learning["learn_rate_success"] * learning["learn_rate_failure_ratio"]


def skill_gain(current_skill: float, success: bool, cfg: dict) -> float:
    """収穫逓減。上限 1.0 に漸近する。失敗からも学ぶ。"""
    base = cfg["learning"]["learn_rate_success"] if success else learn_rate_failure(cfg)
    return base * (1.0 - current_skill)


def apply_skill_gain(agent: Agent, skill_id: str, success: bool, cfg: dict) -> float:
    gain = skill_gain(agent.skills[skill_id], success, cfg)
    agent.skills[skill_id] = min(1.0, agent.skills[skill_id] + gain)
    return gain


def decay_skills(agents: dict[str, Agent], skill_ids: tuple[str, ...], cfg: dict) -> None:
    """練習しなかった技能は減衰する（§6.3）。

    減衰がないと技能は単調増加し、H1『Maker人口は増加するか』が構成上自明になる。
    減衰があって初めて「学習の流入が減衰を上回るか」という非自明な問いになる。

    practiced_this_step には practice した技能に加え、make を実行した Project の
    primary_skill が**成功・失敗を問わず**含まれる。制作に失敗しても技能は
    使用しており、同じ step で「使ったのに腕が鈍る」のは機構として不自然である。
    """
    rate = cfg["learning"]["decay_rate"]
    if rate <= 0.0:
        return
    for agent in agents.values():
        for skill in skill_ids:
            if skill not in agent.practiced_this_step:
                agent.skills[skill] *= 1.0 - rate
