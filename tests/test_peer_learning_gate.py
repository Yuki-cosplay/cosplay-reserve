"""T11: peer learning の遮断点（docs/DESIGN_M1.md §8）。

★必須性質: peer-learning ON/OFF の遮断点の正しさ★

§8.4 manipulation check:
  - method_peer_acquisition は C/D で常に厳密に 0
  - 同時に observe / ask / share の実行回数は C/D でも 0 より大きい

片方でも破れていれば、操作が意図と違うものになっている。
"""

from pathlib import Path

import pytest

from src.world.step import step
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
STEPS = 60


def _run(condition: str, seed: int = 42):
    w = build_world(CONFIG_DIR / f"condition_{condition}.yaml", seed=seed)
    peer, self_disc = 0, 0
    actions: dict[str, int] = {}
    for _ in range(STEPS):
        s = step(w)
        peer += s.peer_acquired
        self_disc += s.self_discovered
        for a, n in s.action_counts.items():
            actions[a] = actions.get(a, 0) + n
    return w, peer, self_disc, actions


@pytest.mark.parametrize("condition", ["c", "d"])
def test_no_peer_method_transfer_when_disabled(condition):
    w, peer, _, _ = _run(condition)
    assert peer == 0, f"条件{condition.upper()} で peer 取得が発生している: {peer}"
    for a in w.agents.values():
        held = [m for m in a.methods.values() if m.is_peer_acquired]
        assert not held, f"{a.id} が peer 由来 Method を保持している"


@pytest.mark.parametrize("condition", ["c", "d"])
def test_social_contact_survives_when_peer_learning_disabled(condition):
    """C/D は「ネットワークを除去した世界」ではない（SPEC §19）。"""
    _, _, self_disc, actions = _run(condition)
    for act in ("observe", "ask", "share"):
        assert actions.get(act, 0) > 0, f"条件{condition.upper()} で {act} が発生していない"
    assert self_disc > 0, "自己発見が発生していない（self-scaffolding が死んでいる）"


@pytest.mark.parametrize("condition", ["a", "b"])
def test_peer_transfer_happens_when_enabled(condition):
    _, peer, _, _ = _run(condition)
    assert peer > 0, f"条件{condition.upper()} で peer 取得が発生していない"


def test_perceived_skills_update_in_all_conditions():
    """ask/observe による信念更新は全条件で有効（§8.1）。"""
    for c in ("a", "b", "c", "d"):
        w, _, _, _ = _run(c)
        updated = sum(1 for a in w.agents.values() if a.perceived_skills)
        assert updated > 0, f"条件{c.upper()} で perceived_skills が更新されていない"


def test_trust_never_changes():
    """trust は M1 では固定値。更新式を実装しない（trust 最終仕様）。"""
    for c in ("a", "c"):
        w = build_world(CONFIG_DIR / f"condition_{c}.yaml", seed=42)
        before = {a.id: dict(a.trust) for a in w.agents.values()}
        for _ in range(30):
            step(w)
        for a in w.agents.values():
            assert a.trust == before[a.id], f"{a.id} の trust が変化した"
