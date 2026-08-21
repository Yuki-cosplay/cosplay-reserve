"""生成した M1 trace 自体の整合性検証（API / LLM を呼ばない、読み取り専用）。

検査:
  1. 156 step がすべて存在するか
  2. participant 30体が各 step で追跡可能か
  3. agent_id の欠落・重複がないか
  4. action が既存 vocabulary 以外になっていないか
  5. trace から集計した action counts が既存 timeseries.csv と一致するか
  6. trace の skill 集団統計が既存 timeseries.csv と一致するか

使い方:
    python -m experiments.verify_m1_trace
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from src.simulation.trace import ALLOWED_ACTIONS

TRACE = Path("figures/demo_video/data/m1_trace")
OUTPUTS = Path("outputs")
EXPECTED_STEPS = 156
EXPECTED_AGENTS = 40
EXPECTED_PARTICIPANTS = 30

# timeseries の count 列 ← trace の action
COUNT_COLS = {
    "observe": "count_observe", "practice": "count_practice",
    "make": "count_make", "idle": "count_idle",
    "ask": "count_ask", "share": "count_share",
}


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]


def canonical_run_dir(condition: str, seed: int) -> Path | None:
    hits = sorted(OUTPUTS.glob(f"*_{condition}_seed{seed}"))
    return hits[0] if hits else None


def check(condition: str, seed: int) -> list[str]:
    """1 run 分の検査。問題があれば理由の一覧を返す。"""
    issues: list[str] = []
    d = TRACE / f"{condition}_seed{seed}"
    actions = read_jsonl(d / "actions.jsonl")
    snaps = read_jsonl(d / "snapshots.jsonl")

    # 1. 156 step
    steps = sorted({r["step"] for r in snaps})
    if steps != list(range(EXPECTED_STEPS)):
        issues.append(f"step 集合が 0..{EXPECTED_STEPS-1} でない: {steps[:3]}..{steps[-3:]}")

    # 2/3. 各 step の agent 追跡可能性・欠落・重複
    for st in steps:
        ids = [r["agent_id"] for r in snaps if r["step"] == st]
        if len(ids) != EXPECTED_AGENTS:
            issues.append(f"step{st}: snapshot が {len(ids)} 体（期待 {EXPECTED_AGENTS}）")
        if len(set(ids)) != len(ids):
            dup = [k for k, v in Counter(ids).items() if v > 1]
            issues.append(f"step{st}: agent_id 重複 {dup}")
        parts = sum(1 for r in snaps if r["step"] == st and r["is_participant"])
        if parts != EXPECTED_PARTICIPANTS:
            issues.append(f"step{st}: participant {parts} 体（期待 {EXPECTED_PARTICIPANTS}）")

    # 4. action vocabulary
    bad = {r["action"] for r in actions} - ALLOWED_ACTIONS
    if bad:
        issues.append(f"未知の action: {sorted(bad)}")

    # 5/6. 既存 timeseries.csv との照合
    run_dir = canonical_run_dir(condition, seed)
    if run_dir is None:
        return issues  # 正典 run ディレクトリが無い seed は照合をスキップ
    rows = list(csv.DictReader((run_dir / "timeseries.csv").open(encoding="utf-8")))
    ts = {int(r["step"]): r for r in rows if r["population"] == "step_totals"}
    allg = {int(r["step"]): r for r in rows if r["population"] == "all_agents"}

    for st in steps:
        # timeseries の step N 行は「step N を実行した結果」= trace の step N
        ref = ts.get(st + 1)
        if ref is None:
            continue
        got = Counter(r["action"] for r in actions if r["step"] == st)
        for act, col in COUNT_COLS.items():
            want = ref.get(col, "")
            if want in ("", None):
                continue
            if int(float(want)) != got.get(act, 0):
                issues.append(
                    f"step{st}: {act} が trace {got.get(act,0)} vs timeseries {want}")

    # skill 集団統計（all_agents）
    for st in steps:
        ref = allg.get(st + 1)
        if ref is None or not ref.get("skill_mean"):
            continue
        vals = [v for r in snaps if r["step"] == st for v in r["skills"].values()]
        if not vals:
            continue
        for col, fn in (("skill_mean", statistics.fmean),
                        ("skill_median", statistics.median),
                        ("skill_max", max)):
            if not ref.get(col):
                continue  # 比較不能な項目は判定しない
            if abs(fn(vals) - float(ref[col])) > 1e-9:
                issues.append(f"step{st}: {col} が trace {fn(vals):.12f} "
                              f"vs timeseries {ref[col]}")
        if issues:
            break  # 1 step 出れば十分

    # maker_stage の集団集計（all_agents）
    stage_cols = {"consumer": "stage_consumer", "customizer": "stage_customizer",
                  "maker": "stage_maker", "advanced_maker": "stage_advanced_maker"}
    for st in steps:
        ref = allg.get(st + 1)
        if ref is None:
            continue
        got = Counter(r["maker_stage"] for r in snaps if r["step"] == st)
        for stage, col in stage_cols.items():
            want = ref.get(col, "")
            if want in ("", None):
                continue  # 比較不能な項目は判定しない
            if int(float(want)) != got.get(stage, 0):
                issues.append(f"step{st}: {col} が trace {got.get(stage,0)} "
                              f"vs timeseries {want}")
        if issues:
            break

    # completed_projects_total の集団集計（all_agents）
    for st in steps:
        ref = allg.get(st + 1)
        if ref is None or not ref.get("completed_projects_total"):
            continue
        got = sum(r["completed_projects_total"] for r in snaps if r["step"] == st)
        if int(float(ref["completed_projects_total"])) != got:
            issues.append(f"step{st}: completed_projects_total が trace {got} "
                          f"vs timeseries {ref['completed_projects_total']}")
            break

    # method 保有数の集団集計（all_agents の method_count_total と照合）
    for st in steps:
        ref = allg.get(st + 1)
        if ref is None or not ref.get("method_count_total"):
            continue
        got = sum(r["methods_total"] for r in snaps if r["step"] == st)
        if int(float(ref["method_count_total"])) != got:
            issues.append(f"step{st}: method_count_total が trace {got} "
                          f"vs timeseries {ref['method_count_total']}")
            break
    return issues


def main() -> int:
    dirs = sorted(p for p in TRACE.iterdir() if p.is_dir())
    print(f"trace ディレクトリ: {len(dirs)} run")
    total_issues, checked = [], 0
    for p in dirs:
        cond, seed = p.name.split("_seed")
        iss = check(cond, int(seed))
        checked += 1
        if iss:
            total_issues.append({"run": p.name, "issues": iss})
    print(f"検査した run: {checked}")
    if total_issues:
        print(f"\n★不一致 {len(total_issues)} run★")
        for t in total_issues[:5]:
            print(f"  {t['run']}: {t['issues'][:3]}")
        return 1
    print("\n整合性検証: すべて一致")
    print("  検査項目: 156 step の存在 / participant 30体の全 step 追跡 / "
          "agent_id 欠落・重複 /")
    print("            action vocabulary（既存6行動のみ） / action counts / "
          "skill 集団統計（mean・median・max） /")
    print("            maker_stage 集計（4段階） / completed_projects_total / "
          "method_count_total")
    print("  ※ timeseries に対応列がない項目は判定していない（無理に一致判定しない）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
