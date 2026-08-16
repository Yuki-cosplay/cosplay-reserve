"""T1（S4 時点の部分版, T1p): 構築フェーズの決定論性。

★必須性質: deterministic reproducibility★

step ループは S10 で実装するため、S4 時点では
「同一 seed で World を2回構築すると初期状態・グラフが完全一致する」
までを検証する。S10 で final_state_sha256 の一致に拡張する。
"""

from pathlib import Path

from src.world.world import build_all_conditions, build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def test_same_seed_reproduces_identical_world():
    for c in ("A", "B", "C", "D"):
        path = CONFIG_DIR / f"condition_{c.lower()}.yaml"
        w1 = build_world(path, seed=42)
        w2 = build_world(path, seed=42)
        assert w1.provenance == w2.provenance, f"条件{c} が再現しない"
        assert set(w1.graph.edges()) == set(w2.graph.edges())


def test_different_seed_changes_graph():
    """seed が効いていること（決定論性が「常に同じ定数」で成立していないことの確認）。"""
    a42 = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    a43 = build_world(CONFIG_DIR / "condition_a.yaml", seed=43)
    assert a42.provenance["base_graph_sha256"] != a43.provenance["base_graph_sha256"]


def test_stream_isolation_agent_init_independent_of_network():
    """network ストリームの消費が変わっても agent_init が汚染されないこと（§12.1）。

    条件によって network の消費は変わる（rewired は double_edge_swap を行う）が、
    agent_init 由来の pre-network 状態は4条件で同一でなければならない。
    """
    worlds = build_all_conditions(CONFIG_DIR, seed=7)
    hashes = {c: w.provenance["agent_initial_states_sha256"] for c, w in worlds.items()}
    assert len(set(hashes.values())) == 1, hashes
