"""M3 P0 テスト: 需要・答えの非漏洩・責務分離・既存条件の不変・コード側転化判定。"""

from pathlib import Path

import pytest

from src.common.config import load_config
from src.common.types import ActionType, AttributeVector, Intent, RejectionReason
from src.llm.prompts import SHOCK_INTENT_LIST_SCHEMA, SHOCK_SYSTEM_PROMPT, build_shock_user_prompt
from src.agents.observation import build_observation
from src.simulation.transition import TransitionJudge, reconfiguration_time
from src.world.demand import RequiredItem, SupplyLedger, apply_shifts
from src.world.shock import ShockState, shock_step, validate_shock
from src.world.world import build_world
from tests.forbidden import assert_clean

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def world():
    return build_world(CONFIG_DIR / "condition_a.yaml", seed=42)


@pytest.fixture(scope="module")
def required(world):
    return RequiredItem.from_config(world.cfg["shock"]["required_item"])


# --- P0: RequiredItem / demand shock が動く --------------------------------


def test_requirement_is_attribute_spec_not_a_name(world, required):
    assert set(required.thresholds) <= {f"attr_{i}" for i in range(7)}
    assert required.unit_demand > 0


def test_no_project_satisfies_the_requirement_as_is(world, required):
    """答えが最初から仕込まれていないこと。再構成なしでは満たせない。"""
    satisfied = [p.project_id for p in world.projects if required.satisfied_by(p.target_profile)]
    assert satisfied == [], f"再構成なしで要求を満たす project がある: {satisfied}"


def test_satisfaction_is_decided_by_attributes_only(required):
    ok = AttributeVector(**{a: 1.0 for a in required.thresholds})
    ng = AttributeVector()
    assert required.satisfied_by(ok)
    assert not required.satisfied_by(ng)


def test_modify_can_reach_the_requirement(world, required):
    """再構成の経路が存在すること（不可能な要求ではない）。"""
    cfg = world.cfg["shock"]
    reachable = False
    for p in world.projects:
        shifts, prof = {}, p.target_profile
        for _ in range(20):
            if required.satisfied_by(prof):
                reachable = True
                break
            attr = max(required.shortfall(prof), key=lambda a: required.shortfall(prof)[a])
            shifts[attr] = shifts.get(attr, 0.0) + cfg["modify_delta"]
            prof = apply_shifts(p.target_profile, shifts)
        if reachable:
            break
    assert reachable, "どの project も modify で要求へ到達できない"


# --- P0: Agent へ答えを漏らさない ------------------------------------------


def test_shock_prompts_have_no_forbidden_terms(world, required):
    state = ShockState()
    for agent in list(world.agents.values())[:5]:
        obs = build_observation(world, agent)
        sf = {p.project_id: required.shortfall(state.profile_for(agent.id, p)) for p in world.projects}
        assert_clean(SHOCK_SYSTEM_PROMPT + build_shock_user_prompt(obs, required, sf),
                     f"shock prompt for {agent.id}")


def test_shock_prompt_does_not_say_what_to_build(world, required):
    state = ShockState()
    agent = world.agents["agent_0"]
    obs = build_observation(world, agent)
    sf = {p.project_id: required.shortfall(state.profile_for(agent.id, p)) for p in world.projects}
    text = build_shock_user_prompt(obs, required, sf).lower()
    for leak in ("you should make", "you should build proj", "the best item is", "use proj_"):
        assert leak not in text, f"プロンプトが答えを与えている: {leak!r}"


# --- P0: LLM Intent と Code feasibility の分離を維持 ------------------------


def test_shock_schema_has_no_quantity_fields():
    props = SHOCK_INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["properties"]
    for banned in ("quantity", "amount", "units", "money", "time", "supply"):
        assert banned not in props
    assert SHOCK_INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["additionalProperties"] is False


def test_shock_validator_rejects_infeasible_llm_intents(world):
    agent = world.agents["agent_2"]
    projects = {p.project_id: p for p in world.projects}
    state = ShockState()
    agent.materials = {m: 0.0 for m in agent.materials}

    accepted = validate_shock(
        agent,
        [
            Intent(action=ActionType.MAKE, target_project_id="proj_2"),
            Intent(action=ActionType.JOIN, target_agent_id="agent_999"),
            Intent(action=ActionType.PRACTICE, target_skill_id="skill_0"),
        ],
        projects, world.cfg, state,
    )
    reasons = [r for _, r in agent.rejected_intents]
    assert RejectionReason.INSUFFICIENT_MATERIAL in reasons
    assert RejectionReason.TARGET_NOT_NEIGHBOR in reasons
    assert [i.action for i in accepted] == [ActionType.PRACTICE]
    agent.rejected_intents.clear()


