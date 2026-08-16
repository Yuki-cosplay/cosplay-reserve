"""M1 スモーク実行: 4条件 × N seed（docs/DESIGN_M1.md §12、完了条件 C1）。

seed 設計:
  開発中の smoke  1〜5    実装反復用。結果の解釈に使わない
  感度分析        5       15セル × 4条件 × 5
  最終主実験      20      4条件 × 20。事前登録してから実行する

使い方:
  python -m experiments.m1_smoke --seeds 5            # 開発 smoke
  python -m experiments.m1_smoke --seeds 20 --output outputs  # 最終主実験
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from src.common.io import write_text
from src.simulation.runner import run_all_conditions

CONDITIONS = ("A", "B", "C", "D")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5, help="seed 数（1..N を使用）")
    ap.add_argument("--steps", type=int, default=None, help="蓄積相の step 数（既定は config）")
    ap.add_argument("--config-dir", default="configs")
    ap.add_argument("--output", default=None, help="run ごとの成果物を書き出す先")
    ap.add_argument("--summary", default="outputs/m1_smoke_summary.csv")
    args = ap.parse_args()

    rows: list[dict] = []
    t0 = time.time()
    for seed in range(1, args.seeds + 1):
        results = run_all_conditions(
            args.config_dir, seed=seed, steps=args.steps, output_dir=args.output
        )
        for cond, summary in results.items():
            rows.append({"seed": seed, **summary})
        print(
            f"seed {seed:>3}: "
            + " ".join(
                f"{c}={results[c]['final_state_sha256'][:8]}" for c in CONDITIONS
            )
        )

    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list({k: None for r in rows for k in r})
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} runs in {time.time() - t0:.1f}s -> {out}")

    # 完全ペアリングの確認（C11）: A/C と B/D の base_graph_sha256 が一致すること
    bad = []
    for seed in range(1, args.seeds + 1):
        by_cond = {r["condition"]: r for r in rows if r["seed"] == seed}
        if by_cond["A"]["base_graph_sha256"] != by_cond["C"]["base_graph_sha256"]:
            bad.append((seed, "A/C"))
        if by_cond["B"]["base_graph_sha256"] != by_cond["D"]["base_graph_sha256"]:
            bad.append((seed, "B/D"))
    print("pairing OK" if not bad else f"PAIRING VIOLATION: {bad}")


if __name__ == "__main__":
    main()
