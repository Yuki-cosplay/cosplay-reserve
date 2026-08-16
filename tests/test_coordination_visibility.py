"""P0修正の回帰テスト: proposal の近傍限定可視化と coordination_edges の到達可能性。

修正前は propose が ShockState に記録されるだけで他Agentに一切見えず、
coordination_edges >= 1 が**原理的に到達不能**だった（freeze解除事由 P0）。

すべて deterministic。LLM API を呼ばない。
"""

import itertools
from pathlib import Path

import pytest

from src.agents.observation import Observation, build_observation
from src.common.types import ActionType, Intent, RejectionReason
from src.simulation.transition import TransitionJudge
from src.world.demand import RequiredItem, SupplyLedger
from src.world.shock import ShockState, shock_step, validate_shock
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def world():
    return build_world(CONFIG_DIR / "condition_a.yaml", seed=42)


def _adjacent_pair(world):
    for a in world.agents.values():
        if a.known_agents:
            return a.id, sorted(a.known_agents)[0]
    raise AssertionError("隣接ペアが存在しない")


def _non_neighbor(world, aid):
    a = world.agents[aid]
    for other in sorted(world.agents):
        if other != aid and other not in a.known_agents:
            return other
    raise AssertionError("非隣接Agentが存在しない")


# --- A: 隣接Agentの提案が観測できる ---------------------------------------


def test_A_neighbour_can_see_proposal(world):
    a, b = _adjacent_pair(world)
    state = ShockState(proposals={a: "proj_2"})
    obs_b = build_observation(world, world.agents[b], proposals=state.proposals)
    assert (a, "proj_2") in obs_b.neighbor_proposals


# --- B: 非隣接Agentには見えない ---------------------------------------------


def test_B_non_neighbour_cannot_see_proposal(world):
    a, _ = _adjacent_pair(world)
    c = _non_neighbor(world, a)
    obs_c = build_observation(world, world.agents[c], proposals={a: "proj_2"})
    assert all(pid != a for pid, _ in obs_c.neighbor_proposals)


def test_B2_no_global_proposal_list_leaks(world):
    """全Agentの提案を渡しても、見えるのは近傍分のみ。"""
    everyone = {aid: "proj_2" for aid in world.agents}
    for agent in list(world.agents.values())[:8]:
        obs = build_observation(world, agent, proposals=everyone)
        seen = {pid for pid, _ in obs.neighbor_proposals}
        assert seen == set(agent.known_agents), "近傍以外の提案が見えている"
        assert agent.id not in seen, "自分の提案が近傍提案として混入している"


def test_B3_accumulation_phase_sees_no_proposals(world):
    """蓄積相（proposals を渡さない）では常に空。M1 の挙動を変えない。"""
    for agent in list(world.agents.values())[:5]:
        assert build_observation(world, agent).neighbor_proposals == ()


# --- C: proposal があれば join が Validator を通過する ----------------------


def test_C_join_passes_validator_when_proposal_exists(world):
    a, b = _adjacent_pair(world)
    projects = {p.project_id: p for p in world.projects}
    agent_b = world.agents[b]

    # 提案が無い状態では却下される
    state = ShockState()
    accepted = validate_shock(
        agent_b, [Intent(action=ActionType.JOIN, target_agent_id=a)], projects, world.cfg, state
    )
    assert accepted == []
    assert RejectionReason.UNKNOWN_PROJECT in [r for _, r in agent_b.rejected_intents]
    agent_b.rejected_intents.clear()

    # 提案があれば通過する
    state = ShockState(proposals={a: "proj_2"})
    accepted = validate_shock(
        agent_b, [Intent(action=ActionType.JOIN, target_agent_id=a)], projects, world.cfg, state
    )
    assert [i.action for i in accepted] == [ActionType.JOIN]
    assert agent_b.rejected_intents == []


