"""M3 main experiment: 4条件 × 5 eligible seed = 20 run（人間承認済み、仕様 freeze）。

固定仕様（本実験中に変更禁止）:
    commit b341e13 / conditions A,B,C,D / seeds 2,4,6,7,9
    shock_agent_count 6 / shock_steps 8 / 48 calls/run / 960 calls total
    D4: share>=0.25, suppliers>=ceil(n/2), duration>=4, edges>=2
    D5: External Supply Parity Reference = 3 × shock_agent_count = 18 units/step
    unit_demand: 200 stock, context only, remaining_demand は使用しない

堅牢性:
    - run 完了ごとに個別ファイルへ即保存。再開時は完了済みをスキップ
    - 実行順序は事前ランダム化し、campaign.json へ保存して再開時も維持
    - 累積 spend は完了済み run の実測値から復元
    - per-run cap $1.25 / campaign cap $20.00
      各 run 開始前に cumulative + per_run_max <= campaign_cap を確認
    - run 失敗時は同一 condition・seed で最大2回まで再試行（計3試行）
      パラメータは一切変えない。試行回数を metadata に記録

使い方（20 run を1コマンド。中断後も同じコマンドで再開）:
    python -m experiments.m3_main
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from src.agents.observation import build_observation
from src.common.config import config_sha256
from src.llm.client import BudgetExceeded, LLMDecider
from src.llm.prompts import PROMPT_VERSION, SHOCK_SYSTEM_PROMPT
from src.simulation.transition import (
    TransitionJudge,
    reconfiguration_time,
    structural_coordination_capacity,
)
from src.world.demand import RequiredItem, SupplyLedger, external_reference_supply_per_step
from src.world.shock import ShockState, select_shock_agents, shock_step
from src.world.step import step as accumulation_step
from src.world.world import build_world

# === 固定仕様（変更禁止）===
CONDITIONS = ("A", "B", "C", "D")
ELIGIBLE_SEEDS = (2, 4, 6, 7, 9)
SHOCK_AGENTS = 6
SHOCK_STEPS = 8
ACCUM_STEPS = 156
PER_RUN_MAX_USD = 1.25
CAMPAIGN_MAX_USD = 20.00
MAX_ATTEMPTS = 3  # 初回 + 再試行2回
ORDER_SEED = 20260816  # 実行順序のランダム化に使う固定 seed（結果を見ずに決定）

OUT_DIR = Path("outputs/main_experiment")


def _git_commit() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or None
    except Exception:
        return None


def _prompt_hash() -> str:
    return hashlib.sha256((PROMPT_VERSION + SHOCK_SYSTEM_PROMPT).encode("utf-8")).hexdigest()


def run_key(condition: str, seed: int) -> str:
    return f"{condition}_seed{seed}"


def result_path(condition: str, seed: int) -> Path:
    return OUT_DIR / f"{run_key(condition, seed)}.json"


def build_execution_order() -> list[dict]:
    """結果を見ずに事前ランダム化した実行順序。condition/seed の識別は保持する。"""
    cells = [{"condition": c, "seed": s} for c in CONDITIONS for s in ELIGIBLE_SEEDS]
    random.Random(ORDER_SEED).shuffle(cells)
    for i, cell in enumerate(cells):
        cell["order_index"] = i
    return cells


def load_campaign() -> dict:
    """campaign.json を読む。無ければ実行順序を確定して作る（再開時も同じ順序）。"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "campaign.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    campaign = {
        "run_purpose": "main_experiment",
        "frozen_spec_commit": "b341e13",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "order_seed": ORDER_SEED,
        "execution_order": build_execution_order(),
        "conditions": list(CONDITIONS),
        "eligible_seeds": list(ELIGIBLE_SEEDS),
        "shock_agent_count": SHOCK_AGENTS,
        "shock_steps": SHOCK_STEPS,
        "per_run_max_usd": PER_RUN_MAX_USD,
        "campaign_max_usd": CAMPAIGN_MAX_USD,
    }
    path.write_text(json.dumps(campaign, ensure_ascii=False, indent=2), encoding="utf-8")
    return campaign


