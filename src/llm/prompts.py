"""LLM プロンプトと structured output スキーマ（M2）。

【絶対ルール】このモジュールが生成する文字列は Agent-facing である。
禁止語（コスプレ / PPE / マスク / COVID / 医療 等）を一切含めてはならない。
識別子は中立コード（skill_N / mat_N / asset_N / proj_N）のみを使う。
tests/test_no_answer_leak.py と tests/test_llm_contract.py が機械的に検証する。

【答えを与えない】プロンプトに「何を作るべきか」「誰を助けるべきか」を書かない。
Agent が受け取るのは自分の局所状態と一般化された選択肢だけである（SPEC §14）。
"""

from __future__ import annotations

from src.agents.observation import Observation

PROMPT_VERSION = "m2-minimal-v1"

# system プロンプト。世界の設定・目的・答えを一切含まない。
SYSTEM_PROMPT = """\
You are one agent in a simulation. Decide what to do next this step.

You can see only your own state and information that reached you locally.
You cannot see the world, other agents' true values, or the simulation's purpose.

Choose from these generalized actions:
- observe: look at one neighbour to update your belief about their skills
- ask: ask one neighbour about a skill you believe they are better at
- practice: practise one skill on your own
- make: attempt to build one item from the catalogue
- share: pass one method you hold to your neighbours
- idle: do nothing

Rules:
- Decide only what you intend. You do not decide quantities, time cost, or whether
  an attempt succeeds. Those are determined outside your control.
- Return several intents ordered by how much you want them, most wanted first.
  Some may be rejected; the next ones are then considered.
- Refer to items only by the identifiers given to you.
"""


def _fmt_float(x: float) -> str:
    return f"{x:.3f}"


def build_user_prompt(obs: Observation) -> str:
    """Observation から user プロンプトを組み立てる。

    Observation 以外を参照してはならない（SPEC §14 Information Locality）。
    build_observation() が唯一の遮断点であるため、ここで world を触ると台無しになる。
    """
    skills = ", ".join(f"{k}={_fmt_float(v)}" for k, v in sorted(obs.self_skills.items()))
    assets = ", ".join(f"{k}={v}" for k, v in sorted(obs.self_assets.items()))
    materials = ", ".join(f"{k}={_fmt_float(v)}" for k, v in sorted(obs.self_materials.items()))

    catalogue = []
    for p in obs.project_catalog:
        cost = ", ".join(f"{m}:{_fmt_float(v)}" for m, v in sorted(p.material_cost.items()))
        catalogue.append(
            f"  {p.project_id}: needs skill {p.primary_skill}, "
            f"difficulty {_fmt_float(p.base_difficulty)}, "
            f"equipment {p.required_asset or 'none'}, materials {{{cost}}}"
        )

    methods = (
        ", ".join(sorted(m.project_id for m in obs.self_methods)) if obs.self_methods else "none"
    )

    beliefs = []
    for nid in sorted(obs.perceived_neighbor_skills):
        est = obs.perceived_neighbor_skills[nid]
        top = ", ".join(f"{s}~{_fmt_float(v.estimate)}" for s, v in sorted(est.items()))
        beliefs.append(f"  {nid}: {top}")

    return f"""\
Step {obs.step}. You are {obs.self_id}.

Your skills: {skills}
Your equipment: {assets}
Your materials: {materials}
Methods you hold (by item they help with): {methods}
Time available this step: {_fmt_float(obs.self_time_budget)}

Your dispositions (0..1):
  engagement={_fmt_float(obs.self_participation_level)}
  sharing={_fmt_float(obs.self_sharing_tendency)}
  imitation={_fmt_float(obs.self_imitation_tendency)}
  helping={_fmt_float(obs.self_helping_norm)}

Item catalogue:
{chr(10).join(catalogue)}

Neighbours you know: {', '.join(obs.neighbors) if obs.neighbors else 'none'}
What you believe about their skills:
{chr(10).join(beliefs) if beliefs else '  (nothing yet)'}

Messages that reached you this step: {len(obs.inbox)}

Return your intents, most wanted first.
"""


