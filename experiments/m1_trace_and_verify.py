"""M1 trace の生成と決定論の全件検証（LLM / API を一切呼ばない）。

【何をするか】
1. seed 1–20 × condition A/B/C/D = 80 run を trace 有効で再実行する
2. 各 run の hash を既存正典 `outputs/m1_main_summary.csv` と突合する
3. **final_state_sha256 が1件でも不一致なら FAIL で停止**（trace を動画に使わない）
4. trace は可視化専用ディレクトリへ書き出す（正典 outputs を上書きしない）

【安全性】
- `src.llm` / `anthropic` を import しない
- 既存の `outputs/` 配下を一切書き換えない（`--out` は figures/demo_video/data 配下）
- trace は RNG を消費せず状態も変更しない（src/simulation/trace.py）

使い方:
    python -m experiments.m1_trace_and_verify --seeds 20
    python -m experiments.m1_trace_and_verify --seeds 20 --verify-only   # trace を書かない
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from src.simulation.runner import run_one

CONDITIONS = ("A", "B", "C", "D")
CANON = Path("outputs/m1_main_summary.csv")
DEFAULT_OUT = Path("figures/demo_video/data/m1_trace")

# 正典と突合する決定論確認項目
COMPARE_KEYS = (
    "final_state_sha256",
    "agent_initial_states_sha256",
    "base_graph_sha256",
    "participant_ids_sha256",
    "cultural_edge_count",
    "network_density",
    "assortativity_achieved_structured",
    "assortativity_achieved_rewired",
    "assortativity_target_reached",
    "steps",
)


def load_canon() -> dict:
    rows = list(csv.DictReader(CANON.open(encoding="utf-8")))
    return {(int(r["seed"]), r["condition"]): r for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--verify-only", action="store_true",
                    help="trace を書かずに hash 検証だけ行う")
    args = ap.parse_args()

    # --- 実行前の安全確認 ---------------------------------------------------
    banned = [m for m in sys.modules if "anthropic" in m.lower() or m.startswith("src.llm")]
    print(f"[事前確認] LLM/API モジュールの読み込み: {banned if banned else 'なし（0件）'}")
    if banned:
        print("FAIL: LLM 関連モジュールが読み込まれている")
        return 1

    canon = load_canon()
    out_dir = None if args.verify_only else Path(args.out)
    if out_dir is not None:
        assert "outputs" not in out_dir.parts, "正典 outputs 配下へは書き出さない"
        out_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    results, mismatches = [], []
    for seed in range(1, args.seeds + 1):
        for c in CONDITIONS:
            s = run_one(f"configs/condition_{c.lower()}.yaml", seed=seed,
                        trace_dir=out_dir)
            ref = canon.get((seed, c))
            row = {"seed": seed, "condition": c}
            if ref is None:
                row["status"] = "no_canonical_reference"
                mismatches.append({**row, "key": "*", "reason": "正典に該当行なし"})
            else:
                bad = []
                for k in COMPARE_KEYS:
                    got, want = str(s.get(k, "")), str(ref.get(k, ""))
                    if got != want:
                        bad.append({"key": k, "got": got, "want": want})
                row["status"] = "match" if not bad else "MISMATCH"
                if bad:
                    mismatches.extend({**row, **b} for b in bad)
            row["final_state_sha256"] = s["final_state_sha256"]
            results.append(row)
        print(f"  seed {seed:>3}: " + " ".join(
            f"{r['condition']}={'OK' if r['status']=='match' else r['status']}"
            for r in results[-4:]))

    n = len(results)
    n_match = sum(1 for r in results if r["status"] == "match")
    fatal = [m for m in mismatches if m.get("key") in ("final_state_sha256", "*")]

    report = {
        "purpose": "M1 trace 追加後の決定論検証（LLM/API 0 call）",
        "canonical_source": str(CANON),
        "runs": n,
        "final_state_sha256_match": f"{n_match} / {n}",
        "compare_keys": list(COMPARE_KEYS),
        "mismatches": mismatches,
        "verdict": "PASS" if not mismatches else "FAIL",
        "trace_dir": str(out_dir) if out_dir else None,
        "wall_seconds": round(time.time() - t0, 1),
        "api_calls_made": 0,
    }
    rp = (out_dir or Path(".")) / "hash_verification.json"
    rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nfinal_state_sha256: {n_match} / {n} 一致")
    print(f"全比較項目の不一致: {len(mismatches)} 件")
    print(f"判定: {report['verdict']}  ({report['wall_seconds']}s)  -> {rp}")
    if mismatches:
        print("\n★FAIL: 不一致があるため trace を動画に使用してはならない★")
        for m in mismatches[:10]:
            print(f"  {m}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
