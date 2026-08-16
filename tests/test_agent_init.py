"""T13: Agent 初期化の最低要件（決定 X2、§15.1 の7要件）。"""

from pathlib import Path

import numpy as np
import pytest

from src.world.world import build_all_conditions

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def worlds():
    return build_all_conditions(CONFIG_DIR, seed=42)


def test_req1_all_agents_start_as_consumer(worlds):
    """要件1: 初期状態で Consumer が 90% 以上。

    決定 Z1 により Customizer は n_projects >= 1 のみで判定するため、
    初期状態（n_projects=0）では構成上 100% になる。
    """
    w = worlds["A"]
    consumers = sum(1 for a in w.agents.values() if a.maker_stage.value == "consumer")
    assert consumers / len(w.agents) >= 0.90
    assert consumers == len(w.agents), "決定 Z1 のもとでは 100% になるはず"


def test_req2_participation_level_has_variance(worlds):
    w = worlds["A"]
    values = [a.participation_level for a in w.agents.values() if a.is_participant]
    assert np.std(values) > 0.05, f"participation_level の分散が小さすぎる: {np.std(values)}"


def test_req3_low_participation_stratum_exists(worlds):
    """要件3: participant 下位20% に低participation層が存在すること。"""
    w = worlds["A"]
    values = sorted(a.participation_level for a in w.agents.values() if a.is_participant)
    p20 = np.percentile(values, 20)
    assert p20 < 0.30, f"下位20%点が高すぎる（低participation層がない）: {p20}"


def test_req4_same_distribution_source_for_both_groups(worlds):
    """要件4: 5項目が participant / non-participant で同一分布（決定 W3・V4・P1）。

    対象: skills / assets / sharing_tendency / imitation_tendency / helping_norm

    participation_level は検証対象に含めない。決定 X3・Z3 により、これは
    participant / non-participant で意図的に差を付けた唯一の項目である。
    同一分布であることを検証すると、設計そのものと矛盾してテストが必ず落ちる。

    materials / time_budget / trust_fixed も対象外。全Agent共通の固定値であり
    群ごとに引くものではないため、要件7 で検証する（決定 V4・P1）。

    統計検定ではなく、同じ config キーから引いていることを構造的に検証する。
    """
    init = worlds["A"].cfg["agent_init"]
    # participant / non-participant で別のキーを持つのは participation_level のみ
    group_specific = {
        k for k in init["traits"] if k.startswith("nonparticipant_")
    }
    assert group_specific == {"nonparticipant_participation_level"}, group_specific

    for key in ("sharing_tendency", "imitation_tendency", "helping_norm"):
        assert f"nonparticipant_{key}" not in init["traits"]
    assert "participant" not in str(init["skills"])
    assert "participant" not in str(init["assets"])


def test_req5_agents_built_before_network(worlds):
    """要件5: Agent 生成が network 生成前に完了していること。

    pre-network ハッシュが network 由来フィールドを含まないことで構造的に担保する。
    """
    from src.agents.agent import NETWORK_DERIVED_FIELDS, pre_network_state

    state = pre_network_state(worlds["A"].agents)
    for entry in state:
        for f in NETWORK_DERIVED_FIELDS:
            assert f not in entry, f"pre-network 状態に network 由来フィールド {f} がある"


def test_req6_pre_network_state_identical_across_conditions(worlds):
    hashes = {c: w.provenance["agent_initial_states_sha256"] for c, w in worlds.items()}
    assert len(set(hashes.values())) == 1, hashes


def test_req7_uniform_scalars(worlds):
    """要件7: time_budget / trust_fixed / materials が全Agent同一（決定 V4・P1）。"""
    w = worlds["A"]
    agents = list(w.agents.values())

    assert len({a.time_budget for a in agents}) == 1

    trust_values = {v for a in agents for v in a.trust.values()}
    assert len(trust_values) == 1, f"trust が全Agent同一でない: {trust_values}"

    ref_materials = agents[0].materials
    assert all(a.materials == ref_materials for a in agents)


def test_skills_within_unit_interval(worlds):
    for a in worlds["A"].agents.values():
        assert all(0.0 <= v <= 1.0 for v in a.skills.values())


def test_no_money_field():
    """決定 D8: money は M1 の因果モデルに存在しない。フィールドごと持たない。"""
    import dataclasses

    from src.agents.agent import Agent

    names = {f.name for f in dataclasses.fields(Agent)}
    assert "money" not in names
    assert "alive" not in names and "joined_step" not in names  # 決定 D7
