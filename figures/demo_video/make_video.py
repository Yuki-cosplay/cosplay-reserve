"""最終デモ動画（1920x1080 / 30fps / 180秒 / h264 / 無音）。

【このスクリプトがやらないこと】
- simulation を実行しない（確定済みログを読むだけ）
- LLM / API を呼ばない
- ログに無い action / 関係 / 状態遷移を描かない

【データと視覚補間の境界】
- **データ**: 描画するイベントは必ずログの1レコードに対応する
- **視覚補間**: `visual_only_*` 接頭辞。座標・レイアウト・step 内の表示順は
  simulation event ではない

再生元:
  Accumulation: figures/demo_video/data/m1_trace/A_seed2/
  Shock:        outputs/main_experiment/A_seed2.json
  Result:       outputs/main_experiment/transition_recomputed_preregistered.json
  Network:      build_world('configs/condition_a.yaml', seed=2)  ※M1中は固定

使い方:
    python figures/demo_video/make_video.py --sample   # 各フェーズ5秒の確認用
    python figures/demo_video/make_video.py            # 最終180秒
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "figures" / "demo_video" / "data" / "m1_trace" / "A_seed2"
SHOCK_LOG = ROOT / "outputs" / "main_experiment" / "A_seed2.json"
CORRECTED = ROOT / "outputs" / "main_experiment" / "transition_recomputed_preregistered.json"
OUT = ROOT / "figures" / "demo_video"

W, H, DPI, FPS = 1920, 1080, 100, 30
FIGSIZE = (W / DPI, H / DPI)

BG, PANEL, INK, MUTED, FAINT = "#14171c", "#1c2027", "#e8eaed", "#8b929c", "#2b3038"
OK, GAP, ACCENT, WARN = "#4ea87a", "#c76a52", "#5b93c7", "#c9a84c"

ACTION_STYLE = {
    "practice": {"color": WARN, "label": "PRACTICE"},
    "make": {"color": OK, "label": "MAKE"},
    "observe": {"color": ACCENT, "label": "OBSERVE"},
    "ask": {"color": "#ab7fc4", "label": "ASK"},
    "share": {"color": "#7fc4b8", "label": "SHARE"},
    "idle": {"color": MUTED, "label": "IDLE"},
}
LINE_ACTIONS = {"observe", "ask"}   # trace に target_agent_id があるのはこの2つだけ
INTRO_ALPHA = 0.18   # P0-3: タイトル背後に敷く格子の不透明度
STAGES = ("consumer", "customizer", "maker", "advanced_maker")
STAGE_COLOR = {"consumer": MUTED, "customizer": ACCENT,
               "maker": OK, "advanced_maker": WARN}

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Meiryo", "Yu Gothic", "MS Gothic", "DejaVu Sans"]

# --- 尺（frames）------------------------------------------------------------
# P1-5(a): クローズアップ対象は select_closeup() が決定論的に選ぶ。
# 固定値は持たない（下の main() で解決し、選定結果をログ出力する）。
ZOOM_SPAN = 5             # クローズアップで見せる週数
# DEMO_VIDEO_FIX_SPEC v1.0 §5 に沿った再配分。
#   P0-2: RESULT 46s -> 28s
#   P0-3: タイトル 12s -> 8s（格子と文字を分離したので長く見せる必要がない）
#   P1-5(b): 蓄積相グリッド 51s -> 40s、クローズアップ 5s -> 8s（P1-5(a) と対）
#   余剰はショック相へ戻す（1 step 7.0s -> 8.5s）
SHOCK_ZOOM_AGENT = "agent_1"   # P1-4(d) 挿入カットの対象（仕様の推奨）
SHOCK_ZOOM_AFTER = 4           # 何 step 目の後に挿入するか
SEG = [
    ("intro", 240),        # 0:00-0:08   8.0s
    ("accum_a", 600),      # 0:08-0:28  20.0s  weeks 0..59
    ("zoom", 240),         # 0:28-0:36   8.0s  個体クローズアップ（等速）
    ("bridge", 180),       # 0:36-0:42   6.0s  個体 -> 集団 の視点変更
    ("accum_b", 480),      # 0:42-0:58  16.0s  weeks 65..155
    ("shock_title", 180),  # 0:56-1:02   6.0s
    ("shock_a", 1020),     # 1:02-1:36  34.0s  step 1-4（1 step = 255f = 8.5s）
    ("shock_zoom", 105),   # 1:36-1:39   3.5s  P1-4(d) 挿入カット
    ("shock_b", 1020),     # 1:39-2:13  34.0s  step 5-8
    ("result", 840),       # 2:13-2:41  28.0s  P0-2
    ("closing", 120),      # 2:41-2:43   4.0s  クロージングカード
]
TOTAL = sum(n for _, n in SEG)
SHOCK_STEP_SEC = 1020 / 4 / 30      # = 8.5s（1 step の再生尺）
GROW_END = .45                      # step 内で変形アニメが完了する進捗
RESULT_SEC = 840 / 30               # = 28.0s
assert TOTAL == 5025, f"総フレーム数が 167.5秒 (5025) でない: {TOTAL}"
assert 150 * 30 <= TOTAL <= 180 * 30, "総尺が 150-180s の範囲外"
assert RESULT_SEC <= 30, "RESULT が 30s を超えている"


# ---------------------------------------------------------------------------
# データ
# ---------------------------------------------------------------------------

def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]


def load_all():
    acts_raw = read_jsonl(TRACE / "actions.jsonl")
    snaps_raw = read_jsonl(TRACE / "snapshots.jsonl")
    acts: dict[int, list[dict]] = {}
    for a in acts_raw:
        acts.setdefault(a["step"], []).append(a)
    snaps: dict[int, dict[str, dict]] = {}
    for s in snaps_raw:
        snaps.setdefault(s["step"], {})[s["agent_id"]] = s

    d = json.loads(SHOCK_LOG.read_text(encoding="utf-8"))
    prov: dict[int, list[dict]] = {}
    for p in d["provenance"]:
        prov.setdefault(p["step"], []).append(p)
    mods: dict[int, list[dict]] = {}
    for aid, hist in d["modify_history"].items():
        for m in hist:
            mods.setdefault(m["step"], []).append({**m, "agent_id": aid})
    coord: dict[int, list[list[str]]] = {}
    for st in sorted(prov):
        pairs = {tuple(sorted(e)) for p in prov[st]
                 for e in p["coordination_relation"]["edges_involving_self"]}
        coord[st] = [list(x) for x in sorted(pairs)]

    corr = json.loads(CORRECTED.read_text(encoding="utf-8"))

    from src.world.world import build_world
    w = build_world(str(ROOT / "configs" / "condition_a.yaml"), seed=2)
    parts = sorted(a.id for a in w.agents.values() if a.is_participant)
    pset = set(parts)
    edges = [(u, v) for u, v in w.graph.edges() if u in pset and v in pset]

    # --- 重要値の assert（ログと表示の乖離を防ぐ）--------------------------
    req = d["provenance"][0]["required_attributes"]
    cfg_req = w.cfg["shock"]["required_item"]["thresholds"]
    assert req == cfg_req, f"required_attributes が config と不一致: {req} vs {cfg_req}"
    assert len(parts) == 30, f"participant が 30 でない: {len(parts)}"
    assert sorted(snaps) == list(range(156)), "蓄積相 156 step が揃っていない"
    supplied = sum(p["supplied_units"] for p in d["provenance"])
    assert abs(supplied - d["community_supply_total"]) < 1e-9, \
        f"供給合計がログと不一致: {supplied} vs {d['community_supply_total']}"
    assert set(d["shock_agent_ids"]) <= pset, "shock agent が participant でない"
    a2 = [x for x in corr["runs"] if x["condition"] == "A" and x["seed"] == 2][0]
    assert a2["corrected_transition"] is False, "A_seed2 の corrected 判定がログと不一致"
    n_trans = sum(1 for x in corr["runs"] if x["corrected_transition"])
    assert n_trans == 0, f"corrected transition が 0/20 でない: {n_trans}"
    return acts, snaps, d, prov, mods, coord, corr, parts, edges


# ---------------------------------------------------------------------------
# 視覚補間（simulation event ではない）
# ---------------------------------------------------------------------------

def visual_only_grid(ids, cols, x0, y0, dx, dy):
    """画面座標。**シミュレーションに位置の概念は無い。**"""
    return {a: (x0 + (i % cols) * dx, y0 - (i // cols) * dy) for i, a in enumerate(ids)}


def visual_only_ui_skill(skills: dict[str, float]) -> float:
    """**UI 用集約値**（6技能の単純平均）。★研究指標ではない★"""
    return float(sum(skills.values()) / len(skills))


def visual_only_ease(t: float) -> float:
    """0..1 の表示用イージング。イベントではない。"""
    return t * t * (3 - 2 * t)


def select_closeup(acts: dict[int, list[dict]], parts: list[str],
                   span: int = 5, window: tuple[int, int] = (55, 90)) -> tuple[str, int]:
    """P1-5(a): クローズアップ対象を**決定論的な規則**で選ぶ（cherry-pick ではない）。

    優先順位（DEMO_VIDEO_FIX_SPEC §P1-5(a)）:
      ① `ask` があり、**翌週に make 成功**がある agent/week（peer learning が効いた瞬間）
      ② `make -> completed` を含む週
      ③ `practice` が連続する週
    いずれも **先頭週がハイライト行 `▶` で `idle` になる週は選ばない**。

    走査順は (week, agent_id) の昇順で固定。最初に条件を満たしたものを採る。
    `window` は蓄積相の時系列が飛ばないようにする探索優先レンジ（動画上の都合）。
    見つからなければ全週へ広げる。
    """
    lo_w, hi_w = window
    weeks = ([w for w in sorted(acts) if lo_w <= w <= min(hi_w, 156 - span)]
             + [w for w in sorted(acts) if not (lo_w <= w <= hi_w) and 0 <= w <= 156 - span])
    pset = set(parts)

    def week_acts(w, aid):
        return [a for a in acts.get(w, []) if a["agent_id"] == aid]

    def head_is_idle(w, aid):
        seq = week_acts(w, aid)
        return (not seq) or seq[0]["action"] == "idle"

    for rank in (1, 2, 3):
        for w in weeks:
            for aid in sorted({a["agent_id"] for a in acts.get(w, [])} & pset):
                seq = week_acts(w, aid)
                if not seq or head_is_idle(w, aid):
                    continue
                if rank == 1:
                    nxt = week_acts(w + 1, aid)
                    if any(a["action"] == "ask" for a in seq) and \
                       any(a["action"] == "make" and a.get("make_success") for a in nxt):
                        return aid, w
                elif rank == 2:
                    if any(a.get("completed_project_added") for a in seq):
                        return aid, w
                else:
                    if sum(1 for a in seq if a["action"] == "practice") >= 2:
                        return aid, w
    raise RuntimeError("クローズアップ対象を選定できなかった")


# ---------------------------------------------------------------------------
# 描画部品
# ---------------------------------------------------------------------------

def new_canvas():
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis("off")
    return fig, ax


def draw_agent(ax, x, y, s, action, *, big=False, ui_skill=None, ring=False,
               alpha=1.0):
    """alpha は背景として敷くとき用（P0-3: タイトル文字を最前面にするため）。"""
    col = ACTION_STYLE.get(action, {}).get("color", MUTED)
    if ring:
        ax.add_patch(Circle((x, y - 0.05), 1.05 * s, fc="none", ec=INK, lw=1.4,
                            alpha=0.6 * alpha, zorder=7))
    ax.add_patch(FancyBboxPatch((x - 0.28 * s, y - 0.55 * s), 0.56 * s, 0.62 * s,
                                boxstyle="round,pad=0.02", fc=FAINT, ec=col,
                                lw=1.6 if big else 1.1, zorder=3, alpha=alpha))
    ax.add_patch(Circle((x, y + 0.28 * s), 0.22 * s, fc=PANEL, ec=col,
                        lw=1.6 if big else 1.1, zorder=4, alpha=alpha))

    def arm(a, b, c, dd):
        ax.plot([x + a * s, x + c * s], [y + b * s, y + dd * s], color=col,
                lw=2.2 if big else 1.5, solid_capstyle="round", zorder=5,
                alpha=alpha)

    if action == "practice":
        arm(-.28, -.05, -.46, .20); arm(.28, -.05, .46, .24)
        ax.plot([x + .40 * s, x + .52 * s], [y + .24 * s, y + .10 * s],
                color=WARN, lw=2.6 if big else 1.8, zorder=5)
    elif action == "make":
        arm(-.28, -.05, -.44, -.26); arm(.28, -.05, .44, -.26)
        ax.add_patch(Rectangle((x - .52 * s, y - .62 * s), 1.04 * s, .10 * s,
                               fc=OK, ec="none", alpha=.55, zorder=2))
        ax.add_patch(Rectangle((x - .13 * s, y - .50 * s), .26 * s, .16 * s,
                               fc=OK, ec="none", alpha=.9, zorder=6))
    elif action == "observe":
        arm(-.28, -.05, -.42, .02); arm(.28, -.05, .42, .02)
        ax.plot([x + .08 * s, x + .20 * s], [y + .30 * s, y + .34 * s],
                color=ACCENT, lw=1.8 if big else 1.2, zorder=6)
    elif action == "ask":
        arm(-.28, -.05, -.40, .16); arm(.28, -.05, .40, .16)
        ax.text(x + .42 * s, y + .48 * s, "?", color=col, fontsize=11 if big else 7,
                fontweight="bold", ha="center", va="center", zorder=6)
    elif action == "share":
        # ★リングも線も描かない★ trace に相手 id が無いため、相手を示唆しない
        arm(-.28, -.05, -.44, .10); arm(.28, -.05, .44, .10)
        ax.text(x, y + .62 * s, "share", color=col, fontsize=9 if big else 5.5,
                ha="center", va="bottom", family="monospace", zorder=6)
    else:
        arm(-.28, -.05, -.30, -.30); arm(.28, -.05, .30, -.30)

    if ui_skill is not None:
        bw = .9 * s
        ax.add_patch(Rectangle((x - bw / 2, y - .80 * s), bw, .07 * s,
                               fc=FAINT, ec="none", zorder=3))
        ax.add_patch(Rectangle((x - bw / 2, y - .80 * s), bw * ui_skill, .07 * s,
                               fc=ACCENT, ec="none", zorder=4))


def provenance(ax, phase, source, note_ja=""):
    """再生元は monospace（英数字のみ）。日本語注記は通常フォントで別行に置く。

    monospace フォント（DejaVu Sans Mono）に日本語グリフが無いため、
    混在させると豆腐になる。ここで確実に分離する。
    """
    ax.text(0.006, 0.052 if note_ja else 0.018, f"{phase}\nsource = {source}",
            transform=ax.transAxes, color=MUTED, fontsize=8.5, va="bottom",
            ha="left", family="monospace", linespacing=1.5, zorder=20)
    if note_ja:
        ax.text(0.006, 0.016, note_ja, transform=ax.transAxes, color=MUTED,
                fontsize=8.5, va="bottom", ha="left", linespacing=1.5, zorder=20)


def stage_panel(ax, snaps_at, x, y, w_=3.05):
    """maker_stage の人口構成（積み上げ）。trace の per-agent stage から集計。"""
    from collections import Counter
    c = Counter(s["maker_stage"] for s in snaps_at.values() if s["is_participant"])
    n = sum(c.values())
    ax.text(x, y + .30, "MAKER STAGE（participant 30）", color=MUTED, fontsize=10)
    left = x
    for st in STAGES:
        v = c.get(st, 0)
        if v:
            ww = w_ * v / n
            ax.add_patch(Rectangle((left, y - .30), ww, .38, fc=STAGE_COLOR[st],
                                   ec=BG, lw=1.0, zorder=4))
            if ww > .30:
                ax.text(left + ww / 2, y - .11, str(v), color=BG, fontsize=9,
                        ha="center", va="center", fontweight="bold", zorder=5)
            left += ww
    for i, st in enumerate(STAGES):
        ax.add_patch(Rectangle((x + (i % 2) * 1.60, y - .78 - (i // 2) * .32), .18, .14,
                               fc=STAGE_COLOR[st], ec="none", zorder=4))
        ax.text(x + (i % 2) * 1.60 + .26, y - .71 - (i // 2) * .32, st,
                color=MUTED, fontsize=8.5, va="center", family="monospace")


def skill_hist(ax, snaps_at, x, y, w_=3.05, h_=1.55):
    """participant 全員 × 6技能のヒストグラム。trace の実値から毎フレーム集計。"""
    vals = [v for s in snaps_at.values() if s["is_participant"]
            for v in s["skills"].values()]
    ax.text(x, y + h_ + .40, "SKILL DISTRIBUTION", color=MUTED, fontsize=10)
    ax.text(x, y + h_ + .14, "participant 30 x 6 skills = 180（実 trace 値）",
            color=MUTED, fontsize=8.5)
    bins = np.linspace(0, 1, 21)
    cnt, _ = np.histogram(vals, bins=bins)
    mx = max(cnt.max(), 1)
    for i, c in enumerate(cnt):
        if c:
            ax.add_patch(Rectangle((x + w_ * i / 20, y), w_ / 20 * .86,
                                   h_ * c / mx, fc=ACCENT, ec="none", zorder=4))
    ax.plot([x, x + w_], [y, y], color=FAINT, lw=1.0, zorder=3)
    for t in (0, .5, 1.0):
        ax.text(x + w_ * t, y - .22, f"{t:.1f}", color=MUTED, fontsize=8,
                ha="center", family="monospace")
    ax.text(x + w_, y + h_ + .38, f"mean {np.mean(vals):.2f}", color=INK,
            fontsize=10, ha="right", family="monospace")


# ---------------------------------------------------------------------------
# フェーズ描画
# ---------------------------------------------------------------------------

def f_intro(ax, t, parts, edges, snaps, pos):
    """P0-3: 格子は薄く敷き、文字は最前面かつ格子と縦に分離する。

    格子は画面幅いっぱいに水平中央寄せ（従来は x<11 に偏り右3割が空白だった）。
    """
    a = visual_only_ease(min(1.0, t * 1.8))
    for u, v in edges:
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=FAINT, lw=.7, alpha=a * INTRO_ALPHA, zorder=1)
    for i, aid in enumerate(parts):
        if t * 1.5 > i / len(parts):
            x, y = pos[aid]
            draw_agent(ax, x, y, .40, "idle", alpha=INTRO_ALPHA)
    # 文字ブロックは格子の下（y<4.0）。zorder を上げて最前面に置く。
    ax.text(8.0, 3.30, "COSPLAY RESERVE", color=INK, fontsize=40,
            fontweight="bold", ha="center", zorder=30)
    ax.text(8.0, 2.55, "文化活動が蓄積した制作能力を、供給ショックで測る",
            color=MUTED, fontsize=17, ha="center", zorder=30)
    ax.text(8.0, 1.72, f"participant {len(parts)}   /   fixed network "
                       f"{len(edges)} edges",
            color=MUTED, fontsize=12, ha="center", family="monospace", zorder=30)
    ax.text(8.0, 1.36, "ネットワークは M1 の間ずっと固定（生成される演出はしない）",
            color=MUTED, fontsize=11, ha="center", zorder=30)
    provenance(ax, "SETUP", "build_world(condition_a, seed=2)",
               "決定論的に復元（API 0 call）")


def f_accum(ax, week, snaps, acts, parts, edges, pos, speed):
    sn, ac = snaps[week], acts.get(week, [])
    ax.text(.30, 8.50, "ACCUMULATION", color=INK, fontsize=22, fontweight="bold")
    ax.text(.30, 8.13, "文化活動による技能・制作物・関係の蓄積", color=MUTED, fontsize=11)
    ax.text(11.30, 8.50, f"WEEK {week + 1} / 156", color=INK, fontsize=22,
            fontweight="bold", family="monospace")
    ax.text(11.30, 8.13, speed, color=WARN, fontsize=11, family="monospace")

    for u, v in edges:
        ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                color=FAINT, lw=.7, zorder=1)
    for a in ac:
        if a["action"] in LINE_ACTIONS and a.get("target_agent_id"):
            s_, t_ = a["agent_id"], a["target_agent_id"]
            if s_ in pos and t_ in pos:
                ax.annotate("", xy=pos[t_], xytext=pos[s_],
                            arrowprops=dict(arrowstyle="-|>", mutation_scale=7,
                                            color=ACTION_STYLE[a["action"]]["color"],
                                            alpha=.30, lw=.85,
                                            connectionstyle="arc3,rad=.14"), zorder=2)
    latest = {a["agent_id"]: a for a in ac if a["is_participant"]}
    for aid in parts:
        x, y = pos[aid]
        draw_agent(ax, x, y, .40, latest.get(aid, {}).get("action", "idle"),
                   ui_skill=visual_only_ui_skill(sn[aid]["skills"]))

    skill_hist(ax, sn, 12.05, 5.15)
    stage_panel(ax, sn, 12.05, 3.75)
    tot_p = sum(s["completed_projects_total"] for s in sn.values() if s["is_participant"])
    tot_m = sum(s["methods_total"] for s in sn.values() if s["is_participant"])
    ax.text(12.05, 2.20, f"completed projects  {tot_p:,}", color=INK, fontsize=11,
            family="monospace")
    ax.text(12.05, 1.88, f"methods held        {tot_m:,}", color=INK, fontsize=11,
            family="monospace")

    # P1-6: 凡例を上へ移動し、左下の provenance キャプションと重ならないようにする
    ax.text(.30, 1.86, "ACTIONS（M1 trace に存在する6行動のみ）", color=MUTED, fontsize=9.5)
    for i, (k, st) in enumerate(ACTION_STYLE.items()):
        xx = .30 + i * 1.72
        draw_agent(ax, xx + .20, 1.36, .26, k)
        ax.text(xx + .48, 1.28, st["label"], color=st["color"], fontsize=9,
                va="center", family="monospace")
    provenance(ax, "ACCUMULATION", "M1 trace / condition A / seed 2",
               "share の相手は trace に記録されていないため表示していない"
               "　／　バーは UI 用集約（研究指標ではない）")


def f_zoom(ax, week, sub, snaps, acts, aid, zw0):
    """1体を等速で表示。practice → skill 上昇 → make → completed の連鎖を見せる。"""
    sn = snaps[week][aid]
    ac = [a for a in acts.get(week, []) if a["agent_id"] == aid]
    ax.text(.30, 8.50, "ACCUMULATION — 個体の等速表示", color=INK, fontsize=22,
            fontweight="bold")
    ax.text(.30, 8.13, f"{aid}  /  weeks {zw0 + 1}-{zw0 + ZOOM_SPAN}",
            color=WARN, fontsize=13, family="monospace")
    ax.text(11.30, 8.50, f"WEEK {week + 1} / 156", color=INK, fontsize=22,
            fontweight="bold", family="monospace")
    ax.text(11.30, 8.13, "REPLAY SPEED  x1 (1 week = 1 s)", color=WARN,
            fontsize=11, family="monospace")

    k = min(len(ac) - 1, int(sub * len(ac))) if ac else -1
    cur = ac[k]["action"] if k >= 0 else "idle"
    draw_agent(ax, 4.60, 5.10, 1.75, cur, big=True, ring=True)
    ax.text(4.60, 2.55, ACTION_STYLE.get(cur, {}).get("label", "IDLE"),
            color=ACTION_STYLE.get(cur, {}).get("color", MUTED), fontsize=20,
            ha="center", fontweight="bold", family="monospace")

    ax.text(9.10, 7.30, "この週の行動列（trace そのまま）", color=MUTED, fontsize=11)
    for i, a in enumerate(ac[:8]):
        c = ACTION_STYLE[a["action"]]["color"]
        mark = "▶" if i == k else " "
        # make は制作対象（project）を主に見せる。practice は技能。
        if a["action"] == "make":
            tgt = a.get("target_project_id", "")
        else:
            tgt = (a.get("target_skill_id") or a.get("target_project_id")
                   or a.get("target_agent_id") or "")
        extra = ""
        if a.get("completed_project_added"):
            extra = f" -> completed {a.get('completed_projects_total', '')}"
        elif a["action"] == "make" and a.get("make_success") is False:
            extra = " (failed)"
        ax.text(9.10, 6.85 - i * .42, f"{mark} {a['action']:<9} {tgt:<9}{extra}",
                color=c if i == k else MUTED, fontsize=12, family="monospace",
                fontweight="bold" if i == k else "normal")

    ax.text(9.10, 3.72, "practice / make が技能を押し上げ、成功した make が制作実績になる",
            color=MUTED, fontsize=10)
    ax.text(9.10, 3.20, "skills（実 trace 値）", color=MUTED, fontsize=11)
    for i, (kk, v) in enumerate(sorted(sn["skills"].items())):
        yy = 2.80 - i * .38
        ax.text(9.10, yy, kk, color=MUTED, fontsize=9.5, va="center",
                family="monospace")
        ax.add_patch(Rectangle((10.05, yy - .10), 2.60, .20, fc=FAINT, ec="none"))
        ax.add_patch(Rectangle((10.05, yy - .10), 2.60 * v, .20, fc=ACCENT, ec="none"))
        ax.text(12.78, yy, f"{v:.3f}", color=INK, fontsize=9.5, va="center",
                family="monospace")
    ax.text(14.00, 2.80, f"stage\n{sn['maker_stage']}", color=INK, fontsize=11,
            family="monospace", linespacing=1.6)
    ax.text(14.00, 1.85, f"projects {sn['completed_projects_total']}\n"
                         f"methods  {sn['methods_total']}",
            color=INK, fontsize=11, family="monospace", linespacing=1.6)
    provenance(ax, "ACCUMULATION", "M1 trace / condition A / seed 2",
               "share の相手は trace に記録されていないため表示していない")


def f_shock_title(ax, t, req):
    ax.text(8.0, 5.90, "SUPPLY SHOCK", color=GAP, fontsize=46, fontweight="bold",
            ha="center")
    if t > .25:
        ax.text(8.0, 4.95, "REQUIRED", color=MUTED, fontsize=16, ha="center")
        for i, (k, v) in enumerate(sorted(req.items())):
            if t > .35 + i * .12:
                ax.text(8.0, 4.35 - i * .55, f"{k} >= {v:.2f}", color=INK,
                        fontsize=26, ha="center", family="monospace")
    if t > .62:
        ax.text(8.0, 2.85, "何を作るべきかは指示していない", color=MUTED,
                fontsize=15, ha="center")
    provenance(ax, "SHOCK",
               "outputs/main_experiment/A_seed2.json  (no re-run / API calls = 0)")


def f_shock(ax, step, sub, d, prov, mods, coord, pos, supply_running, onset,
            step_no):
    req = d["provenance"][0]["required_attributes"]
    ax.text(.30, 8.50, "SUPPLY SHOCK", color=GAP, fontsize=22, fontweight="bold")
    ax.text(.30, 8.13, "未知仕様への適応（答えは与えていない）", color=MUTED, fontsize=11)
    ax.text(10.90, 8.50, f"STEP {step_no} / 8   (6h each)", color=INK,
            fontsize=18, fontweight="bold", family="monospace")
    ax.text(10.90, 8.13, f"REPLAY SPEED  1 step = {SHOCK_STEP_SEC:.1f} s", color=WARN,
            fontsize=11, family="monospace")

    ax.add_patch(FancyBboxPatch((.30, 6.10), 3.35, 1.42, boxstyle="round,pad=.06",
                                fc=PANEL, ec=GAP, lw=1.6, zorder=8))
    ax.text(.52, 7.22, "REQUIRED", color=GAP, fontsize=12, fontweight="bold", zorder=9)
    for i, (k, v) in enumerate(sorted(req.items())):
        ax.text(.52, 6.82 - i * .36, f"{k} >= {v:.2f}", color=INK, fontsize=13,
                family="monospace", zorder=9)
    ax.add_patch(FancyBboxPatch((.30, 4.40), 3.35, 1.30, boxstyle="round,pad=.06",
                                fc=PANEL, ec=OK, lw=1.4, zorder=8))
    ax.text(.52, 5.35, "COMMUNITY SUPPLY", color=MUTED, fontsize=10, zorder=9)
    ax.text(.52, 4.76, f"{supply_running:.0f} units", color=OK, fontsize=21,
            fontweight="bold", family="monospace", zorder=9)

    pairs = coord.get(step, [])
    for u, v in pairs:
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color=WARN,
                    lw=2.0, alpha=.7, zorder=2, solid_capstyle="round")
    if pairs:
        ax.text(.30, 3.85, f"COORDINATION ACTIVE  ({len(pairs)} pair)", color=WARN,
                fontsize=11, fontweight="bold", family="monospace")
        ax.text(.30, 3.52, "※ 成立済みの累積状態。", color=MUTED, fontsize=8.5)
        ax.text(.30, 3.26, "　 成立の瞬間は復元不能のため演出しない", color=MUTED,
                fontsize=8.5)

    mods_now: dict[str, list[dict]] = {}
    for m in mods.get(step, []):
        mods_now.setdefault(m["agent_id"], []).append(m)
    by_agent: dict[str, list[dict]] = {}
    for p in prov.get(step, []):
        by_agent.setdefault(p["agent_id"], []).append(p)

    # step 内の表示順は視覚補間（ログは step 粒度）。0-.45 変形 / .45-1 結果
    grow = visual_only_ease(min(1.0, sub / GROW_END))
    show_result = sub > GROW_END + .10

    for aid, recs in by_agent.items():
        if aid not in pos:
            continue
        p, (x, y) = recs[0], pos[aid]
        ax.text(x, y + 1.06, aid, color=INK, fontsize=11, ha="center",
                family="monospace", fontweight="bold")
        if len(recs) > 1:
            ax.text(x, y + .82, f"({len(recs)} make attempts)", color=MUTED,
                    fontsize=7.5, ha="center", family="monospace")
        draw_agent(ax, x, y, .58, "make", big=True)
        ax.text(x, y - .60, p["source_project_id"], color=MUTED, fontsize=8,
                ha="center", family="monospace")

        # P1-4(a): バーを拡大（1.30 -> 2.05 data unit ≒ 121px -> 246px、高さ .18 -> .28）
        reached_all = True
        for i, k in enumerate(sorted(req)):
            yy = y - .88 - i * .34
            b, a2, thr = p["before_attributes"][k], p["after_attributes"][k], req[k]
            cur = b + (a2 - b) * grow
            # P1-4(b): 到達判定は**ログ値から導出**する。閾値は動かさない。
            reached = a2 >= thr and cur >= thr - 1e-12
            reached_all = reached_all and reached
            fill = OK if reached else ACCENT
            bw, bh = 1.70, .26
            ax.add_patch(Rectangle((x - bw / 2, yy - bh / 2), bw, bh, fc=FAINT,
                                   ec="none", zorder=3))
            ax.add_patch(Rectangle((x - bw / 2, yy - bh / 2), bw * b, bh, fc=MUTED,
                                   ec="none", zorder=4))
            if cur > b:
                ax.add_patch(Rectangle((x - bw / 2 + bw * b, yy - bh / 2),
                                       bw * (cur - b), bh, fc=fill, ec="none",
                                       zorder=5))
            # 到達フレームだけ閾値線を白でフラッシュ、以降は緑
            flash = reached and grow >= 1.0 and sub < GROW_END + 1 / 255
            tick = "#FFFFFF" if flash else (OK if reached else GAP)
            ax.plot([x - bw / 2 + bw * thr] * 2, [yy - bh / 2 - .07, yy + bh / 2 + .07],
                    color=tick, lw=2.6 if flash else 1.8, zorder=6)
            ax.text(x - bw / 2 - .10, yy, k, color=MUTED, fontsize=8, ha="right",
                    va="center", family="monospace")
            # P1-4(c): 「越えた」ではなく「ぴったり届いた」と書く
            lab = f"{b:.2f}→{a2:.2f}"
            ax.text(x + bw / 2 + .10, yy + .07, lab, color=INK, fontsize=8,
                    ha="left", va="center", family="monospace")
            if reached:   # P1-4(c)「越えた」ではなく「届いた」
                ax.text(x + bw / 2 + .10, yy - .17, "✓ required", color=OK,
                        fontsize=7.5, ha="left", va="center", family="monospace")
        # 両属性が到達した直後だけ輪郭を太くする（0.3s）
        if reached_all and GROW_END <= sub < GROW_END + .3 / SHOCK_STEP_SEC:
            ax.add_patch(Circle((x, y - .05), .62, fc="none", ec=OK, lw=3.0,
                                alpha=.9, zorder=8))

        if aid in mods_now and grow > .05:
            txt = "  ".join(f"{m['attr']} +{m['delta']:.2f}" for m in mods_now[aid])
            ax.text(x, y - 1.72, f"MODIFY {txt}", color=ACCENT, fontsize=9,
                    ha="center", fontweight="bold", family="monospace")
        if show_result:
            if p["supplied_units"] > 0:
                ax.text(x, y - 2.04, f"SUPPLY +{p['supplied_units']:.0f}", color=OK,
                        fontsize=12, ha="center", fontweight="bold",
                        family="monospace")
            elif not p["make_success"]:
                ax.text(x, y - 2.04, "MAKE FAILED", color=GAP, fontsize=10,
                        ha="center", family="monospace")
            elif not p["meets_requirement"]:
                ax.text(x, y - 2.04, "REQ NOT MET", color=WARN, fontsize=10,
                        ha="center", family="monospace")

    ax.text(11.9, .58, "6体が独立に同一の最小コスト経路へ収束（実ログ）",
            color=MUTED, fontsize=10.5, ha="center")
    provenance(ax, "SHOCK", "outputs/main_experiment/A_seed2.json  (no re-run / API calls = 0)",
               "step 内の表示順は視覚補間（ログは step 粒度）")


def f_bridge(ax, t, snaps, parts, aid, week):
    """個体 → 集団 の視点変更（6.0s）。

    直前のクローズアップで見た1体が、30体の分布のどこにいるかを示す。
    表示値はすべて snapshots.jsonl の実測（個体の skills と、participant 全員の skills）。
    **新しい概念や集計を持ち込まない**（ヒストグラムは既存の skill_hist と同一の集計）。
    """
    sn = snaps[week]
    me = sn[aid]
    ax.text(.60, 8.45, "個体 → 集団", color=INK, fontsize=24, fontweight="bold")
    ax.text(.60, 8.02, f"{aid} の積み上がりは、participant 30体のどこにあるか"
                       f"（week {week + 1}）",
            color=MUTED, fontsize=13)

    # 左: 直前に見ていた1体（実 trace 値）
    draw_agent(ax, 2.55, 5.35, 1.15, "make", big=True, ring=True)
    ax.text(2.55, 3.75, aid, color=INK, fontsize=14, ha="center",
            family="monospace", fontweight="bold")
    for i, (k, v) in enumerate(sorted(me["skills"].items())):
        yy = 3.20 - i * .40
        ax.text(.85, yy, k, color=MUTED, fontsize=9.5, va="center", family="monospace")
        ax.add_patch(Rectangle((1.75, yy - .10), 1.90, .20, fc=FAINT, ec="none"))
        ax.add_patch(Rectangle((1.75, yy - .10), 1.90 * v, .20, fc=ACCENT, ec="none"))
        ax.text(3.75, yy, f"{v:.2f}", color=INK, fontsize=9.5, va="center",
                family="monospace")

    # 右: 集団の分布に、この1体の6技能を重ねる
    vals = [x for s in sn.values() if s["is_participant"] for x in s["skills"].values()]
    x0, y0, w_, h_ = 6.40, 3.05, 8.60, 3.10
    ax.text(x0, y0 + h_ + 1.62, "participant 30 x 6 skills = 180（実 trace 値）",
            color=MUTED, fontsize=11)
    ax.text(x0 + w_, y0 + h_ + 1.62, f"population mean {np.mean(vals):.2f}", color=INK,
            fontsize=11, ha="right", family="monospace")
    bins = np.linspace(0, 1, 21)
    cnt, _ = np.histogram(vals, bins=bins)
    mx = max(cnt.max(), 1)
    for i, c in enumerate(cnt):
        if c:
            ax.add_patch(Rectangle((x0 + w_ * i / 20, y0), w_ / 20 * .86,
                                   h_ * c / mx, fc=FAINT, ec="none", zorder=3))
    # この1体の6技能を分布上へ（段階的に出す）
    shown = int(min(6, t * 9))
    # 近接した技能のラベルが重ならないよう、x 昇順に段を割り当てる（視覚補間）
    order = sorted(me["skills"].items(), key=lambda kv: kv[1])
    tier, last_x = {}, -9.0
    lvl = 0
    for k, v in order:
        xx = x0 + w_ * v
        lvl = (lvl + 1) % 4 if xx - last_x < .95 else 0
        tier[k] = lvl
        last_x = xx
    for i, (k, v) in enumerate(sorted(me["skills"].items())):
        if i >= shown:
            continue
        xx = x0 + w_ * v
        top = y0 + h_ * .92
        ax.plot([xx, xx], [y0, top], color=ACCENT, lw=2.2, zorder=6)
        ax.text(xx, top + .14 + tier[k] * .30, k, color=ACCENT, fontsize=9,
                ha="center", family="monospace", zorder=7)
    ax.plot([x0, x0 + w_], [y0, y0], color=MUTED, lw=1.2, zorder=4)
    for tk in (0, .5, 1.0):
        ax.text(x0 + w_ * tk, y0 - .28, f"{tk:.1f}", color=MUTED, fontsize=9,
                ha="center", family="monospace")

    if t > .70:
        ax.text(x0, 1.95, f"この1体   projects {me['completed_projects_total']}"
                          f"   methods {me['methods_total']}"
                          f"   stage {me['maker_stage']}",
                color=INK, fontsize=12)
        tot = sum(s["completed_projects_total"] for s in sn.values()
                  if s["is_participant"])
        ax.text(x0, 1.55, f"30体の合計   projects {tot:,}", color=MUTED, fontsize=12)
    provenance(ax, "ACCUMULATION", "M1 trace / condition A / seed 2",
               "個体と集団は同じ snapshots.jsonl から集計している")


def f_shock_zoom(ax, t, d, prov, mods, onset):
    """P1-4(d): 1体のバー2本に寄る挿入カット（3.5s）。8 step の反復を一度断つ。

    表示値はすべて実ログ（provenance / modify_history）から取得する。
    キャプションの成功確率は **provenance の effective_success_probability の実測**
    であり、新規計算はしない。
    """
    step = onset + SHOCK_ZOOM_AFTER - 1
    recs = [p for p in prov.get(step, []) if p["agent_id"] == SHOCK_ZOOM_AGENT]
    if not recs:
        recs = prov.get(step, [])[:1]
    p = recs[0]
    req = p["required_attributes"]
    ax.text(.60, 8.40, "仕様への到達", color=INK, fontsize=24, fontweight="bold")
    ax.text(.60, 7.95, f"{p['agent_id']}  /  step {SHOCK_ZOOM_AFTER} / 8  /  "
                       f"{p['source_project_id']}",
            color=WARN, fontsize=14, family="monospace")

    for i, k in enumerate(sorted(req)):
        yy = 5.75 - i * 2.05
        b, a2, thr = p["before_attributes"][k], p["after_attributes"][k], req[k]
        bw, bh = 8.6, .70                      # 画面幅の 50%超
        x0 = 3.30
        ax.add_patch(Rectangle((x0, yy - bh / 2), bw, bh, fc=FAINT, ec="none", zorder=3))
        ax.add_patch(Rectangle((x0, yy - bh / 2), bw * b, bh, fc=MUTED, ec="none",
                               zorder=4))
        ax.add_patch(Rectangle((x0 + bw * b, yy - bh / 2), bw * (a2 - b), bh,
                               fc=OK, ec="none", zorder=5))
        ax.plot([x0 + bw * thr] * 2, [yy - bh / 2 - .22, yy + bh / 2 + .22],
                color=OK, lw=3.0, zorder=6)
        ax.text(x0 + bw * thr, yy + bh / 2 + .38, f"required {thr:.2f}", color=OK,
                fontsize=11, ha="center", family="monospace")
        ax.text(x0 - .22, yy, k, color=INK, fontsize=15, ha="right", va="center",
                family="monospace")
        ax.text(x0 + bw + .25, yy, f"{b:.2f} → {a2:.2f}", color=INK, fontsize=15,
                ha="left", va="center", family="monospace")
        ax.text(x0 + bw + .25, yy - .48, "✓ ぴったり到達", color=OK, fontsize=11,
                ha="left", va="center")

    mm = [m for m in mods.get(step, []) if m["agent_id"] == p["agent_id"]]
    if mm:
        ax.text(.60, 2.30, "  ".join(f"MODIFY {m['attr']} +{m['delta']:.2f}" for m in mm),
                color=ACCENT, fontsize=13, family="monospace", fontweight="bold")
    ax.text(.60, 1.75, f"2箇所の modify で仕様に到達（この試行の成功確率 "
                       f"{p['effective_success_probability']:.3f}）",
            color=MUTED, fontsize=12)
    ax.text(.60, 1.35, "仕様上、属性は閾値ちょうどまでしか上がらない。"
                       "越えるのではなく、届く。",
            color=MUTED, fontsize=11)
    provenance(ax, "SHOCK",
               "outputs/main_experiment/A_seed2.json  (no re-run / API calls = 0)")


def f_closing(ax, t, corr):
    """クロージングカード（4.0s）。§5 の許容内の唯一の静止区間。"""
    R = corr["runs"]
    n_tr = sum(1 for x in R if x["corrected_transition"])
    ax.text(8.0, 5.55, "COSPLAY RESERVE", color=INK, fontsize=34,
            fontweight="bold", ha="center")
    ax.text(8.0, 4.75, "未知の仕様には届いた。量には届かなかった。",
            color=MUTED, fontsize=17, ha="center")
    ax.text(8.0, 3.90, f"preregistered D4 / Transition {n_tr} / {len(R)} run",
            color=MUTED, fontsize=13, ha="center", family="monospace")
    ax.text(8.0, 3.35, "この動画は既存ログの再生であり、"
                       "現実のコスプレ制作について何かを証明したものではない。",
            color=MUTED, fontsize=11, ha="center")
    provenance(ax, "RESULT",
               "outputs/main_experiment/transition_recomputed_preregistered.json",
               "preregistered D4 / corrected adjudication")


def f_result(ax, t, d, corr):
    R = corr["runs"]
    n = len(R)
    ev = {k: sum(1 for x in R if x["ever_met"][k]) for k in
          ("active_supplier_count", "supply_duration", "coordination_edges",
           "community_supply_share")}
    n_tr = sum(1 for x in R if x["corrected_transition"])
    # --- 出現タイミング（秒）。P0-2: RESULT 28.0s。間隔はすべて 4.0s 以下 -----
    T = RESULT_SEC
    def at(sec):           # 秒 → 進捗 t の比較
        return t >= sec / T
    ax.text(8.0, 8.52, "RESULT", color=INK, fontsize=28, fontweight="bold",
            ha="center")
    # ★P0-1: 要約行はサブタイトルと「置き換える」。同時に描画しないので重なり得ない★
    if at(24.5):
        ax.text(8.0, 8.16, "3つは全 run で満たされ、届かなかったのは量だけだった。",
                color=INK, fontsize=15, ha="center")
    else:
        ax.text(8.0, 8.16, "事前登録した転化基準（4条件の同時充足）／ 20 run",
                color=MUTED, fontsize=13, ha="center")

    rows = [("供給者の形成", "active_supplier_count >= 3", ev["active_supplier_count"]),
            ("供給の継続", "supply_duration >= 4 step", ev["supply_duration"]),
            ("協調関係の形成", "coordination_edges >= 2", ev["coordination_edges"]),
            ("量", "community_supply_share >= 0.25", ev["community_supply_share"])]
    if at(0.3):
        ax.text(2.10, 6.95, "各条件を 1 step でも充足した run 数", color=MUTED,
                fontsize=11)
    # --- 4条件を 1.2s 間隔で連続的に出す（3つ緑→最後が赤のリズムを保つ）-------
    for i, (lab, cond, v) in enumerate(rows):
        if not at(0.4 + i * 1.2):
            continue
        yy = 6.35 - i * .78
        col = OK if v == n else GAP
        ax.text(2.10, yy, lab, color=col, fontsize=17, fontweight="bold")
        ax.text(5.10, yy, cond, color=MUTED, fontsize=13, family="monospace")
        ax.text(12.60, yy, f"{v} / {n} run", color=col, fontsize=19,
                fontweight="bold", family="monospace", ha="right")

    # --- ★ share 2/20 と Transition 0/20 を明確に分離する ★ ------------------
    if at(6.0):        # 表示後 4.0s 保持（次の要素は 10.0s）
        ax.add_patch(FancyBboxPatch((1.95, 2.32), 12.0, .92,
                                    boxstyle="round,pad=.07", fc=PANEL, ec=WARN,
                                    lw=1.4, zorder=8))
        ax.text(2.25, 2.90, f"量の条件を満たしたのは {ev['community_supply_share']} / {n} run。"
                            f"ただし、いずれもショック直後の1 step だけ。",
                color=WARN, fontsize=14, fontweight="bold", zorder=9)
        ax.text(2.25, 2.55, "供給が継続した（duration >= 4）と認められる時刻には届いていない",
                color=MUTED, fontsize=12, zorder=9)
    if at(10.0):
        ax.text(2.25, 1.95, "share が最大になるのは onset+0、"
                            "duration >= 4 が成立するのは onset+3。両者の時間帯は重ならない。",
                color=MUTED, fontsize=11)
    if at(13.5):
        ax.plot([1.95, 13.95], [1.72, 1.72], color=FAINT, lw=1.4)
        ax.text(2.10, 1.16, "4条件の同時成立（Transition）", color=INK, fontsize=19,
                fontweight="bold")
        ax.text(12.60, 1.16, f"{n_tr} / {n} run", color=GAP, fontsize=22,
                fontweight="bold", family="monospace", ha="right")
    if at(17.0):
        ax.text(13.05, 1.16, "←", color=GAP, fontsize=18, ha="left")
        ax.text(2.10, .78, "「share が 0/20」ではない。0/20 は 4条件が同時に成立した run の数。",
                color=GAP, fontsize=12)
    if at(20.5):       # Transition 行を囲って締める
        ax.add_patch(FancyBboxPatch((1.95, .74), 12.0, .96,
                                    boxstyle="round,pad=.06", fc="none", ec=GAP,
                                    lw=1.6, zorder=2))
    provenance(ax, "RESULT",
               "outputs/main_experiment/transition_recomputed_preregistered.json",
               "preregistered D4 / corrected adjudication")


# ---------------------------------------------------------------------------
# タイムライン
# ---------------------------------------------------------------------------

def frame_plan() -> list[tuple[str, float]]:
    plan = []
    for name, n in SEG:
        for i in range(n):
            plan.append((name, i / n))
    return plan


def render(i, plan, ctx) -> np.ndarray:
    (acts, snaps, d, prov, mods, coord, corr, parts, edges,
     pos_a, pos_s, pos_i, zaid, zw0) = ctx
    name, t = plan[i]
    fig, ax = new_canvas()
    onset = d["onset_step"]
    if name == "intro":
        f_intro(ax, t, parts, edges, snaps, pos_i)
    elif name == "accum_a":
        wk = min(zw0 - 1, int(t * zw0))
        f_accum(ax, wk, snaps, acts, parts, edges, pos_a,
                "REPLAY SPEED  x45 (1 s = 3.0 weeks)")
    elif name == "zoom":
        span = ZOOM_SPAN
        k = min(span - 1, int(t * span))
        f_zoom(ax, zw0 + k, (t * span) - k, snaps, acts, zaid, zw0)
    elif name == "bridge":
        f_bridge(ax, t, snaps, parts, zaid, zw0 + ZOOM_SPAN - 1)
    elif name == "accum_b":
        lo, hi = zw0 + ZOOM_SPAN, 156
        wk = min(hi - 1, lo + int(t * (hi - lo)))
        f_accum(ax, wk, snaps, acts, parts, edges, pos_a,
                "REPLAY SPEED  x45 (1 s = 4.6 weeks)")
    elif name == "shock_title":
        f_shock_title(ax, t, d["provenance"][0]["required_attributes"])
    elif name in ("shock_a", "shock_b"):
        base = 0 if name == "shock_a" else SHOCK_ZOOM_AFTER
        k = min(3, int(t * 4))
        step = onset + base + k
        run = sum(p["supplied_units"] for s in range(onset, step + 1)
                  for p in prov.get(s, []))
        f_shock(ax, step, (t * 4) - k, d, prov, mods, coord, pos_s, run, onset,
                base + k + 1)
    elif name == "shock_zoom":
        f_shock_zoom(ax, t, d, prov, mods, onset)
    elif name == "closing":
        f_closing(ax, t, corr)
    else:
        f_result(ax, t, d, corr)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return buf


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true",
                    help="各フェーズ5秒の確認用（静止画も出す）")
    args = ap.parse_args()

    acts, snaps, d, prov, mods, coord, corr, parts, edges = load_all()
    pos_a = visual_only_grid(parts, 6, 1.70, 7.10, 1.86, 1.20)
    pos_s = visual_only_grid(sorted(d["shock_agent_ids"]), 3, 5.55, 6.20, 3.45, 3.30)
    # P0-3: intro 専用の格子。10列x3行で画面幅いっぱいに水平中央寄せし、
    # 文字ブロック(y<4.0)と縦に分離する。
    pos_i = visual_only_grid(parts, 10, 2.15, 7.45, 1.30, 1.30)
    # P1-5(a): クローズアップ対象を決定論的に選び、選定結果をログに残す
    zaid, zw0 = select_closeup(acts, parts, span=ZOOM_SPAN)
    print(f"  closeup（選定規則による）: {zaid} / weeks {zw0 + 1}-{zw0 + ZOOM_SPAN}")
    ctx = (acts, snaps, d, prov, mods, coord, corr, parts, edges,
           pos_a, pos_s, pos_i, zaid, zw0)
    plan = frame_plan()
    assert len(plan) == TOTAL

    if args.sample:
        out = OUT / "prototype"
        out.mkdir(parents=True, exist_ok=True)
        offs, idx = {}, 0
        for name, n in SEG:
            offs[name] = idx
            idx += n
        # ★フレームを溜め込まず1枚ずつ書き出す★
        # 1920x1080x3 = 6.2MB/frame。5400 frame を list に持つと約 33GB になり
        # MemoryError で落ちる（実際に落ちた）。writer へ逐次 append する。
        n_written = 0
        with imageio.get_writer(out / "sample.mp4", fps=FPS, codec="libx264",
                                quality=8, macro_block_size=1) as wr:
            for name, n in SEG:
                mid = offs[name] + n // 2
                lo = max(offs[name], mid - 75)
                for j in range(lo, min(lo + 150, offs[name] + n)):
                    wr.append_data(render(j, plan, ctx))
                    n_written += 1
                # 段階表示のフェーズがあるため、静止画は終盤（85%地点）を使う
                imageio.imwrite(out / f"phase_{name}.png",
                                render(offs[name] + int(n * 0.85), plan, ctx))
                print(f"  phase {name}: 静止画 + 5秒")
        print(f"\nsample.mp4  {n_written} frames / {n_written/FPS:.1f}s -> {out}")
        return 0

    path = OUT / "cosplay_reserve_demo.mp4"
    n_written = 0
    with imageio.get_writer(path, fps=FPS, codec="libx264", quality=8,
                            macro_block_size=1) as wr:
        for i in range(len(plan)):
            wr.append_data(render(i, plan, ctx))
            n_written += 1
            if i % 300 == 0:
                print(f"  {i}/{len(plan)}  ({i/FPS:.0f}s)", flush=True)
    assert n_written == TOTAL, f"書き出したフレーム数が {TOTAL} でない: {n_written}"
    print(f"\n{n_written} frames / {n_written/FPS:.1f}s -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
