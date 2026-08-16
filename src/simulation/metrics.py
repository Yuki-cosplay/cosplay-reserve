"""Metrics の算出と出力（docs/DESIGN_M1.md §10）。

すべての集計 Metrics を 3系列で保存する（決定 Z4、必須）:
  all_agents / participants_only / nonparticipants_only

H1/H2 の主要判定指標は participants_only である。
non-participant を分母に含めた指標を主要判定に使うと、条件操作が到達しない層で
効果量が機械的に希釈される。

M1 では記録しないもの:
  asset_distribution  — 設備は run 中不変で定数列になる（決定 U1）
  network_density     — グラフを変更する処理がなく定数列になる（決定 P2）
  どちらも初期値を metadata.json に保存する。
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

import networkx as nx

POPULATIONS = ("all_agents", "participants_only", "nonparticipants_only")


def _select(agents: dict, population: str) -> list:
    values = list(agents.values())
    if population == "participants_only":
        return [a for a in values if a.is_participant]
    if population == "nonparticipants_only":
        return [a for a in values if not a.is_participant]
    return values


def _safe(fn, seq, default=0.0):
    return fn(seq) if seq else default


@dataclass
class MetricsRecorder:
    rows: list[dict] = field(default_factory=list)
    method_events: list[dict] = field(default_factory=list)

    def record(self, world, stats) -> None:
        base = {"step": world.step, "condition": world.cfg["condition"]}

        for pop in POPULATIONS:
            agents = _select(world.agents, pop)
            row = dict(base)
            row["population"] = pop
            row["n_agents"] = len(agents)

            stages = [a.maker_stage.value for a in agents]
            row["maker_count"] = sum(1 for s in stages if s in ("maker", "advanced_maker"))
            for s in ("consumer", "customizer", "maker", "advanced_maker"):
                row[f"stage_{s}"] = stages.count(s)

            all_skills = [v for a in agents for v in a.skills.values()]
            row["skill_mean"] = _safe(statistics.fmean, all_skills)
            row["skill_median"] = _safe(statistics.median, all_skills)
            row["skill_max"] = _safe(max, all_skills)
            row["skill_var"] = statistics.pvariance(all_skills) if len(all_skills) > 1 else 0.0

            methods = [m for a in agents for m in a.methods.values()]
            row["method_count_total"] = len({m.method_id for m in methods})
            row["method_holders"] = sum(1 for a in agents if a.methods)
            row["method_adoption_rate"] = (
                row["method_holders"] / len(agents) if agents else 0.0
            )
            peer_methods = [m for m in methods if m.is_peer_acquired]
            row["method_peer_held"] = len(peer_methods)
            row["knowledge_diffusion_lag_mean"] = _safe(
                statistics.fmean, [m.acquired_step - m.origin_step for m in peer_methods]
            )
            row["hop_count_mean"] = _safe(statistics.fmean, [m.hop_count for m in peer_methods])

            # latent_capacity は積で単一スコア化しない（§10.2.2）。構成指標を別々に保存する。
            row["latent_distributed_resources"] = _safe(
                statistics.fmean, [sum(a.materials.values()) for a in agents]
            )
            row["completed_projects_total"] = sum(len(a.completed_projects) for a in agents)
            self.rows.append(row)

        # 時間正規化指標は世界全体で1系列（step 単位の観測）
        step_row = dict(base)
        step_row["population"] = "step_totals"
        step_row["time_total"] = stats.time_total
        for action, t in stats.time_by_action.items():
            step_row[f"time_{action}"] = t
            step_row[f"time_share_{action}"] = (
                t / stats.time_total if stats.time_total else 0.0
            )
        step_row["skill_gain_per_time"] = (
            stats.skill_gain_total / stats.time_total if stats.time_total else 0.0
        )
        step_row["method_self_discovery_per_time"] = (
            stats.self_discovered / stats.make_time if stats.make_time else 0.0
        )
        # C/D では定義上 0 になる。§8.4 の manipulation check を兼ねる。
        step_row["method_peer_acquisition_per_time"] = (
            stats.peer_acquired / stats.social_time if stats.social_time else 0.0
        )
        step_row["peer_acquired_count"] = stats.peer_acquired
        step_row["self_discovered_count"] = stats.self_discovered
        for reason, n in stats.rejections.items():
            step_row[f"reject_{reason}"] = n
        for action, n in stats.action_counts.items():
            step_row[f"count_{action}"] = n
        self.rows.append(step_row)

    def record_reachability(self, world) -> None:
        """10step 毎。技能・資源の変化に依存するため時系列記録を継続する（決定 P2）。"""
        g = world.graph
        th = world.cfg["stage_thresholds"]["breadth_threshold"]
        skilled = {a.id for a in world.agents.values() if max(a.skills.values()) >= th}
        row = {
            "step": world.step,
            "condition": world.cfg["condition"],
            "population": "reachability",
            "skill_reachability": _mean_hops(g, skilled),
            "resource_reachability": _mean_hops(
                g, {a.id for a in world.agents.values() if sum(a.materials.values()) > 0}
            ),
        }
        self.rows.append(row)

    def fieldnames(self) -> list[str]:
        keys: dict[str, None] = {}
        for r in self.rows:
            for k in r:
                keys[k] = None
        return list(keys)


def _mean_hops(g: nx.Graph, targets: set[str]) -> float:
    """各ノードから targets のいずれかへ到達する最短ホップ数の平均。"""
    if not targets:
        return float("inf")
    total, n = 0.0, 0
    for node in g.nodes():
        if node in targets:
            d = 0
        else:
            lengths = nx.single_source_shortest_path_length(g, node)
            reachable = [v for t, v in lengths.items() if t in targets]
            if not reachable:
                continue
            d = min(reachable)
        total += d
        n += 1
    return total / n if n else float("inf")
