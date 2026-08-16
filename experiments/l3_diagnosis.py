"""L3 診断: 既存 timeseries のみを使い「到達速度」を測る（測定器の診断）。

モデル・閾値・パラメータは一切変更しない。新しいシミュレーションも行わない。
"""
from __future__ import annotations
import csv, glob, json, statistics as st, sys
from collections import defaultdict

N_PART = 30
STEPS = 156

def load_runs(pattern="outputs/*_seed*/"):
    runs = []
    for d in sorted(glob.glob(pattern)):
        meta = json.load(open(d + "metadata.json", encoding="utf-8"))
        part, tot = [], []
        for r in csv.DictReader(open(d + "timeseries.csv", encoding="utf-8")):
            if r["population"] == "participants_only":
                part.append(r)
            elif r["population"] == "step_totals":
                tot.append(r)
        part.sort(key=lambda r: int(r["step"]))
        tot.sort(key=lambda r: int(r["step"]))
        runs.append({"meta": meta, "part": part, "tot": tot})
    return runs

def curve(part):
    return [(int(r["step"]), int(r["maker_count"])) for r in part]

def diagnose(run):
    c = curve(run["part"])
    steps = [s for s, _ in c]
    counts = [m for _, m in c]
    monotone = all(b >= a for a, b in zip(counts, counts[1:]))

    # 初到達 step: maker_count の増分を「新規到達者数」とみなす（単調なら厳密）
    arrivals, prev = [], 0
    for s, m in c:
        for _ in range(max(0, m - prev)):
            arrivals.append(s)
        prev = max(prev, m)
    mean_ttm = st.fmean(arrivals) if arrivals else float("nan")
    med_ttm = st.median(arrivals) if arrivals else float("nan")

    auc = sum(counts)                       # step 幅 1
    auc_norm = auc / (N_PART * len(counts))

    def first_at(frac):
        need = frac * N_PART
        for s, m in c:
            if m >= need:
                return s
        return None

    tot = run["tot"]
    sgpt = [float(r["skill_gain_per_time"]) for r in tot if r.get("skill_gain_per_time")]
    mpapt = [float(r.get("method_peer_acquisition_per_time") or 0) for r in tot]
    cp = [int(r["completed_projects_total"]) for r in run["part"]]
    make_time = [float(r.get("time_make") or 0) for r in tot]
    succ_per_time = (cp[-1] - cp[0]) / sum(make_time) if sum(make_time) else 0.0

    return {
        "condition": run["meta"]["condition"],
        "seed": run["meta"]["random_seed"],
        "monotone": monotone,
        "n_arrived": len(arrivals),
        "mean_time_to_maker": mean_ttm,
        "median_time_to_maker": med_ttm,
        "maker_count_auc": auc,
        "maker_count_auc_norm": auc_norm,
        "time_to_50pct": first_at(0.5),
        "time_to_90pct": first_at(0.9),
        "skill_gain_per_time": st.fmean(sgpt) if sgpt else 0.0,
        "successful_projects_per_time": succ_per_time,
        "method_peer_acquisition_per_time": st.fmean(mpapt) if mpapt else 0.0,
        "peer_methods_final": int(run["part"][-1]["method_peer_held"]),
    }

def report(pattern, label):
    runs = load_runs(pattern)
    rows = [diagnose(r) for r in runs]
    by = defaultdict(list)
    for r in rows:
        by[r["condition"]].append(r)
    print(f"=== {label} ({len(rows)} runs, seeds={sorted({r['seed'] for r in rows})[:3]}..) ===")
    keys = ["mean_time_to_maker","median_time_to_maker","maker_count_auc",
            "time_to_50pct","time_to_90pct","skill_gain_per_time",
            "successful_projects_per_time","method_peer_acquisition_per_time","peer_methods_final"]
    print(f"{'metric':<34}" + "".join(f"{c:>12}" for c in "ABCD"))
    for k in keys:
        line = f"{k:<34}"
        for c in "ABCD":
            v = [x[k] for x in by[c] if x[k] is not None]
            line += f"{st.fmean(v):>12.3f}" if v else f"{'-':>12}"
        print(line)
    print(f"{'(sd mean_time_to_maker)':<34}" + "".join(
        f"{st.pstdev([x['mean_time_to_maker'] for x in by[c]]):>12.3f}" for c in "ABCD"))
    print(f"monotone maker_count: {sum(1 for r in rows if r['monotone'])}/{len(rows)}")

    # paired seed contrast
    print("\npaired-seed contrasts on mean_time_to_maker (negative = faster):")
    idx = {(r["condition"], r["seed"]): r for r in rows}
    seeds = sorted({r["seed"] for r in rows})
    for name, (x, y) in {"peer A-C": ("A","C"), "peer B-D": ("B","D"),
                          "topo A-B": ("A","B"), "topo C-D": ("C","D")}.items():
        d = [idx[(x,s)]["mean_time_to_maker"] - idx[(y,s)]["mean_time_to_maker"]
             for s in seeds if (x,s) in idx and (y,s) in idx]
        print(f"  {name}: mean={st.fmean(d):+.3f} sd={st.pstdev(d):.3f} "
              f"range=[{min(d):+.2f},{max(d):+.2f}] n_neg={sum(1 for v in d if v<0)}/{len(d)}")
    inter = [ (idx[("A",s)]["mean_time_to_maker"]-idx[("B",s)]["mean_time_to_maker"])
             -(idx[("C",s)]["mean_time_to_maker"]-idx[("D",s)]["mean_time_to_maker"]) for s in seeds]
    print(f"  interaction (A-B)-(C-D): mean={st.fmean(inter):+.3f} sd={st.pstdev(inter):.3f}")
    return rows

if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else "outputs/*_seed*/", sys.argv[2] if len(sys.argv)>2 else "seed 1-20")
