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
    """assortativity 計算に使う「技能水準」のスカラー。**6技能の平均**（確定）。

    max を採用しない理由（DESIGN_M1 §7）:

    (a) N=40 で6技能の最大値は単一の順序統計量にすぎず、「1技能だけ高い者同士が
        繋がる」構造になる。assortativity で表現したいのは全体的な習熟度の近さである。
    (b) max_skill は judge_maker_stage() の MAKER 判定に使われている。同じ量を
        2つの異なる構成概念に流用すると、「技能水準」と「段階」の交絡を疑われる。

    平均という選択自体は設計上の任意選択である（max や合計を採ると構造が変わりうる）。
    docs/LIMITATIONS_CANDIDATES.md に記録済み。
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
      - 打ち切り上限は config（network.assortativity_swaps × |E|）

    **network.assortativity（既定 0.3）は目標係数である（確定）。**
    係数が目標に達した時点で早期終了する。固定スワップ回数にすると達成
    assortativity が seed ごとにばらつき、条件A の構造の強さが seed 依存になる。
    目標値で止める方が条件間比較が安定する。

    **打ち切り上限に達して目標未達だった場合も、再試行や上限延長はしない。**
    達成値をそのまま記録して続行する（達成値は metadata.json に保存）。
    未達を埋めるために上限を伸ばすのは、結果に合わせた調整に接近する。
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
) -> tuple[dict[str, nx.Graph], dict]:
    """topology ごとに base graph を1回だけ生成し、(graphs, stats) を返す。

    ノード番号 = リング上の位置である。participant は agent_init ストリームで
    ノード番号と無関係にランダム割り当てされているため（決定 V1）、
    リング上に分散する。

    stats には達成 assortativity（structured / rewired の両方）と目標・上限を
    含める。全 run・全条件で metadata.json に記録する義務がある。
    """
    net = cfg["network"]
    n = len(agents)

    ws_seed = int(rng.integers(0, 2**31 - 1))
    structured = nx.watts_strogatz_graph(
        n=n, k=net["mean_degree"], p=net["rewire_p"], seed=ws_seed
    )

    skill = {_node_index(a.id): _skill_scalar(a) for a in agents.values()}
    target = float(net["assortativity"])
    budget = int(net["assortativity_swaps"] * structured.number_of_edges())
    structured = add_skill_assortativity(
        structured, skill, target=target, swap_budget=budget, rng=rng
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

    achieved_structured = _assortativity_coefficient(structured, skill)
    stats = {
        "assortativity_target": target,
        "assortativity_swap_budget": budget,
        "assortativity_achieved_structured": achieved_structured,
        "assortativity_achieved_rewired": _assortativity_coefficient(rewired, skill),
        # 未達でも再試行・上限延長はせず、達成値をそのまま記録して続行する
        "assortativity_target_reached": bool(achieved_structured >= target),
    }
    return {"structured": structured, "rewired": rewired}, stats


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
