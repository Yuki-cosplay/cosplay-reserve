"""需要（RequiredItem）と供給の記帳（M3、SPEC §17 / §18）。

【最重要】RequiredItem は**抽象化された仕様であり、名称ではない**（SPEC §18）。
需要は属性ベクトル attr_0..attr_6 の下限要求として表現され、
「何を作れば満たされるか」はコードが属性の充足判定で決める。
Agent へ品目名を渡さない。名称照合は一切行わない（docs/REVIEW.md I2）。

Hospital 等は「これを作れ」ではなく「この要求仕様を満たす物資が不足している」
という需要を世界へ発生させる。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from src.common.types import AttributeVector


@dataclass(frozen=True)
class RequiredItem:
    """要求仕様。属性の下限しきい値と必要総量のみを持つ。

    thresholds に現れない属性は「問われていない」= 何でもよい。
    """

    thresholds: dict[str, float]
    unit_demand: float

    @classmethod
    def from_config(cls, d: dict) -> "RequiredItem":
        return cls(
            thresholds={k: float(v) for k, v in d["thresholds"].items()},
            unit_demand=float(d["unit_demand"]),
        )

    def satisfied_by(self, profile: AttributeVector) -> bool:
        """属性の充足判定。**これが唯一の判定経路である。**

        品目名・project_id・技能名では判定しない（名称照合の禁止）。
        """
        return all(
            getattr(profile, attr) >= threshold for attr, threshold in self.thresholds.items()
        )

    def shortfall(self, profile: AttributeVector) -> dict[str, float]:
        """どの属性がどれだけ足りないか。Agent へ渡してよい（局所情報）。"""
        return {
            attr: round(max(0.0, threshold - getattr(profile, attr)), 4)
            for attr, threshold in self.thresholds.items()
        }


def apply_shifts(base: AttributeVector, shifts: dict[str, float]) -> AttributeVector:
    """変形（modify）で属性を移動させた結果を返す。

    既存の制作物を別用途へ振り向ける経路そのもの。属性は 0..1 に丸める。
    """
    values = {f.name: getattr(base, f.name) for f in dataclasses.fields(base)}
    for attr, delta in shifts.items():
        values[attr] = min(1.0, max(0.0, values[attr] + delta))
    return AttributeVector(**values)


def external_reference_supply_per_step(cfg: dict, shock_agent_count: int) -> float:
    """External Supply Parity Reference（D5、人間確定 2026-08-16）。

    ★現実の外部メーカー能力の実証値ではない★
    community supply を無次元比較するための正規化基準である。
    「Manufacturer 能力の推定値」と呼んではならない。

        = (time_budget / action_time_cost.make) × shock_agent_count

    shock 対象コミュニティ全員が 1 step の時間予算をすべて make へ投入した場合の
    理論最大供給能力と同量を、比較用 reference capacity とする。
    """
    time_budget = float(cfg["agent_init"]["traits"]["time_budget"]["value"])
    make_cost = float(cfg["action_time_cost"]["make"])
    max_make_per_agent = time_budget // make_cost
    return max_make_per_agent * shock_agent_count


@dataclass
class SupplyLedger:
    """供給の記帳（SPEC §22）。転化判定はここではなく transition.py が行う。

    baseline_per_step は External Supply Parity Reference（D5）。
    実証的な外部供給能力ではなく正規化基準である。
    """

    baseline_per_step: float
    community_total: float = 0.0
    baseline_total: float = 0.0
    per_step_community: list[float] = field(default_factory=list)
    suppliers_per_step: list[set[str]] = field(default_factory=list)
    first_supply_step: int | None = None

    def start_step(self) -> None:
        self.per_step_community.append(0.0)
        self.suppliers_per_step.append(set())
        self.baseline_total += self.baseline_per_step

    def record_supply(self, agent_id: str, units: float, step: int) -> None:
        self.per_step_community[-1] += units
        self.suppliers_per_step[-1].add(agent_id)
        self.community_total += units
        if self.first_supply_step is None:
            self.first_supply_step = step

    def community_supply_share(self) -> float:
        total = self.community_total + self.baseline_total
        return self.community_total / total if total > 0 else 0.0

    def active_supplier_count(self) -> int:
        return len(self.suppliers_per_step[-1]) if self.suppliers_per_step else 0

    def supply_duration(self) -> int:
        """直近まで連続して供給が発生している step 数。"""
        n = 0
        for units in reversed(self.per_step_community):
            if units <= 0:
                break
            n += 1
        return n
