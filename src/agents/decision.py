"""M1 の意思決定ルール（LLMなし）と Validator（docs/DESIGN_M1.md §5）。

M2 で decide() を LLM 実装に差し替えられるよう、シグネチャを M2 と同一にする。
M1 実装は decide_rule_based() としても公開し、M2 のベースラインとして再利用する。

【重要】この効用関数は「Agent がループを回すため」に設計されていない。
各 Agent は自分の局所状態から自分の効用を最大化するだけであり、
ループは結果としてマクロに現れる（SPEC §5 の要求）。

効用関数は4条件で完全に同一である。条件によって重みや選択肢を変えてはならない。
C/D の Agent も ask と share を通常どおり選択する（§8）。
"""

from __future__ import annotations

import math

import numpy as np

from src.agents.agent import Agent
from src.agents.observation import Observation
from src.common.types import ActionType, Intent, Project, RejectionReason


def _expected_success(obs: Observation, project: Project, cfg: dict) -> float:
    """Agent が自分の局所情報だけから見積もる成功確率。

    production.success_probability と同じ式だが、Agent 自身の state のみを使う。
    世界の真値には触れない。
    """
    learning = cfg["learning"]
    skill = obs.self_skills[project.primary_skill]
    owns = project.required_asset is None or _obs_owns(obs, project.required_asset, cfg)
    asset_bonus = learning["asset_bonus"] if owns else 0.0
    reduction = max(
        (m.difficulty_reduction for m in obs.self_methods if m.project_id == project.project_id),
        default=0.0,
    )
    raw = skill + asset_bonus - project.base_difficulty * (1.0 - reduction)
    return 1.0 / (1.0 + math.exp(-raw / learning["temperature"]))


def _obs_owns(obs: Observation, asset_id: str, cfg: dict) -> bool:
    v = obs.self_assets[asset_id]
    if cfg["agent_init"]["assets"][asset_id]["type"] == "bernoulli":
        return v is True
    return v >= 1


def decide(obs: Observation, rng: np.random.Generator, cfg: dict) -> list[Intent]:
    """効用ベースの決定論的ルール（rng は同点処理のみに使用）。

    1 step = 1週間あるため、候補を効用降順に並べて返す。
    時間予算と実現可能性は Validator が判定する（決定 X1）。
    """
    w = cfg["decision_weights"]
    candidates: list[tuple[float, Intent]] = []

    # observe: 情報が少ないほど観測したくなる
    if obs.neighbors:
        unknown = sum(1 for n in obs.neighbors if n not in obs.perceived_neighbor_skills)
        u = w["observe"] * (unknown / len(obs.neighbors))
        target = min(
            obs.neighbors, key=lambda n: len(obs.perceived_neighbor_skills.get(n, {}))
        )
        candidates.append((u, Intent(ActionType.OBSERVE, target_agent_id=target)))

    # ask: 自分より上手い相手がいるほど尋ねたくなる
    best_gap, best_target = 0.0, None
    for n in obs.neighbors:
        beliefs = obs.perceived_neighbor_skills.get(n, {})
        for skill_id, belief in beliefs.items():
            gap = max(0.0, belief.estimate - obs.self_skills[skill_id])
            if gap > best_gap:
                best_gap, best_target = gap, (n, skill_id)
    if best_target is not None:
        n, skill_id = best_target
        u = w["ask"] * obs.self_imitation_tendency * best_gap * obs.trust.get(n, 0.0)
        candidates.append(
            (u, Intent(ActionType.ASK, target_agent_id=n, target_skill_id=skill_id))
        )

    # practice: 技能が低いほど練習の限界効用が高い
    weakest = min(obs.self_skills, key=lambda s: obs.self_skills[s])
    max_skill = max(obs.self_skills.values())
    candidates.append(
        (w["practice"] * (1.0 - max_skill), Intent(ActionType.PRACTICE, target_skill_id=weakest))
    )

    # make: 成功見込みが高いほど作りたくなる。全 project を候補にする。
    # 実現可能性（材料・設備）は Validator が判定し、不可なら次の候補へ回る。
    for project in obs.project_catalog:
        p = _expected_success(obs, project, cfg)
        u = w["make"] * obs.self_participation_level * p
        candidates.append(
            (u, Intent(ActionType.MAKE, target_project_id=project.project_id))
        )

    # share: 共有性向と手持ち知識に比例
    if obs.self_methods:
        u = w["share"] * obs.self_sharing_tendency * len(obs.self_methods)
        m = obs.self_methods[0]
        candidates.append((u, Intent(ActionType.SHARE, target_method_id=m.method_id)))

    # 効用が 0 の候補は「そもそも望んでいない」ため提案しない。
    #
    # §5 は「時間予算が尽きるまで貪欲に行動を選ぶ」とし、§3.4.5（決定 Z3）は
    # 「non-participant は participation_level ≒ 0 により make を実行しない」とする。
    # 全候補を無条件に貪欲実行すると効用 0 の make も実行されてしまい、両者が両立しない。
    # 効用が正の候補のみを提案することが、両方を同時に満たす唯一の読みである。
    candidates = [(u, i) for u, i in candidates if u > 0.0]

    # idle は「何もしない選択肢」として常に残る（§5.1 の下限値）
    candidates.append((w["idle"], Intent(ActionType.IDLE)))

    # 同点は rng で崩す（決定論性は seed で担保される）
    jitter = rng.random(len(candidates)) * 1e-9
    order = sorted(range(len(candidates)), key=lambda i: -(candidates[i][0] + jitter[i]))
    return [candidates[i][1] for i in order]


