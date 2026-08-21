"""modify_difficulty_penalty の感度分析（deterministic replay、API / LLM 0 call）。

事前登録: docs/PREREGISTRATION_SENSITIVITY.md（本スクリプト実行**前**に確定済み）
限界の記録: docs/LIMITATIONS_CANDIDATES.md L12（技能飽和）/ L13（partial-equilibrium）

【何をするか】
既存 main experiment の provenance から p_base を復元し、
production layer だけを 4 つの penalty 値で再計算する。
Agent の意思決定（intent）はログに固定する。LLM は再実行しない。

【なぜ replay が厳密か】
success_probability() は penalty を参照しないため p_base は penalty 非依存であり、
    p_base = p_eff_logged × (1 + 0.35 × n_shifts)
で復元できる。唯一の帰還経路（成功/失敗 → 技能 → p_base）は、
技能が 0.998 に飽和し p_base が上限 0.98 にクリップされているため不活性である
（最悪ケースの技能乖離 0.0008 << クリップまでの余裕 0.314）。詳細は L12。

【判定ロジックを再実装しない】
副次指標の転化判定は既存の src.simulation.transition.TransitionJudge.evaluate() を
そのまま呼ぶ。ledger も本物の SupplyLedger を使う。

使い方:
    python -m experiments.sensitivity_replay
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from src.simulation.transition import TransitionJudge
from src.world.demand import SupplyLedger

IN_DIR = Path("outputs/main_experiment")
OUT_DIR = Path("outputs/sensitivity_replay")

# --- 事前登録で固定した値（結果を見て変更しない）---------------------------
PENALTIES = (0.00, 0.15, 0.35, 0.50)
CURRENT_PENALTY = 0.35
N_MC = 2000  # common random numbers の反復数
PREREGISTERED_D4 = {
    "community_supply_share": 0.25,
    "active_supplier_count": 3,
    "supply_duration_steps": 4,
    "coordination_edges": 2,
}
UNIT_YIELD = 1.0
EXTERNAL_REF_PER_STEP = 18.0  # D5 = 3 × shock_agent_count(6)
CONDITIONS = ("A", "B", "C", "D")
SEEDS = (2, 4, 6, 7, 9)
SHOCK_STEPS = 8

# 予測 P1（事前登録 §4、実行前に記録済み）
PREDICTION = {
    "P1": "penalty=0.00 のとき条件A の供給は約 6.4 units/step（6.58 × 0.98 ≈ 6.45）",
    "P1_value_units_per_step": 6.45,
    "P2": "D4 閾値 6.00 をわずかに超える水準（約 +7%）。転化の有無は断定しない",
}


def recover_p_base(p_eff: float, n_shifts: int) -> float:
    """ログの実効確率から penalty 適用前の p_base を復元する。

    success_probability() は penalty を参照しないため、この復元は厳密である。
    """
    return p_eff * (1.0 + CURRENT_PENALTY * n_shifts)


def apply_penalty(p_base: float, n_shifts: int, penalty: float) -> float:
    """src/world/shock.py:132-136 と同一の式。"""
    div = 1.0 + penalty * n_shifts
    return max(0.02, min(0.98, p_base / div))


def draw_u(condition: str, seed: int, step: int, agent_id: str, idx: int) -> float:
    """make 試行ごとの一様乱数。penalty 値によらず同一（common random numbers）。

    ハッシュから決定論的に導出するため、実行のたびに同じ値になる。
    """
    key = f"{condition}|{seed}|{step}|{agent_id}|{idx}".encode()
    h = hashlib.sha256(key).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def load_attempts(run: dict) -> list[dict]:
    """make 試行を、penalty 非依存な属性つきで取り出す。"""
    out, counter = [], {}
    for p in run["provenance"]:
        n = len(p["applied_modifications"] or {})
        k = (p["step"], p["agent_id"])
        counter[k] = counter.get(k, 0) + 1
        out.append({
            "step": p["step"],
            "agent_id": p["agent_id"],
            "idx": counter[k] - 1,
            "n_shifts": n,
            "p_base": recover_p_base(p["effective_success_probability"], n),
            # penalty 非依存な量はログ値をそのまま使う
            "meets_requirement": bool(p["meets_requirement"]),
            "logged_p_eff": p["effective_success_probability"],
            "logged_success": bool(p["make_success"]),
            "logged_units": p["supplied_units"],
        })
    return out


def analytic(attempts: list[dict], penalty: float) -> dict:
    """主要指標: 解析的期待値（RNG 不使用、Monte Carlo 誤差ゼロ）。"""
    e_supply = 0.0
    e_success = 0.0
    for a in attempts:
        pe = apply_penalty(a["p_base"], a["n_shifts"], penalty)
        e_success += pe
        if a["meets_requirement"]:
            e_supply += pe * UNIT_YIELD
    n = len(attempts)
    return {
        "make_attempts": n,
        "qualifying_attempts": sum(1 for a in attempts if a["meets_requirement"]),
        "expected_community_supply_total": e_supply,
        "expected_units_per_step": e_supply / SHOCK_STEPS,
        "expected_make_success_rate": e_success / n if n else 0.0,
        "gap_vs_required_6_per_step": e_supply / SHOCK_STEPS - 6.0,
        "ratio_vs_required": (e_supply / SHOCK_STEPS) / 6.0 if e_supply else 0.0,
    }


def monte_carlo(attempts: list[dict], penalty: float, coord_by_step: dict) -> dict:
    """副次指標: CRN Monte Carlo。転化判定は本物の TransitionJudge を再利用する。"""
    steps = sorted({a["step"] for a in attempts} | set(coord_by_step))
    # 各試行の u は penalty によらず固定
    us = np.array([draw_u(a["_c"], a["_s"], a["step"], a["agent_id"], a["idx"])
                   for a in attempts])
    pes = np.array([apply_penalty(a["p_base"], a["n_shifts"], penalty) for a in attempts])
    qual = np.array([a["meets_requirement"] for a in attempts])
    rng = np.random.default_rng(20260816)  # MC 反復の攪拌のみに使用

    n_trans, trans_steps, max_shares, supplies = 0, [], [], []
    for r in range(N_MC):
        # 反復ごとに u を決定論的に回転させる（CRN を保ちつつ反復間で独立にする）
        shift = rng.random(len(us)) if r > 0 else np.zeros(len(us))
        u = (us + shift) % 1.0
        succ = u < pes
        ledger = SupplyLedger(baseline_per_step=EXTERNAL_REF_PER_STEP)
        judge = TransitionJudge.from_config(PREREGISTERED_D4)
        by_step = {}
        for i, a in enumerate(attempts):
            if succ[i] and qual[i]:
                by_step.setdefault(a["step"], []).append(a["agent_id"])
        ms = 0.0
        for st in steps:
            ledger.start_step()
            for aid in by_step.get(st, []):
                ledger.record_supply(aid, UNIT_YIELD, st)
            judge.evaluate(st, ledger, coord_by_step.get(st, 0))
            ms = max(ms, ledger.community_supply_share())
        supplies.append(ledger.community_total)
        max_shares.append(ms)
        if judge.transitioned_at is not None:
            n_trans += 1
            trans_steps.append(judge.transitioned_at)
    return {
        "mc_replications": N_MC,
        "mc_mean_community_supply_total": float(np.mean(supplies)),
        "mc_mean_max_community_supply_share": float(np.mean(max_shares)),
        "mc_p95_max_community_supply_share": float(np.percentile(max_shares, 95)),
        "corrected_transition_probability": n_trans / N_MC,
        "corrected_transition_step_median": (
            float(np.median(trans_steps)) if trans_steps else None
        ),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = {}
    for c in CONDITIONS:
        for s in SEEDS:
            runs[(c, s)] = json.loads(
                (IN_DIR / f"{c}_seed{s}.json").read_text(encoding="utf-8")
            )

    # --- 妥当性検証: penalty=0.35 の解析期待値が実測を再現するか ------------
    obs = sum(sum(p["supplied_units"] for p in r["provenance"]) for r in runs.values())
    exp = 0.0
    for r in runs.values():
        exp += analytic(load_attempts(r), CURRENT_PENALTY)["expected_community_supply_total"]
    validation = {
        "observed_total_supply": obs,
        "analytic_expected_at_current_penalty": exp,
        "difference": obs - exp,
        "relative_difference_pct": (obs - exp) / exp * 100.0,
        "note": (
            "解析的期待値が実測を Monte Carlo 誤差の範囲で再現していることの確認。"
            "系統的なズレがあれば replay 方式が誤っている。"
        ),
    }
    print(f"[検証] penalty={CURRENT_PENALTY}: 実測 {obs:.1f} / 解析 {exp:.2f} "
          f"({validation['relative_difference_pct']:+.1f}%)")

    records = []
    for c in CONDITIONS:
        for s in SEEDS:
            run = runs[(c, s)]
            att = load_attempts(run)
            for a in att:
                a["_c"], a["_s"] = c, s
            coord = {row["step"]: row["coordination_edges"]
                     for row in run["transition_history"]}
            for pen in PENALTIES:
                rec = {
                    "condition": c,
                    "seed": s,
                    "modify_difficulty_penalty": pen,
                    "is_current_model": pen == CURRENT_PENALTY,
                    **analytic(att, pen),
                    **monte_carlo(att, pen, coord),
                }
                rec["observed_supply_at_current_penalty"] = sum(
                    p["supplied_units"] for p in run["provenance"]
                )
                records.append(rec)
        print(f"  条件 {c} 完了")

    out = {
        "purpose": (
            "modify_difficulty_penalty=0.35 は実データで校正されていない。"
            "B8 の bottleneck 診断がこの単一パラメータにどの程度依存するかを測る。"
            "Transition を成功させることは目的ではない。"
        ),
        "preregistration": "docs/PREREGISTRATION_SENSITIVITY.md",
        "limitations": ["L12 技能飽和", "L13 partial-equilibrium"],
        "api_calls_made": 0,
        "penalties": list(PENALTIES),
        "penalty_note": (
            "0.35 = current model（未校正）。0.00 = penalty なしの構造的上限。"
            "0.15 / 0.50 は実証値ではなく model sensitivity range。"
        ),
        "preregistered_D4": PREREGISTERED_D4,
        "prediction_recorded_before_execution": PREDICTION,
        "p_base_recovery_formula": "p_base = p_eff_logged * (1 + 0.35 * n_shifts)",
        "skill_feedback_inert_proof": (
            "技能 0.9976-0.9985 に飽和、p_base の 99.6% が上限 0.98 にクリップ。"
            "最悪ケースの技能乖離 0.0008 << クリップまでの余裕 0.314。詳細は L12。"
        ),
        "method_validation": validation,
        "records": records,
    }
    (OUT_DIR / "penalty_sensitivity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"-> {OUT_DIR / 'penalty_sensitivity.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
