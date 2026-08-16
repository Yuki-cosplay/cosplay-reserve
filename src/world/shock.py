"""ショック相の1ステップ（M3、SPEC §25: 1 step = 6時間）。

蓄積相（src/world/step.py）とは別の step 関数である。蓄積相の実装は変更しない
（A/B/C/D の既存結果を壊さないため）。

再構成の経路:
  modify  既存 project の制作物の属性を別方向へ振り向ける（技能・設備・Method を再利用）
  make    変形後の制作物を作る。属性が要求仕様を満たせば供給として記帳される
  propose 協調を提案する
  join    提案に加わる（協調エッジになる）

【答えを与えない】どの project をどう変形すれば要求を満たすかはコードが判定するだけで、
Agent には指示しない。Agent が見るのは「不足している属性と量」だけである。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.common.types import ActionType, RejectionReason
from src.culture.learning import apply_skill_gain
from src.world.demand import RequiredItem, apply_shifts
from src.world.production import consume_materials, has_materials, has_required_asset
from src.world.resources import replenish_materials, reset_time_budgets


@dataclass
class ShockState:
    """ショック相で追加される Agent 側の状態。Agent 本体を変更しないため外部に持つ。

    variants: agent_id -> project_id -> {attr: delta}  変形の蓄積
    proposals: proposer_id -> project_id              協調の提案
    joined: set of (a, b)                             協調エッジ（無向）
    """

    variants: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    proposals: dict[str, str] = field(default_factory=dict)
    joined: set[tuple[str, str]] = field(default_factory=set)
    modify_count: int = 0

    # ★研究者専用★ 供給イベント単位の provenance（M3 P0修正時に追加）。
    # Observation にも decide_fn にも渡さない。Agent の意思決定を一切変えない。
    provenance: list[dict] = field(default_factory=list)
    # agent_id -> [(step, project_id, attr, delta), ...] 変形の履歴（研究者専用）
    modify_history: dict[str, list] = field(default_factory=dict)

    def profile_for(self, agent_id: str, project) -> object:
        shifts = self.variants.get(agent_id, {}).get(project.project_id, {})
        return apply_shifts(project.target_profile, shifts) if shifts else project.target_profile

    def coordination_edges(self) -> int:
        return len(self.joined)


def shock_infeasible_reason(agent, intent, projects, cfg, state: ShockState):
    """ショック相の実現可能性判定。M1 と同じく世界側コードの責務（SPEC §13）。"""
    if intent.action in (ActionType.MAKE, ActionType.MODIFY):
        project = projects.get(intent.target_project_id)
        if project is None:
            return RejectionReason.UNKNOWN_PROJECT
        if not has_required_asset(agent, project, cfg):
            return RejectionReason.MISSING_ASSET
        if intent.action == ActionType.MAKE and not has_materials(agent, project):
            return RejectionReason.INSUFFICIENT_MATERIAL
    elif intent.action == ActionType.PROPOSE:
        if intent.target_project_id not in projects:
            return RejectionReason.UNKNOWN_PROJECT
    elif intent.action == ActionType.JOIN:
        if intent.target_agent_id not in agent.known_agents:
            return RejectionReason.TARGET_NOT_NEIGHBOR
        if intent.target_agent_id not in state.proposals:
            return RejectionReason.UNKNOWN_PROJECT
    elif intent.action in (ActionType.OBSERVE, ActionType.ASK):
        if intent.target_agent_id not in agent.known_agents:
            return RejectionReason.TARGET_NOT_NEIGHBOR
    return None


def validate_shock(agent, intents, projects, cfg, state: ShockState):
    """時間超過は break、実行不能は continue（M1 の validate と同じ規約）。"""
    remaining, accepted = agent.time_budget, []
    for intent in intents[: cfg["time"]["max_actions_per_step"]]:
        cost = cfg["action_time_cost"][intent.action.value]
        if cost > remaining:
            agent.rejected_intents.append((intent, RejectionReason.TIME_BUDGET_EXCEEDED))
            break
        reason = shock_infeasible_reason(agent, intent, projects, cfg, state)
        if reason is not None:
            agent.rejected_intents.append((intent, reason))
            continue
        remaining -= cost
        accepted.append(intent)
    return accepted


def _resolve_shock(world, agent, intents, state, required: RequiredItem, ledger, stats):
    cfg = world.cfg
    projects = {p.project_id: p for p in world.projects}
    rng = world.rng["simulation"]
    shock = cfg["shock"]

    for intent in intents:
        act = intent.action.value
        stats["actions"][act] = stats["actions"].get(act, 0) + 1

        if intent.action == ActionType.MODIFY:
            project = projects[intent.target_project_id]
            # 変形は「どの属性を動かすか」を Agent が選ぶ。どの属性が要求されているかは
            # Observation 経由で不足分として見えている（局所情報）。
            attr = intent.target_skill_id if intent.target_skill_id in _ATTRS else None
            if attr is None:
                attr = min(required.thresholds, key=lambda a: required.thresholds[a])
            shifts = state.variants.setdefault(agent.id, {}).setdefault(project.project_id, {})
            shifts[attr] = shifts.get(attr, 0.0) + shock["modify_delta"]
            state.modify_history.setdefault(agent.id, []).append(
                {"step": world.step, "project_id": project.project_id,
                 "attr": attr, "delta": shock["modify_delta"]}
            )
            state.modify_count += 1
            agent.practiced_this_step.add(project.primary_skill)

        elif intent.action == ActionType.MAKE:
            project = projects[intent.target_project_id]
            shifts = dict(state.variants.get(agent.id, {}).get(project.project_id, {}))
            # feasibility は validate_shock で判定済み。ここでは記録のため再評価する
            asset_ok = has_required_asset(agent, project, cfg)
            mat_ok = has_materials(agent, project)
            consume_materials(agent, project)
            profile = state.profile_for(agent.id, project)
            n_shifts = len(shifts)
            # 変形した分だけ実効難度が上がる（ただ乗りできない）
            penalty = 1.0 + shock["modify_difficulty_penalty"] * n_shifts
            from src.world.production import success_probability

            p = success_probability(agent, project, cfg)
            p = max(0.02, min(0.98, p / penalty))
            success = bool(rng.random() < p)
            agent.practiced_this_step.add(project.primary_skill)
            apply_skill_gain(agent, project.primary_skill, success, cfg)

            qualifies = required.satisfied_by(profile)
            supplied = 0.0
            if success:
                agent.completed_projects.append((world.step, project.project_id))
                # ★充足判定はコード側★ 名称照合はしない（SPEC §18）
                if qualifies:
                    supplied = shock["unit_yield"]
                    ledger.record_supply(agent.id, supplied, world.step)
                    stats["qualifying_makes"] += 1
                else:
                    stats["nonqualifying_makes"] += 1

            state.provenance.append({
                "step": world.step,
                "condition": cfg["condition"],
                "seed": cfg["run"]["seed"],
                "agent_id": agent.id,
                "intent": {
                    "action": intent.action.value,
                    "target_project_id": intent.target_project_id,
                    "target_skill_id": intent.target_skill_id,
                    "target_agent_id": intent.target_agent_id,
                    "reason": intent.reason,
                },
                "modify_history": list(state.modify_history.get(agent.id, [])),
                "before_attributes": {
                    f"attr_{i}": round(getattr(project.target_profile, f"attr_{i}"), 4)
                    for i in range(7)
                },
                "required_attributes": dict(required.thresholds),
                "source_project_id": project.project_id,
                "applied_modifications": shifts,
                "after_attributes": {
                    f"attr_{i}": round(getattr(profile, f"attr_{i}"), 4) for i in range(7)
                },
                "required_asset": project.required_asset,
                "asset_feasible": asset_ok,
                "required_materials": dict(project.material_cost),
                "material_feasible": mat_ok,
                "effective_success_probability": round(p, 6),
                "make_success": success,
                "meets_requirement": qualifies,
                "supplied_units": supplied,
                "proposal_relation": {
                    "self_proposed": state.proposals.get(agent.id),
                    "visible_neighbour_proposals": {
                        pid: proj for pid, proj in state.proposals.items()
                        if pid in agent.known_agents and pid != agent.id
                    },
                },
                "join_relation": sorted(
                    o for pair in state.joined if agent.id in pair for o in pair if o != agent.id
                ),
                "coordination_relation": {
                    "edges_total": len(state.joined),
                    "edges_involving_self": sorted(
                        list(p) for p in state.joined if agent.id in p
                    ),
                },
            })

        elif intent.action == ActionType.PROPOSE:
            state.proposals[agent.id] = intent.target_project_id

        elif intent.action == ActionType.JOIN:
            other = intent.target_agent_id
            state.joined.add(tuple(sorted((agent.id, other))))

        elif intent.action == ActionType.PRACTICE and intent.target_skill_id:
            agent.practiced_this_step.add(intent.target_skill_id)
            apply_skill_gain(agent, intent.target_skill_id, False, cfg)


_ATTRS = tuple(f"attr_{i}" for i in range(7))


def shock_step(world, state, required, ledger, judge, decide_fn, llm_agent_ids, stats) -> dict:
    """ショック相の1 step（= 6時間）。

    decide_fn(obs) -> list[Intent] は LLM または決定論ルール。
    llm_agent_ids に含まれる Agent だけが decide_fn を使う（コスト制御、SPEC §24）。
    """
    from src.agents.observation import build_observation

    cfg = world.cfg
    ids = world.id_registry
    projects = {p.project_id: p for p in world.projects}

    replenish_materials(world.agents, ids.material_ids, cfg)
    reset_time_budgets(world.agents, cfg)
    for a in world.agents.values():
        a.practiced_this_step.clear()
    ledger.start_step()

    for aid in sorted(llm_agent_ids):
        agent = world.agents[aid]
        obs = build_observation(world, agent, proposals=state.proposals)
        intents = decide_fn(obs)
        accepted = validate_shock(agent, intents, projects, cfg, state)
        stats["proposed"] += len(intents)
        stats["accepted"] += len(accepted)
        for _, reason in agent.rejected_intents:
            stats["rejections"][reason.value] = stats["rejections"].get(reason.value, 0) + 1
        agent.rejected_intents.clear()
        _resolve_shock(world, agent, accepted, state, required, ledger, stats)

    row = judge.evaluate(world.step, ledger, state.coordination_edges())
    world.step += 1
    return row
