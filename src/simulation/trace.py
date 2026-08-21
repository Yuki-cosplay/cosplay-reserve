"""蓄積相（M1）の per-agent / per-step trace 記録（**観測専用**）。

【このモジュールの立場】
これは**可視化のための観測装置であり、シミュレーションの一部ではない。**
`world.trace` が None のとき（=既定・全実験）、`src/world/step.py` の hook は
一切呼ばれず、実行は logging 追加前と bit 単位で同一である。

【絶対に守る規約】
1. **RNG を一切呼ばない。** 本モジュールに `rng` は import されない
2. **agent / world の状態を書き換えない。** 読み取りのみ
3. **mutable object の参照を保持しない。** 記録時点の値を必ずコピーする
   （`dict(...)` / `float(...)` / `sorted(...)` で即時に値へ落とす）
4. **新しい行動概念を作らない。** action 名は `ActionType` の語彙のみ
5. **iteration order を変えない。** hook は既存ループの内側で「呼ばれる側」に徹する

【なぜ参照コピーが必須か】
`agent.skills` は step ごとに `apply_skill_gain` / `decay_skills` が破壊的に更新する。
参照を保持すると、記録済みのはずの値が後から書き換わり、
**動画が実際の履歴と食い違う**（決定論の問題ではなく記録の正確性の問題）。
"""

from __future__ import annotations

import json
from pathlib import Path

# 既存の action 語彙。これ以外を trace に入れてはならない（動画用の新概念禁止）。
from src.common.types import ActionType

ALLOWED_ACTIONS: frozenset[str] = frozenset(a.value for a in ActionType)


class TraceRecorder:
    """per-agent / per-step の観測記録。追記のみ。"""

    def __init__(self) -> None:
        self.actions: list[dict] = []      # 行動イベント（解決順）
        self.snapshots: list[dict] = []    # step 終了時の per-agent 状態
        self.method_events: list[dict] = []  # method 取得（自己発見 / peer 受容）

    # --- hook: 行動が解決した直後（_resolve 内）-----------------------------
    def on_action(
        self,
        step: int,
        agent,
        action: str,
        *,
        target_agent_id: str | None = None,
        target_skill_id: str | None = None,
        target_project_id: str | None = None,
        target_method_id: str | None = None,
        make_success: bool | None = None,
        completed_project_added: bool = False,
    ) -> None:
        """action は既存語彙のみ。target は実在する場合のみ入れる。"""
        assert action in ALLOWED_ACTIONS, f"未知の action: {action}"
        rec = {
            "step": int(step),
            "agent_id": str(agent.id),
            "is_participant": bool(agent.is_participant),
            "action": str(action),
            # ★値のコピー。参照を持たない★
            "skills_after": {k: float(v) for k, v in sorted(agent.skills.items())},
            "maker_stage": str(agent.maker_stage.value),
        }
        # target は「実際に存在する場合のみ」記録する（None を並べない）
        if target_agent_id is not None:
            rec["target_agent_id"] = str(target_agent_id)
        if target_skill_id is not None:
            rec["target_skill_id"] = str(target_skill_id)
        if target_project_id is not None:
            rec["target_project_id"] = str(target_project_id)
        if target_method_id is not None:
            rec["target_method_id"] = str(target_method_id)
        if make_success is not None:
            rec["make_success"] = bool(make_success)
        if completed_project_added:
            rec["completed_project_added"] = True
            rec["completed_projects_total"] = int(len(agent.completed_projects))
        self.actions.append(rec)

    # --- hook: method 取得が発生したとき ------------------------------------
    def on_method(self, step: int, agent, method_id: str, origin: str,
                  from_agent_id: str | None = None) -> None:
        """origin は 'self_discovery' または 'peer_acquisition'。"""
        assert origin in ("self_discovery", "peer_acquisition")
        rec = {
            "step": int(step),
            "agent_id": str(agent.id),
            "method_id": str(method_id),
            "origin": origin,
            "methods_total": int(len(agent.methods)),
        }
        if from_agent_id is not None:
            rec["from_agent_id"] = str(from_agent_id)
        self.method_events.append(rec)

    # --- hook: step 終了時（decay / stage 更新の後）-------------------------
    def on_step_end(self, step: int, agents: dict) -> None:
        for aid in sorted(agents):
            a = agents[aid]
            self.snapshots.append({
                "step": int(step),
                "agent_id": str(a.id),
                "is_participant": bool(a.is_participant),
                # ★すべて値のコピー★
                "skills": {k: float(v) for k, v in sorted(a.skills.items())},
                "maker_stage": str(a.maker_stage.value),
                "completed_projects_total": int(len(a.completed_projects)),
                "methods_total": int(len(a.methods)),
            })

    # --- 書き出し -----------------------------------------------------------
    def write(self, out_dir: Path, meta: dict) -> None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        for name, rows in (("actions", self.actions),
                           ("snapshots", self.snapshots),
                           ("method_events", self.method_events)):
            with open(out_dir / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
