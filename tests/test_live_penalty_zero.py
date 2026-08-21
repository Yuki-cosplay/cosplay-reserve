"""live run 2本（partial-equilibrium 実測）の事前登録固定値と機構のテスト。

**API / LLM を呼ばない。** 検証するのは、事前登録した設定が実装と一致していること、
penalty 上書きが 1 キーだけに限定されていること、出力が main experiment と
混ざらないこと。
"""

import json

import pytest

from experiments import live_penalty_zero as L
from experiments import m3_main as M


def test_frozen_settings_match_preregistration():
    """docs/PREREGISTRATION_SENSITIVITY.md §7.1 / §7.3.2 の固定値。"""
    assert L.CONDITION == "A"
    assert L.SEEDS == (2, 4)
    assert L.PENALTY == 0.00
    assert L.PER_RUN_MAX_USD == 1.25
    assert L.CAMPAIGN_MAX_USD == 3.00
    assert L.MAX_ATTEMPTS == 3


def test_replay_predictions_are_frozen():
    """§7.3 の予測値。live 実行後に書き換えられていないこと。"""
    assert L.REPLAY_PREDICTION[2]["expected_community_supply_total"] == 49.980
    assert L.REPLAY_PREDICTION[4]["expected_community_supply_total"] == 54.880
    assert L.REPLAY_PREDICTION[2]["tolerance_2sd"] == 2.00
    assert L.REPLAY_PREDICTION[4]["tolerance_2sd"] == 2.10


def test_predictions_match_the_replay_output_file():
    """予測値が感度分析の出力と一致すること（転記ミスの検出）。"""
    from pathlib import Path

    p = Path("outputs/sensitivity_replay/penalty_sensitivity.json")
    if not p.exists():
        pytest.skip("replay 出力がない")
    d = json.loads(p.read_text(encoding="utf-8"))
    for seed in L.SEEDS:
        rec = next(
            r for r in d["records"]
            if r["condition"] == "A" and r["seed"] == seed
            and r["modify_difficulty_penalty"] == 0.00
        )
        exp = L.REPLAY_PREDICTION[seed]["expected_community_supply_total"]
        assert round(rec["expected_community_supply_total"], 3) == exp
        assert rec["qualifying_attempts"] == L.REPLAY_PREDICTION[seed]["qualifying_attempts"]


def test_penalty_override_changes_exactly_one_key():
    """上書きは modify_difficulty_penalty のみ。他の設定を動かしていないこと。

    D4 / D5 / unit_demand / topology / peer_learning / 材料 / 設備 / 時間予算が
    main experiment と同一であることを保証する。
    """
    base = M.build_world("configs/condition_a.yaml", seed=2)
    patched = L._build_world_with_penalty("configs/condition_a.yaml", seed=2)

    diffs = []

    def walk(a, b, path=""):
        if isinstance(a, dict) and isinstance(b, dict):
            for k in set(a) | set(b):
                walk(a.get(k), b.get(k), f"{path}.{k}" if path else k)
        elif a != b:
            diffs.append(path)

    walk(base.cfg, patched.cfg)
    assert diffs == ["shock.modify_difficulty_penalty"], f"想定外の差分: {diffs}"
    assert patched.cfg["shock"]["modify_difficulty_penalty"] == 0.00
    assert base.cfg["shock"]["modify_difficulty_penalty"] == 0.35


def test_d4_used_by_live_run_is_the_preregistered_value():
    """live run の転化判定が正式事前登録 D4 を使うこと。"""
    w = L._build_world_with_penalty("configs/condition_a.yaml", seed=2)
    assert w.cfg["shock"]["transition"] == {
        "community_supply_share": 0.25,
        "active_supplier_count": 3,
        "supply_duration_steps": 4,
        "coordination_edges": 2,
    }


def test_override_is_recorded_in_provenance():
    w = L._build_world_with_penalty("configs/condition_a.yaml", seed=4)
    ov = w.provenance["modify_difficulty_penalty_override"]
    assert ov["from"] == 0.35 and ov["to"] == 0.00


def test_output_does_not_collide_with_main_experiment():
    """main experiment の出力を上書きしないこと。"""
    assert L.OUT_DIR != M.OUT_DIR
    for s in L.SEEDS:
        assert L.result_path(s).parent == L.OUT_DIR
        assert L.result_path(s) != M.result_path("A", s)


def test_campaign_cap_blocks_a_third_run():
    """2 run 打ち止め: cap $3.00 は 3 run 目を開始させない。"""
    def may_start(cumulative):
        return cumulative + L.PER_RUN_MAX_USD <= L.CAMPAIGN_MAX_USD

    assert may_start(0.00) is True
    assert may_start(0.95) is True          # 2 run 目
    assert may_start(1.90) is False         # 3 run 目は開始できない
    # 実測単価 $0.9252/run なら 2 run で $1.85、cap 内
    assert 0.9252 * 2 < L.CAMPAIGN_MAX_USD


def test_main_experiment_outputs_are_untouched():
    """既存 20 run が read-only であること（件数・call 数・費用）。"""
    from pathlib import Path

    d = Path("outputs/main_experiment")
    if not d.exists():
        pytest.skip("main experiment の出力がない")
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in d.glob("[ABCD]_seed*.json")]
    assert len(runs) == 20
    assert sum(r["llm_calls"] for r in runs) == 960
    assert round(sum(r["spent_usd"] for r in runs), 6) == 18.503645
