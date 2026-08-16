"""P0回帰テスト: ショック対象 Agent 選出とペアリングの同一性（2026-08-16）。

修正前は「蓄積相後の技能上位 n 名」で選出していたため、peer_learning の有無で
技能が分岐し、同一 seed でも A≠C / B≠D の Agent 集合になっていた。
その結果 structural_coordination_capacity が A/C・B/D で一致せず、
SPEC §19 の完全ペアリングが実質的に破れていた。

すべて deterministic。LLM API を呼ばない。
"""

import hashlib
from pathlib import Path

import pytest

from src.common.rng import ROOT_STREAM_ORDER, make_streams
from src.simulation.transition import structural_coordination_capacity
from src.world.shock import select_shock_agents
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
SEEDS = [1, 2, 3, 5, 11]
N_AGENTS = 6


def _facts(condition: str, seed: int) -> dict:
    w = build_world(CONFIG_DIR / f"condition_{condition.lower()}.yaml", seed=seed)
    ids = select_shock_agents(w, N_AGENTS)
    sub = sorted(sorted(e) for e in w.graph.subgraph(ids).edges())
    return {
        "shock_agent_ids": tuple(ids),
        "graph_hash": w.provenance["base_graph_sha256"],
        "pre_network_hash": w.provenance["agent_initial_states_sha256"],
        "induced_subgraph_hash": hashlib.sha256(repr(sub).encode()).hexdigest(),
        "capacity": structural_coordination_capacity(w.graph, ids, 2)[
            "structurally_available_pairs"
        ],
    }


@pytest.fixture(scope="module")
def facts():
    return {seed: {c: _facts(c, seed) for c in "ABCD"} for seed in SEEDS}


@pytest.mark.parametrize("seed", SEEDS)
def test_shock_agent_ids_identical_across_all_conditions(seed, facts):
    ids = {c: facts[seed][c]["shock_agent_ids"] for c in "ABCD"}
    assert len(set(ids.values())) == 1, f"seed {seed}: 条件で選出が異なる {ids}"
    assert len(ids["A"]) == N_AGENTS


@pytest.mark.parametrize("seed", SEEDS)
def test_capacity_A_equals_C_and_B_equals_D(seed, facts):
    f = facts[seed]
    assert f["A"]["capacity"] == f["C"]["capacity"], f"seed {seed}: capacity A != C"
    assert f["B"]["capacity"] == f["D"]["capacity"], f"seed {seed}: capacity B != D"


@pytest.mark.parametrize("seed", SEEDS)
def test_graph_hash_A_equals_C_and_B_equals_D(seed, facts):
    f = facts[seed]
    assert f["A"]["graph_hash"] == f["C"]["graph_hash"]
    assert f["B"]["graph_hash"] == f["D"]["graph_hash"]


@pytest.mark.parametrize("seed", SEEDS)
def test_induced_subgraph_A_equals_C_and_B_equals_D(seed, facts):
    f = facts[seed]
    assert f["A"]["induced_subgraph_hash"] == f["C"]["induced_subgraph_hash"]
    assert f["B"]["induced_subgraph_hash"] == f["D"]["induced_subgraph_hash"]


@pytest.mark.parametrize("seed", SEEDS)
def test_pre_network_initial_state_identical_across_conditions(seed, facts):
    hashes = {facts[seed][c]["pre_network_hash"] for c in "ABCD"}
    assert len(hashes) == 1, f"seed {seed}: pre-network 初期状態が条件間で不一致"


@pytest.mark.parametrize("seed", SEEDS)
def test_structured_and_rewired_still_differ(seed, facts):
    """ペアリングを直した結果、A と B が同一になってしまっていないこと。"""
    f = facts[seed]
    assert f["A"]["graph_hash"] != f["B"]["graph_hash"]


# --- 選出が条件・技能に依存しないことの構造的担保 --------------------------


def test_selection_does_not_depend_on_skills():
    """技能を書き換えても選出が変わらないこと（技能非依存の担保）。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=3)
    before = select_shock_agents(build_world(CONFIG_DIR / "condition_a.yaml", seed=3), N_AGENTS)
    for a in w.agents.values():
        for s in a.skills:
            a.skills[s] = 0.99 if a.id.endswith("1") else 0.01
    assert select_shock_agents(w, N_AGENTS) == before


def test_selection_uses_dedicated_stream():
    """選出は専用ストリームから行われ、他ストリームを消費しない。"""
    assert ROOT_STREAM_ORDER[4] == "shock_agents"
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=3)
    sim_before = w.rng["simulation"].bit_generator.state
    init_before = w.rng["agent_init"].bit_generator.state
    select_shock_agents(w, N_AGENTS)
    assert w.rng["simulation"].bit_generator.state == sim_before
    assert w.rng["agent_init"].bit_generator.state == init_before


def test_adding_stream_preserves_existing_streams():
    """末尾追加により index 0〜3 の子ストリームが不変であること（既存 run の再現性）。"""
    import numpy as np

    four = [c.spawn_key for c in np.random.SeedSequence(42).spawn(4)]
    five = [c.spawn_key for c in np.random.SeedSequence(42).spawn(5)]
    assert five[:4] == four


def test_selection_only_returns_participants():
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=5)
    ids = select_shock_agents(w, N_AGENTS)
    assert all(w.agents[i].is_participant for i in ids)
    assert len(set(ids)) == N_AGENTS
