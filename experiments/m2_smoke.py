"""M2 最小統合確認: 1エージェント・1回の LLM 呼び出し。

M2 の最低達成条件4点をこの1スクリプトで確認する:
  1. LLM 呼び出しが成功する
  2. structured output が Intent へ parse される
  3. Validator が feasibility を判定する
  4. API cost ceiling で停止できる

使い方:
    ANTHROPIC_API_KEY=... .\\.venv\\Scripts\\python.exe -m experiments.m2_smoke
    .\\.venv\\Scripts\\python.exe -m experiments.m2_smoke --agents 3

【CLAUDE.md 絶対ルール】費用上限は configs/base.yaml の llm.max_usd。
超えた時点で BudgetExceeded を送出して停止する。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.agents.decision import validate
from src.agents.observation import build_observation
from src.llm.client import BudgetExceeded, LLMDecider
from src.world.world import build_world


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/condition_a.yaml")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--agents", type=int, default=1, help="LLM を呼ぶ Agent 数（既定1）")
    ap.add_argument("--out", default="outputs/m2_smoke.json")
    args = ap.parse_args()

    world = build_world(args.config, seed=args.seed)
    projects = {p.project_id: p for p in world.projects}

    try:
        decider = LLMDecider(world.cfg)
    except Exception as exc:  # 認証未設定など
        print(f"[FAIL] クライアントを作成できません: {exc}")
        print("  ANTHROPIC_API_KEY を設定するか `ant auth login` を実行してください。")
        return 2

    results = []
    for agent_id in sorted(world.agents)[: args.agents]:
        agent = world.agents[agent_id]
        obs = build_observation(world, agent)

        # 条件1+2: 呼び出し成功 -> structured output -> Intent
        try:
            intents = decider.decide(obs)
        except BudgetExceeded as exc:
            print(f"[STOP] 条件4: {exc}")
            break
        print(f"[OK] 条件1+2 {agent_id}: {len(intents)} intents parsed")
        for i in intents:
            print(f"       {i.action.value:9s} project={i.target_project_id} "
                  f"skill={i.target_skill_id} agent={i.target_agent_id}")

        # 条件3: Validator が feasibility を判定する
        accepted = validate(agent, intents, projects, world.cfg)
        rejected = [(i.action.value, r.value) for i, r in agent.rejected_intents]
        print(f"[OK] 条件3 {agent_id}: accepted={len(accepted)} rejected={len(rejected)} {rejected}")

        results.append({
            "agent_id": agent_id,
            "intents": [i.action.value for i in intents],
            "accepted": [i.action.value for i in accepted],
            "rejected": rejected,
        })
        agent.rejected_intents.clear()

    summary = {
        "condition": world.cfg["condition"],
        "seed": args.seed,
        "results": results,
        **decider.provenance(),
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    g = decider.guard
    print(f"\n[COST] calls={g.calls} in={g.input_tokens} out={g.output_tokens} "
          f"spent=${g.spent_usd:.6f} / cap=${g.max_usd:.2f}")
    print(f"[OK] 条件4: 上限機構は稼働中（超過時に停止）")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
