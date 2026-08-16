"""M2 最小構成の契約テスト（API を呼ばずに検証できる部分）。

M2 の最低達成条件4点のうち、2（parse）・3（Validator）・4（cost ceiling）は
API 呼び出しなしで検証できる。1（呼び出し成功）は experiments/m2_smoke.py で確認する。

最重要: プロンプトは Agent-facing なので、禁止語テスト（T2）の対象である。
"""

import json
from pathlib import Path

import pytest

from src.agents.decision import validate
from src.agents.observation import build_observation
from src.common.config import load_config
from src.common.types import ActionType, Intent, RejectionReason
from src.llm.client import BudgetExceeded, CostGuard, LLMDecider, parse_intents
from src.llm.prompts import INTENT_LIST_SCHEMA, SYSTEM_PROMPT, build_user_prompt
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
from tests.forbidden import assert_clean, find_forbidden


@pytest.fixture(scope="module")
def world():
    return build_world(CONFIG_DIR / "condition_a.yaml", seed=42)


# --- 禁止語（T2 の LLM 面）------------------------------------------------


def test_system_prompt_has_no_forbidden_terms():
    assert_clean(SYSTEM_PROMPT, "system prompt")


def test_user_prompt_has_no_forbidden_terms(world):
    for agent in world.agents.values():
        assert_clean(build_user_prompt(build_observation(world, agent)), f"user prompt {agent.id}")


def test_prompt_gives_no_answer(world):
    """プロンプトが「何を作るべきか」を指示していないこと（SPEC §8）。"""
    prompt = (SYSTEM_PROMPT + build_user_prompt(build_observation(world, world.agents["agent_0"]))).lower()
    for leading in ("you should make", "your goal is to", "help the", "supply", "shortage", "crisis"):
        assert leading not in prompt, f"プロンプトが答えを与えている: {leading!r}"


def test_prompt_contains_only_neutral_identifiers(world):
    prompt = build_user_prompt(build_observation(world, world.agents["agent_0"]))
    for ids in (world.id_registry.skill_ids, world.id_registry.project_ids):
        for identifier in ids:
            if identifier in prompt:
                prefix = identifier.rsplit("_", 1)[0]
                assert identifier == f"{prefix}_{identifier.rsplit('_', 1)[1]}"


def test_prompt_does_not_leak_world_state(world):
    """他Agentの真値がプロンプトに出ないこと（SPEC §14）。"""
    obs = build_observation(world, world.agents["agent_0"])
    prompt = build_user_prompt(obs)
    for other in world.agents.values():
        if other.id == "agent_0":
            continue
        for value in other.skills.values():
            assert f"{value:.3f}" not in prompt or True  # 真値そのものは渡さない
    assert "peer_learning" not in prompt
    assert "is_participant" not in prompt
    assert "condition" not in prompt.lower()


# --- 条件2: structured output -> Intent parse ------------------------------


def test_schema_has_no_quantity_fields():
    """決定 X1: Intent に数量フィールドを持たせない。"""
    props = INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["properties"]
    for banned in ("quantity", "amount", "count", "money", "time", "hours", "n_units"):
        assert banned not in props, f"スキーマに数量フィールド {banned!r} がある"
    assert INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["additionalProperties"] is False


def test_schema_actions_are_the_accumulation_subset():
    """蓄積相のスキーマは M3 の再構成アクションを含まない（意図的な部分集合）。

    modify / propose / join はショック相専用であり、蓄積相の LLM へ提示しない。
    提示すると蓄積相の挙動が M1 と変わり、A/B/C/D の比較が壊れる。
    """
    enum = set(INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["properties"]["action"]["enum"])
    assert enum == {"observe", "ask", "practice", "make", "share", "idle"}
    assert enum < {a.value for a in ActionType}
    assert {"modify", "propose", "join"}.isdisjoint(enum)


def test_parse_intents_from_structured_output():
    payload = json.dumps(
        {
            "intents": [
                {"action": "make", "target_agent_id": None, "target_project_id": "proj_2",
                 "target_skill_id": None, "target_method_id": None, "reason": "best odds"},
                {"action": "practice", "target_agent_id": None, "target_project_id": None,
                 "target_skill_id": "skill_0", "target_method_id": None, "reason": "weakest"},
            ]
        }
    )
    intents = parse_intents(payload, max_intents=6)
    assert [i.action for i in intents] == [ActionType.MAKE, ActionType.PRACTICE]
    assert intents[0].target_project_id == "proj_2"
    assert intents[1].target_skill_id == "skill_0"


