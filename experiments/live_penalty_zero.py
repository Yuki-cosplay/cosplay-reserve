"""partial-equilibrium 仮定の実測（live run 2本、LLM を実行する）。

事前登録: docs/PREREGISTRATION_SENSITIVITY.md §7（本スクリプト実行**前**に確定済み）
限界の記録: docs/LIMITATIONS_CANDIDATES.md L13

【目的】
replay（Agent の意思決定をログに固定）の予測値 X と、
live run（Agent が再意思決定する）の実測値 Y の差 D = Y − X を測り、
partial-equilibrium 近似の妥当性を判定する。

**「penalty=0 なら転化するか」を確かめる実験ではない。**
転化の有無は結果として報告するのみ。

【設定（事前登録で固定。変更禁止）】
    condition A / seed 2, 4 / modify_difficulty_penalty = 0.00
    他は main experiment と完全に同一（D4 は正式事前登録値 0.25/3/4/2）
    2 run で打ち止め。追加 run を実行しない。

【実装方針】
main experiment と**同一のコード経路**を使う。experiments.m3_main.execute_run() を
そのまま呼び、build_world だけを差し替えて penalty を上書きする。
execute_run を複製しない（複製すると main experiment と経路が乖離しうる）。
src/ は一切変更しない。

【予測（実行前に固定、docs/PREREGISTRATION_SENSITIVITY.md §7.3）】
    seed 2: X = 49.980 units,  許容帯 ±2.00
    seed 4: X = 54.880 units,  許容帯 ±2.10

使い方:
    python -m experiments.live_penalty_zero --dry-run   # API を呼ばず設定だけ確認
    python -m experiments.live_penalty_zero             # 実行
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from experiments import m3_main as M
from src.world.world import build_world as _build_world_original

OUT_DIR = Path("outputs/live_penalty_zero")

# --- 事前登録で固定した値（結果を見て変更しない）---------------------------
CONDITION = "A"
SEEDS = (2, 4)
PENALTY = 0.00
PER_RUN_MAX_USD = 1.25
CAMPAIGN_MAX_USD = 3.00
MAX_ATTEMPTS = 3  # 初回 + 再試行2回

# docs/PREREGISTRATION_SENSITIVITY.md §7.3（live run 実行前に確定）
REPLAY_PREDICTION = {
    2: {"expected_community_supply_total": 49.980, "units_per_step": 6.247,
        "tolerance_2sd": 2.00, "qualifying_attempts": 51,
        "corrected_transition_probability": 0.9855},
    4: {"expected_community_supply_total": 54.880, "units_per_step": 6.860,
        "tolerance_2sd": 2.10, "qualifying_attempts": 56,
        "corrected_transition_probability": 1.0000},
}


def _build_world_with_penalty(config_path, seed: int):
    """main experiment と同一の build_world に penalty の上書きだけを加える。

    **上書きするのは modify_difficulty_penalty の 1 キーのみ。**
    D4・D5・unit_demand・topology・peer_learning・材料・設備・時間予算はすべて
    main experiment と同一である（configs を変更しないため）。
    """
    world = _build_world_original(config_path, seed=seed)
    before = world.cfg["shock"]["modify_difficulty_penalty"]
    world.cfg["shock"]["modify_difficulty_penalty"] = PENALTY
    world.provenance["modify_difficulty_penalty_override"] = {
        "from": before, "to": PENALTY,
        "reason": "docs/PREREGISTRATION_SENSITIVITY.md §7 partial-equilibrium の実測",
    }
    return world


def result_path(seed: int) -> Path:
    return OUT_DIR / f"{CONDITION}_seed{seed}_penalty0.json"


def completed() -> dict[int, dict]:
    done = {}
    for s in SEEDS:
        p = result_path(s)
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if d.get("status") in ("completed", "failed"):
                done[s] = d
    return done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="API を呼ばず設定だけ表示")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = completed()
    cumulative = sum(float(d.get("spent_usd", 0.0)) for d in done.values())
    pending = [s for s in SEEDS if s not in done]

    print(f"live run (penalty={PENALTY:.2f}): {len(done)}/{len(SEEDS)} 完了済み / 残り {len(pending)}")
    print(f"累積費用: ${cumulative:.4f} / campaign cap ${CAMPAIGN_MAX_USD:.2f}")
    print(f"対象: 条件{CONDITION} seed {list(SEEDS)}  per-run cap ${PER_RUN_MAX_USD:.2f}")
    for s in SEEDS:
        p = REPLAY_PREDICTION[s]
        print(f"  seed{s} replay 予測 X={p['expected_community_supply_total']:.3f} "
              f"許容帯 ±{p['tolerance_2sd']:.2f}")

    if args.dry_run:
        print(f"\n[DRY-RUN] 残り {len(pending)} run。API は呼びません。")
        return 0

    # main experiment と同一経路を使うための差し替え（このプロセス内のみ）
    M.build_world = _build_world_with_penalty
    M.PER_RUN_MAX_USD = PER_RUN_MAX_USD
    M.SHOCK_AGENTS = 6
    M.SHOCK_STEPS = 8

    for seed in pending:
        if cumulative + PER_RUN_MAX_USD > CAMPAIGN_MAX_USD:
            print(f"\n[STOP] campaign cap 到達: "
                  f"${cumulative:.4f} + ${PER_RUN_MAX_USD:.2f} > ${CAMPAIGN_MAX_USD:.2f}")
            print("新規 run を開始せず停止します。")
            break

        result = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"\n>>> {CONDITION}_seed{seed} penalty={PENALTY:.2f} "
                  f"(attempt {attempt}/{MAX_ATTEMPTS})")
            try:
                result = M.execute_run(CONDITION, seed, attempt)
            except Exception as exc:
                result = {
                    "status": "failed", "error": f"{type(exc).__name__}: {exc}",
                    "attempt": attempt, "condition": CONDITION, "seed": seed,
                    "spent_usd": 0.0,
                    "run_ended_utc": datetime.now(timezone.utc).isoformat(),
                }
            cumulative += float(result.get("spent_usd", 0.0))
            if result["status"] == "completed":
                break
            print(f"    失敗: {result.get('error')}")

        # main experiment の run と取り違えないよう用途を上書きする
        result["run_purpose"] = "live_penalty_zero_partial_equilibrium_check"
        result["modify_difficulty_penalty"] = PENALTY
        result["preregistration"] = "docs/PREREGISTRATION_SENSITIVITY.md §7"
        result["replay_prediction"] = REPLAY_PREDICTION[seed]
        result["cumulative_spend_after_run"] = round(cumulative, 6)
        result["not_for_condition_comparison"] = (
            "n=2。条件間比較・仮説検証には使用しない。主結果にも使用しない。"
        )
        obs = result.get("community_supply_total")
        if obs is not None:
            x = REPLAY_PREDICTION[seed]["expected_community_supply_total"]
            tol = REPLAY_PREDICTION[seed]["tolerance_2sd"]
            result["live_minus_replay"] = round(obs - x, 4)
            result["within_tolerance"] = abs(obs - x) <= tol
            print(f"    供給 Y={obs:.1f}  X={x:.3f}  D={obs - x:+.3f}  "
                  f"許容帯 ±{tol:.2f} → {'一致' if abs(obs - x) <= tol else '不一致'}")

        result_path(seed).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"    {result['status']}  ${result.get('spent_usd', 0):.4f}  "
              f"累積=${cumulative:.4f}")

    print(f"\n完了。累積費用 ${cumulative:.4f} / cap ${CAMPAIGN_MAX_USD:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