def test_agent_cannot_declare_supply_quantity():
    """Intent に供給量フィールドが存在しないこと（型レベルの担保）。"""
    import dataclasses
    names = {f.name for f in dataclasses.fields(Intent)}
    assert names == {"action", "target_agent_id", "target_project_id",
                     "target_skill_id", "target_method_id", "reason"}


# --- P0: transition 判定がコード側で行われる --------------------------------


def test_transition_thresholds_come_from_config(world):
    judge = TransitionJudge.from_config(world.cfg["shock"]["transition"])
    cfg = world.cfg["shock"]["transition"]
    assert judge.community_supply_share == cfg["community_supply_share"]
    assert judge.active_supplier_count == cfg["active_supplier_count"]


def test_transition_requires_all_four_conditions():
    judge = TransitionJudge(community_supply_share=0.2, active_supplier_count=3,
                            supply_duration_steps=2, coordination_edges=1)
    ledger = SupplyLedger(baseline_per_step=0.0)
    ledger.start_step()
    ledger.record_supply("a", 10.0, 0)          # share=1.0, suppliers=1, duration=1
    row = judge.evaluate(0, ledger, coordination_edges=5)
    assert row["met_community_supply_share"] and not row["all_met"]
    assert judge.transitioned_at is None

    # step1 で suppliers=3 かつ duration=2 となり、4条件すべてが揃う
    ledger.start_step()
    for aid in ("a", "b", "c"):
        ledger.record_supply(aid, 5.0, 1)
    row = judge.evaluate(1, ledger, coordination_edges=5)
    assert row["all_met"] and judge.transitioned_at == 1


def test_transition_is_not_decided_by_text():
    """LLM の文章では転化しないこと。judge は ledger と数値しか受け取らない。"""
    import inspect
    sig = inspect.signature(TransitionJudge.evaluate)
    assert set(sig.parameters) == {"self", "step", "ledger", "coordination_edges"}


def test_reconfiguration_time_is_none_when_no_transition():
    judge = TransitionJudge(1.0, 99, 99, 99)
    ledger = SupplyLedger(baseline_per_step=1.0)
    recon = reconfiguration_time(0, ledger, judge)
    assert recon["steps_to_transition"] is None
    assert recon["steps_to_first_community_supply"] is None


# --- P0: A/B/C/D の既存条件を壊さない --------------------------------------


def test_accumulation_phase_unchanged_by_m3_additions():
    """M3 の追加で蓄積相の結果が変わっていないこと。

    M3 は ActionType と config にキーを足したが、蓄積相の決定ルールは
    それらを提案しないため final_state_sha256 は変わらないはず。
    """
    from src.simulation.runner import run_one

    a = run_one(CONFIG_DIR / "condition_a.yaml", seed=1, steps=20)
    b = run_one(CONFIG_DIR / "condition_a.yaml", seed=1, steps=20)
    assert a["final_state_sha256"] == b["final_state_sha256"]

    c = run_one(CONFIG_DIR / "condition_c.yaml", seed=1, steps=20)
    assert a["base_graph_sha256"] == c["base_graph_sha256"], "A/C ペアリングが壊れた"
    assert a["agent_initial_states_sha256"] == c["agent_initial_states_sha256"]


def test_new_actions_have_time_costs(world):
    for action in ActionType:
        assert action.value in world.cfg["action_time_cost"], f"{action.value} の時間コストがない"


def test_shock_step_runs_without_llm(world, required):
    """pipeline がコード側だけでも一周すること（LLM なしのスモーク）。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=7)
    state = ShockState()
    ledger = SupplyLedger(baseline_per_step=w.cfg["shock"]["baseline_supply_per_step"])
    judge = TransitionJudge.from_config(w.cfg["shock"]["transition"])
    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}

    def fake_decide(obs):
        return [
            Intent(action=ActionType.MODIFY, target_project_id="proj_0", target_skill_id="attr_0"),
            Intent(action=ActionType.MAKE, target_project_id="proj_0"),
        ]

    ids = [a.id for a in list(w.agents.values())[:3]]
    row = shock_step(w, state, required, ledger, judge, fake_decide, ids, stats)
    assert row["step"] == 0
    assert state.modify_count == 3
    assert stats["actions"].get("modify") == 3
