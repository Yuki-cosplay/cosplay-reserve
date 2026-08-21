"""デモ動画の visual prototype（静止画2枚 + 10〜15秒の低負荷プレビュー）。

【このスクリプトがやらないこと】
- simulation を実行しない（確定済みログを読むだけ）
- LLM / API を呼ばない（`src.llm` / `anthropic` を import しない）
- ログに無い action / coordination event / attribute 変化を描かない

【データと演出の境界】
- **データ**: 描画するイベントは必ず trace / main_experiment ログの1レコードに対応する
- **視覚補間**: 座標・レイアウト・ポーズは `visual_only_*` 接頭辞で分離。
  これらは simulation event ではない

再生元:
  Accumulation: figures/demo_video/data/m1_trace/A_seed2/   （M1 trace, 条件A/seed2）
  Shock:        outputs/main_experiment/A_seed2.json        （読み取り専用）
  Network:      build_world('configs/condition_a.yaml', seed=2)  ※固定・M1中不変

使い方:
    python figures/demo_video/make_prototype.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # リポジトリ直下を import 可能に

import imageio.v2 as imageio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "figures" / "demo_video" / "data" / "m1_trace" / "A_seed2"
SHOCK_LOG = ROOT / "outputs" / "main_experiment" / "A_seed2.json"
OUT = ROOT / "figures" / "demo_video" / "prototype"

W, H = 1920, 1080
DPI = 100
FIGSIZE = (W / DPI, H / DPI)

# --- 配色（研究可視化寄り。子供向けにしない）--------------------------------
BG = "#14171c"
PANEL = "#1c2027"
INK = "#e8eaed"
MUTED = "#8b929c"
FAINT = "#2b3038"
OK = "#4ea87a"
GAP = "#c76a52"
ACCENT = "#5b93c7"
WARN = "#c9a84c"

# 実 trace に存在する M1 の6行動のみ。propose / join は M1 に存在しない。
ACTION_STYLE = {
    "practice": {"color": WARN,   "label": "PRACTICE"},
    "make":     {"color": OK,     "label": "MAKE"},
    "observe":  {"color": ACCENT, "label": "OBSERVE"},
    "ask":      {"color": "#ab7fc4", "label": "ASK"},
    "share":    {"color": "#7fc4b8", "label": "SHARE"},
    "idle":     {"color": MUTED,   "label": "IDLE"},
}
# target_agent_id を持つ action だけ有向線を描いてよい（trace で確認済み）
LINE_ACTIONS = {"observe", "ask"}

matplotlib.rcParams["font.family"] = "sans-serif"
matplotlib.rcParams["font.sans-serif"] = ["Meiryo", "Yu Gothic", "MS Gothic", "DejaVu Sans"]


# ---------------------------------------------------------------------------
# データ読み込み（唯一の真実の出どころ）
# ---------------------------------------------------------------------------

def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]


def load_accumulation():
    acts = read_jsonl(TRACE / "actions.jsonl")
    snaps = read_jsonl(TRACE / "snapshots.jsonl")
    by_step_act: dict[int, list[dict]] = {}
    for a in acts:
        by_step_act.setdefault(a["step"], []).append(a)
    by_step_snap: dict[int, dict[str, dict]] = {}
    for s in snaps:
        by_step_snap.setdefault(s["step"], {})[s["agent_id"]] = s
    return by_step_act, by_step_snap


def load_shock():
    d = json.loads(SHOCK_LOG.read_text(encoding="utf-8"))
    prov: dict[int, list[dict]] = {}
    for p in d["provenance"]:
        prov.setdefault(p["step"], []).append(p)
    mods: dict[int, list[dict]] = {}
    for aid, hist in d["modify_history"].items():
        for m in hist:
            mods.setdefault(m["step"], []).append({**m, "agent_id": aid})
    # coordination は「その step までに成立済み」の累積状態のみ（イベント時刻は復元不能）
    coord: dict[int, list[list[str]]] = {}
    for st in sorted(prov):
        pairs: set[tuple[str, str]] = set()
        for p in prov[st]:
            for e in p["coordination_relation"]["edges_involving_self"]:
                pairs.add(tuple(sorted(e)))
        coord[st] = [list(x) for x in sorted(pairs)]
    return d, prov, mods, coord


def load_network():
    """M1 中は固定のネットワーク。build_world は決定論的で API を呼ばない。"""
    from src.world.world import build_world

    w = build_world(str(ROOT / "configs" / "condition_a.yaml"), seed=2)
    parts = sorted(a.id for a in w.agents.values() if a.is_participant)
    edges = [(u, v) for u, v in w.graph.edges() if u in set(parts) and v in set(parts)]
    return parts, edges


# ---------------------------------------------------------------------------
# 視覚補間（simulation event ではない）
# ---------------------------------------------------------------------------

def visual_only_grid(ids: list[str], cols: int, x0: float, y0: float,
                     dx: float, dy: float) -> dict[str, tuple[float, float]]:
    """Agent の画面座標。**シミュレーションに位置の概念は無い。純粋な描画都合。**"""
    pos = {}
    for i, aid in enumerate(ids):
        pos[aid] = (x0 + (i % cols) * dx, y0 - (i // cols) * dy)
    return pos


def visual_only_ui_skill(skills: dict[str, float]) -> float:
    """**UI 用の集約値**。6技能の単純平均。

    ★研究指標ではない★ RESULTS.md / SPEC.md のどの指標とも対応しない。
    バー1本で「だいたいの熟練度」を示すためだけに使う。
    """
    return float(sum(skills.values()) / len(skills))


# ---------------------------------------------------------------------------
# キャラクター描画（頭・胴・腕・道具。版権要素なし）
# ---------------------------------------------------------------------------

def draw_agent(ax, x, y, s, action: str, *, stage: str = "", ui_skill: float | None = None,
               label: str | None = None, big: bool = False):
    """1体を図形で描く。ポーズは action ごとに変える（色だけに頼らない）。"""
    col = ACTION_STYLE.get(action, {}).get("color", MUTED)
    # 胴
    ax.add_patch(FancyBboxPatch((x - 0.28 * s, y - 0.55 * s), 0.56 * s, 0.62 * s,
                                boxstyle="round,pad=0.02", fc=FAINT, ec=col,
                                lw=1.6 if big else 1.1, zorder=3))
    # 頭
    ax.add_patch(Circle((x, y + 0.28 * s), 0.22 * s, fc=PANEL, ec=col,
                        lw=1.6 if big else 1.1, zorder=4))

    # 腕（action ごとのポーズ）— これは視覚表現であり、ログの action に1対1対応する
    def arm(dx1, dy1, dx2, dy2):
        ax.plot([x + dx1 * s, x + dx2 * s], [y + dy1 * s, y + dy2 * s],
                color=col, lw=2.2 if big else 1.5, solid_capstyle="round", zorder=5)

    if action == "practice":       # 工具を上下に動かす
        arm(-0.28, -0.05, -0.46, 0.20); arm(0.28, -0.05, 0.46, 0.24)
        ax.plot([x + 0.40 * s, x + 0.52 * s], [y + 0.24 * s, y + 0.10 * s],
                color=WARN, lw=2.6 if big else 1.8, zorder=5)      # 工具
    elif action == "make":         # 作業台に向かう
        arm(-0.28, -0.05, -0.44, -0.26); arm(0.28, -0.05, 0.44, -0.26)
        ax.add_patch(Rectangle((x - 0.52 * s, y - 0.62 * s), 1.04 * s, 0.10 * s,
                               fc=OK, ec="none", alpha=0.55, zorder=2))  # 作業台
        ax.add_patch(Rectangle((x - 0.13 * s, y - 0.50 * s), 0.26 * s, 0.16 * s,
                               fc=OK, ec="none", alpha=0.9, zorder=6))   # project object
    elif action == "observe":      # 相手の方を見る（頭に視線）
        arm(-0.28, -0.05, -0.42, 0.02); arm(0.28, -0.05, 0.42, 0.02)
        ax.plot([x + 0.08 * s, x + 0.20 * s], [y + 0.30 * s, y + 0.34 * s],
                color=ACCENT, lw=1.8 if big else 1.2, zorder=6)
    elif action == "ask":          # 「?」
        arm(-0.28, -0.05, -0.40, 0.16); arm(0.28, -0.05, 0.40, 0.16)
        ax.text(x + 0.42 * s, y + 0.48 * s, "?", color=col, fontsize=11 if big else 7,
                fontweight="bold", ha="center", va="center", zorder=6)
    elif action == "share":        # 発信（全方位。trace に相手 id が無いため線は引かない）
        arm(-0.28, -0.05, -0.44, 0.10); arm(0.28, -0.05, 0.44, 0.10)
        ax.add_patch(Circle((x, y + 0.28 * s), 0.34 * s, fc="none", ec=col,
                            lw=1.0, alpha=0.55, zorder=2))
    else:                          # idle — 静止
        arm(-0.28, -0.05, -0.30, -0.30); arm(0.28, -0.05, 0.30, -0.30)

    if ui_skill is not None:       # UI 用集約バー（研究指標ではない）
        bw = 0.9 * s
        ax.add_patch(Rectangle((x - bw / 2, y - 0.80 * s), bw, 0.07 * s,
                               fc=FAINT, ec="none", zorder=3))
        ax.add_patch(Rectangle((x - bw / 2, y - 0.80 * s), bw * ui_skill, 0.07 * s,
                               fc=ACCENT, ec="none", zorder=4))
    if label:
        ax.text(x, y - 0.95 * s, label, color=MUTED, fontsize=6.5,
                ha="center", va="top", zorder=5)
    if big and stage:
        ax.text(x, y + 0.62 * s, stage.upper(), color=MUTED, fontsize=8,
                ha="center", va="bottom", zorder=5)


def provenance_box(ax, phase: str, source: str, extra: str = ""):
    """画面隅に常時表示する再生元。概念アニメーションではないことの明示。"""
    txt = f"{phase}\nsource = {source}"
    if extra:
        txt += f"\n{extra}"
    ax.text(0.006, 0.018, txt, transform=ax.transAxes, color=MUTED, fontsize=8.5,
            va="bottom", ha="left", family="monospace", linespacing=1.5, zorder=20)


def new_canvas():
    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    ax.set_xlim(0, 16); ax.set_ylim(0, 9); ax.axis("off")
    return fig, ax


# ---------------------------------------------------------------------------
# 蓄積相フレーム
# ---------------------------------------------------------------------------

def draw_accumulation(ax, step, acts_at, snaps_at, parts, edges, pos, speed_label,
                      focus: str | None = None):
    ax.text(0.30, 8.55, "ACCUMULATION", color=INK, fontsize=21, fontweight="bold")
    ax.text(0.30, 8.18, "文化活動による技能・制作物・関係の蓄積", color=MUTED, fontsize=11)
    ax.text(11.55, 8.55, f"WEEK {step + 1} / 156", color=INK, fontsize=21,
            fontweight="bold", family="monospace")
    ax.text(11.55, 8.18, speed_label, color=WARN, fontsize=11, family="monospace")

    # 固定ネットワーク（M1 中不変。生成される演出はしない）
    for u, v in edges:
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=FAINT, lw=0.7, zorder=1)

    # その step の行動（participant のみ表示）
    latest = {}
    for a in acts_at:
        if a["is_participant"]:
            latest[a["agent_id"]] = a          # 同 step 複数行動は最後を代表表示

    # 有向線は target_agent_id を持つ action だけ（trace で確認済み: observe / ask）
    for a in acts_at:
        if a["action"] in LINE_ACTIONS and a.get("target_agent_id"):
            s_, t_ = a["agent_id"], a["target_agent_id"]
            if s_ in pos and t_ in pos:
                ax.annotate("", xy=pos[t_], xytext=pos[s_],
                            arrowprops=dict(arrowstyle="-|>", mutation_scale=8,
                                            color=ACTION_STYLE[a["action"]]["color"],
                                            alpha=0.34, lw=0.9,
                                            connectionstyle="arc3,rad=0.14"), zorder=2)

    for aid in parts:
        x, y = pos[aid]
        act = latest.get(aid, {}).get("action", "idle")
        sn = snaps_at.get(aid, {})
        if aid == focus:  # 選択中は明示的に大きく＋リング
            ax.add_patch(Circle((x, y - 0.05), 0.62, fc="none", ec=INK, lw=1.4,
                                alpha=0.65, zorder=7))
        draw_agent(ax, x, y, 0.62 if aid == focus else 0.44, act,
                   ui_skill=visual_only_ui_skill(sn["skills"]) if sn else None,
                   label=aid if aid == focus else None,
                   big=(aid == focus))

    # 凡例（6行動）— 最下段の Agent と重ならない位置に置く
    ax.text(0.30, 1.44, "ACTIONS（M1 trace に存在する6行動のみ）",
            color=MUTED, fontsize=9.5)
    for i, (k, st) in enumerate(ACTION_STYLE.items()):
        xx = 0.30 + i * 1.72
        draw_agent(ax, xx + 0.20, 0.92, 0.26, k)
        ax.text(xx + 0.48, 0.84, st["label"], color=st["color"], fontsize=9,
                va="center", family="monospace")

    # 右パネル: 選択 Agent の詳細6技能
    if focus and focus in snaps_at:
        sn = snaps_at[focus]
        px, py = 13.15, 7.35
        ax.add_patch(FancyBboxPatch((px - 0.25, py - 4.35), 2.95, 4.55,
                                    boxstyle="round,pad=0.05", fc=PANEL, ec=FAINT, lw=1.2,
                                    zorder=8))
        ax.text(px, py, f"{focus}", color=INK, fontsize=12, fontweight="bold", zorder=9)
        ax.text(px, py - 0.34, f"stage: {sn['maker_stage']}", color=MUTED, fontsize=9,
                zorder=9, family="monospace")
        ax.text(px, py - 0.62, f"projects: {sn['completed_projects_total']}   "
                               f"methods: {sn['methods_total']}",
                color=MUTED, fontsize=9, zorder=9, family="monospace")
        ax.text(px, py - 1.00, "skills（実 trace 値）", color=MUTED, fontsize=9, zorder=9)
        for i, (k, v) in enumerate(sorted(sn["skills"].items())):
            yy = py - 1.35 - i * 0.42
            ax.text(px, yy, k, color=MUTED, fontsize=8.5, va="center",
                    family="monospace", zorder=9)
            ax.add_patch(Rectangle((px + 0.85, yy - 0.09), 1.6, 0.18,
                                   fc=FAINT, ec="none", zorder=9))
            ax.add_patch(Rectangle((px + 0.85, yy - 0.09), 1.6 * v, 0.18,
                                   fc=ACCENT, ec="none", zorder=10))
            ax.text(px + 2.50, yy, f"{v:.2f}", color=INK, fontsize=8, va="center",
                    ha="left", family="monospace", zorder=10)

    provenance_box(ax, "ACCUMULATION",
                   "M1 trace / condition A / seed 2",
                   "bars under agents = UI aggregate (not a research metric)")


# ---------------------------------------------------------------------------
# ショック相フレーム
# ---------------------------------------------------------------------------

def draw_shock(ax, step, d, prov, mods, coord, pos, speed_label, supply_running):
    req = d["provenance"][0]["required_attributes"]
    onset = d["onset_step"]
    ax.text(0.30, 8.55, "SUPPLY SHOCK", color=GAP, fontsize=21, fontweight="bold")
    ax.text(0.30, 8.18, "未知仕様への適応（答えは与えていない）", color=MUTED, fontsize=11)
    ax.text(11.30, 8.55, f"STEP {step - onset + 1} / 8  (6h each)", color=INK,
            fontsize=17, fontweight="bold", family="monospace")
    ax.text(11.30, 8.18, speed_label, color=WARN, fontsize=11, family="monospace")

    # REQUIRED（常時表示。品名・用途は出さない）
    ax.add_patch(FancyBboxPatch((0.30, 6.10), 3.35, 1.42, boxstyle="round,pad=0.06",
                                fc=PANEL, ec=GAP, lw=1.6, zorder=8))
    ax.text(0.52, 7.22, "REQUIRED", color=GAP, fontsize=12, fontweight="bold", zorder=9)
    for i, (k, v) in enumerate(sorted(req.items())):
        ax.text(0.52, 6.82 - i * 0.36, f"{k} >= {v:.2f}", color=INK, fontsize=13,
                family="monospace", zorder=9)

    # COMMUNITY SUPPLY（左カラムへ移し、Agent 領域と重ねない）
    ax.add_patch(FancyBboxPatch((0.30, 4.40), 3.35, 1.30, boxstyle="round,pad=0.06",
                                fc=PANEL, ec=OK, lw=1.4, zorder=8))
    ax.text(0.52, 5.35, "COMMUNITY SUPPLY", color=MUTED, fontsize=10, zorder=9)
    ax.text(0.52, 4.76, f"{supply_running:.0f} units", color=OK, fontsize=21,
            fontweight="bold", family="monospace", zorder=9)

    # coordination は「その step までに成立済み」の累積状態のみ（イベント演出はしない）
    pairs = coord.get(step, [])
    for u, v in pairs:
        if u in pos and v in pos:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
                    color=WARN, lw=2.0, alpha=0.7, zorder=2, solid_capstyle="round")
    if pairs:
        ax.text(0.30, 3.85, f"COORDINATION ACTIVE  ({len(pairs)} pair)",
                color=WARN, fontsize=11, fontweight="bold", family="monospace")
        ax.text(0.30, 3.52, "※ 成立済みの累積状態。", color=MUTED, fontsize=8.5)
        ax.text(0.30, 3.26, "　 成立の瞬間は復元不能のため演出しない",
                color=MUTED, fontsize=8.5)

    mods_now: dict[str, list[dict]] = {}
    for m in mods.get(step, []):
        mods_now.setdefault(m["agent_id"], []).append(m)

    # 同一 step に複数 make がある Agent は最初の1件を代表表示し、件数を添える
    by_agent: dict[str, list[dict]] = {}
    for p in prov.get(step, []):
        by_agent.setdefault(p["agent_id"], []).append(p)

    for aid, recs in by_agent.items():
        if aid not in pos:
            continue
        p = recs[0]
        x, y = pos[aid]
        ax.text(x, y + 0.95, aid, color=INK, fontsize=11, ha="center",
                family="monospace", fontweight="bold")
        if len(recs) > 1:
            ax.text(x, y + 0.70, f"({len(recs)} make attempts)", color=MUTED,
                    fontsize=7.5, ha="center", family="monospace")
        draw_agent(ax, x, y, 0.58, "make", big=True)
        ax.text(x, y - 0.60, p["source_project_id"], color=MUTED, fontsize=8,
                ha="center", family="monospace")

        # 属性バー（実ログの before / after。値は毎レコードから読む）
        for i, k in enumerate(sorted(req)):
            yy = y - 0.86 - i * 0.30
            b, a2, thr = p["before_attributes"][k], p["after_attributes"][k], req[k]
            bw = 1.30
            ax.add_patch(Rectangle((x - bw / 2, yy - 0.09), bw, 0.18,
                                   fc=FAINT, ec="none", zorder=3))
            ax.add_patch(Rectangle((x - bw / 2, yy - 0.09), bw * b, 0.18,
                                   fc=MUTED, ec="none", zorder=4))
            if a2 > b:   # modify で伸びた分
                ax.add_patch(Rectangle((x - bw / 2 + bw * b, yy - 0.09), bw * (a2 - b),
                                       0.18, fc=ACCENT, ec="none", zorder=5))
            ax.plot([x - bw / 2 + bw * thr] * 2, [yy - 0.15, yy + 0.15],
                    color=GAP, lw=1.6, zorder=6)
            ax.text(x - bw / 2 - 0.08, yy, k, color=MUTED, fontsize=7.5,
                    ha="right", va="center", family="monospace")
            ax.text(x + bw / 2 + 0.08, yy, f"{b:.2f}→{a2:.2f}", color=INK, fontsize=7.5,
                    ha="left", va="center", family="monospace")

        if aid in mods_now:
            txt = "  ".join(f"{m['attr']} +{m['delta']:.2f}" for m in mods_now[aid])
            ax.text(x, y - 1.50, f"MODIFY {txt}", color=ACCENT, fontsize=8.5,
                    ha="center", fontweight="bold", family="monospace")

        # 成功・失敗の両方を隠さず表示
        if p["supplied_units"] > 0:
            ax.text(x, y - 1.82, f"SUPPLY +{p['supplied_units']:.0f}", color=OK,
                    fontsize=12, ha="center", fontweight="bold", family="monospace")
        elif not p["make_success"]:
            ax.text(x, y - 1.82, "MAKE FAILED", color=GAP, fontsize=10,
                    ha="center", family="monospace")
        elif not p["meets_requirement"]:
            ax.text(x, y - 1.82, "REQ NOT MET", color=WARN, fontsize=10,
                    ha="center", family="monospace")

    provenance_box(ax, "SHOCK", "outputs/main_experiment/A_seed2.json",
                   "no re-run / API calls = 0")


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------

def render(fn, *args, **kw) -> np.ndarray:
    fig, ax = new_canvas()
    fn(ax, *args, **kw)
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return buf


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    acts, snaps = load_accumulation()
    d, prov, mods, coord = load_shock()
    parts, edges = load_network()
    pos_acc = visual_only_grid(parts, 6, 1.70, 7.10, 1.86, 1.20)
    shock_ids = sorted(d["shock_agent_ids"])
    pos_shk = visual_only_grid(shock_ids, 3, 5.55, 6.10, 3.45, 3.28)

    ACC_SPEED = "REPLAY SPEED  x30 (1 frame = 1 week)"
    SHK_SPEED = "REPLAY SPEED  x0.25 (1 step = 4 frames)"

    # --- 静止画1: 蓄積相 ---------------------------------------------------
    st = 120
    img = render(draw_accumulation, st, acts[st], snaps[st], parts, edges,
                 pos_acc, ACC_SPEED, focus="agent_5")
    imageio.imwrite(OUT / "accumulation_prototype.png", img)

    # --- 静止画2: ショック相 -----------------------------------------------
    st = 158
    run = sum(p["supplied_units"] for s in range(156, st + 1) for p in prov.get(s, []))
    img = render(draw_shock, st, d, prov, mods, coord, pos_shk, SHK_SPEED, run)
    imageio.imwrite(OUT / "shock_prototype.png", img)

    # --- プレビュー動画（10〜15秒）------------------------------------------
    FPS = 30
    frames: list[np.ndarray] = []
    # 0–5秒: 蓄積相を高速再生（1 frame = 1 week、150 frame = 5秒）
    for st in range(0, 150):
        frames.append(render(draw_accumulation, st, acts[st], snaps[st], parts, edges,
                             pos_acc, ACC_SPEED,
                             focus="agent_5" if st > 40 else None))
    # 5–7秒: SHOCK 表示（60 frame）
    for _ in range(60):
        fig, ax = new_canvas()
        req = d["provenance"][0]["required_attributes"]
        ax.text(8.0, 5.30, "SUPPLY SHOCK", color=GAP, fontsize=44,
                fontweight="bold", ha="center")
        ax.text(8.0, 4.55, "REQUIRED", color=MUTED, fontsize=15, ha="center")
        for i, (k, v) in enumerate(sorted(req.items())):
            ax.text(8.0, 4.00 - i * 0.52, f"{k} >= {v:.2f}", color=INK, fontsize=24,
                    ha="center", family="monospace")
        ax.text(8.0, 2.75, "何を作るべきかは指示していない", color=MUTED,
                fontsize=13, ha="center")
        provenance_box(ax, "SHOCK", "outputs/main_experiment/A_seed2.json",
                       "no re-run / API calls = 0")
        fig.canvas.draw()
        frames.append(np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy())
        plt.close(fig)
    # 7–15秒: ショック相 8 step（1 step = 30 frame = 1秒 → 240 frame = 8秒）
    run = 0.0
    for st in range(156, 164):
        run += sum(p["supplied_units"] for p in prov.get(st, []))
        f = render(draw_shock, st, d, prov, mods, coord, pos_shk, SHK_SPEED, run)
        frames.extend([f] * 30)

    path = OUT / "prototype.mp4"
    imageio.mimwrite(path, frames, fps=FPS, codec="libx264", quality=8,
                     macro_block_size=1)
    print(f"frames={len(frames)}  duration={len(frames)/FPS:.1f}s  -> {path}")
    print(f"-> {OUT/'accumulation_prototype.png'}")
    print(f"-> {OUT/'shock_prototype.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
