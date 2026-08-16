"""T2: Agent-facing answer leak protection。

★必須性質: Agent-facing answer leak protection★

検査対象は §3.0.1 で確定した Agent-facing strings のみ:
  - Action 名
  - Agent へ渡る Item / Material / Skill / Asset / Project の identifier
  - Observation 上に現れる文字列
  - Agent memory へ格納される文字列
  （M2 以降は system/user prompt も対象）

検査対象外（researcher-facing）:
  README / RESULTS.md / SPEC.md / docs/ / config_resolved.yaml / config のキー名 /
  researcher-facing logs / コードコメント・docstring
"""

import dataclasses
from pathlib import Path

import pytest

from src.agents.observation import build_observation
from src.common.types import ActionType
from src.world.world import build_world

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"

# CLAUDE.md 絶対ルールの禁止語。英語表記も含める。
FORBIDDEN_TERMS = (
    "コスプレ",
    "cosplay",
    "ppe",
    "マスク",
    "mask",
    "covid",
    "医療",
    "medical",
    "sewing",
    "縫製",
    "3d_print",
    "cad",
)


def _assert_clean(text: str, where: str) -> None:
    low = str(text).lower()
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in low, f"{where} に禁止語 {term!r} が含まれる: {text!r}"


@pytest.fixture(scope="module")
def world():
    return build_world(CONFIG_DIR / "condition_a.yaml", seed=42)


def test_action_names_are_generalized():
    """答えを含む Action（make_ppe / make_mask 等）が存在しないこと。"""
    for a in ActionType:
        _assert_clean(a.value, "ActionType")
    assert "make" in {a.value for a in ActionType}, "一般化された make が存在しない"


def test_identifiers_are_neutral_code_names(world):
    ids = world.id_registry
    for group, prefix in (
        (ids.skill_ids, "skill_"),
        (ids.material_ids, "mat_"),
        (ids.asset_ids, "asset_"),
        (ids.project_ids, "proj_"),
    ):
        for identifier in group:
            _assert_clean(identifier, "IdRegistry")
            assert identifier.startswith(prefix), f"{identifier} が中立コード表記でない"
            assert identifier[len(prefix) :].isdigit(), f"{identifier} に意味が付いている"


def test_project_fields_reference_only_neutral_ids(world):
    for p in world.projects:
        _assert_clean(p.project_id, "Project.project_id")
        _assert_clean(p.primary_skill, "Project.primary_skill")
        if p.required_asset:
            _assert_clean(p.required_asset, "Project.required_asset")
        for m in p.material_cost:
            _assert_clean(m, "Project.material_cost")


def test_observation_strings_are_clean(world):
    """Observation 上に現れる全文字列が禁止語を含まないこと。"""
    for agent in world.agents.values():
        obs = build_observation(world, agent)
        for f in dataclasses.fields(obs):
            value = getattr(obs, f.name)
            if isinstance(value, str):
                _assert_clean(value, f"Observation.{f.name}")
            elif isinstance(value, dict):
                for k in value:
                    _assert_clean(k, f"Observation.{f.name} key")
            elif isinstance(value, tuple):
                for v in value:
                    if isinstance(v, str):
                        _assert_clean(v, f"Observation.{f.name}")


def test_attribute_vector_has_no_semantic_names(world):
    """RequiredItem の属性が attr_N のみであること（対応表は SPEC §18 のみ）。"""
    fields = {f.name for f in dataclasses.fields(world.projects[0].target_profile)}
    assert fields == {f"attr_{i}" for i in range(7)}, fields
