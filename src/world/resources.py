"""材料の外生補充（docs/DESIGN_M1.md §9、決定 D13 / Y1）。

決定 D8 により money を M1 の因果モデルから外した。材料が初期配分のみの
枯渇性ストックだと (a) 在庫が尽きた時点で make が停止し以降の技能蓄積が
初期配分の関数になる、(b) 枯渇回避のための「貯め込み」挙動を設計に入れたくなる
（非線形性をコードに埋め込むことになる）。

inventory_cap 方式は材料の可用性を全条件で同一の定常的な背景条件にする。
上限があるため貯め込みも発生しない。
"""

from __future__ import annotations

from src.agents.agent import Agent


def replenish_materials(agents: dict[str, Agent], material_ids: tuple[str, ...], cfg: dict) -> None:
    """毎step、各Agentの材料在庫を上限に向けて一定量補充する。

    全条件・全Agentで同一の外生パラメータ。条件間の差を一切作らない。
    """
    mats = cfg["materials"]
    cap, rate = mats["inventory_cap"], mats["replenish_rate"]
    for agent in agents.values():
        for m in material_ids:
            agent.materials[m] = min(cap[m], agent.materials[m] + rate[m])


def reset_time_budgets(agents: dict[str, Agent], cfg: dict) -> None:
    budget = float(cfg["agent_init"]["traits"]["time_budget"]["value"])
    for agent in agents.values():
        agent.time_budget = budget
