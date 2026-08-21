"""RESULTS.md の Figure 5枚を既存ログから生成する（新規実験なし、API 0 call）。

【原則】
- **数値は一切ハードコードしない。** すべて outputs/ 配下の JSON から読み取る。
  ハードコードした瞬間、図とログの乖離を検出できなくなる。
- 図中に禁止表現を入れない（RESULTS.md §11 の一覧を参照）。
- 各図の下にデータの出所（ファイルパス）を1行入れる。

使い方:
    python figures/make_figures.py
"""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "outputs" / "main_experiment"
SENS = ROOT / "outputs" / "sensitivity_replay" / "penalty_sensitivity.json"
OUT = ROOT / "figures"
DPI = 300

# --- 日本語フォント設定（Windows 実績。無ければ順に fallback）-----------------
JP_FONTS = ["Meiryo", "Yu Gothic", "MS Gothic", "Noto Sans CJK JP", "Hiragino Sans",
            "IPAGothic", "TakaoGothic", "DejaVu Sans"]
matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = JP_FONTS
matplotlib.rcParams["axes.unicode_minus"] = False  # 日本語フォントで負号が化けるため

INK = "#1a1a1a"
MUTED = "#8a8a8a"
OK = "#2e7d5b"
GAP = "#b5533c"
ACCENT = "#33628f"
LIGHT = "#dcdcdc"

CONDITIONS = ("A", "B", "C", "D")
SEEDS = (2, 4, 6, 7, 9)


# --- データ読み込み（ここが唯一の数値の出どころ）-----------------------------

def load_runs() -> dict:
    return {(c, s): json.loads((MAIN / f"{c}_seed{s}.json").read_text(encoding="utf-8"))
            for c in CONDITIONS for s in SEEDS}


def load_corrected() -> dict:
    return json.loads((MAIN / "transition_recomputed_preregistered.json").read_text(encoding="utf-8"))


def load_sens() -> dict:
    return json.loads(SENS.read_text(encoding="utf-8"))


def source_note(fig, text: str) -> None:
    fig.text(0.5, 0.012, text, ha="center", va="bottom",
             fontsize=6.5, color=MUTED, style="italic")


# --- F1: 主結果 — 転化条件の内訳 ---------------------------------------------

