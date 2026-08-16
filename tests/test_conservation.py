"""T4 / T12: 保存則と材料の外生補充（§9、決定 D13 / Y1）。"""

from pathlib import Path

import pytest

from src.common.config import load_config
from src.world.step import step
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.mark.parametrize("condition", ["a", "b", "c", "d"])
def test_materials_stay_within_bounds(condition):
    w = build_world(CONFIG_DIR / f"condition_{condition}.yaml", seed=42)
    cap = w.cfg["materials"]["inventory_cap"]
    for _ in range(60):
        step(w)
        for a in w.agents.values():
            for m, v in a.materials.items():
                assert v >= 0.0, f"{a.id}.{m} が負になった: {v}"
                assert v <= cap[m] + 1e-9, f"{a.id}.{m} が cap を超えた: {v}"


def test_replenish_settings_identical_across_conditions():
    cfgs = [load_config(CONFIG_DIR / f"condition_{c}.yaml") for c in "abcd"]
    ref = cfgs[0]["materials"]
    for cfg in cfgs[1:]:
        assert cfg["materials"] == ref, "材料設定が条件間で異なる"


def test_skills_stay_within_unit_interval():
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    for _ in range(60):
        step(w)
        for a in w.agents.values():
            for s, v in a.skills.items():
                assert 0.0 <= v <= 1.0, f"{a.id}.{s} が範囲外: {v}"


def test_time_budget_never_exceeded():
    """1 step の消費時間が time_budget を超えないこと（Validator の担保）。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    budget = w.cfg["agent_init"]["traits"]["time_budget"]["value"]
    costs = w.cfg["action_time_cost"]
    n_agents = len(w.agents)
    for _ in range(30):
        s = step(w)
        assert s.time_total <= budget * n_agents + 1e-9


def test_no_money_attribute_appears():
    """決定 D8: money は M1 の因果モデルに存在しない。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    for _ in range(10):
        step(w)
    for a in w.agents.values():
        assert not hasattr(a, "money")
