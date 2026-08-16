"""LLM クライアントと CostGuard（M2 最小構成）。

M2 の最低達成条件は4点のみ:
  1. LLM 呼び出しが成功する
  2. structured output が Intent へ parse される
  3. Validator が feasibility を判定する（既存の validate() を再利用）
  4. API cost ceiling で停止できる

プロンプト最適化・キャッシュ・複数モデル振り分けは P2 とし、時間が余った場合のみ実装する。

【CLAUDE.md 絶対ルール】API費用の上限を設定し、超えたら実行を止める仕組みを必ず入れる。
CostGuard がそれであり、上限超過時は BudgetExceeded を送出して run を止める。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from src.common.types import ActionType, Intent
from src.llm.prompts import (
    INTENT_LIST_SCHEMA,
    PROMPT_VERSION,
    SHOCK_INTENT_LIST_SCHEMA,
    SHOCK_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_shock_user_prompt,
    build_user_prompt,
)


class BudgetExceeded(RuntimeError):
    """API 費用が config の上限に達した。run を停止する。"""


@dataclass
class CostGuard:
    """累積コストのハード上限（SPEC §24、CLAUDE.md 絶対ルール）。

    上限に達した時点で以降の呼び出しを拒否する。呼び出し「後」ではなく
    呼び出し「前」に判定するため、上限を超えて課金され続けることがない。
    """

    max_usd: float
    input_usd_per_mtok: float
    output_usd_per_mtok: float

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    spent_usd: float = 0.0
    per_call: list[dict] = field(default_factory=list)

    def check_before_call(self) -> None:
        if self.spent_usd >= self.max_usd:
            raise BudgetExceeded(
                f"API費用が上限に達しました: ${self.spent_usd:.4f} >= ${self.max_usd:.4f} "
                f"({self.calls} calls). run を停止します。"
            )

    def record(self, usage) -> float:
        in_tok = int(getattr(usage, "input_tokens", 0) or 0)
        out_tok = int(getattr(usage, "output_tokens", 0) or 0)
        cost = (
            in_tok / 1_000_000 * self.input_usd_per_mtok
            + out_tok / 1_000_000 * self.output_usd_per_mtok
        )
        self.calls += 1
        self.input_tokens += in_tok
        self.output_tokens += out_tok
        self.spent_usd += cost
        self.per_call.append(
            {"call": self.calls, "input_tokens": in_tok, "output_tokens": out_tok, "usd": cost}
        )
        return cost

    def summary(self) -> dict:
        return {
            "llm_calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "spent_usd": round(self.spent_usd, 6),
            "max_usd": self.max_usd,
            "budget_exhausted": self.spent_usd >= self.max_usd,
        }


def parse_intents(payload: str, max_intents: int) -> list[Intent]:
    """structured output の JSON テキストを Intent 列へ変換する（M2 条件2）。

    未知の action や余分なフィールドは受け付けない。Intent には数量フィールドが
    存在しないため、LLM が数量を宣言する経路が型レベルで存在しない（決定 X1）。
    """
    data = json.loads(payload)
    out: list[Intent] = []
    for raw in data["intents"][:max_intents]:
        out.append(
            Intent(
                action=ActionType(raw["action"]),
                target_agent_id=raw.get("target_agent_id"),
                target_project_id=raw.get("target_project_id"),
                target_skill_id=raw.get("target_skill_id"),
                target_method_id=raw.get("target_method_id"),
                reason=raw.get("reason", ""),
            )
        )
    return out


class LLMDecider:
    """decide() を LLM 実装に差し替えるための最小クライアント（§19 引き継ぎ設計）。

    シグネチャは M1 の decide() と同一に保つ。Validator（validate()）は M1 の
    実装をそのまま使うため、feasibility 判定は世界側コードのままである。
    """

    def __init__(self, cfg: dict, client: anthropic.Anthropic | None = None):
        llm = cfg["llm"]
        self.cfg = cfg
        self.model = llm["model"]
        self.max_tokens = llm["max_tokens"]
        self.effort = llm["effort"]
        self.max_intents = cfg["time"]["max_actions_per_step"]
        self.guard = CostGuard(
            max_usd=llm["max_usd"],
            input_usd_per_mtok=llm["input_usd_per_mtok"],
            output_usd_per_mtok=llm["output_usd_per_mtok"],
        )
        self._client = client or anthropic.Anthropic()

    def decide(self, obs, rng=None) -> list[Intent]:
        """M2 条件1+2。rng は未使用（LLM の非決定性は seed で制御できない — SPEC §23）。"""
        return self._call(SYSTEM_PROMPT, build_user_prompt(obs), INTENT_LIST_SCHEMA)

    def decide_shock(self, obs, required, shortfalls: dict) -> list[Intent]:
        """M3 ショック相。需要は属性の下限としてのみ渡す（SPEC §18）。"""
        return self._call(
            SHOCK_SYSTEM_PROMPT,
            build_shock_user_prompt(obs, required, shortfalls),
            SHOCK_INTENT_LIST_SCHEMA,
        )

    def _call(self, system: str, user: str, schema: dict) -> list[Intent]:
        self.guard.check_before_call()

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        )
        self.guard.record(response.usage)

        if response.stop_reason == "refusal":
            # 拒否された場合は空の Intent 列を返す。世界は idle として扱う。
            return []

        text = next(b.text for b in response.content if b.type == "text")
        return parse_intents(text, self.max_intents)

    def provenance(self) -> dict:
        """metadata.json へ記録する再現性メタデータ（SPEC §23）。"""
        return {
            "llm": self.model,
            "prompt_version": PROMPT_VERSION,
            "effort": self.effort,
            **self.guard.summary(),
        }