def fig1(corrected: dict) -> None:
    d4 = corrected["preregistered_D4"]
    runs = corrected["runs"]
    n = len(runs)
    keys = [
        ("active_supplier_count", f"供給者が形成されたか\n(active_supplier_count ≥ {d4['active_supplier_count']})"),
        ("supply_duration", f"供給が継続したか\n(supply_duration ≥ {d4['supply_duration_steps']} step = 24h)"),
        ("coordination_edges", f"協調関係が形成されたか\n(coordination_edges ≥ {d4['coordination_edges']})"),
        ("community_supply_share", f"量が閾値に達したか\n(community_supply_share ≥ {d4['community_supply_share']})"),
    ]
    counts = [sum(1 for r in runs if r["ever_met"][k]) for k, _ in keys]
    labels = [lab for _, lab in keys]

    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    y = range(len(keys))
    ax.barh(list(y), [n] * len(keys), color=LIGHT, height=0.6, zorder=1)
    colors = [OK if c == n else GAP for c in counts]
    ax.barh(list(y), counts, color=colors, height=0.6, zorder=2)

    for i, c in enumerate(counts):
        ax.text(c + 0.35, i, f"{c} / {n} run", va="center", ha="left",
                fontsize=11, color=colors[i], fontweight="bold", zorder=3)

    ax.set_yticks(list(y))
    ax.set_yticklabels(labels, fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(0, n * 1.28)
    ax.set_xticks([0, 5, 10, 15, 20])
    ax.set_xlabel("条件を1 step でも充足した run 数", fontsize=9.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)

    n_trans = sum(1 for r in runs if r["corrected_transition"])
    n_share = sum(1 for r in runs if r["ever_met"]["community_supply_share"])
    fig.text(0.012, 0.945, "転化の4条件のうち、3つは全 run で充足された",
             fontsize=13, fontweight="bold", color=INK)
    fig.text(0.012, 0.893,
             f"4条件の同時充足（転化）は {n_trans}/{n} run。未充足は量の1条件のみ。",
             fontsize=9.5, color=MUTED)
    fig.text(0.012, 0.113,
             f"※ 量の条件は {n_share}/{n} run で瞬間的に充足したが（いずれもショック直後）、"
             f"供給継続の条件（≥ {d4['supply_duration_steps']} step）が成立する時刻には"
             f"届いていない。\n"
             f"　 そのため4条件が同時に成立した run は {n_trans}/{n} である。",
             fontsize=8, color=MUTED, linespacing=1.5)
    source_note(fig, "出所: outputs/main_experiment/transition_recomputed_preregistered.json"
                     "（事前登録 D4 による判定）")
    fig.tight_layout(rect=(0, 0.175, 1, 0.865))
    fig.savefig(OUT / "F1_transition_conditions.png", dpi=DPI)
    plt.close(fig)
    return counts, n_trans, n


# --- F2: 感度分析 — 何が結論を支配していたか ---------------------------------

def solve_boundary(runs: dict, target: float, current_penalty: float) -> float:
    """P* を既存ログから数値的に解く（RESULTS.md §8.5 と同一手続き）。"""
    att = []
    for r in runs.values():
        for p in r["provenance"]:
            k = len(p["applied_modifications"] or {})
            att.append((k, p["effective_success_probability"] * (1 + current_penalty * k),
                        p["meets_requirement"]))
    n_run = len(runs)
    steps = len(next(iter(runs.values()))["transition_history"])

    def supply(P):
        return sum(max(0.02, min(0.98, pb / (1.0 + P * k)))
                   for k, pb, q in att if q) / n_run / steps

    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if supply(mid) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def fig2(sens: dict, runs: dict) -> None:
    R = sens["records"]
    pens = sorted(sens["penalties"])
    cur = next(p for p in pens if any(
        x["is_current_model"] for x in R if x["modify_difficulty_penalty"] == p))
    prob = {p: st.fmean(x["corrected_transition_probability"]
                        for x in R if x["modify_difficulty_penalty"] == p) for p in pens}
    rate = {p: st.fmean(x["expected_units_per_step"]
                        for x in R if x["modify_difficulty_penalty"] == p) for p in pens}
    required = 6.0  # D4 share=0.25 の逆算値。下で検証する
    # 6.0 の根拠を config 由来で確認（ハードコードを避ける）
    d4 = sens["preregistered_D4"]
    ext = json.loads((MAIN / "A_seed2.json").read_text(encoding="utf-8"))[
        "D5_external_reference_supply_per_step"]
    s = d4["community_supply_share"]
    required = s * ext / (1 - s)

    pstar = solve_boundary(runs, required, cur)
    span_pen = max(rate.values()) - min(rate.values())
    span_cond = max(
        abs(st.fmean(x["expected_units_per_step"] for x in R
                     if x["modify_difficulty_penalty"] == p and x["condition"] == a)
            - st.fmean(x["expected_units_per_step"] for x in R
                       if x["modify_difficulty_penalty"] == p and x["condition"] == b))
        for p in pens for a in CONDITIONS for b in CONDITIONS)

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(11.5, 4.9), gridspec_kw={"width_ratios": [2.05, 1]})

    ax.plot(pens, [prob[p] for p in pens], "-o", color=ACCENT, lw=2, ms=7, zorder=3)
    for p in pens:
        # 先頭は P* の縦線と重なるため左下へ逃がす
        off = (2, -18) if p == pens[0] else (6, 8)
        ax.annotate(f"{prob[p]:.4f}", (p, prob[p]), textcoords="offset points",
                    xytext=off, fontsize=9, color=ACCENT, fontweight="bold")

    ax.axvline(pstar, color=GAP, ls="--", lw=1.6, zorder=2)
    ax.text(pstar + 0.008, 0.60, f"P* = {pstar:.4f}\nD4 供給閾値相当の感度境界",
            fontsize=8.5, color=GAP, fontweight="bold", va="center")
    ax.axvline(cur, color=INK, ls=":", lw=1.6, zorder=2)
    ax.text(cur - 0.01, 0.60, f"current model\n{cur:.2f}（P* の約 {cur / pstar:.1f} 倍）",
            fontsize=8.5, color=INK, fontweight="bold", va="center", ha="right")

    ax.set_xlabel("modify_difficulty_penalty（実データで校正されていない）", fontsize=9.5)
    ax.set_ylabel("転化確率（事前登録 D4、CRN Monte Carlo）", fontsize=9.5)
    ax.set_ylim(-0.06, 1.12)
    ax.set_xlim(-0.03, max(pens) + 0.05)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.set_title("結論を支配していたのは、校正されていない1パラメータだった",
                 fontsize=12.5, fontweight="bold", color=INK, loc="left", pad=12)

    ax.annotate("penalty = 0.00 は\n「追加ペナルティをゼロと仮定した\nモデル上の構造的上限ケース」",
                xy=(pens[0] + 0.004, prob[pens[0]] + 0.02), xytext=(0.115, 0.97),
                fontsize=8, color=MUTED, linespacing=1.5,
                arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.9,
                                connectionstyle="arc3,rad=0.15"))

    ax2.bar([0, 1], [span_pen, span_cond], color=[ACCENT, LIGHT], width=0.55)
    for i, v in enumerate([span_pen, span_cond]):
        ax2.text(i, v + 0.09, f"{v:.3f}", ha="center", fontsize=10.5,
                 fontweight="bold", color=INK)
    ax2.set_xticks([0, 1])
    ax2.set_xticklabels(["penalty\n(0.00→0.50)", "条件\nA/B/C/D"], fontsize=9)
    ax2.set_ylabel("期待供給率の変動幅 (units/step)", fontsize=9)
    ax2.set_ylim(0, span_pen * 1.32)
    for sp in ("top", "right"):
        ax2.spines[sp].set_visible(False)
    ax2.set_title(f"penalty の効果は\n実験の主要因子の約 {span_pen / span_cond:.1f} 倍",
                  fontsize=10.5, fontweight="bold", color=INK, loc="left", pad=10)

    source_note(fig, "出所: outputs/sensitivity_replay/penalty_sensitivity.json"
                     " / outputs/main_experiment/*.json（P* は同ログから数値解）")
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(OUT / "F2_penalty_sensitivity.png", dpi=DPI)
    plt.close(fig)
    return pstar, cur, span_pen, span_cond


