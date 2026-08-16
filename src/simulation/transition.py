"""転化（Transition）の判定（M3、SPEC §20 / §21）。

【最重要】転化は**物語ではなくコードで判定する**。
LLM の文章や「それらしさ」を根拠にしない。閾値化された4条件のみで判定し、
閾値はすべて config 管理とする。

  community_supply_share  コミュニティ供給が全体供給に占める割合
  active_supplier_count   その step に供給した Agent 数
  supply_duration         供給が連続している step 数
  coordination_edges      協調関係にある Agent ペア数

4条件すべてを満たした最初の step を転化成立とする。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TransitionJudge:
    """閾値はすべて config 由来。コード内にハードコードしない。"""

    community_supply_share: float
    active_supplier_count: int
    supply_duration_steps: int
    coordination_edges: int

    transitioned_at: int | None = None
    history: list[dict] = field(default_factory=list)

    @classmethod
    def from_config(cls, d: dict) -> "TransitionJudge":
        return cls(
            community_supply_share=float(d["community_supply_share"]),
            active_supplier_count=int(d["active_supplier_count"]),
            supply_duration_steps=int(d["supply_duration_steps"]),
            coordination_edges=int(d["coordination_edges"]),
        )

    def evaluate(self, step: int, ledger, coordination_edges: int) -> dict:
        """1 step 分の判定。満たした条件を個別に記録する。

        「どの条件がボトルネックだったか」が後から分かるよう、
        合否だけでなく各条件の実測値を残す。
        """
        share = ledger.community_supply_share()
        suppliers = ledger.active_supplier_count()
        duration = ledger.supply_duration()

        checks = {
            "community_supply_share": share >= self.community_supply_share,
            "active_supplier_count": suppliers >= self.active_supplier_count,
            "supply_duration": duration >= self.supply_duration_steps,
            "coordination_edges": coordination_edges >= self.coordination_edges,
        }
        row = {
            "step": step,
            "share": round(share, 6),
            "suppliers": suppliers,
            "duration": duration,
            "coordination_edges": coordination_edges,
            **{f"met_{k}": v for k, v in checks.items()},
            "all_met": all(checks.values()),
        }
        if row["all_met"] and self.transitioned_at is None:
            self.transitioned_at = step
        self.history.append(row)
        return row

    def emergence_level(self, ledger, any_modify: bool, any_peer_method: bool) -> str:
        """Emergence Level E0〜E4 の暫定的な操作的定義（docs/REVIEW.md §12.3 R2）。

        ★この定義は未承認の暫定案である★ DESIGN_M1 §18 R2 で「M3 着手前に決定が必要」
        とされたまま決着していない。結果の主張には使わず、記録のみに用いる。
        """
        if self.transitioned_at is not None:
            return "E4" if ledger.supply_duration() >= self.supply_duration_steps else "E3"
        if ledger.community_total > 0:
            return "E2"
        if any_modify or any_peer_method:
            return "E1"
        return "E0"

    def summary(self) -> dict:
        return {
            "transitioned": self.transitioned_at is not None,
            "transition_step": self.transitioned_at,
            "thresholds": {
                "community_supply_share": self.community_supply_share,
                "active_supplier_count": self.active_supplier_count,
                "supply_duration_steps": self.supply_duration_steps,
                "coordination_edges": self.coordination_edges,
            },
        }


def reconfiguration_time(onset_step: int, ledger, judge: TransitionJudge) -> dict:
    """再構成時間（SPEC §22 Reconfiguration Time）。

    未知の需要発生から、新しい供給構造が成立するまでの時間。
    成立しなかった場合は None を返す（打ち切りであり、失敗ではない）。
    """
    to_first = (
        ledger.first_supply_step - onset_step if ledger.first_supply_step is not None else None
    )
    to_transition = (
        judge.transitioned_at - onset_step if judge.transitioned_at is not None else None
    )
    return {
        "onset_step": onset_step,
        "steps_to_first_community_supply": to_first,
        "steps_to_transition": to_transition,
    }
