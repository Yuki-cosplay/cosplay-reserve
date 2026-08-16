"""World の状態（docs/DESIGN_M1.md §3.2.1）。

S1〜S4 の範囲では step ループを実装しない（S10）。ここでは Observation の
切り出しに必要な状態保持と、4条件の World 構築のみを提供する。

【重要】Agent はこの object を直接参照しない。
build_observation() だけが World から Observation を切り出す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx

from src.agents.agent import (
    Agent,
    agent_initial_states_sha256,
    build_agents,
    participant_ids_sha256,
)
from src.common.config import load_config, load_projects, validate_config
from src.common.rng import RngStreams, make_streams
from src.common.types import IdRegistry, Project
from src.culture.network import (
    build_base_graphs,
    build_edge_layers,
    cultural_edge_count,
    graph_for,
    graph_sha256,
)


@dataclass
class World:
    step: int
    cfg: dict
    id_registry: IdRegistry
    projects: tuple[Project, ...]
    agents: dict[str, Agent]
    graph: nx.Graph
    rng: RngStreams
    metrics: object | None = None
    peer_learning_enabled: bool = True

    # 再現性メタデータ（§10.3）。S12 で metadata.json へ書き出す。
    provenance: dict = field(default_factory=dict)


def build_world(condition_path: str | Path, seed: int | None = None) -> World:
    """条件別 config から World を1つ構築する。

    順序は §12.1 の spawn 規約に従う:
      agent_init（Agent 生成 + is_participant 割り当て）-> network（グラフ生成）
    Agent 生成は network 構築より前に完了する（§15.1 要件5）。
    """
    cfg = load_config(condition_path)
    if seed is not None:
        cfg["run"]["seed"] = int(seed)

    ids = validate_config(cfg)
    projects = load_projects(cfg)
    streams = make_streams(cfg["run"]["seed"])

    # --- spawn 0: agent_init ---
    agents = build_agents(cfg, ids, streams["agent_init"])
    pre_hash = agent_initial_states_sha256(agents)

    # --- spawn 2: network ---
    base_graphs = build_base_graphs(agents, cfg, streams["network"])
    graph = graph_for(cfg["condition"], base_graphs, agents)
    build_edge_layers(graph, agents)

    # M1 では trust は固定値。更新式は実装しない（trust 最終仕様）。
    trust_fixed = float(cfg["agent_init"]["traits"]["trust_fixed"]["value"])
    for a in agents.values():
        a.trust = {n: trust_fixed for n in a.known_agents}

    world = World(
        step=0,
        cfg=cfg,
        id_registry=ids,
        projects=projects,
        agents=agents,
        graph=graph,
        rng=streams,
        peer_learning_enabled=bool(cfg["peer_learning_enabled"]),
        provenance={
            "condition": cfg["condition"],
            "topology": cfg["topology"],
            "peer_learning_enabled": bool(cfg["peer_learning_enabled"]),
            "random_seed": cfg["run"]["seed"],
            "agent_initial_states_sha256": pre_hash,
            "participant_ids_sha256": participant_ids_sha256(agents),
            "base_graph_sha256": graph_sha256(graph),
            "cultural_edge_count": cultural_edge_count(graph, agents),
            "network_density": nx.density(graph),
        },
    )
    return world


def build_all_conditions(config_dir: str | Path, seed: int | None = None) -> dict[str, World]:
    """A/B/C/D の World をまとめて構築する（テスト用ヘルパ）。"""
    config_dir = Path(config_dir)
    return {
        c: build_world(config_dir / f"condition_{c.lower()}.yaml", seed=seed)
        for c in ("A", "B", "C", "D")
    }