def test_C2_join_to_non_neighbour_still_rejected(world):
    a, _ = _adjacent_pair(world)
    c = _non_neighbor(world, a)
    projects = {p.project_id: p for p in world.projects}
    agent_c = world.agents[c]
    state = ShockState(proposals={a: "proj_2"})
    accepted = validate_shock(
        agent_c, [Intent(action=ActionType.JOIN, target_agent_id=a)], projects, world.cfg, state
    )
    assert accepted == []
    assert RejectionReason.TARGET_NOT_NEIGHBOR in [r for _, r in agent_c.rejected_intents]
    agent_c.rejected_intents.clear()


# --- D: join 成立で coordination_edges >= 1 --------------------------------


def test_D_coordination_edges_reachable_end_to_end():
    """propose -> 近傍が観測 -> join -> edges >= 1 が deterministic に成立する。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    a, b = _adjacent_pair(w)
    state = ShockState()
    required = RequiredItem.from_config(w.cfg["shock"]["required_item"])
    ledger = SupplyLedger(baseline_per_step=w.cfg["shock"]["baseline_supply_per_step"])
    judge = TransitionJudge.from_config(w.cfg["shock"]["transition"])
    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}

    seen_by_b = {}

    def decide(obs):
        if obs.self_id == a:
            return [Intent(action=ActionType.PROPOSE, target_project_id="proj_2")]
        seen_by_b[obs.self_id] = obs.neighbor_proposals
        return [
            Intent(action=ActionType.JOIN, target_agent_id=pid)
            for pid, _ in obs.neighbor_proposals
        ] or [Intent(action=ActionType.IDLE)]

    # step1: a が提案（この step 内で b も観測できる）
    row = shock_step(w, state, required, ledger, judge, decide, [a, b], stats)
    assert state.proposals.get(a) == "proj_2"
    assert (a, "proj_2") in seen_by_b.get(b, ()), "b が a の提案を観測できていない"
    assert state.coordination_edges() >= 1, "join が成立していない"
    assert row["coordination_edges"] >= 1
    assert row["met_coordination_edges"] is (
        row["coordination_edges"] >= w.cfg["shock"]["transition"]["coordination_edges"]
    )


def test_D2_edges_are_undirected_and_deduplicated():
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    a, b = _adjacent_pair(w)
    state = ShockState(proposals={a: "proj_2", b: "proj_2"})
    projects = {p.project_id: p for p in w.projects}
    from src.world.shock import _resolve_shock

    required = RequiredItem.from_config(w.cfg["shock"]["required_item"])
    ledger = SupplyLedger(baseline_per_step=0.0)
    ledger.start_step()
    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}
    _resolve_shock(w, w.agents[a], [Intent(action=ActionType.JOIN, target_agent_id=b)],
                   state, required, ledger, stats)
    _resolve_shock(w, w.agents[b], [Intent(action=ActionType.JOIN, target_agent_id=a)],
                   state, required, ledger, stats)
    assert state.coordination_edges() == 1, "同じペアが二重計上されている"


# --- P0 の再発防止: 可視化がなければ到達不能であることを明示 -----------------


def test_without_visibility_join_is_impossible(world):
    """修正前の状態（proposals を Observation へ渡さない）では join の根拠が無い。"""
    a, b = _adjacent_pair(world)
    obs_b = build_observation(world, world.agents[b])  # proposals を渡さない
    assert obs_b.neighbor_proposals == ()


def test_observation_has_no_forbidden_fields():
    """可視化追加で locality の禁止フィールドが増えていないこと。"""
    import dataclasses

    from src.agents.observation import FORBIDDEN_OBSERVATION_FIELDS

    names = {f.name for f in dataclasses.fields(Observation)}
    assert not (names & FORBIDDEN_OBSERVATION_FIELDS)
    assert "neighbor_proposals" in names


# --- provenance logging（研究者専用。意思決定に影響しない）------------------


def test_provenance_records_every_make_attempt():
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    state = ShockState()
    required = RequiredItem.from_config(w.cfg["shock"]["required_item"])
    ledger = SupplyLedger(baseline_per_step=w.cfg["shock"]["baseline_supply_per_step"])
    judge = TransitionJudge.from_config(w.cfg["shock"]["transition"])
    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}

    def decide(obs):
        return [
            Intent(action=ActionType.MODIFY, target_project_id="proj_2", target_skill_id="attr_0"),
            Intent(action=ActionType.MODIFY, target_project_id="proj_2", target_skill_id="attr_2"),
            Intent(action=ActionType.MAKE, target_project_id="proj_2"),
        ]

    ids = sorted(w.agents)[:3]
    shock_step(w, state, required, ledger, judge, decide, ids, stats)

    assert len(state.provenance) == 3, "make 試行ごとに1件記録されていない"
    required_keys = {
        "step", "agent_id", "source_project_id", "applied_modifications",
        "resulting_attribute_vector", "required_asset", "asset_feasible",
        "required_materials", "material_feasible", "make_success",
        "meets_requirement", "supplied_units", "joined_with",
    }
    for rec in state.provenance:
        assert required_keys <= set(rec), f"provenance に欠落: {required_keys - set(rec)}"
        assert rec["applied_modifications"] == {"attr_0": 0.15, "attr_2": 0.15}
        assert rec["resulting_attribute_vector"]["attr_0"] == pytest.approx(0.60)
        assert rec["resulting_attribute_vector"]["attr_2"] == pytest.approx(0.55)
        assert rec["meets_requirement"] is True
        # 供給は make 成功時のみ。失敗しても記録は残る
        assert rec["supplied_units"] in (0.0, w.cfg["shock"]["unit_yield"])
        assert rec["supplied_units"] == (w.cfg["shock"]["unit_yield"] if rec["make_success"] else 0.0)


def test_provenance_does_not_reach_observation():
    """provenance は研究者専用。Observation にも decide_fn にも渡らない。"""
    import dataclasses

    names = {f.name for f in dataclasses.fields(Observation)}
    assert "provenance" not in names

    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    state = ShockState(provenance=[{"secret": "must not leak"}])
    obs = build_observation(w, w.agents["agent_0"], proposals=state.proposals)
    assert "secret" not in str(obs)


# --- 構造的到達可能性の記録（§10.5）------------------------------------------


def test_structural_capacity_counts_adjacent_pairs(world):
    from src.simulation.transition import structural_coordination_capacity

    a, b = _adjacent_pair(world)
    c = _non_neighbor(world, a)

    r = structural_coordination_capacity(world.graph, [a, b], edges_threshold=1)
    assert r["structurally_available_pairs"] == 1
    assert r["structurally_reachable"] is True
    assert r["selected_agent_ids"] == sorted([a, b])

    r2 = structural_coordination_capacity(world.graph, [a, b], edges_threshold=2)
    assert r2["structurally_reachable"] is False, "閾値2に対し1組しかないのに reachable"


def test_structural_capacity_is_independent_of_agent_behaviour(world):
    """行動を一切起こさなくても同じ値になる（構造量であることの確認）。"""
    from src.simulation.transition import structural_coordination_capacity

    ids = sorted(world.agents)[:6]
    before = structural_coordination_capacity(world.graph, ids, 2)
    for aid in ids:  # 提案・参加を発生させる
        world.agents[aid].rejected_intents.append((None, None))
    after = structural_coordination_capacity(world.graph, ids, 2)
    for aid in ids:
        world.agents[aid].rejected_intents.clear()
    assert before == after


def test_structural_capacity_distinguishes_unmeasurable_from_no_join(world):
    """§10.5 の2状態が区別できること。"""
    from src.simulation.transition import structural_coordination_capacity

    a, _ = _adjacent_pair(world)
    c = _non_neighbor(world, a)
    unmeasurable = structural_coordination_capacity(world.graph, [a, c], edges_threshold=1)
    assert unmeasurable["structurally_available_pairs"] == 0
    assert unmeasurable["structurally_reachable"] is False  # -> 測定不能

    a2, b2 = _adjacent_pair(world)
    reachable = structural_coordination_capacity(world.graph, [a2, b2], edges_threshold=1)
    assert reachable["structurally_reachable"] is True     # -> 行動の知見として報告可