# --- F3: 創発経路 — Agent は何をしたか ---------------------------------------

def pick_path(runs: dict):
    """要求を満たさない状態から modify で充足へ至った最初の記録を選ぶ。"""
    for (c, s), r in sorted(runs.items()):
        for p in r["provenance"]:
            mods = p["applied_modifications"] or {}
            req = p["required_attributes"]
            if (p["supplied_units"] > 0 and len(mods) >= 2
                    and all(p["before_attributes"][a] < t for a, t in req.items())):
                return c, s, p
    raise RuntimeError("該当する経路が見つからない")


def fig3(runs: dict) -> None:
    c, s, p = pick_path(runs)
    req = p["required_attributes"]
    attrs = sorted(req)
    before = [p["before_attributes"][a] for a in attrs]
    after = [p["after_attributes"][a] for a in attrs]
    thr = [req[a] for a in attrs]
    mods = p["applied_modifications"]

    fig, ax = plt.subplots(figsize=(9.8, 4.9))
    xs = [0.0, 1.0]
    for i, a in enumerate(attrs):
        col = [ACCENT, OK][i % 2]
        # modify 矢印は属性ごとに水平位置をずらす（重ねると読めなくなる）
        ax_pos = 0.34 + i * 0.30
        ax.plot(xs, [before[i], after[i]], "-o", lw=2.2, ms=9,
                color=col, zorder=3, label=f"{a}（要求 ≥ {req[a]}）")
        ax.axhline(thr[i], color=col, ls="--", lw=1.0, alpha=0.55, zorder=1)
        ax.text(-0.055, before[i], f"{before[i]:.2f}", ha="right", va="center",
                fontsize=10, color=INK)
        ax.text(1.055, after[i], f"{after[i]:.2f}", ha="left", va="center",
                fontsize=10, fontweight="bold", color=INK)
        lo = before[i] + (after[i] - before[i]) * ax_pos
        ax.annotate("", xy=(ax_pos, lo + mods[a] * 0.42),
                    xytext=(ax_pos, lo - mods[a] * 0.42),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.4, alpha=0.8))
        ax.text(ax_pos + 0.022, lo, f"modify +{mods[a]:.2f}",
                fontsize=8.5, color=col, va="center", fontweight="bold")

    ax.set_xticks(xs)
    ax.set_xticklabels(["制作対象の初期状態\n（要求を満たさない）",
                        f"modify ×{len(mods)} 後\n→ 要求充足 → 供給成立 "
                        f"({p['supplied_units']:.0f} unit)"], fontsize=9.5)
    ax.set_xlim(-0.28, 1.30)
    ax.set_ylabel("属性値", fontsize=9.5)
    ax.set_ylim(min(before) - 0.10, max(max(after), max(thr)) + 0.11)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.legend(fontsize=8.5, loc="lower left", frameon=False)

    fig.text(0.012, 0.945, "答えを与えずに、既存の制作対象を要求仕様まで作り替えた",
             fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.012, 0.895,
             f"条件 {c} / seed {s} / step {p['step']} / {p['agent_id']} / "
             f"制作対象 {p['source_project_id']}     破線 = 要求閾値",
             fontsize=8.5, color=MUTED)
    fig.text(0.012, 0.075,
             "Agent に与えたのは要求属性の数値のみ。何を作るべきかは与えていない。\n"
             "属性は中立コード表記であり、判定は属性閾値のみで行う（名称照合をしない）。",
             fontsize=8.5, color=INK)
    source_note(fig, f"出所: outputs/main_experiment/{c}_seed{s}.json"
                     f"（provenance、make 試行ごとの直接記録）")
    fig.tight_layout(rect=(0, 0.16, 1, 0.865))
    fig.savefig(OUT / "F3_adaptation_path.png", dpi=DPI)
    plt.close(fig)
    return c, s, p


