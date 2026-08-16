"""T6: Consumer -> Customizer -> Maker の遷移（SPEC §28 の M1 目標）。

決定 Z1 により Customizer は n_projects >= 1 のみで判定する。
「履歴」と「現在の能力」の非対称:
  Customizer = 行動したことがあるか -> 不可逆
  Maker 以上 = 現在その能力があるか -> 可逆
"""

import copy
from pathlib import Path

from src.agents.agent import Agent
from src.common.types import MakerStage
from src.culture.capability import judge_maker_stage
from src.world.step import step
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def _agent(w) -> Agent:
    return next(iter(w.agents.values()))


def test_fixed_scenario_stage_ladder():
    """固定シナリオで各段階の判定を直接確認する。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    cfg, a = w.cfg, copy.deepcopy(_agent(w))

    a.completed_projects = []
    for s in a.skills:
        a.skills[s] = 0.9
    assert judge_maker_stage(a, cfg) == MakerStage.CONSUMER, "技能だけでは Customizer にならない"

    a.completed_projects = [(0, "proj_0")]
    assert judge_maker_stage(a, cfg) == MakerStage.CUSTOMIZER

    a.completed_projects = [(0, "proj_0")] * cfg["stage_thresholds"]["maker_projects"]
    assert judge_maker_stage(a, cfg) == MakerStage.MAKER


def test_customizer_is_irreversible_but_maker_is_not():
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    cfg, a = w.cfg, copy.deepcopy(_agent(w))
    a.completed_projects = [(0, "proj_0")] * 5
    for s in a.skills:
        a.skills[s] = 0.9
    assert judge_maker_stage(a, cfg) == MakerStage.MAKER

    # 技能が減衰しても、経歴は消えないので Customizer までしか落ちない
    for s in a.skills:
        a.skills[s] = 0.01
    assert judge_maker_stage(a, cfg) == MakerStage.CUSTOMIZER


def test_transition_fires_in_simulation():
    """実行中に実際に Consumer -> Customizer -> Maker が発火すること。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    assert all(a.maker_stage == MakerStage.CONSUMER for a in w.agents.values())

    seen = set()
    for _ in range(156):
        step(w)
        seen.update(a.maker_stage for a in w.agents.values())

    assert MakerStage.CUSTOMIZER in seen, "Customizer が一度も発火しなかった"
    assert MakerStage.MAKER in seen, "Maker が一度も発火しなかった"


def test_nonparticipants_remain_consumer():
    """決定 Z3: non-participant は M1 では構造的に不活性である。"""
    w = build_world(CONFIG_DIR / "condition_a.yaml", seed=42)
    for _ in range(156):
        step(w)
    for a in w.agents.values():
        if not a.is_participant:
            assert a.maker_stage == MakerStage.CONSUMER
            assert not a.completed_projects
