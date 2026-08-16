"""T3: Information Locality（SPEC §14）。

準必須性質: Observation への World 参照・条件情報の混入は、答えの漏洩であると
同時に「C/D の Agent が条件を知って振る舞いを変える」＝条件交絡になる。

Observation に入れてはならないもの:
  World 参照 / 他Agentの真値 / peer_learning_enabled / is_participant / cultural_peers
"""

import dataclasses
from pathlib import Path

import pytest

from src.agents.observation import (
    FORBIDDEN_OBSERVATION_FIELDS,
    Observation,
    build_observation,
)
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture(scope="module")
def world():
    return build_world(CONFIG_DIR / "condition_c.yaml", seed=42)


def test_observation_has_no_forbidden_fields():
    names = {f.name for f in dataclasses.fields(Observation)}
    leaked = names & FORBIDDEN_OBSERVATION_FIELDS
    assert not leaked, f"Observation に禁止フィールドがある: {leaked}"


def test_observation_carries_no_world_or_agent_objects(world):
    from src.agents.agent import Agent
    from src.world.world import World

    obs = build_observation(world, world.agents["agent_0"])
    for f in dataclasses.fields(obs):
        value = getattr(obs, f.name)
        assert not isinstance(value, (World, Agent))
        if isinstance(value, (tuple, list)):
            assert not any(isinstance(v, (World, Agent)) for v in value)
        if isinstance(value, dict):
            assert not any(isinstance(v, (World, Agent)) for v in value.values())


def test_neighbors_limited_to_known_agents(world):
    for agent in world.agents.values():
        obs = build_observation(world, agent)
        assert set(obs.neighbors) == agent.known_agents


def test_no_true_skills_of_others(world):
    """他Agentの技能の真値が Observation に現れないこと。

    perceived_neighbor_skills は信念であり、M1 の初期状態では空である。
    真値が混入していれば、他Agentの skills dict と一致してしまう。
    """
    obs = build_observation(world, world.agents["agent_0"])
    others = {a.id: a.skills for a in world.agents.values() if a.id != "agent_0"}
    for oid, true_skills in others.items():
        assert obs.perceived_neighbor_skills.get(oid) != true_skills


def test_observation_is_frozen():
    """Observation が不変であること（decide() が世界を書き換えられない構造的担保）。"""
    assert Observation.__dataclass_params__.frozen
