"""T15: is_participant の割り当て規則（決定 V1）。

準必須性質: T15-② が崩れると V1 の density 交絡が復活し、
freeze 解除事由の P0「条件交絡」に直接該当する。

検証は2項目のみ。cultural_edge_count の条件間差は §13.2 により
テストにしない（合否判定を持たせると seed 除外の運用につながるため）。
"""

from pathlib import Path

import pytest

from src.world.world import build_all_conditions

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def worlds():
    return build_all_conditions(CONFIG_DIR, seed=42)


def test_assignment_identical_across_conditions(worlds):
    """① is_participant の割り当てが A/B/C/D で完全一致すること。"""
    ref = {a.id for a in worlds["A"].agents.values() if a.is_participant}
    for c, w in worlds.items():
        got = {a.id for a in w.agents.values() if a.is_participant}
        assert got == ref, f"条件{c} の participant 集合が A と異なる"


def test_participant_count_matches_config(worlds):
    w = worlds["A"]
    expected = w.cfg["world"]["n_participant_agents"]
    assert sum(1 for a in w.agents.values() if a.is_participant) == expected


@pytest.mark.parametrize("seed", [1, 2, 3, 42, 99])
def test_participants_not_contiguous_on_ring(seed):
    """② participant の agent_id がノード番号順に連続していないこと。

    ノード番号はリング格子上の位置そのものである。連番の先頭 N 名を
    participant にすると、participant がリング上で連続した弧を占め、
    条件A で cultural edge が密・条件B で疎になって topology 主効果が交絡する。
    """
    w = build_all_conditions(CONFIG_DIR, seed=seed)["A"]
    idx = sorted(int(a.id.split("_")[1]) for a in w.agents.values() if a.is_participant)
    n_participants = len(idx)

    # 連番ブロック（0..n-1 や任意の連続区間）でないこと
    assert idx != list(range(n_participants)), "participant が先頭連番に割り当てられている"
    assert idx != list(range(idx[0], idx[0] + n_participants)), "participant が連続区間を占めている"

    # non-participant がリング上に散らばっていること。
    # 連続弧なら non-participant の隣接ギャップは1箇所に集中する。
    non_idx = sorted(
        int(a.id.split("_")[1]) for a in w.agents.values() if not a.is_participant
    )
    assert len(non_idx) >= 2
    # non-participant のうち、隣り合う番号でないものが複数あること
    breaks = sum(1 for a, b in zip(non_idx, non_idx[1:]) if b - a > 1)
    assert breaks >= 2, f"non-participant がリング上で塊になっている: {non_idx}"


def test_cultural_edge_count_is_recorded(worlds):
    """条件間差は判定しない。記録されていることだけを確認する（§13.2 / §10.4）。"""
    for c, w in worlds.items():
        assert "cultural_edge_count" in w.provenance
        assert isinstance(w.provenance["cultural_edge_count"], int)
