"""M3 end-to-end: 蓄積相 → ショック → LLM意思決定 → feasibility → supply → metrics。

最初の目標は「期待した転化を出すこと」ではなく、pipeline を1回通すことである。
期待結果が出なくてもパラメータを調整しない。negative / null result もそのまま保存する。

使い方:
    # 費用を先に見積もる（API を呼ばない）
    python -m experiments.m3_shock --dry-run --shock-steps 4 --llm-agents 3

    # 本実行
    python -m experiments.m3_shock --shock-steps 4 --llm-agents 3 --max-usd 0.50
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from src.agents.observation import build_observation
from src.llm.client import BudgetExceeded, LLMDecider
from src.llm.prompts import SHOCK_SYSTEM_PROMPT, build_shock_user_prompt
from src.simulation.transition import TransitionJudge, reconfiguration_time
from src.world.demand import RequiredItem, SupplyLedger
from src.world.shock import ShockState, shock_step
from src.world.step import step as accumulation_step
from src.world.world import build_world
from src.common.config import config_sha256
from src.simulation.runner import _git_commit

# M2 実測（in=1430 / out=295 で $0.014525）。ショック相プロンプトは需要ブロック分だけ長い。
MEASURED_IN, MEASURED_OUT = 1430, 295


def _shortfalls(required, state, agent_id, projects):
    return {
        p.project_id: required.shortfall(state.profile_for(agent_id, p)) for p in projects
    }


def dry_run(args, world, required, state) -> dict:
    """API を呼ばずに、呼び出し回数と費用を見積もる。"""
    llm_cfg = world.cfg["llm"]
    calls = args.shock_steps * args.llm_agents

    # 実際のプロンプト長からトークンを概算（1 token ≒ 4 chars）
    agent = world.agents[sorted(world.agents)[0]]
    obs = build_observation(world, agent)
    sf = _shortfalls(required, state, agent.id, world.projects)
    prompt_chars = len(SHOCK_SYSTEM_PROMPT) + len(build_shock_user_prompt(obs, required, sf))
    est_in = max(MEASURED_IN, prompt_chars // 4)
    est_out = MEASURED_OUT

    per_call = est_in / 1e6 * llm_cfg["input_usd_per_mtok"] + est_out / 1e6 * llm_cfg["output_usd_per_mtok"]
    return {
        "dry_run": True,
        "shock_steps": args.shock_steps,
        "llm_agents_per_step": args.llm_agents,
        "estimated_calls": calls,
        "estimated_input_tokens_per_call": est_in,
        "estimated_output_tokens_per_call": est_out,
        "estimated_usd_per_call": round(per_call, 6),
        "estimated_total_usd": round(per_call * calls, 4),
        "cost_ceiling_usd": args.max_usd,
        "within_ceiling": per_call * calls <= args.max_usd,
        "prompt_chars": prompt_chars,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/condition_a.yaml")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--accum-steps", type=int, default=156, help="蓄積相の step 数")
    ap.add_argument("--shock-steps", type=int, default=4, help="ショック相の step 数（1 step=6h）")
    ap.add_argument("--llm-agents", type=int, default=3, help="毎step LLM を呼ぶ Agent 数")
    ap.add_argument("--max-usd", type=float, default=0.50, help="この run の費用上限")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default="outputs/m3_shock.json")
    ap.add_argument("--run-type", default="PIPELINE_VALIDATION")
    args = ap.parse_args()

    world = build_world(args.config, seed=args.seed)
    world.cfg["llm"]["max_usd"] = args.max_usd
    shock_cfg = world.cfg["shock"]
    required = RequiredItem.from_config(shock_cfg["required_item"])
    state = ShockState()

    if args.dry_run:
        est = dry_run(args, world, required, state)
        print(json.dumps(est, ensure_ascii=False, indent=2))
        return 0

    t0 = time.time()

    # --- 蓄積相（LLM なし。決定 D12）---
    for _ in range(args.accum_steps):
        accumulation_step(world)
    accum_makers = sum(
        1 for a in world.agents.values()
        if a.is_participant and a.maker_stage.value in ("maker", "advanced_maker")
    )
    print(f"[1/4] 蓄積相 {args.accum_steps} steps 完了: participant makers={accum_makers}/30")

    # --- ショック発生 ---
    onset = world.step
    ledger = SupplyLedger(baseline_per_step=shock_cfg["baseline_supply_per_step"])
    judge = TransitionJudge.from_config(shock_cfg["transition"])
    print(f"[2/4] ショック発生 step={onset} 要求={required.thresholds} "
          f"（要求を初期状態で満たす project は存在しない）")

    try:
        decider = LLMDecider(world.cfg)
    except Exception as exc:
        print(f"[FAIL] LLM クライアントを作成できません: {exc}")
        return 2

    # LLM を呼ぶ Agent は participant のうち技能上位（コスト制御、SPEC §24）
    participants = sorted(
        (a for a in world.agents.values() if a.is_participant),
        key=lambda a: -max(a.skills.values()),
    )
    llm_ids = [a.id for a in participants[: args.llm_agents]]

    stats = {"actions": {}, "rejections": {}, "proposed": 0, "accepted": 0,
             "qualifying_makes": 0, "nonqualifying_makes": 0}
    rows, stopped = [], None

    def decide_fn(obs):
        sf = _shortfalls(required, state, obs.self_id, world.projects)
        return decider.decide_shock(obs, required, sf)

    for i in range(args.shock_steps):
        try:
            row = shock_step(world, state, required, ledger, judge, decide_fn, llm_ids, stats)
        except BudgetExceeded as exc:
            stopped = str(exc)
            print(f"[STOP] {exc}")
            break
        rows.append(row)
        print(f"  step {row['step']}: share={row['share']:.3f} suppliers={row['suppliers']} "
              f"duration={row['duration']} edges={row['coordination_edges']} "
              f"all_met={row['all_met']} (${decider.guard.spent_usd:.4f})")

    print(f"[3/4] ショック相 {len(rows)} steps 完了")

    recon = reconfiguration_time(onset, ledger, judge)
    emergence = judge.emergence_level(
        ledger,
        any_modify=state.modify_count > 0,
        any_peer_method=any(
            m.is_peer_acquired for a in world.agents.values() for m in a.methods.values()
        ),
    )
    summary = {
        # --- この run の位置づけ（人間承認済み、2026-08-16）---
        "run_type": args.run_type,
        "confirmatory_evidence": False,
        "excluded_from_main_experiment": True,
        "excluded_from_d4_d5_calibration": True,
        "purpose": (
            "end-to-end pipeline 疎通の確認のみ。Transition が TRUE になることは"
            "成功条件ではない。FALSE でも pipeline が正常なら成功。"
        ),
        "provisional_parameters": {
            "note": (
                "D4（転化閾値）と D5（baseline_supply_per_step）は PIPELINE_VALIDATION 用の"
                "暫定値であり、研究上の確定値ではない。この run の結果を見て D4/D5 を"
                "調整・選択してはならない。本実験前に独立した根拠から固定し"
                "PREREGISTRATION へ記録すること。"
            ),
            "D5_baseline_supply_per_step": shock_cfg["baseline_supply_per_step"],
            "D4_transition": dict(shock_cfg["transition"]),
            "status": "provisional / not research-final",
        },
        "config_sha256": config_sha256(world.cfg),
        "code_git_commit": _git_commit(),
        **world.provenance,
        "accumulation_steps": args.accum_steps,
        "accumulation_participant_makers": accum_makers,
        "shock_steps_run": len(rows),
        "shock_step_hours": shock_cfg["step_hours"],
        "required_item": {"thresholds": required.thresholds, "unit_demand": required.unit_demand},
        "llm_agent_ids": llm_ids,
        "community_supply_total": ledger.community_total,
        "baseline_supply_total": ledger.baseline_total,
        "community_supply_share": round(ledger.community_supply_share(), 6),
        "modify_count": state.modify_count,
        "coordination_edges": state.coordination_edges(),
        "qualifying_makes": stats["qualifying_makes"],
        "nonqualifying_makes": stats["nonqualifying_makes"],
        "action_counts": stats["actions"],
        "rejection_counts": stats["rejections"],
        "intents_proposed": stats["proposed"],
        "intents_accepted": stats["accepted"],
        "emergence_level_provisional": emergence,
        **judge.summary(),
        **recon,
        **decider.provenance(),
        "per_call_usage": decider.guard.per_call,
        "stopped_by_budget": stopped,
        "wall_seconds": round(time.time() - t0, 1),
        "transition_history": rows,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    g = decider.guard
    print(f"[4/4] 転化={summary['transitioned']} step={summary['transition_step']} "
          f"emergence={emergence} community_supply={ledger.community_total}")
    print(f"[COST] calls={g.calls} in={g.input_tokens} out={g.output_tokens} "
          f"spent=${g.spent_usd:.6f} / cap=${g.max_usd:.2f}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
