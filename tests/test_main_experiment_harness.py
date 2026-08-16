"""main experiment の堅牢性機構のテスト（API を呼ばない）。

検証対象: 実行順序の事前ランダム化と再開時の不変性、完了検出、
累積 spend の復元、campaign cap の判定、固定仕様の保持。
"""

import json

import pytest

from experiments import m3_main as M


def test_frozen_spec_matches_approved_values():
    """人間承認済みの固定仕様が変わっていないこと。"""
    assert M.CONDITIONS == ("A", "B", "C", "D")
    assert M.ELIGIBLE_SEEDS == (2, 4, 6, 7, 9)
    assert M.SHOCK_AGENTS == 6
    assert M.SHOCK_STEPS == 8
    assert M.PER_RUN_MAX_USD == 1.25
    assert M.CAMPAIGN_MAX_USD == 20.00
    assert M.MAX_ATTEMPTS == 3


def test_execution_order_covers_every_cell_exactly_once():
    order = M.build_execution_order()
    cells = [(c["condition"], c["seed"]) for c in order]
    assert len(cells) == 20
    assert len(set(cells)) == 20
    assert set(cells) == {(c, s) for c in M.CONDITIONS for s in M.ELIGIBLE_SEEDS}


def test_execution_order_is_randomised_but_reproducible():
    """事前ランダム化されており、再開時に同じ順序へ復元できること。"""
    a = M.build_execution_order()
    b = M.build_execution_order()
    assert a == b, "順序が再現しない（再開時に順序が変わる）"
    naive = [{"condition": c, "seed": s} for c in M.CONDITIONS for s in M.ELIGIBLE_SEEDS]
    assert [(x["condition"], x["seed"]) for x in a] != [
        (x["condition"], x["seed"]) for x in naive
    ], "ランダム化されていない"


def test_execution_order_preserves_identity_for_paired_analysis():
    for cell in M.build_execution_order():
        assert cell["condition"] in M.CONDITIONS
        assert cell["seed"] in M.ELIGIBLE_SEEDS
        assert isinstance(cell["order_index"], int)


def test_completed_runs_and_spend_restore(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "OUT_DIR", tmp_path)
    (tmp_path / "A_seed2.json").write_text(
        json.dumps({"status": "completed", "condition": "A", "seed": 2, "spent_usd": 0.9}),
        encoding="utf-8",
    )
    (tmp_path / "B_seed4.json").write_text(
        json.dumps({"status": "failed", "condition": "B", "seed": 4, "spent_usd": 0.3}),
        encoding="utf-8",
    )
    done = M.completed_runs()
    assert set(done) == {"A_seed2", "B_seed4"}
    # 失敗 run の費用も累積に含める
    assert M.restore_cumulative_spend(done) == pytest.approx(1.2)


def test_resume_skips_completed_cells(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "OUT_DIR", tmp_path)
    order = M.build_execution_order()
    for cell in order[:7]:
        (tmp_path / f"{cell['condition']}_seed{cell['seed']}.json").write_text(
            json.dumps({"status": "completed", "condition": cell["condition"],
                        "seed": cell["seed"], "spent_usd": 0.9}),
            encoding="utf-8",
        )
    done = M.completed_runs()
    pending = [c for c in order if M.run_key(c["condition"], c["seed"]) not in done]
    assert len(pending) == 13
    assert [c["order_index"] for c in pending] == list(range(7, 20)), "再開時に順序が崩れている"


def test_campaign_cap_blocks_new_run_before_starting():
    """cumulative + per_run_max > cap で新規 run を開始しないこと。"""
    def may_start(cumulative):
        return cumulative + M.PER_RUN_MAX_USD <= M.CAMPAIGN_MAX_USD

    assert may_start(18.00) is True     # 18.00 + 1.25 = 19.25 <= 20
    assert may_start(18.75) is True     # ちょうど 20.00
    assert may_start(18.76) is False    # 20.01 > 20 -> 停止
    assert may_start(19.50) is False


def test_campaign_cap_allows_all_twenty_runs_at_expected_cost():
    """想定費用（$0.914/run）なら 20 run が cap 内に収まること。"""
    expected_per_run = 48 * 0.019035
    assert expected_per_run * 20 < M.CAMPAIGN_MAX_USD
    assert expected_per_run < M.PER_RUN_MAX_USD


def test_campaign_file_is_written_once_and_reused(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "OUT_DIR", tmp_path)
    first = M.load_campaign()
    second = M.load_campaign()
    assert first["execution_order"] == second["execution_order"]
    assert first["created_at"] == second["created_at"], "再開時に campaign が作り直されている"
    assert first["run_purpose"] == "main_experiment"


def test_result_path_is_per_cell(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "OUT_DIR", tmp_path)
    paths = {M.result_path(c, s) for c in M.CONDITIONS for s in M.ELIGIBLE_SEEDS}
    assert len(paths) == 20, "run ごとの個別ファイルになっていない"
