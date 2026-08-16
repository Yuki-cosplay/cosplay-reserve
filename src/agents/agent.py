"""Agent のデータ構造と初期化（docs/DESIGN_M1.md §3.2 / §3.4 / §15.1）。

【最重要】このモジュールは条件（A/B/C/D）を一切参照しない。
条件分岐はネットワーク構築（src/culture/network.py）と
peer 受容ゲート（src/agents/memory.py）にのみ存在する。
tests/test_condition_invariance.py がこれを機械的に検証する。
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from src.common.io import sha256_of
from src.common.types import IdRegistry, MakerStage, Method, PerceivedSkill

# pre-network ハッシュから除外するフィールド（決定 Y6）。
# post-network 状態でハッシュを取ると、A と B は近傍が違うため必ず不一致になり、
# T5 が成立しなくなる。trust は M1 では固定値だが近傍ごとの dict として
# 展開されるため、値が条件不変でもキー集合が条件によって変わる。
NETWORK_DERIVED_FIELDS = ("known_agents", "cultural_peers", "trust", "perceived_skills")


@dataclass
class Agent:
    id: str
    rng_seed: int

    # §3.4: 生成後は変化しない（M1 では参加の出入りを扱わない）
    is_participant: bool

    skills: dict[str, float]
    practice_count: dict[str, int]
    success_count: dict[str, int]
    failure_count: dict[str, int]
    practiced_this_step: set[str] = field(default_factory=set)

    assets: dict[str, bool | int] = field(default_factory=dict)
    time_budget: float = 0.0
    materials: dict[str, float] = field(default_factory=dict)

    participation_level: float = 0.0
    maker_stage: MakerStage = MakerStage.CONSUMER
    sharing_tendency: float = 0.0
    imitation_tendency: float = 0.0
    helping_norm: float = 0.0

    # --- ここから下は network 構築後に埋まる（pre-network ハッシュ対象外）---
    known_agents: set[str] = field(default_factory=set)
    cultural_peers: set[str] = field(default_factory=set)
    trust: dict[str, float] = field(default_factory=dict)
    perceived_skills: dict[str, dict[str, PerceivedSkill]] = field(default_factory=dict)

    methods: dict[str, Method] = field(default_factory=dict)
    recent_events: list = field(default_factory=list)
    completed_projects: list = field(default_factory=list)
    rejected_intents: list = field(default_factory=list)

    inbox: list = field(default_factory=list)
    outbox: list = field(default_factory=list)

    # 決定 D8: money は M1 の因果モデルに存在しない。フィールドごと持たない。
    # 決定 D7: 参入・退出はない。alive / joined_step のようなフィールドも作らない。


def _draw(spec: dict, rng: np.random.Generator):
    """config の分布指定から1つ引く。キー名は type に統一済み（決定 V2/V3）。"""
    t = spec["type"]
    if t == "beta":
        return float(rng.beta(spec["a"], spec["b"]))
    if t == "constant":
        return spec["value"]
    if t == "bernoulli":
        return bool(rng.random() < spec["p"])
    if t == "categorical":
        return int(rng.choice(spec["values"], p=spec["probs"]))
    raise ValueError(f"unknown distribution type: {t!r}")


def assign_participants(cfg: dict, rng: np.random.Generator) -> tuple[list[str], set[str]]:
    """agent_id 一覧と participant 集合を返す（決定 V1）。

    【禁止】agent_0 〜 agent_{n-1} を participant にするような連番割り当て。

    base graph はリング格子でありノード番号はリング上の位置そのものである。
    participant を連番の先頭に割り当てると participant がリング上で連続した弧を
    占め、その弧の内部で cultural edge がほぼ閉じる。rewire によってこの弧は
    壊れるため、条件A では密・条件B では疎になり、topology 主効果が交絡する。

    この割り当ては agent_init ストリームで行うため、4条件で完全に同一になる。
    """
    world = cfg["world"]
    n_total = world["n_participant_agents"] + world["n_nonparticipant_agents"]
    agent_ids = [f"agent_{i}" for i in range(n_total)]

    perm = rng.permutation(n_total)
    participant_idx = set(int(i) for i in perm[: world["n_participant_agents"]])
    participants = {agent_ids[i] for i in participant_idx}
    return agent_ids, participants


def build_agents(cfg: dict, ids: IdRegistry, rng: np.random.Generator) -> dict[str, Agent]:
    """Agent を生成する。network 構築より前に完了する（§15.1 要件5）。

    条件（A/B/C/D）を一切参照しないため、同一 seed なら4条件で完全に一致する。

    ストリーム消費順序を固定するため、agent_id 昇順で、各Agentについて
    skills → assets → traits の順に引く。participation_level は
    participant / non-participant のどちらでも1回引き、non-participant では
    引いた値を捨てて constant で上書きする。これにより1Agentあたりの
    消費数が母集団構成によらず一定になる。
    """
    init = cfg["agent_init"]
    traits = init["traits"]
    materials_initial = cfg["materials"]["initial"]

    agent_ids, participants = assign_participants(cfg, rng)

    agents: dict[str, Agent] = {}
    for aid in agent_ids:
        skills = {sid: float(_draw(init["skills"][sid], rng)) for sid in ids.skill_ids}
        assets = {a: _draw(init["assets"][a], rng) for a in ids.asset_ids}

        participation_draw = float(_draw(traits["participation_level"], rng))
        sharing = float(_draw(traits["sharing_tendency"], rng))
        imitation = float(_draw(traits["imitation_tendency"], rng))
        helping = float(_draw(traits["helping_norm"], rng))

        is_participant = aid in participants
        participation = (
            participation_draw
            if is_participant
            else float(traits["nonparticipant_participation_level"]["value"])
        )

        agents[aid] = Agent(
            id=aid,
            rng_seed=int(cfg["run"]["seed"]),
            is_participant=is_participant,
            skills=skills,
            practice_count={s: 0 for s in ids.skill_ids},
            success_count={s: 0 for s in ids.skill_ids},
            failure_count={s: 0 for s in ids.skill_ids},
            assets=assets,
            time_budget=float(traits["time_budget"]["value"]),
            materials={m: float(materials_initial[m]) for m in ids.material_ids},
            participation_level=participation,
            maker_stage=MakerStage.CONSUMER,
            sharing_tendency=sharing,
            imitation_tendency=imitation,
            helping_norm=helping,
        )
    return agents


def pre_network_state(agents: dict[str, Agent]) -> list[dict]:
    """pre-network 状態の正準表現（決定 Y6）。

    network 由来フィールドを含めない。含めると A と B は近傍が違うため
    必ず不一致になり、T5 が成立しなくなる。
    """
    out = []
    for aid in sorted(agents):
        a = agents[aid]
        out.append(
            {
                "id": a.id,
                "is_participant": a.is_participant,
                "skills": {k: repr(v) for k, v in sorted(a.skills.items())},
                "assets": {k: repr(v) for k, v in sorted(a.assets.items())},
                "materials": {k: repr(v) for k, v in sorted(a.materials.items())},
                "time_budget": repr(a.time_budget),
                "participation_level": repr(a.participation_level),
                "sharing_tendency": repr(a.sharing_tendency),
                "imitation_tendency": repr(a.imitation_tendency),
                "helping_norm": repr(a.helping_norm),
                "maker_stage": a.maker_stage.value,
            }
        )
    return out


def agent_initial_states_sha256(agents: dict[str, Agent]) -> str:
    return sha256_of(pre_network_state(agents))


def participant_ids_sha256(agents: dict[str, Agent]) -> str:
    return sha256_of(sorted(a.id for a in agents.values() if a.is_participant))