# --- F4: ボトルネック診断 -----------------------------------------------------

COST_KEYS = ("observe", "ask", "practice", "make", "share", "idle",
             "modify", "propose", "join")


def fig4(runs: dict) -> None:
    import yaml
    cfg = yaml.safe_load((ROOT / "configs" / "as_executed"
                          / "main_experiment_20260816.yaml").read_text(encoding="utf-8"))
    cost = cfg["action_time_cost"]
    tb = float(cfg["agent_init"]["traits"]["time_budget"]["value"])
    a_runs = {s: runs[("A", s)] for s in SEEDS}
    n_agents = len(next(iter(a_runs.values()))["shock_agent_ids"])
    steps = len(next(iter(a_runs.values()))["transition_history"])
    avail = tb * n_agents * steps * len(a_runs)

    # 帰属順は RESULTS.md §7.3 と同一（成功可否を材料・設備より先に見る）。
    # 根拠: _resolve_shock は material_feasible / asset_feasible を**記録するだけ**で
    # make を阻止しない。実際、material_feasible=False の 8 件のうち 4 件は成功し供給
    # しており、これらを「材料不足で供給に至らなかった」と数えるのは誤りである。
    buckets = {"供給成立": 0, "確率的な制作失敗": 0, "仕様未達": 0,
               "材料不足で阻止": 0, "設備なしで阻止": 0}
    mat_flag = 0
    for r in a_runs.values():
        for p in r["provenance"]:
            if not p["material_feasible"]:
                mat_flag += 1
            if p["supplied_units"] > 0:
                buckets["供給成立"] += 1
            elif not p["meets_requirement"]:
                buckets["仕様未達"] += 1
            elif not p["make_success"]:
                buckets["確率的な制作失敗"] += 1
            elif not p["material_feasible"]:
                buckets["材料不足で阻止"] += 1
            elif not p["asset_feasible"]:
                buckets["設備なしで阻止"] += 1
    total = sum(buckets.values())

    used = sum(n * cost[a] for r in a_runs.values()
               for a, n in r["action_counts"].items())

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.7),
                                  gridspec_kw={"width_ratios": [1.65, 1]})

    order = ["供給成立", "確率的な制作失敗", "仕様未達", "材料不足で阻止", "設備なしで阻止"]
    vals = [buckets[k] for k in order]
    cols = [OK, GAP, "#c89b3c", LIGHT, LIGHT]
    ax.barh(range(len(order)), vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + total * 0.012, i, f"{v} 件  ({v / total * 100:.1f}%)",
                va="center", fontsize=10,
                fontweight="bold" if v else "normal",
                color=INK if v else MUTED)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.42)
    ax.set_xlabel(f"make 試行 {total} 件の内訳（条件A、{len(a_runs)} run）", fontsize=9.5)
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("資源でも時間でもなく、成功確率が律速だった",
                 fontsize=12.5, fontweight="bold", color=INK, loc="left", pad=12)

    ax2.bar([0], [used / avail * 100], color=ACCENT, width=0.5, label="使用")
    ax2.bar([0], [100 - used / avail * 100], bottom=[used / avail * 100],
            color=LIGHT, width=0.5, label="未使用")
    ax2.text(0, used / avail * 50, f"使用\n{used / avail * 100:.0f}%",
             ha="center", va="center", fontsize=11, color="white", fontweight="bold")
    ax2.text(0, used / avail * 100 + (100 - used / avail * 100) / 2,
             f"未使用\n{100 - used / avail * 100:.0f}%",
             ha="center", va="center", fontsize=11, color=INK, fontweight="bold")
    ax2.set_xticks([])
    ax2.set_ylim(0, 108)
    ax2.set_ylabel("総時間予算に対する割合 (%)", fontsize=9)
    for sp in ("top", "right", "bottom"):
        ax2.spines[sp].set_visible(False)
    ax2.set_title("時間予算は余っていた", fontsize=11, fontweight="bold",
                  color=INK, loc="left", pad=10)

    fig.text(0.012, 0.128,
             f"※ 材料在庫が不足した状態での make 試行は {mat_flag} 件あったが、"
             f"うち {sum(1 for r in a_runs.values() for p in r['provenance'] if not p['material_feasible'] and p['supplied_units'] > 0)} 件は成功し供給している"
             "（材料は make を阻止しない）。",
             fontsize=8, color=MUTED)
    fig.text(0.012, 0.075,
             "※ モデル内で材料・設備・時間が律速でなかったことは、現実でそれらの介入が"
             "有効でないことを意味しない（本モデルに共有プールの競合・調達リードタイムは存在しない）。",
             fontsize=8, color=MUTED)
    source_note(fig, "出所: outputs/main_experiment/A_seed{2,4,6,7,9}.json"
                     " / configs/as_executed/main_experiment_20260816.yaml")
    fig.tight_layout(rect=(0, 0.165, 1, 1))
    fig.savefig(OUT / "F4_bottleneck.png", dpi=DPI)
    plt.close(fig)
    return buckets, total, used / avail * 100


