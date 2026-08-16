"""RNG spawn 規約（docs/DESIGN_M1.md §12.1、決定 W4）。

T1（決定論性）と T5（条件間不変）の両方がこの規約に依存する。
規約が曖昧なまま実装すると、後から「なぜ条件間で初期状態がずれるのか」を
追跡できなくなる。

第1階層の spawn 順序は固定である:

    0: agent_init        Agent 初期状態の生成、および is_participant の割り当て
    1: project_catalog   M1 では固定値のため未使用。番号は予約する（決定 W1/P4）
    2: network           structured topology の生成と rewiring
    3: simulation        step ループ内の全確率的判定

index 1 を空けたまま予約する理由: M1 でカタログを固定値にしたからといって
番号を詰めると、将来カタログを生成方式に変えたときに network 以降の全ストリームが
ずれ、過去の run が再現できなくなる。
"""

from __future__ import annotations

import numpy as np

# 第1階層の spawn 順序。この並びを変更してはならない（過去 run の再現性が壊れる）。
ROOT_STREAM_ORDER: tuple[str, ...] = (
    "agent_init",
    "project_catalog",
    "network",
    "simulation",
    # index 4: M3 のショック対象 Agent 選出専用（P0修正 2026-08-16）。
    # 【重要】**末尾への追加**であるため index 0〜3 の子ストリームは一切変化しない
    # （SeedSequence.spawn は spawn_key=(i,) で決まるため、spawn(5) の先頭4件は
    #   spawn(4) と完全に同一）。既存 run の再現性は保たれる。
    # 条件（A/B/C/D）から独立させるために専用ストリームを設ける。
    "shock_agents",
)


class RngStreams:
    """master_seed から派生した第1階層ストリームの束。

    追加規約（§12.1）:
    - agent_init は1回の spawn で全Agentを生成する。Agent ごとに spawn しない。
      理由: Agent 数を変えても他のストリームがずれないようにするため。
    - simulation ストリームは step ごとに spawn せず、単一のストリームを
      step 順・agent_id 昇順で消費する。
    - 条件 A/B/C/D で agent_init ストリームの消費が完全に同一になること。
      条件によって消費が変わってよいのは network ストリームのみ。
    """

    def __init__(self, master_seed: int):
        self.master_seed = int(master_seed)
        root = np.random.SeedSequence(self.master_seed)
        children = root.spawn(len(ROOT_STREAM_ORDER))
        self._seq = dict(zip(ROOT_STREAM_ORDER, children))
        self._rng = {name: np.random.default_rng(s) for name, s in self._seq.items()}

    def __getitem__(self, name: str) -> np.random.Generator:
        if name not in self._rng:
            raise KeyError(
                f"unknown stream {name!r}; must be one of {ROOT_STREAM_ORDER}"
            )
        return self._rng[name]

    def legacy_seed(self, name: str) -> int:
        """networkx のように int seed しか受け取れない API へ渡すための値。

        当該ストリームから決定論的に導出するため、ストリーム分離の契約は保たれる。
        """
        return int(self[name].integers(0, 2**31 - 1))


def make_streams(master_seed: int) -> RngStreams:
    return RngStreams(master_seed)