def completed_runs() -> dict[str, dict]:
    """完了済み run を検出する。累積 spend の復元にも使う。"""
    done = {}
    for p in sorted(OUT_DIR.glob("*_seed*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("status") in ("completed", "failed"):
            done[run_key(d["condition"], d["seed"])] = d
    return done


def restore_cumulative_spend(done: dict[str, dict]) -> float:
    """完了済み run の実測値から累積 spend を復元する（失敗 run の費用も加算）。"""
    return sum(float(d.get("spent_usd", 0.0)) for d in done.values())


def execute_run(condition: str, seed: int, attempt: int) -> dict:
    """1 run（1条件 × 1seed）。仕様は固定。パラメータを変えて再試行しない。"""
    started = datetime.now(timezone.utc)
    t0 = time.time()

    world = build_world(f"configs/condition_{condition.lower()}.yaml", seed=seed)
    world.cfg["llm"]["max_usd"] = PER_RUN_MAX_USD
    shock_cfg = world.cfg["shock"]
    required = RequiredItem.from_config(shock_cfg["required_item"])
    state = ShockState()

    for _ in range(ACCUM_STEPS):
        accumulation_step(world)

    onset = world.step
    external_ref = external_reference_supply_per_step(world.cfg, SHOCK_AGENTS)
    ledger = SupplyLedger(baseline_per_step=external_ref)
    judge = TransitionJudge.from_config(shock_cfg["transition"])

    llm_ids = select_shock_agents(world, SHOCK_AGENTS)
    structural = structural_coordination_capacity(
        world.graph, llm_ids, shock_cfg["transition"]["coordination_edges"]
    )
    sub = sorted(sorted(e) for e in world.graph.subgraph(llm_ids).edges())
    induced_hash = hashlib.sha256(repr(sub).encode()).hexdigest()

    decider = LLMDecider(world.cfg)

    def decide_fn(obs):
        sf = {
            p.project_id: required.shortfall(state.profile_for(obs.self_id, p))
            for p in world.projects
        }
        return decider.decide_shock(obs, required, sf)

    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}
    rows, stopped = [], None

    try:
        for _ in range(SHOCK_STEPS):
            try:
                rows.append(
                    shock_step(world, state, required, ledger, judge, decide_fn, llm_ids, stats)
                )
            except BudgetExceeded as exc:
                stopped = str(exc)
                break
        status = "completed"
        error = None
    except Exception as exc:  # API エラー等
        status = "failed"
        error = f"{type(exc).__name__}: {exc}"

    emergence = judge.emergence_level(
        ledger,
        any_modify=state.modify_count > 0,
        any_peer_method=any(
            m.is_peer_acquired for a in world.agents.values() for m in a.methods.values()
        ),
    )
    return {
        "run_purpose": "main_experiment",
        "status": status,
        "error": error,
        "attempt": attempt,
        "condition": condition,
        "seed": seed,
        "code_git_commit": _git_commit(),
        "config_sha256": config_sha256(world.cfg),
        "prompt_version": PROMPT_VERSION,
        "prompt_sha256": _prompt_hash(),
        "model": world.cfg["llm"]["model"],
        "effort": world.cfg["llm"]["effort"],
        "shock_agent_ids": llm_ids,
        "base_graph_sha256": world.provenance["base_graph_sha256"],
        "induced_subgraph_sha256": induced_hash,
        "agent_initial_states_sha256": world.provenance["agent_initial_states_sha256"],
        "participant_ids_sha256": world.provenance["participant_ids_sha256"],
        "cultural_edge_count": world.provenance["cultural_edge_count"],
        "structural_coordination": structural,
        "D4_transition": dict(shock_cfg["transition"]),
        "D5_external_reference_supply_per_step": external_ref,
        "unit_demand_stock": required.unit_demand,
        "unit_demand_note": "context only; remaining_demand depletion is not used",
        "accumulation_steps": ACCUM_STEPS,
        "shock_steps_run": len(rows),
        "shock_step_hours": shock_cfg["step_hours"],
        "community_supply_total": ledger.community_total,
        "external_reference_total": ledger.baseline_total,
        "community_supply_share": round(ledger.community_supply_share(), 6),
        "modify_count": state.modify_count,
        "coordination_edges": state.coordination_edges(),
        "coordination_pairs": sorted(list(p) for p in state.joined),
        "qualifying_makes": stats["qualifying_makes"],
        "nonqualifying_makes": stats["nonqualifying_makes"],
        "action_counts": stats["actions"],
        "rejection_counts": stats["rejections"],
        "intents_proposed": stats["proposed"],
        "intents_accepted": stats["accepted"],
        "emergence_level_provisional": emergence,
        **judge.summary(),
        **reconfiguration_time(onset, ledger, judge),
        "llm_calls": decider.guard.calls,
        "input_tokens": decider.guard.input_tokens,
        "output_tokens": decider.guard.output_tokens,
        "spent_usd": round(decider.guard.spent_usd, 6),
        "per_call_usage": decider.guard.per_call,
        "stopped_by_budget": stopped,
        "run_started_utc": started.isoformat(),
        "run_ended_utc": datetime.now(timezone.utc).isoformat(),
        "wall_seconds": round(time.time() - t0, 1),
        "transition_history": rows,
        "provenance": state.provenance,
        "modify_history": state.modify_history,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API を呼ばず計画のみ表示")
    args = ap.parse_args()

    campaign = load_campaign()
    order = campaign["execution_order"]
    done = completed_runs()
    cumulative = restore_cumulative_spend(done)

    pending = [c for c in order if run_key(c["condition"], c["seed"]) not in done]
    print(f"main experiment: {len(done)}/{len(order)} 完了済み / 残り {len(pending)}")
    print(f"累積費用（完了済みから復元）: ${cumulative:.4f} / campaign cap ${CAMPAIGN_MAX_USD:.2f}")
    print(f"実行順序 (order_seed={campaign['order_seed']}): "
          + " ".join(f"{c['condition']}{c['seed']}" for c in order))

    if args.dry_run:
        print(f"\n[DRY-RUN] 残り {len(pending)} run。API は呼びません。")
        return 0

    for cell in pending:
        cond, seed = cell["condition"], cell["seed"]
        key = run_key(cond, seed)

        # campaign cap 判定: 新 run を開始してよいか
        if cumulative + PER_RUN_MAX_USD > CAMPAIGN_MAX_USD:
            print(f"\n[STOP] campaign cap 到達: "
                  f"${cumulative:.4f} + ${PER_RUN_MAX_USD:.2f} > ${CAMPAIGN_MAX_USD:.2f}")
            print("新規 run を開始せず停止します。未完了セルは補完しないでください。")
            break

        result = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"\n>>> {key} (order {cell['order_index']}, attempt {attempt}/{MAX_ATTEMPTS})")
            try:
                result = execute_run(cond, seed, attempt)
            except Exception as exc:
                result = {
                    "run_purpose": "main_experiment", "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}", "attempt": attempt,
                    "condition": cond, "seed": seed, "spent_usd": 0.0,
                    "run_ended_utc": datetime.now(timezone.utc).isoformat(),
                }
            cumulative += float(result.get("spent_usd", 0.0))  # 失敗分も加算
            if result["status"] == "completed":
                break
            print(f"    失敗: {result.get('error')}")

        result["order_index"] = cell["order_index"]
        result["cumulative_spend_after_run"] = round(cumulative, 6)
        result_path(cond, seed).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"    {result['status']}  transition={result.get('transitioned')} "
              f"supply={result.get('community_supply_total')} "
              f"edges={result.get('coordination_edges')} "
              f"${result.get('spent_usd', 0):.4f}  累積=${cumulative:.4f}")

    done = completed_runs()
    ok = [k for k, d in done.items() if d["status"] == "completed"]
    failed = [k for k, d in done.items() if d["status"] == "failed"]
    missing = [run_key(c["condition"], c["seed"]) for c in order
               if run_key(c["condition"], c["seed"]) not in done]

    print(f"\n=== campaign 終了 ===")
    print(f"completed: {len(ok)}/20   failed: {len(failed)}   未実行: {len(missing)}")
    if failed:
        print(f"  failed cells: {failed}")
    if missing:
        print(f"  未完了 cells（補完しないこと）: {missing}")
    print(f"累積費用: ${restore_cumulative_spend(done):.4f} / ${CAMPAIGN_MAX_USD:.2f}")
    print(f"-> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