# --- F5: 研究手続き（Methods 図）---------------------------------------------

def fig5(corrected: dict, sens: dict) -> None:
    d4 = corrected["preregistered_D4"]
    rt = corrected["runtime_D4"]
    runs = corrected["runs"]
    n = len(runs)
    n_corr = sum(1 for r in runs if r["corrected_transition"])
    n_rt = sum(1 for r in runs if r["runtime_transition"])
    elig = json.loads((ROOT / "outputs" / "seed_eligibility.json").read_text(encoding="utf-8"))
    scanned, n_elig = elig["seeds_scanned"], len(elig["eligible_seeds"])
    live = sorted((ROOT / "outputs" / "live_penalty_zero").glob("*.json"))

    fig, ax = plt.subplots(figsize=(10.2, 8.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis("off")

    ax.text(0.15, 9.72, "Methods — 研究手続き", fontsize=15, fontweight="bold", color=INK)
    ax.text(0.15, 9.42, "（これは結果の図ではない。判定基準の決定順序を示す）",
            fontsize=9, color=MUTED)

    def box(x, y, w, h, text, fc, ec, fs=9, bold=False, tc=INK):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.10",
                                    fc=fc, ec=ec, lw=1.5, zorder=2))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
                color=tc, fontweight="bold" if bold else "normal", zorder=3,
                linespacing=1.55)

    def arrow(x, y0, y1, label=None, color=MUTED, lx=0.16, fs=8):
        ax.add_patch(FancyArrowPatch((x, y0), (x, y1), arrowstyle="-|>",
                                     mutation_scale=15, color=color, lw=1.5, zorder=1))
        if label:
            ax.text(x + lx, (y0 + y1) / 2, label, fontsize=fs, color=color,
                    va="center", ha="left", linespacing=1.4)

    box(1.6, 8.45, 6.8, 0.80,
        f"① 事前登録（実験開始前に固定）\n"
        f"D4 = share {d4['community_supply_share']} / suppliers {d4['active_supplier_count']}"
        f" / duration {d4['supply_duration_steps']} / edges {d4['coordination_edges']}",
        "#eef3f8", ACCENT, fs=9.5, bold=True)
    arrow(5.0, 8.42, 7.92)

    box(1.6, 7.10, 6.8, 0.78,
        f"② seed の事前選別（構造的測定可能性による）\n"
        f"scan {scanned} → eligible {n_elig}　※ Agent の行動結果を参照していない",
        "#f6f6f6", MUTED, fs=9)
    arrow(5.0, 7.07, 6.62)

    box(1.6, 5.85, 6.8, 0.72,
        f"③ {n} run 実行（4条件 × {n // 4} seed）",
        "#f6f6f6", MUTED, fs=9.5, bold=True)
    arrow(5.0, 5.82, 5.40)

    # 実行時判定（副次）
    box(0.35, 4.42, 3.75, 0.98,
        f"④ 実行時 config（暫定値）による判定\n"
        f"share ≥ {rt['community_supply_share']} / duration ≥ {rt['supply_duration_steps']}\n"
        f"→ 転化 {n_rt} / {n}　【副次的記録】",
        "#faf4ee", "#c2a184", fs=8.5)

    # 突合（ラベルは矢印の上に十分な間隔を空けて置く）
    ax.add_patch(FancyArrowPatch((4.14, 4.91), (5.28, 4.91), arrowstyle="-|>",
                                 mutation_scale=14, color=GAP, lw=1.6, zorder=1))
    # ラベルは両ボックスの上端より上へ出す（box の天面は 4.42+0.98=5.40）
    ax.text(4.71, 5.62, "事前登録値との突合", fontsize=8.5, color=GAP,
            ha="center", fontweight="bold")

    box(5.30, 4.42, 3.05, 0.98,
        f"不一致を検出\nshare {rt['community_supply_share']} ≠ {d4['community_supply_share']}\n"
        f"duration {rt['supply_duration_steps']} ≠ {d4['supply_duration_steps']}",
        "#fdf1ee", GAP, fs=8.5)

    # ①からの点線: 基準は最初から決まっていた
    ax.add_patch(FancyArrowPatch((8.45, 8.85), (9.62, 8.85), arrowstyle="-",
                                 color=ACCENT, lw=1.3, ls=(0, (4, 3)), zorder=1))
    ax.add_patch(FancyArrowPatch((9.62, 8.85), (9.62, 3.42), arrowstyle="-",
                                 color=ACCENT, lw=1.3, ls=(0, (4, 3)), zorder=1))
    ax.add_patch(FancyArrowPatch((9.62, 3.42), (8.45, 3.42), arrowstyle="-|>",
                                 mutation_scale=14, color=ACCENT, lw=1.3,
                                 ls=(0, (4, 3)), zorder=1))
    ax.text(9.50, 6.75, "①で固定した基準を適用", fontsize=8.5, color=ACCENT,
            rotation=90, va="center", ha="center", fontweight="bold")

    box(1.6, 2.90, 6.8, 0.98,
        f"⑤ 事前登録値による判定 → 転化 {n_corr} / {n}\n"
        f"【主結果】既存ログを改変せず、①の基準で再判定",
        "#eaf3ee", OK, fs=10, bold=True)
    arrow(5.0, 2.87, 2.22)

    box(1.6, 1.20, 6.8, 0.98,
        f"⑥ 感度分析（API 0 call、penalty {len(sens['penalties'])} 値）\n"
        f"＋ live run {len(live)} 本による近似の妥当性検証",
        "#f6f6f6", MUTED, fs=9)

    ax.text(5.0, 0.60,
            "④と⑤は同一のログに対する判定であり、測定値そのものは変更していない。\n"
            "基準を選び直したのではなく、①で決めてあった基準を適用した結果である。",
            fontsize=8.5, color=INK, ha="center", linespacing=1.6)

    source_note(fig, "出所: outputs/main_experiment/transition_recomputed_preregistered.json"
                     " / outputs/seed_eligibility.json / outputs/sensitivity_replay/"
                     "penalty_sensitivity.json / outputs/live_penalty_zero/")
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(OUT / "F5_methods.png", dpi=DPI)
    plt.close(fig)
    return n_rt, n_corr, scanned, n_elig, len(live)