# M2 のベースラインとして名前を残す（§19 引き継ぎ設計）
decide_rule_based = decide


def infeasible_reason(agent: Agent, intent: Intent, projects: dict, cfg: dict):
    """実行不能なら RejectionReason、実行可能なら None を返す。

    Agent（M2 以降は LLM）はこれらを宣言できない。
    実現可能性の判定は世界側コードの責務である（SPEC §13）。
    """
    from src.world.production import has_materials, has_required_asset

    if intent.action == ActionType.MAKE:
        project = projects.get(intent.target_project_id)
        if project is None:
            return RejectionReason.UNKNOWN_PROJECT
        if not has_required_asset(agent, project, cfg):
            return RejectionReason.MISSING_ASSET
        if not has_materials(agent, project):
            return RejectionReason.INSUFFICIENT_MATERIAL
    elif intent.action in (ActionType.OBSERVE, ActionType.ASK):
        if intent.target_agent_id not in agent.known_agents:
            return RejectionReason.TARGET_NOT_NEIGHBOR
    elif intent.action == ActionType.SHARE:
        if intent.target_method_id not in agent.methods:
            return RejectionReason.METHOD_NOT_OWNED
    return None


def validate(agent: Agent, intents: list[Intent], projects: dict, cfg: dict) -> list[Intent]:
    """time_budget 内で順に Intent を評価し、予算を超えた Intent 以降は却下する。

    時間超過は break、実行不能は continue である点に注意。
    時間が尽きたら以降はすべて却下されるが、材料不足で作れない Project の次に
    「練習する」という Intent があれば、それは実行できる。

    却下された Intent は agent.rejected_intents へ記録し、学習信号として残す。
    """
    remaining = agent.time_budget
    accepted: list[Intent] = []
    max_actions = cfg["time"]["max_actions_per_step"]

    for intent in intents:
        if len(accepted) >= max_actions:
            break
        cost = cfg["action_time_cost"][intent.action.value]
        if cost > remaining:
            agent.rejected_intents.append((intent, RejectionReason.TIME_BUDGET_EXCEEDED))
            break
        reason = infeasible_reason(agent, intent, projects, cfg)
        if reason is not None:
            agent.rejected_intents.append((intent, reason))
            continue
        remaining -= cost
        accepted.append(intent)
    return accepted
