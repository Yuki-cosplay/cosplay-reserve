"""trace logging がシミュレーション結果を変えないことの回帰テスト。

trace は**観測専用**であり、RNG を消費せず状態も変更しない。
その保証は「安全に見えるコードだから」ではなく、
**hash が既存正典と一致すること**で与える。

API / LLM を呼ばない。
"""

import csv
import json
from pathlib import Path

import pytest

from src.simulation.runner import run_one
from src.simulation.trace import ALLOWED_ACTIONS, TraceRecorder
from src.world.world import build_world

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "outputs" / "m1_main_summary.csv"
VERIFY = ROOT / "figures" / "demo_video" / "data" / "m1_trace" / "hash_verification.json"


@pytest.fixture(scope="module")
def canon():
    if not CANON.exists():
        pytest.skip("正典 summary がない")
    return {(int(r["seed"]), r["condition"]): r
            for r in csv.DictReader(CANON.open(encoding="utf-8"))}


def test_world_trace_defaults_to_none():
    """既定では観測装置が付かない = 全実験は追加前と同一経路を通る。"""
    w = build_world("configs/condition_a.yaml", seed=1)
    assert w.trace is None


@pytest.mark.parametrize("condition,seed", [("a", 1), ("c", 2), ("b", 3), ("d", 4)])
def test_trace_enabled_matches_canonical_hash(condition, seed, canon, tmp_path):
    """trace を有効にしても final_state_sha256 が正典と一致すること。"""
    s = run_one(f"configs/condition_{condition.lower()}.yaml", seed=seed,
                trace_dir=tmp_path)
    ref = canon[(seed, condition.upper())]
    assert s["final_state_sha256"] == ref["final_state_sha256"]
    assert s["agent_initial_states_sha256"] == ref["agent_initial_states_sha256"]
    assert s["base_graph_sha256"] == ref["base_graph_sha256"]


@pytest.mark.parametrize("condition,seed", [("a", 1), ("c", 2)])
def test_trace_on_equals_trace_off(condition, seed, tmp_path):
    """trace の有無で結果が変わらないこと（正典に依存しない直接比較）。"""
    off = run_one(f"configs/condition_{condition}.yaml", seed=seed)
    on = run_one(f"configs/condition_{condition}.yaml", seed=seed, trace_dir=tmp_path)
    assert off["final_state_sha256"] == on["final_state_sha256"]


def test_trace_module_imports_no_rng_or_llm():
    """trace モジュールが RNG / LLM を import しないこと。

    docstring 内の語を拾わないよう、**AST の import 文だけ**を見る。
    """
    import ast

    tree = ast.parse((ROOT / "src" / "simulation" / "trace.py").read_text(encoding="utf-8"))
    mods: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
    banned = {m for m in mods
              if m.split(".")[0] in {"numpy", "random", "anthropic"}
              or m.startswith("src.llm") or "rng" in m.lower()}
    assert not banned, f"trace.py が禁止モジュールを import: {sorted(banned)}"
    assert mods == {"__future__", "json", "pathlib", "src.common.types"}, \
        f"想定外の import: {sorted(mods)}"


def test_trace_module_never_calls_rng():
    """trace モジュール内に RNG 呼び出しが存在しないこと（AST の呼び出し検査）。"""
    import ast

    tree = ast.parse((ROOT / "src" / "simulation" / "trace.py").read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute):
            assert n.attr not in {"random", "normal", "shuffle", "integers", "permutation"}, \
                f"trace.py に RNG 由来の呼び出し {n.attr} がある"


def test_step_hooks_are_guarded_and_call_no_rng():
    """step.py の trace hook が RNG を渡していない／呼んでいないこと。"""
    src = (ROOT / "src" / "world" / "step.py").read_text(encoding="utf-8")
    hook_lines = [l for l in src.splitlines() if "trace.on_" in l]
    assert hook_lines, "hook が見つからない"
    for l in hook_lines:
        assert "rng" not in l, f"hook 行に rng が現れる: {l.strip()}"


def test_trace_copies_values_not_references(tmp_path):
    """記録値が後続 step の変更で書き換わらないこと（参照保持の禁止）。"""
    from src.world.step import step

    w = build_world("configs/condition_a.yaml", seed=1)
    t = TraceRecorder()
    w.trace = t
    step(w)
    first = [dict(r["skills"]) for r in t.snapshots if r["step"] == 0]
    for _ in range(3):
        step(w)
    still = [r["skills"] for r in t.snapshots if r["step"] == 0]
    assert first == still, "記録済み snapshot が後続 step で書き換わっている"


def test_trace_action_vocabulary_is_existing_only():
    """動画用に新しい行動概念を作っていないこと。"""
    from src.common.types import ActionType

    assert ALLOWED_ACTIONS == frozenset(a.value for a in ActionType)


def test_full_80run_verification_passed():
    """80 run 全件検証のレポートが PASS であること。"""
    if not VERIFY.exists():
        pytest.skip("80 run 検証レポートがない")
    d = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert d["verdict"] == "PASS"
    assert d["final_state_sha256_match"] == "80 / 80"
    assert d["mismatches"] == []
    assert d["api_calls_made"] == 0


def test_trace_output_is_outside_canonical_outputs():
    """trace が正典 outputs を汚さないこと。"""
    if not VERIFY.exists():
        pytest.skip("80 run 検証レポートがない")
    d = json.loads(VERIFY.read_text(encoding="utf-8"))
    assert "outputs" not in Path(d["trace_dir"]).parts
