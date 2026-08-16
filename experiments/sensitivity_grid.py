"""感度分析 15セル（docs/DESIGN_M1.md §11、完了条件 C13）。

因子は L（learn_rate_success）と L/D 比。技能の均衡水準は L と D の比が
支配するため、片方だけを振っても意味がない。

  L    = 0.02 / 0.04 / 0.08
  L/D  = 4 / 8 / 16 / 32          -> 12セル
  加えて各 L の no-decay baseline（D=0）    ->  3セル
  合計 15セル × 4条件 × 5 seed = 300 run

no-decay baseline を必ず入れる理由: 減衰の導入（決定 D6）は H1 を自明化させない
ための設計判断だが、減衰自体がパラメータであり、減衰の値によって結論が変わるなら
その結論は減衰の設定の産物である。D=0 を併走させることで
「減衰なしでも成立するか / 減衰がある場合にのみ成立するか」を明示的に報告できる。

**感度分析は「良い結果が出るセルを探す作業ではない」。**
全15セルの結果を報告し、条件間の関係がパラメータ領域を通じて安定か不安定かを示す。
安定でなければ、それが結果である。
"""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

from src.simulation.runner import run_all_conditions

L_VALUES = (0.02, 0.04, 0.08)
LD_RATIOS = (4, 8, 16, 32)


def build_grid() -> list[dict]:
    cells = []
    n = 0
    for L in L_VALUES:
        for ratio in LD_RATIOS:
            n += 1
            cells.append(
                {"cell": f"S{n:02d}", "L": L, "ld_ratio": ratio, "decay_rate": L / ratio}
            )
    for L in L_VALUES:
        n += 1
        cells.append({"cell": f"S{n:02d}", "L": L, "ld_ratio": None, "decay_rate": 0.0})
    return cells


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--config-dir", default="configs")
    ap.add_argument("--output", default="outputs/sensitivity_grid.csv")
    ap.add_argument("--cells", default=None, help="実施するセル（例: S01,S06）。既定は全15セル")
    args = ap.parse_args()

    grid = build_grid()
    if args.cells:
        wanted = set(args.cells.split(","))
        grid = [c for c in grid if c["cell"] in wanted]

    rows: list[dict] = []
    t0 = time.time()
    for cell in grid:
        overrides = {
            "learning": {
                "learn_rate_success": cell["L"],
                "decay_rate": cell["decay_rate"],
            }
        }
        for seed in range(1, args.seeds + 1):
            results = run_all_conditions(
                args.config_dir, seed=seed, steps=args.steps, overrides=overrides
            )
            for cond, summary in results.items():
                rows.append({**cell, "seed": seed, **summary})
        print(
            f"{cell['cell']}: L={cell['L']} D={cell['decay_rate']:.6g} "
            f"({args.seeds} seeds x 4 conditions) [{time.time() - t0:.0f}s]"
        )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list({k: None for r in rows for k in r})
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n{len(rows)} runs / {len(grid)} cells in {time.time() - t0:.1f}s -> {out}")
    print("未実施セルがある場合は RESULTS.md の Limitations に必ず明記すること。")


if __name__ == "__main__":
    main()