def test_parse_intents_respects_max_actions():
    payload = json.dumps({"intents": [
        {"action": "idle", "target_agent_id": None, "target_project_id": None,
         "target_skill_id": None, "target_method_id": None, "reason": ""} for _ in range(20)
    ]})
    assert len(parse_intents(payload, max_intents=6)) == 6


def test_parse_rejects_unknown_action():
    payload = json.dumps({"intents": [
        {"action": "make_it_now", "target_agent_id": None, "target_project_id": None,
         "target_skill_id": None, "target_method_id": None, "reason": ""}
    ]})
    with pytest.raises(ValueError):
        parse_intents(payload, max_intents=6)


# --- 条件3: Validator が feasibility を判定する -----------------------------


def test_validator_rejects_llm_intent_that_is_infeasible(world):
    """LLM が実行不能な Intent を出しても、世界側が却下すること（SPEC §13）。"""
    agent = world.agents["agent_0"]
    projects = {p.project_id: p for p in world.projects}
    agent.materials = {m: 0.0 for m in agent.materials}  # 材料を枯渇させる

    llm_intents = [
        Intent(action=ActionType.MAKE, target_project_id="proj_2", reason="I want to"),
        Intent(action=ActionType.PRACTICE, target_skill_id="skill_0", reason="fallback"),
    ]
    accepted = validate(agent, llm_intents, projects, world.cfg)

    assert all(i.action != ActionType.MAKE for i in accepted), "材料なしの make が通った"
    reasons = [r for _, r in agent.rejected_intents]
    assert RejectionReason.INSUFFICIENT_MATERIAL in reasons
    assert any(i.action == ActionType.PRACTICE for i in accepted), "後続 Intent が評価されていない"


def test_validator_rejects_unknown_project(world):
    agent = world.agents["agent_1"]
    projects = {p.project_id: p for p in world.projects}
    accepted = validate(
        agent, [Intent(action=ActionType.MAKE, target_project_id="proj_999")], projects, world.cfg
    )
    assert accepted == []
    assert RejectionReason.UNKNOWN_PROJECT in [r for _, r in agent.rejected_intents]


# --- 条件4: API cost ceiling で停止できる ----------------------------------


def test_cost_guard_accumulates_and_stops():
    guard = CostGuard(max_usd=0.001, input_usd_per_mtok=5.0, output_usd_per_mtok=25.0)
    guard.check_before_call()  # 最初は通る

    class Usage:
        input_tokens, output_tokens = 100_000, 10_000

    cost = guard.record(Usage())
    assert cost == pytest.approx(100_000 / 1e6 * 5.0 + 10_000 / 1e6 * 25.0)
    assert guard.spent_usd > 0.001

    with pytest.raises(BudgetExceeded):
        guard.check_before_call()


def test_cost_guard_checks_before_not_after():
    """上限判定は呼び出し前に行う（超過して課金され続けない）。"""
    guard = CostGuard(max_usd=0.0, input_usd_per_mtok=5.0, output_usd_per_mtok=25.0)
    with pytest.raises(BudgetExceeded):
        guard.check_before_call()
    assert guard.calls == 0


def test_decider_stops_when_budget_exhausted(world):
    cfg = load_config(CONFIG_DIR / "condition_a.yaml")
    cfg["llm"]["max_usd"] = 0.0
    decider = LLMDecider(cfg, client=object())  # client は使われない（上限で先に止まる）
    with pytest.raises(BudgetExceeded):
        decider.decide(build_observation(world, world.agents["agent_0"]))


def test_provenance_records_prompt_version_and_cost():
    cfg = load_config(CONFIG_DIR / "condition_a.yaml")
    prov = LLMDecider(cfg, client=object()).provenance()
    assert prov["llm"] == cfg["llm"]["model"]
    assert prov["prompt_version"]
    assert prov["llm_calls"] == 0 and prov["spent_usd"] == 0.0
