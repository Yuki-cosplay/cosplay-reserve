"""T9: A/C および B/D の network identity、および次数保存。

★必須性質: A/C および B/D の network identity★

SPEC §19 の完全ペアリング要件:
  同一seedにおいて A と C は完全に同じ Graph object 由来、
  B と D は完全に同じ rewired graph 由来でなければならない。
  同じ生成アルゴリズムを使うだけでは不十分。
"""

from pathlib import Path

import pytest

from src.culture.network import graph_sha256
from src.world.world import build_all_conditions

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def worlds():
    return build_all_conditions(CONFIG_DIR, seed=42)


def test_a_and_c_share_the_same_graph(worlds):
    assert set(worlds["A"].graph.edges()) == set(worlds["C"].graph.edges())
    assert worlds["A"].provenance["base_graph_sha256"] == worlds["C"].provenance["base_graph_sha256"]


def test_b_and_d_share_the_same_graph(worlds):
    assert set(worlds["B"].graph.edges()) == set(worlds["D"].graph.edges())
    assert worlds["B"].provenance["base_graph_sha256"] == worlds["D"].provenance["base_graph_sha256"]


def test_structured_and_rewired_are_different(worlds):
    """rewire が実際に構造を壊していること（ペアリングが自明に成立していないこと）。"""
    assert set(worlds["A"].graph.edges()) != set(worlds["B"].graph.edges())


def test_degree_sequence_preserved(worlds):
    """A と B の次数列とエッジ数が一致すること（次数保存リワイヤリング）。

    add_skill_assortativity も double_edge_swap も次数保存型であるため（決定 W5）、
    structured と rewired は同一の次数列を持つ。
    """
    deg_a = sorted(d for _, d in worlds["A"].graph.degree())
    deg_b = sorted(d for _, d in worlds["B"].graph.degree())
    assert deg_a == deg_b
    assert worlds["A"].graph.number_of_edges() == worlds["B"].graph.number_of_edges()


def test_no_isolated_nodes_and_layers_are_subsets(worlds):
    """C/D は孤立ノードの世界ではない。cultural_peers は known_agents の部分集合。"""
    for c, w in worlds.items():
        for a in w.agents.values():
            assert a.known_agents, f"条件{c} の {a.id} が孤立している"
            assert a.cultural_peers <= a.known_agents
            if not a.is_participant:
                assert not a.cultural_peers, "non-participant に cultural edge がある"


def test_nonparticipants_keep_social_contact(worlds):
    """non-participant も一般社会接触を持つ（§3.4.3）。"""
    for c, w in worlds.items():
        nps = [a for a in w.agents.values() if not a.is_participant]
        assert nps, "non-participant が存在しない"
        assert all(a.known_agents for a in nps), f"条件{c} で non-participant が孤立している"


def test_graph_hash_is_sensitive(worlds):
    """ハッシュが構造の違いを検出できること（定数を返していないことの確認）。"""
    assert graph_sha256(worlds["A"].graph) != graph_sha256(worlds["B"].graph)
