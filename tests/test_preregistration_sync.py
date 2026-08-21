"""事前登録値と runtime config の同期テスト（L11 の再発防止）。

【背景】
main experiment 20 run は、事前登録 D4（share>=0.25 / duration>=4）ではなく
PIPELINE_VALIDATION 時の暫定値（share>=0.20 / duration>=3）で実行された。
実行後の逸脱チェックが「20 run で同じ値だったか」という**内部整合性**しか
見ておらず、「事前登録値と一致しているか」を検査していなかったため検出されなかった。

【このテストの役割】
事前登録値をここにリテラルで固定し、runtime config と突き合わせる。
config から読んだ値どうしを比べても同期不良は永久に検出できないため、
期待値は必ずテスト側に literal で置く。

API / LLM は呼ばない。
"""

import json
import math
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
OUT_DIR = ROOT / "outputs" / "main_experiment"
# main experiment が実際に使用した runtime config の歴史的アーカイブ
AS_EXECUTED = CONFIG_DIR / "as_executed" / "main_experiment_20260816.yaml"

SHOCK_AGENT_COUNT = 6

# docs/PREREGISTRATION_H1.md §D4（人間確定 2026-08-16、commit 2de6b52）
PREREGISTERED_D4 = {
    "community_supply_share": 0.25,
    "active_supplier_count": math.ceil(SHOCK_AGENT_COUNT / 2),  # ceil(6/2) = 3
    "supply_duration_steps": 4,  # 4 step × 6h = 24h
    "coordination_edges": 2,
}

PREREGISTERED_SEEDS = [2, 4, 6, 7, 9]
PREREGISTERED_REQUIRED_ITEM = {"attr_0": 0.60, "attr_2": 0.55}
PREREGISTERED_UNIT_DEMAND = 200.0


@pytest.fixture(scope="module")
def base_cfg():
    return yaml.safe_load((CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"))


def test_config_d4_matches_preregistration(base_cfg):
    """runtime config の D4 が事前登録値と一致すること。

    L11 の再発防止テスト。第三者が現在の configs/base.yaml から実行した場合、
    正式事前登録値による判定になることを保証する。
    （2026-08-16 に同期完了。それ以前は xfail だった。）
    """
    assert base_cfg["shock"]["transition"] == PREREGISTERED_D4


def test_config_d4_has_all_four_keys(base_cfg):
    """D4 の項目が4つとも存在すること（キー欠落での暗黙スキップを防ぐ）。"""
    assert set(base_cfg["shock"]["transition"]) == set(PREREGISTERED_D4)


def test_config_required_item_matches_preregistration(base_cfg):
    assert base_cfg["shock"]["required_item"]["thresholds"] == PREREGISTERED_REQUIRED_ITEM


def test_config_unit_demand_matches_preregistration(base_cfg):
    assert base_cfg["shock"]["required_item"]["unit_demand"] == PREREGISTERED_UNIT_DEMAND


def test_harness_seeds_match_preregistration():
    from experiments import m3_main as M

    assert list(M.ELIGIBLE_SEEDS) == PREREGISTERED_SEEDS
    assert M.SHOCK_AGENTS == SHOCK_AGENT_COUNT


def test_active_supplier_count_is_ceil_half_of_agents():
    """ceil(n/2) は n に依存する。n を変えたら D4 も追随する必要がある。"""
    assert PREREGISTERED_D4["active_supplier_count"] == math.ceil(SHOCK_AGENT_COUNT / 2)


# --- 実行済み run に対する事後監査 -----------------------------------------
# 内部整合性（20 run で同一）だけでなく、事前登録値との一致を検査する。


def _completed_runs():
    if not OUT_DIR.exists():
        return []
    return [
        json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(OUT_DIR.glob("*_seed*.json"))
    ]


def test_run_metadata_is_internally_consistent():
    """従来からあった検査。これだけでは L11 を検出できない（回帰の記録として残す）。"""
    runs = _completed_runs()
    if not runs:
        pytest.skip("main experiment の出力がない")
    assert len({json.dumps(r["D4_transition"], sort_keys=True) for r in runs}) == 1
    assert len({r["prompt_sha256"] for r in runs}) == 1
    assert len({r["code_git_commit"] for r in runs}) == 1


def test_run_metadata_matches_the_as_executed_artifact():
    """実行済み 20 run の D4 が as_executed アーカイブと一致すること。

    既存 run は暫定 D4（0.20/3/3/2）で実行された。**ログは改変しない**ため、
    run metadata が事前登録値と一致することはありえない。
    代わりに検査すべきは「実行時に何を使ったかが正確に保存されているか」である。
    as_executed アーカイブが失われたり書き換わったりすれば、
    実行条件の再現不能を意味するのでここで落ちる。
    """
    runs = _completed_runs()
    if not runs:
        pytest.skip("main experiment の出力がない")
    assert AS_EXECUTED.exists(), "実行時 config のアーカイブが存在しない"
    as_exec = yaml.safe_load(AS_EXECUTED.read_text(encoding="utf-8"))
    for r in runs:
        assert r["D4_transition"] == as_exec["shock"]["transition"], (
            f"{r['condition']}_seed{r['seed']} が as_executed と不一致: {r['D4_transition']}"
        )


def test_as_executed_differs_from_preregistration_as_documented():
    """L11 の事実そのものを固定する。

    as_executed が事前登録値と**一致してしまった**場合、
    アーカイブが取り違えられたか上書きされたことを意味する。
    """
    if not AS_EXECUTED.exists():
        pytest.skip("as_executed アーカイブがない")
    tr = yaml.safe_load(AS_EXECUTED.read_text(encoding="utf-8"))["shock"]["transition"]
    assert tr["community_supply_share"] == 0.20
    assert tr["supply_duration_steps"] == 3
    # 一致していた2項目
    assert tr["active_supplier_count"] == PREREGISTERED_D4["active_supplier_count"]
    assert tr["coordination_edges"] == PREREGISTERED_D4["coordination_edges"]


def test_corrected_adjudication_is_the_main_result():
    """主結果ファイルが事前登録値で判定されていること（人間確定 2026-08-16）。"""
    p = OUT_DIR / "transition_recomputed_preregistered.json"
    if not p.exists():
        pytest.skip("corrected adjudication の出力がない")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["preregistered_D4"] == PREREGISTERED_D4
    assert d["api_calls_made"] == 0
    assert len(d["runs"]) == 20
