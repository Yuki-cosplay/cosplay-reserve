"""T5: A/B/C/D の pre-network 初期Agent状態・Projectカタログが完全一致すること。

★必須性質: A/B/C/D pre-network initial-state invariance★

一致しなければ、条件分岐が Agent 初期化へ漏れている。
決定 Y6 により、ハッシュ対象に network 由来フィールドを含めない。
"""

from pathlib import Path

import pytest

from src.agents.agent import agent_initial_states_sha256, pre_network_state
from src.common.config import CONDITION_OVERRIDE_KEYS, load_config
from src.world.world import build_all_conditions

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
CONDITIONS = ("A", "B", "C", "D")


@pytest.fixture(scope="module")
def worlds():
    return build_all_conditions(CONFIG_DIR, seed=42)


def test_pre_network_agent_states_identical(worlds):
    hashes = {c: worlds[c].provenance["agent_initial_states_sha256"] for c in CONDITIONS}
    assert len(set(hashes.values())) == 1, f"pre-network 初期状態が条件間で不一致: {hashes}"


def test_pre_network_state_field_by_field(worlds):
    """ハッシュだけでなく中身も比較する（ハッシュ実装の誤りを検出するため）。"""
    ref = pre_network_state(worlds["A"].agents)
    for c in ("B", "C", "D"):
        assert pre_network_state(worlds[c].agents) == ref, f"条件{c} の初期状態が A と異なる"


def test_participant_assignment_identical(worlds):
    ref = worlds["A"].provenance["participant_ids_sha256"]
    for c in CONDITIONS:
        assert worlds[c].provenance["participant_ids_sha256"] == ref


def test_project_catalog_identical(worlds):
    ref = worlds["A"].projects
    for c in CONDITIONS:
        assert worlds[c].projects == ref, f"条件{c} の Project カタログが A と異なる"


def test_config_differs_only_in_two_keys():
    """条件間の差分が topology / peer_learning_enabled / condition のみであること。"""
    cfgs = {c: load_config(CONFIG_DIR / f"condition_{c.lower()}.yaml") for c in CONDITIONS}
    ref = cfgs["A"]
    for c in ("B", "C", "D"):
        diff = {k for k in ref if ref[k] != cfgs[c][k]}
        assert diff <= CONDITION_OVERRIDE_KEYS, f"条件{c} が余分なキーで A と異なる: {diff}"


def test_seed_variation_changes_state():
    """別 seed では初期状態が変わること（ハッシュが定数を返していないことの確認）。"""
    w42 = build_all_conditions(CONFIG_DIR, seed=42)["A"]
    w43 = build_all_conditions(CONFIG_DIR, seed=43)["A"]
    assert agent_initial_states_sha256(w42.agents) != agent_initial_states_sha256(w43.agents)
