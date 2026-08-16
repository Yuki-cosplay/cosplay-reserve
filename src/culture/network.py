"""4条件のネットワーク構築（docs/DESIGN_M1.md §7）。

【最重要】base graph を1回だけ生成し、deep copy で配布する。
条件ごとに生成し直してはならない。生成の乱数差で A/C または B/D に差が出ることを
SPEC §19 が明示的に禁止している。

    A と C は完全に同じ structured graph 由来
    B と D は完全に同じ rewired graph 由来

条件が変えるのは「どちらの base graph を使うか」と peer_learning_enabled の
2点だけである。
"""

from __future__ import annotations

import copy

import networkx as nx
import numpy as np

from src.agents.agent import Agent
from src.common.io import sha256_of

# 条件 -> (topology, peer_learning_enabled)
CONDITIONS: dict[str, tuple[str, bool]] = {
    "A": ("structured", True),
    "B": ("rewired", True),
    "C": ("structured", False),
    "D": ("rewired", False),
}


def _node_index(agent_id: str) -> int:
    return int(agent_id.split("_")[1])


def _skill_scalar(agent: Agent) -> float:
    """assortativity 計算に使う「技能水準」のスカラー。

    ★暫定解釈（設計書に定義がない）★ 6技能の平均を用いる。
    docs/DESIGN_M1.md §7 は add_skill_assortativity の対象を
    「技能の近い者同士」とだけ記しており、複数技能をどうスカラー化するかを
    定めていない。max を使うか mean を使うかで structured topology の
    性質が変わるため、人間の確認が必要（報告済み）。
    """
    return float(np.mean(list(agent.skills.values())))


def _assortativity_coefficient(g: nx.Graph, skill: dict[int, float]) -> float:
    """エッジ両端の技能スカラーの Pearson 相関。"""
    if g.number_of_edges() == 0:
        return 0.0
    xs, ys = [], []
    for u, v in g.edges():
        # 無向グラフなので両向きを入れて対称化する
        xs.extend((skill[u], skill[v]))
        ys.extend((skill[v], skill[u]))
    if np.std(xs) == 0 or np.std(ys) == 0:
        return 0.0
    return float(np.corrcoef(xs, ys)[0, 1])


def add_skill_assortativity(
    g: nx.Graph, skill: dict[int, float], target: float, swap_budget: int,
    rng: np.random.Generator,
) -> nx.Graph:
    """技能の近い者同士が繋がる方向へ、次数保存スワップを繰り返す（決定 W5）。

    契約（§7）:
      - 入力グラフの次数分布と総エッジ数を完全に保存する
      - エッジの追加・削除は行わない
      - スワップ回数は config（network.assortativity_swaps × |E|）

    ★暫定解釈（設計書に定義がない）★
    network.assortativity（既定 0.3）を「目標 assortativity 係数」と解釈し、
    係数が目標に達した時点で早期終了する。swap_budget は打ち切り上限。
    この2パラメータの関係が設計書で定義されていないため、人間の確認が必要（報告済み）。
    """
    edges = list(g.edges())
    if len(edges) < 2:
        return g

    check_every = max(1, swap_budget // 50)
    for i in range(swap_budget):
        if i % check_every == 0:
            if _assortativity_coefficient(g, skill) >= target:
                break

        edges = list(g.edges())
        i1, i2 = rng.choice(len(edges), size=2, replace=False)
        (u, v), (x, y) = edges[int(i1)], edges[int(i2)]
        if len({u, v, x, y}) < 4:
            continue
        # 次数保存スワップ: (u,v),(x,y) -> (u,x),(v,y)
        if g.has_edge(u, x) or g.has_edge(v, y):
            continue
        before = abs(skill[u] - skill[v]) + abs(skill[x] - skill[y])
        after = abs(skill[u] - skill[x]) + abs(skill[v] - skill[y])
        if after < before:  # 技能差の合計が減る = 似た者同士が繋がる
            g.remove_edge(u, v)
            g.remove_edge(x, y)
            g.add_edge(u, x)
            g.add_edge(v, y)
    return g


def build_base_graphs(
    agents: dict[str, Agent], cfg: dict, rng: np.random.Generator
) -> dict[str, nx.Graph]:
    """topology ごとに base graph を1回だけ生成する。

    ノード番号 = リング上の位置である。participant は agent_init ストリームで
    ノード番号と無関係にランダム割り当てされているため（決定 V1）、
    リング上に分散する。
    """
    net = cfg["network"]
    n = len(agents)

    ws_seed = int(rng.integers(0, 2**31 - 1))
    structured = nx.watts_strogatz_graph(
        n=n, k=net["mean_degree"], p=net["rewire_p"], seed=ws_seed
    )

    skill = {_node_index(a.id): _skill_scalar(a) for a in agents.values()}
    structured = add_skill_assortativity(
        structured,
        skill,
        target=float(net["assortativity"]),
        swap_budget=int(net["assortativity_swaps"] * structured.number_of_edges()),
        rng=rng,
    )

    # 次数保存リワイヤリング。次数分布とエッジ数を完全に保存し、
    # 『誰と誰が繋がっているか』だけを壊す -> topology の効果を単離できる
    rewired = copy.deepcopy(structured)
    swap_seed = int(rng.integers(0, 2**31 - 1))
    nx.double_edge_swap(
        rewired,
        nswap=net["swap_multiplier"] * rewired.number_of_edges(),
        max_tries=10**7,
        seed=swap_seed,
    )
    return {"structured": structured, "rewired": rewired}


def graph_for(
    condition: str, base_graphs: dict[str, nx.Graph], agents: dict[str, Agent]
) -> nx.Graph:
    """A と C は同一の structured graph、B と D は同一の rewired graph を受け取る。

    deep copy するのは run 中の変更が他条件へ漏れないようにするためだけであり、
    構造は完全に同一である。tests/test_network_pairing.py が検証する。
    """
    topology, _ = CONDITIONS[condition]
    g = copy.deepcopy(base_graphs[topology])
    return nx.relabel_nodes(g, {i: f"agent_{i}" for i in g.nodes()}, copy=True)


def build_edge_layers(graph: nx.Graph, agents: dict[str, Agent]) -> None:
    """エッジの二層構造（§7.2）。cultural_peers は known_agents の部分集合。

    エッジ自体は削除しない。non-participant の known_agents は空にならない。
    彼らは観測され、尋ねられ、共有の宛先にもなる。運ばれないのは Method だけ。
    """
    for a in agents.values():
        a.known_agents = set(graph.neighbors(a.id))
        a.cultural_peers = {
            n for n in a.known_agents if a.is_participant and agents[n].is_participant
        }


def cultural_edge_count(graph: nx.Graph, agents: dict[str, Agent]) -> int:
    """両端が participant のエッジ数（決定 V1）。

    metadata.json に記録する。テストの合否判定には使わない（§13.2）。
    """
    return sum(
        1
        for u, v in graph.edges()
        if agents[u].is_participant and agents[v].is_participant
    )


def graph_sha256(graph: nx.Graph) -> str:
    """完全ペアリングの証拠。A と C、B と D でこの値が一致する必要がある。"""
    return sha256_of(sorted(tuple(sorted((str(u), str(v)))) for u, v in graph.edges()))
