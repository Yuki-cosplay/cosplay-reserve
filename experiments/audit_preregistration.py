"""事前登録値 vs 実行config vs run metadata の三者突合監査（API を呼ばない）。

【なぜこの監査が必要になったか】
main experiment 後の逸脱チェックは「20 run で同じ値だったか」しか見ておらず、
「**事前登録値と一致しているか**」を検査していなかった。
その結果、configs/base.yaml に PIPELINE_VALIDATION 時の暫定 D4
（share>=0.20 / duration>=3）が残存したまま 20 run が実行され、
「prompt_sha256 は20 run で1種類」「config_sha256 の差は seed のみ」という
内部整合性チェックはすべて通過してしまった。
内部整合性は**外部基準との一致を保証しない**。

【この監査の設計原則】
1. 事前登録値をこのファイルに**リテラルで固定**し、出典を明記する。
   config から読んだ値どうしを比べても、同期不良は検出できない。
2. 三者（PREREGISTERED / CONFIG / RUN METADATA）をすべて突き合わせる。
   config と metadata が一致していても、両方が事前登録から外れていることがある。
3. src/ の実験ロジックには一切触れない。読み取りのみ。

使い方:
    python -m experiments.audit_preregistration
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import yaml

OUT_DIR = Path("outputs/main_experiment")
CONFIG_DIR = Path("configs")
OUT_FILE = OUT_DIR / "preregistration_audit.json"

CONDITIONS = ("A", "B", "C", "D")
SEEDS = (2, 4, 6, 7, 9)
SHOCK_AGENT_COUNT = 6

# ---------------------------------------------------------------------------
# 事前登録値（リテラル固定）。出典を必ず添える。
# ここを config から読み込んではならない — 同期不良が検出できなくなる。
# ---------------------------------------------------------------------------
PREREGISTERED = {
    "conditions": (
        list(CONDITIONS),
        "SPEC §19 2×2完全要因計画 / docs/PREREGISTRATION_H1.md 規模表",
    ),
    "eligible_seeds": (
        [2, 4, 6, 7, 9],
        "docs/PREREGISTRATION_H1.md「確定 seed（P0修正後の再スキャン）」表",
    ),
    "shock_agent_count": (6, "docs/PREREGISTRATION_H1.md 規模表"),
    "shock_steps": (8, "docs/PREREGISTRATION_H1.md 規模表"),
    "total_runs": (20, "docs/PREREGISTRATION_H1.md 規模表"),
    "calls_per_run": (48, "docs/PREREGISTRATION_H1.md 規模表"),
    "total_calls": (960, "docs/PREREGISTRATION_H1.md 規模表"),
    "D4_community_supply_share": (0.25, "docs/PREREGISTRATION_H1.md §D4"),
    "D4_active_supplier_count": (
        math.ceil(SHOCK_AGENT_COUNT / 2),
        "docs/PREREGISTRATION_H1.md §D4（ceil(n/2), n=6 → 3）",
    ),
    "D4_supply_duration_steps": (4, "docs/PREREGISTRATION_H1.md §D4（4 step = 24h）"),
    "D4_coordination_edges": (2, "docs/PREREGISTRATION_H1.md §D4"),
    "D5_external_reference_supply_per_step": (
        3.0 * SHOCK_AGENT_COUNT,
        "docs/PREREGISTRATION_H1.md §D5 External Supply Parity Reference = 3 × n",
    ),
    "unit_demand": (200.0, "docs/PREREGISTRATION_H1.md「unit_demand の定義」（stock）"),
    "required_item_thresholds": (
        {"attr_0": 0.60, "attr_2": 0.55},
        "configs/base.yaml shock.required_item（M3 設計時に固定、SPEC §18 属性ベクトル）",
    ),
    "model": ("claude-opus-5", "M2 freeze（人間承認 2026-08-16）"),
    "prompt_version": ("m2-minimal-v1", "M2 freeze（人間承認 2026-08-16）"),
    "per_run_max_usd": (1.25, "人間承認メッセージ: CostGuard per-run $1.25"),
    "campaign_max_usd": (20.00, "人間承認メッセージ: campaign cap $20.00"),
    "max_attempts": (3, "人間承認メッセージ: run 単体の失敗は最大2回再試行（初回+2）"),
    "run_order_randomised": (True, "人間承認メッセージ: 実験順序ランダム化"),
    "topology_of_condition": (
        {"A": "structured", "B": "rewired", "C": "structured", "D": "rewired"},
        "SPEC §19",
    ),
    "peer_learning_of_condition": (
        {"A": True, "B": True, "C": False, "D": False},
        "SPEC §19",
    ),
}


def load_runs() -> dict:
    runs = {}
    for c in CONDITIONS:
        for s in SEEDS:
            p = OUT_DIR / f"{c}_seed{s}.json"
            if p.exists():
                runs[(c, s)] = json.loads(p.read_text(encoding="utf-8"))
    return runs


def load_configs() -> dict:
    base = yaml.safe_load((CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"))
    conds = {}
    for c in CONDITIONS:
        conds[c] = yaml.safe_load(
            (CONFIG_DIR / f"condition_{c.lower()}.yaml").read_text(encoding="utf-8")
        )
    return base, conds


def unique(values):
    """全 run で単一の値なら返す。割れていれば MIXED を示す。"""
    s = {json.dumps(v, sort_keys=True, ensure_ascii=False) for v in values}
    if len(s) == 1:
        return json.loads(next(iter(s)))
    return {"__MIXED__": sorted(s)}


def main() -> int:
    runs = load_runs()
    base, conds = load_configs()
    campaign = json.loads((OUT_DIR / "campaign.json").read_text(encoding="utf-8"))
    shock = base["shock"]
    tr = shock["transition"]
    rvals = list(runs.values())

    # (key, config 側の値, run metadata 側の値)
    observed = {
        "conditions": (
            sorted(conds), sorted({r["condition"] for r in rvals}),
        ),
        "eligible_seeds": (
            campaign["eligible_seeds"], sorted({r["seed"] for r in rvals}),
        ),
        "shock_agent_count": (
            campaign["shock_agent_count"], unique([len(r["shock_agent_ids"]) for r in rvals]),
        ),
        "shock_steps": (campaign["shock_steps"], unique([r["shock_steps_run"] for r in rvals])),
        "total_runs": (len(campaign["execution_order"]), len(rvals)),
        "calls_per_run": ("(config になし)", unique([r["llm_calls"] for r in rvals])),
        "total_calls": ("(config になし)", sum(r["llm_calls"] for r in rvals)),
        "D4_community_supply_share": (
            tr["community_supply_share"],
            unique([r["D4_transition"]["community_supply_share"] for r in rvals]),
        ),
        "D4_active_supplier_count": (
            tr["active_supplier_count"],
            unique([r["D4_transition"]["active_supplier_count"] for r in rvals]),
        ),
        "D4_supply_duration_steps": (
            tr["supply_duration_steps"],
            unique([r["D4_transition"]["supply_duration_steps"] for r in rvals]),
        ),
        "D4_coordination_edges": (
            tr["coordination_edges"],
            unique([r["D4_transition"]["coordination_edges"] for r in rvals]),
        ),
        "D5_external_reference_supply_per_step": (
            f"(derived: {shock.get('external_reference_mode')})",
            unique([r["D5_external_reference_supply_per_step"] for r in rvals]),
        ),
        "unit_demand": (
            shock["required_item"]["unit_demand"],
            unique([r["unit_demand_stock"] for r in rvals]),
        ),
        "required_item_thresholds": (
            shock["required_item"]["thresholds"],
            "(run metadata に未記録)",
        ),
        "model": ("(config になし)", unique([r["model"] for r in rvals])),
        "prompt_version": ("(config になし)", unique([r["prompt_version"] for r in rvals])),
        "per_run_max_usd": (
            campaign["per_run_max_usd"],
            "(run metadata に未記録; stopped_by_budget で間接確認)",
        ),
        "campaign_max_usd": (campaign["campaign_max_usd"], "(run metadata に未記録)"),
        # max_attempts は「上限」であり実測値との等値比較ではない。
        # 実測 attempt が上限以下であることを検査する（BOUND_OK）。
        "max_attempts": (
            "(config になし)",
            {"__BOUND__": max(r["attempt"] for r in rvals)},
        ),
        # 順序ランダム化は campaign.json の order_seed で駆動され、
        # 「素朴な条件×seed 順と異なること」で検査する。config 側は情報のみ。
        "run_order_randomised": (
            f"(order_seed={campaign['order_seed']})",
            [(o["condition"], o["seed"]) for o in campaign["execution_order"]]
            != [(c, s) for c in CONDITIONS for s in SEEDS],
        ),
        "topology_of_condition": (
            {c: conds[c]["topology"] for c in CONDITIONS}, "(run metadata に未記録)",
        ),
        "peer_learning_of_condition": (
            {c: conds[c]["peer_learning_enabled"] for c in CONDITIONS},
            "(run metadata に未記録)",
        ),
    }

    rows, mismatches = [], []
    for key, (expected, source) in PREREGISTERED.items():
        cfg_v, meta_v = observed[key]
        # 「未記録」「config になし」は不一致ではなく不可検証として扱う
        def cmp(v):
            # 「config になし」「run metadata に未記録」等は不一致ではなく不可検証
            if isinstance(v, str) and v.startswith("("):
                return "N/A"
            if isinstance(v, dict) and "__MIXED__" in v:
                return "MISMATCH"  # 20 run で値が割れている
            if isinstance(v, dict) and "__BOUND__" in v:
                # 上限項目: 実測 <= 事前登録上限 なら適合
                return "MATCH" if v["__BOUND__"] <= expected else "MISMATCH"
            return "MATCH" if v == expected else "MISMATCH"

        c_res, m_res = cmp(cfg_v), cmp(meta_v)
        verdict = (
            "MISMATCH" if "MISMATCH" in (c_res, m_res)
            else ("N/A" if c_res == m_res == "N/A" else "MATCH")
        )
        row = {
            "item": key,
            "preregistered": expected,
            "preregistered_source": source,
            "runtime_config": cfg_v,
            "run_metadata": meta_v,
            "config_vs_prereg": c_res,
            "metadata_vs_prereg": m_res,
            "verdict": verdict,
        }
        rows.append(row)
        if verdict == "MISMATCH":
            mismatches.append(row)

    out = {
        "purpose": (
            "PREREGISTRATION で固定された値 / 実行 config / run metadata の"
            "三者を明示的に突き合わせる。内部整合性（20 run で同一か）だけでは"
            "事前登録との同期不良を検出できないため。"
        ),
        "api_calls_made": 0,
        "n_items": len(rows),
        "n_mismatch": len(mismatches),
        "mismatched_items": [r["item"] for r in mismatches],
        "known_document_inconsistencies": [
            {
                "file": "docs/PREREGISTRATION_H1.md",
                "section": "main experiment 規模（人間承認待ち）",
                "problem": "eligible seeds が無効化済み旧 scan の 5,7,11,13,14 のまま",
                "authoritative": "同ファイル「確定 seed（P0修正後の再スキャン）」表の 2,4,6,7,9",
                "runtime_impact": "なし。実行は 2,4,6,7,9 を使用している",
            }
        ],
        "rows": rows,
    }
    OUT_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    w = max(len(r["item"]) for r in rows)
    print(f"{'item'.ljust(w)} | {'PREREGISTERED':<28} | {'RUNTIME(config/metadata)':<34} | verdict")
    print("-" * (w + 76))
    for r in rows:
        pre = json.dumps(r["preregistered"], ensure_ascii=False)[:28]
        rt = f"{json.dumps(r['runtime_config'], ensure_ascii=False)[:16]} / {json.dumps(r['run_metadata'], ensure_ascii=False)[:16]}"
        print(f"{r['item'].ljust(w)} | {pre:<28} | {rt:<34} | {r['verdict']}")
    print(f"\nMISMATCH: {len(mismatches)} 件 -> {OUT_FILE}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
