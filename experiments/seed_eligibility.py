"""main experiment 用 seed の事前選定（API / LLM を一切使用しない）。

coordination_edges >= 2 を Transition Threshold に用いる以上、ネットワーク構造上
この値を達成不能な run を「Agent が協調しなかった」として扱ってはならない
（DESIGN_M1 §10.5）。したがって seed を**事前に**選定する。

【これは outcome selection ではない】
LLM の Intent / community supply / supplier count / transition 結果 /
emergence level など、**Agent の行動結果を一切参照しない**。
参照するのはネットワーク構造と Agent 選出規則のみであり、
測定可能性に基づく pre-experiment eligibility check である。

使い方:
    python -m experiments.seed_eligibility --need 5 --max-seed 40 --agents 6
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.simulation.transition import structural_coordination_capacity
from src.world.step import step as accumulation_step
from src.world.world import build_world

CONDITIONS = ("A", "B", "C", "D")
TOPOLOGY_OF = {"A": "structured", "B": "rewired", "C": "structured", "D": "rewired"}


def capacity_for(condition: str, seed: int, agents: int, accum_steps: int) -> dict:
    """1条件について、蓄積相後の Agent 選出と構造的到達可能性を計算する。

    Agent 選出規則は本実験の runner と同一（participant の技能上位 n 名）。
    LLM は一切呼ばない。
    """
    w = build_world(f"configs/condition_{condition.lower()}.yaml", seed=seed)
    for _ in range(accum_steps):
        accumulation_step(w)
    participants = sorted(
        (a for a in w.agents.values() if a.is_participant),
        key=lambda a: -max(a.skills.values()),
    )
    ids = [a.id for a in participants[:agents]]
    threshold = w.cfg["shock"]["transition"]["coordination_edges"]
    cap = structural_coordination_capacity(w.graph, ids, threshold)
    cap["condition"] = condition
    cap["topology"] = TOPOLOGY_OF[condition]
    return cap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--need", type=int, default=5, help="必要な eligible seed 数")
    ap.add_argument("--max-seed", type=int, default=40, help="scan する seed の上限")
    ap.add_argument("--agents", type=int, default=6, help="shock_agent_count")
    ap.add_argument("--accum-steps", type=int, default=156)
    ap.add_argument("--out", default="outputs/seed_eligibility.json")
    args = ap.parse_args()

    records, eligible = [], []
    scanned = 0
    for seed in range(1, args.max_seed + 1):
        scanned += 1
        caps = {c: capacity_for(c, seed, args.agents, args.accum_steps) for c in CONDITIONS}
        # structured / rewired の双方で到達可能であることを要求する
        ok = all(caps[c]["structurally_reachable"] for c in CONDITIONS)
        rec = {
            "seed": seed,
            "eligible": ok,
            "structured": {
                c: caps[c]["structurally_available_pairs"] for c in ("A", "C")
            },
            "rewired": {c: caps[c]["structurally_available_pairs"] for c in ("B", "D")},
            "per_condition": caps,
        }
        records.append(rec)
        if ok:
            eligible.append(seed)
        print(
            f"seed {seed:>3}: structured A={rec['structured']['A']} C={rec['structured']['C']} | "
            f"rewired B={rec['rewired']['B']} D={rec['rewired']['D']} | "
            f"eligible={ok}"
        )
        if len(eligible) >= args.need:
            break

    result = {
        "purpose": (
            "coordination_edges >= 2 が構造的に測定可能な seed のみを事前選定する。"
            "LLM / Agent 行動結果は一切参照していない（outcome selection ではない）。"
        ),
        "eligibility_rule": (
            "structured(A,C) と rewired(B,D) の4条件すべてで "
            "structurally_available_pairs >= coordination_edges 閾値 であること"
        ),
        "coordination_edges_threshold": records[0]["per_condition"]["A"][
            "coordination_edges_threshold"
        ],
        "shock_agent_count": args.agents,
        "accumulation_steps": args.accum_steps,
        "seeds_scanned": scanned,
        "scan_range": [1, records[-1]["seed"]],
        "eligible_seeds": eligible[: args.need],
        "ineligible_seeds": [r["seed"] for r in records if not r["eligible"]],
        "records": records,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nscanned={scanned}  eligible={eligible[: args.need]}  -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
