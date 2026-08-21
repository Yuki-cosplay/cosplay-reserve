"""事前登録 D4 値による corrected adjudication（API / LLM を一切呼ばない）。

【なぜ必要か】
main experiment の runtime config（configs/base.yaml）に、PIPELINE_VALIDATION 時の
暫定値 share>=0.20 / duration>=3 が残存したまま 20 run が実行された。
人間承認済みの正式事前登録値は docs/PREREGISTRATION_H1.md §D4 の
share>=0.25 / suppliers>=ceil(n/2) / duration>=4 / edges>=2 である。

【これは「結果を見て閾値を変えた判定」ではない】
事前登録値へ**戻す**再判定である。runtime 判定（a）は削除も上書きもしない。

【新しい判定ロジックを作らない】
既存 run ログの transition_history には、判定に必要な4つの実測値
(share, suppliers, duration, coordination_edges) が step 単位で記録されている。
これらはすべて**閾値に依存しない量**である:

  - share    = 累積 community /(累積 community + 累積 baseline)   … 閾値非依存
  - suppliers= その step に供給した Agent の集合サイズ            … 閾値非依存
  - duration = 末尾から連続して供給がある step 数                 … 閾値非依存
  - edges    = len(ShockState.joined)                             … 閾値非依存

したがって記録済みの実測値を、**本物の TransitionJudge.evaluate() へそのまま
再投入する**ことで、比較演算子・同時充足ルール（all()）・
初回成立で latch する保持規則を1行も書き換えずに再判定できる。
そのために ledger の3メソッドだけを持つ replay stub を用いる。

【自己検証】
runtime D4 で replay した結果が、ログ済みの met_* / all_met / transition_step と
完全一致することを 20 run 全件で確認する。一致しなければ再判定は行わない。

使い方:
    python -m experiments.recompute_transition
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

from src.simulation.transition import TransitionJudge

OUT_DIR = Path("outputs/main_experiment")
OUT_FILE = OUT_DIR / "transition_recomputed_preregistered.json"

# docs/PREREGISTRATION_H1.md §D4（人間確定 2026-08-16、commit 2de6b52）
SHOCK_AGENT_COUNT = 6
PREREGISTERED_D4 = {
    "community_supply_share": 0.25,
    "active_supplier_count": math.ceil(SHOCK_AGENT_COUNT / 2),  # = 3
    "supply_duration_steps": 4,
    "coordination_edges": 2,
}

CONDITIONS = ("A", "B", "C", "D")
SEEDS = (2, 4, 6, 7, 9)


@dataclass(frozen=True)
class ReplayLedger:
    """記録済みの実測値を ledger インタフェースで返すだけの stub。

    TransitionJudge.evaluate() が呼ぶ3メソッドのみを提供する。
    値の再計算は一切行わない（ログ値をそのまま返す）ため、
    runtime と corrected の間に算術上の差が入らない。
    """

    share: float
    suppliers: int
    duration: int

    def community_supply_share(self) -> float:
        return self.share

    def active_supplier_count(self) -> int:
        return self.suppliers

    def supply_duration(self) -> int:
        return self.duration


def replay(rows: list[dict], thresholds: dict) -> TransitionJudge:
    """本物の TransitionJudge へログ値を再投入する。判定ロジックは再実装しない。"""
    judge = TransitionJudge.from_config(thresholds)
    for r in rows:
        judge.evaluate(
            r["step"],
            ReplayLedger(r["share"], r["suppliers"], r["duration"]),
            r["coordination_edges"],
        )
    return judge


def verify_replay_reproduces_runtime(run: dict) -> list[str]:
    """runtime 閾値で replay して、ログと1件でも食い違えば理由を返す。"""
    rows = run["transition_history"]
    judge = replay(rows, run["D4_transition"])
    problems = []
    for logged, got in zip(rows, judge.history):
        for k in ("step", "all_met", "met_community_supply_share",
                  "met_active_supplier_count", "met_supply_duration",
                  "met_coordination_edges"):
            if logged[k] != got[k]:
                problems.append(f"step {logged['step']}: {k} logged={logged[k]} replay={got[k]}")
    if judge.transitioned_at != run["transition_step"]:
        problems.append(
            f"transition_step logged={run['transition_step']} replay={judge.transitioned_at}"
        )
    if (judge.transitioned_at is not None) != run["transitioned"]:
        problems.append("transitioned フラグ不一致")
    return problems


def main() -> int:
    runs = {}
    for c in CONDITIONS:
        for s in SEEDS:
            p = OUT_DIR / f"{c}_seed{s}.json"
            runs[(c, s)] = json.loads(p.read_text(encoding="utf-8"))

    # --- 自己検証: replay が runtime を再現できるか -------------------------
    all_problems = {}
    for key, run in runs.items():
        pr = verify_replay_reproduces_runtime(run)
        if pr:
            all_problems[f"{key[0]}_seed{key[1]}"] = pr
    if all_problems:
        print("REPLAY 自己検証に失敗。corrected adjudication を中止する:")
        print(json.dumps(all_problems, ensure_ascii=False, indent=2))
        return 1
    print(f"replay 自己検証 OK: 20 run × 8 step の met_*/all_met/transition_step が完全一致")

    # --- 境界近接の確認（丸め由来の反転がないか）---------------------------
    eps = 1e-6
    near = []
    for (c, s), run in runs.items():
        for r in run["transition_history"]:
            for name, val, thr in (
                ("share", r["share"], PREREGISTERED_D4["community_supply_share"]),
            ):
                if abs(val - thr) < eps:
                    near.append(f"{c}_seed{s} step{r['step']} {name}={val} thr={thr}")

    records = []
    for c in CONDITIONS:
        for s in SEEDS:
            run = runs[(c, s)]
            rows = run["transition_history"]
            corrected = replay(rows, PREREGISTERED_D4)
            rec = {
                "condition": c,
                "seed": s,
                "runtime_D4": dict(run["D4_transition"]),
                "preregistered_D4": dict(PREREGISTERED_D4),
                "max_community_supply_share": max(r["share"] for r in rows),
                "max_active_supplier_count": max(r["suppliers"] for r in rows),
                "max_supply_duration_steps": max(r["duration"] for r in rows),
                "max_coordination_edges": max(r["coordination_edges"] for r in rows),
                "runtime_transition": run["transitioned"],
                "runtime_transition_step": run["transition_step"],
                "corrected_transition": corrected.transitioned_at is not None,
                "corrected_transition_step": corrected.transitioned_at,
                "changed_by_correction": (
                    run["transitioned"] != (corrected.transitioned_at is not None)
                    or run["transition_step"] != corrected.transitioned_at
                ),
                "corrected_history": corrected.history,
                "onset_step": run["onset_step"],
                "corrected_steps_to_transition": (
                    corrected.transitioned_at - run["onset_step"]
                    if corrected.transitioned_at is not None
                    else None
                ),
                # 未転化のボトルネック（最終 step ではなく全 step で一度でも満たせたか）
                "ever_met": {
                    k: any(r[f"met_{k}"] for r in corrected.history)
                    for k in ("community_supply_share", "active_supplier_count",
                              "supply_duration", "coordination_edges")
                },
            }
            records.append(rec)

    out = {
        "purpose": (
            "事前登録 D4 値（docs/PREREGISTRATION_H1.md §D4、commit 2de6b52）と "
            "runtime config の同期不良を、既存ログ上で事前登録値へ戻して再判定したもの。"
            "観測結果を見て閾値を変更した判定ではない。API/LLM は一切呼び出していない。"
        ),
        "not_a_replacement_of_runtime": (
            "runtime 判定（share>=0.20/duration>=3）は各 run ファイルに保持されており、"
            "本ファイルは削除・上書きしていない。どちらを主結果とするかは人間が決定する。"
        ),
        "method": (
            "既存の src.simulation.transition.TransitionJudge.evaluate() を再利用し、"
            "ログ済みの閾値非依存な実測値 (share/suppliers/duration/edges) を "
            "ReplayLedger 経由で再投入した。判定ロジックの再実装は行っていない。"
        ),
        "replay_self_check": (
            "runtime 閾値で replay した結果が、20 run 全件・全 step で "
            "ログの met_*/all_met/transition_step と完全一致することを確認済み。"
        ),
        "rounding_boundary_cases": near or "なし（閾値との差が 1e-6 未満の step は存在しない）",
        "runtime_D4": dict(runs[("A", 2)]["D4_transition"]),
        "preregistered_D4": dict(PREREGISTERED_D4),
        "preregistered_D4_source": "docs/PREREGISTRATION_H1.md §D4 (commit 2de6b52)",
        "shock_agent_count": SHOCK_AGENT_COUNT,
        "api_calls_made": 0,
        "runs": records,
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> {OUT_FILE}")

    changed = [r for r in records if r["changed_by_correction"]]
    print(f"\n変化した run: {len(changed)}")
    for r in changed:
        print(f"  {r['condition']}_seed{r['seed']}: "
              f"runtime={r['runtime_transition']}@{r['runtime_transition_step']} -> "
              f"corrected={r['corrected_transition']}@{r['corrected_transition_step']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
