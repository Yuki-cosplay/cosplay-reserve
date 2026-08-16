"""Method Library と peer 受容ゲート（docs/DESIGN_M1.md §6.5 / §8）。

SPEC §19 が定める C/D の意味は「ネットワークを除去した世界」ではなく

    人は社会的につながっているが、そのつながりが制作能力の再生産経路として
    機能しない世界

である。したがって遮断するのは peer Method transfer だけである。
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from src.agents.agent import Agent
from src.common.types import Method


def make_method_id(agent_id: str, project_id: str, step: int) -> str:
    return f"m:{agent_id}:{project_id}:{step}"


def discover_method(agent: Agent, project_id: str, primary_skill: str, step: int, cfg: dict) -> Method:
    """make 成功時の自己発見（全条件で有効）。hop_count=0、source=origin=自分。"""
    return Method(
        method_id=make_method_id(agent.id, project_id, step),
        project_id=project_id,
        primary_skill=primary_skill,
        difficulty_reduction=cfg["learning"]["base_reduction"],
        origin_agent_id=agent.id,
        source_agent_id=agent.id,
        origin_step=step,
        acquired_step=step,
        hop_count=0,
    )


def accept_peer_method(
    agent: Agent, method: Method, sender_id: str, cfg: dict, rng: np.random.Generator
) -> bool:
    """peer learning の遮断点は、コード全体でこの関数の1箇所のみ。

    ここ以外に peer_learning_enabled を参照する分岐を書いてはならない。
    分岐が散らばると「C/D で何が無効なのか」が追跡不能になる。

    ゲートは2段だが、どちらも「受容するか」の判定であり外に分岐を出さない:
      1. cfg.peer_learning_enabled  -> 条件（A/B/C/D）の操作
      2. sender in cultural_peers   -> 母集団構成（participant / non-participant）

    両者は独立しており、C/D では participant 同士でも Method は渡らない。
    """
    if not cfg["peer_learning_enabled"]:
        return False  # ← C/D はここで止まる。ask/share 自体は起きている
    if sender_id not in agent.cultural_peers:
        return False  # ← non-participant はここで止まる（§7.2）
    if method.project_id in {m.project_id for m in agent.methods.values()}:
        return False
    # trust は M1 では固定値。ここで参照はするが、更新はどこでも行わない
    p = agent.imitation_tendency * agent.trust.get(sender_id, 0.0)
    return bool(rng.random() < p)


def receive_method(agent: Agent, method: Method, sender_id: str, step: int) -> Method:
    """受容された Method を Library へ格納する。hop_count を +1 する。"""
    received = replace(
        method,
        method_id=f"{method.method_id}>{agent.id}",
        source_agent_id=sender_id,
        acquired_step=step,
        hop_count=method.hop_count + 1,
    )
    agent.methods[received.method_id] = received
    return received
