"""1ステップの処理シーケンス（docs/DESIGN_M1.md §4）。

1 step = 1週間（蓄積相、SPEC §25）。

同時解決の意味: 全 Agent の Intent を確定させてから解決する。逐次実行だと、
先に動いた Agent が材料を使い切って後続が行動できない等の順序依存が生じる。
order は資源競合時の解決順序にのみ使い、マスターseed由来で再現可能にする。
"""

from __future__ import annotations

from src.agents.decision import decide, validate
from src.agents.memory import accept_peer_method, discover_method, receive_method
from src.agents.observation import build_observation
from src.common.types import ActionType, MakerStage, PerceivedSkill
from src.culture.capability import update_maker_stages
from src.culture.learning import apply_skill_gain, decay_skills
from src.world.production import consume_materials, success_probability
from src.world.resources import replenish_materials, reset_time_budgets


class StepStats:
    """1 step の観測値。Metrics が集計する（§10.1）。"""

    def __init__(self):
        self.time_by_action: dict[str, float] = {}
        self.skill_gain_total: float = 0.0
        self.time_total: float = 0.0
        self.make_time: float = 0.0
        self.social_time: float = 0.0
        self.self_discovered: int = 0
        self.peer_acquired: int = 0
        self.rejections: dict[str, int] = {}
        self.action_counts: dict[str, int] = {}
        # population 別の集計に使う
        self.per_agent_skill_gain: dict[str, float] = {}


def _resolve(world, agent, intents, stats: StepStats):
    cfg = world.cfg
    projects = {p.project_id: p for p in world.projects}
    rng = world.rng["simulation"]

    for intent in intents:
        act = intent.action.value
        cost = cfg["action_time_cost"][act]
        stats.time_by_action[act] = stats.time_by_action.get(act, 0.0) + cost
        stats.time_total += cost
        stats.action_counts[act] = stats.action_counts.get(act, 0) + 1
        if intent.action == ActionType.MAKE:
            stats.make_time += cost
        elif intent.action in (ActionType.OBSERVE, ActionType.ASK, ActionType.SHARE):
            stats.social_time += cost

        if intent.action == ActionType.PRACTICE:
            sid = intent.target_skill_id
            gain = apply_skill_gain(agent, sid, success=False, cfg=cfg)
            agent.practice_count[sid] += 1
            agent.practiced_this_step.add(sid)
            stats.skill_gain_total += gain
            stats.per_agent_skill_gain[agent.id] = (
                stats.per_agent_skill_gain.get(agent.id, 0.0) + gain
            )

        elif intent.action == ActionType.MAKE:
            project = projects[intent.target_project_id]
            consume_materials(agent, project)
            p = success_probability(agent, project, cfg)
            success = bool(rng.random() < p)
            sid = project.primary_skill
            # 成功・失敗を問わず practiced_this_step へ（§6.3）
            agent.practiced_this_step.add(sid)
            gain = apply_skill_gain(agent, sid, success=success, cfg=cfg)
            stats.skill_gain_total += gain
            stats.per_agent_skill_gain[agent.id] = (
                stats.per_agent_skill_gain.get(agent.id, 0.0) + gain
            )
            if success:
                agent.success_count[sid] += 1
                agent.completed_projects.append((world.step, project.project_id))
                if rng.random() < cfg["learning"]["method_discovery_prob"]:
                    m = discover_method(agent, project.project_id, sid, world.step, cfg)
                    agent.methods[m.method_id] = m
                    stats.self_discovered += 1
            else:
                agent.failure_count[sid] += 1

        elif intent.action == ActionType.OBSERVE:
            target = world.agents[intent.target_agent_id]
            noise = cfg["decision"]["observation_noise"]
            beliefs = agent.perceived_skills.setdefault(target.id, {})
            for sid, true_value in target.skills.items():
                est = float(min(1.0, max(0.0, true_value + rng.normal(0.0, noise))))
                prev = beliefs.get(sid)
                beliefs[sid] = PerceivedSkill(
                    estimate=est,
                    last_updated_step=world.step,
                    observation_count=(prev.observation_count + 1) if prev else 1,
                )

        elif intent.action == ActionType.ASK:
            target = world.agents[intent.target_agent_id]
            # 信念の更新は全条件で有効（trust は M1 では固定・更新しない）
            beliefs = agent.perceived_skills.setdefault(target.id, {})
            sid = intent.target_skill_id
            prev = beliefs.get(sid)
            est = float(min(1.0, max(0.0, target.skills[sid] + rng.normal(0.0, cfg["decision"]["observation_noise"] * 0.5))))
            beliefs[sid] = PerceivedSkill(
                estimate=est,
                last_updated_step=world.step,
                observation_count=(prev.observation_count + 1) if prev else 1,
            )
            # 相手が Method を持っていれば offer として inbox へ入れる。
            # 受容は accept_peer_method のゲートを必ず経由する。
            for m in target.methods.values():
                agent.inbox.append((m, target.id))
                break

        elif intent.action == ActionType.SHARE:
            m = agent.methods.get(intent.target_method_id)
            if m is not None:
                # share は一般社会接触層（known_agents）へ届く。
                # Method が実際に渡るかは受容ゲートが決める（§7.2 / §8.3）。
                for n in sorted(agent.known_agents):
                    world.agents[n].inbox.append((m, agent.id))


def _deliver(world, stats: StepStats) -> None:
    """inbox の Method offer を受容判定にかける。遮断点は accept_peer_method のみ。"""
    rng = world.rng["simulation"]
    cfg = world.cfg
    for aid in sorted(world.agents):
        agent = world.agents[aid]
        for method, sender_id in agent.inbox:
            if accept_peer_method(agent, method, sender_id, cfg, rng):
                receive_method(agent, method, sender_id, world.step)
                stats.peer_acquired += 1
        agent.inbox.clear()


def step(world) -> StepStats:
    cfg = world.cfg
    ids = world.id_registry
    stats = StepStats()

    # (0) 外生補充 — 全条件で同一（§9）
    replenish_materials(world.agents, ids.material_ids, cfg)
    reset_time_budgets(world.agents, cfg)
    for a in world.agents.values():
        a.practiced_this_step.clear()

    # (1) perceive — 局所情報の切り出し
    observations = {aid: build_observation(world, a) for aid, a in world.agents.items()}

    # (2) decide + (2b) validate
    projects = {p.project_id: p for p in world.projects}
    rng = world.rng["simulation"]
    intents = {}
    for aid in sorted(world.agents):
        proposed = decide(observations[aid], rng, cfg)
        intents[aid] = validate(world.agents[aid], proposed, projects, cfg)

    # (3)(4) act / resolve — 解決順序のみ乱数で決める
    order = list(sorted(world.agents))
    rng.shuffle(order)
    for aid in order:
        _resolve(world, world.agents[aid], intents[aid], stats)

    # (5) update
    decay_skills(world.agents, ids.skill_ids, cfg)
    update_maker_stages(world.agents, cfg)
    _deliver(world, stats)

    for agent in world.agents.values():
        for _, reason in agent.rejected_intents[-20:]:
            stats.rejections[reason.value] = stats.rejections.get(reason.value, 0) + 1
        agent.rejected_intents.clear()

    world.step += 1
    return stats