def main() -> int:
    OUT.mkdir(exist_ok=True)
    runs, corrected, sens = load_runs(), load_corrected(), load_sens()

    c1 = fig1(corrected)
    print(f"F1 転化条件の充足 run 数: {c1[0]}  転化 {c1[1]}/{c1[2]}")
    pstar, cur, sp, sc = fig2(sens, runs)
    print(f"F2 P*={pstar:.4f}  current={cur}  比={cur / pstar:.1f}x  "
          f"penalty幅={sp:.3f} 条件幅={sc:.3f} 比={sp / sc:.1f}x")
    c, s, p = fig3(runs)
    print(f"F3 経路: 条件{c} seed{s} step{p['step']} {p['agent_id']} "
          f"{p['source_project_id']} mods={p['applied_modifications']}")
    b, tot, pct = fig4(runs)
    print(f"F4 make試行 {tot} 件: {b}  時間使用率 {pct:.1f}%")
    f5 = fig5(corrected, sens)
    print(f"F5 runtime {f5[0]}/20 -> corrected {f5[1]}/20  "
          f"scan {f5[2]}->{f5[3]}  live {f5[4]}本")

    print(f"\n-> {OUT}")
    for f in sorted(OUT.glob("*.png")):
        print(f"   {f.name}  {f.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