# structured output スキーマ。Intent と 1:1 に対応する（決定 X1）。
# 【構造的制約】数量フィールドを持たせない。生産数量・金額・消費時間量は含めない。
INTENT_LIST_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "intents": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["observe", "ask", "practice", "make", "share", "idle"],
                    },
                    "target_agent_id": {"type": ["string", "null"]},
                    "target_project_id": {"type": ["string", "null"]},
                    "target_skill_id": {"type": ["string", "null"]},
                    "target_method_id": {"type": ["string", "null"]},
                    "reason": {"type": "string"},
                },
                "required": [
                    "action",
                    "target_agent_id",
                    "target_project_id",
                    "target_skill_id",
                    "target_method_id",
                    "reason",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["intents"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# M3 ショック相
# ---------------------------------------------------------------------------

SHOCK_SYSTEM_PROMPT = """\
You are one agent in a simulation. Decide what to do next this step.

You can see only your own state and information that reached you locally.
You cannot see the world, other agents' true values, or the simulation's purpose.

A requirement has appeared. It is stated only as minimum levels on abstract
attributes of an item. Nothing tells you what the item is for, and you should not
assume. Items you already know how to build have their own attribute values.

Actions available:
- observe: look at one neighbour to update your belief about their skills
- ask: ask one neighbour about a skill you believe they are better at
- practice: practise one skill on your own
- modify: shift one attribute of an item you know how to build
    (target_project_id = the item, target_skill_id = the attribute name, e.g. attr_0)
- make: attempt to build one item, as you have currently shaped it
- share: pass one method you hold to your neighbours
- propose: propose working together on one item (target_project_id)
- join: join a neighbour's proposal (target_agent_id)
- idle: do nothing

Rules:
- Decide only what you intend. You do not decide quantities, time cost, or whether
  an attempt succeeds, or whether what you build meets the requirement.
  Those are determined outside your control.
- Modifying an item makes it harder to build. There is no free change.
- Return several intents ordered by how much you want them, most wanted first.
- Refer to items and attributes only by the identifiers given to you.
"""


def build_shock_user_prompt(obs, required, shortfalls: dict, state=None) -> str:
    """ショック相の user プロンプト。

    Agent が受け取るのは「要求されている属性の下限」と「自分が作れる物の属性が
    どれだけ足りないか」だけである。**何を作るべきかは書かない**（SPEC §8）。
    """
    base = build_user_prompt(obs)

    req = ", ".join(f"{a} >= {v:.2f}" for a, v in sorted(required.thresholds.items()))
    lines = []
    for p in obs.project_catalog:
        gap = shortfalls.get(p.project_id, {})
        if not gap:
            continue
        missing = ", ".join(f"{a}: short by {v:.2f}" for a, v in sorted(gap.items()) if v > 0)
        lines.append(f"  {p.project_id}: {missing or 'meets the requirement as-is'}")

    return f"""{base}
A requirement is currently unmet. Minimum attribute levels required: {req}

How far each item you know is from meeting it, as you have currently shaped it:
{chr(10).join(lines) if lines else '  (none)'}

You may shift an attribute of an item with `modify`, then `make` it.
Return your intents, most wanted first.
"""


# ショック相の structured output スキーマ。M2 のスキーマに再構成アクションを足す。
# 数量フィールドを持たせない制約は変わらない（決定 X1）。
import copy as _copy

SHOCK_INTENT_LIST_SCHEMA: dict = _copy.deepcopy(INTENT_LIST_SCHEMA)
SHOCK_INTENT_LIST_SCHEMA["properties"]["intents"]["items"]["properties"]["action"]["enum"] = [
    "observe", "ask", "practice", "make", "share", "idle", "modify", "propose", "join",
]
