"""config のロードと起動時検証（docs/DESIGN_M1.md §14.3、決定 Z6 / W2 / V2 / V3 / P4）。

n_skills などの個数指定と、agent_init / materials / Project カタログの明示的な
キー集合は二重に結合している。片方だけを変更すると、実行の途中で KeyError に
なるか、より悪い場合は静かに一部の技能だけが初期化されないまま進む。

実行後ではなく実行前に落とす。300 run の感度分析が走り終わってから
「mat_4 だけ補充されていなかった」と気付くのが最悪の失敗であり、
それを構造的に防ぐ。
"""

from __future__ import annotations

import copy
from pathlib import Path

from src.common.io import read_yaml, sha256_of
from src.common.types import IdRegistry, Project

# 条件別 YAML が base.yaml に対して上書きしてよいキー（DESIGN_M1 §14.5）。
# 条件間の差分がこの2キー（+ 識別用の condition）だけであることが比較の妥当性の担保。
CONDITION_OVERRIDE_KEYS = frozenset({"condition", "topology", "peer_learning_enabled"})

DISTRIBUTION_TYPES = frozenset({"beta", "constant", "bernoulli", "categorical"})


class ConfigError(ValueError):
    """config の不整合。実行前に送出する。"""


def load_config(condition_path: str | Path) -> dict:
    """条件別 YAML を読み、extends を解決して検証済み config を返す。"""
    condition_path = Path(condition_path)
    raw = read_yaml(condition_path)

    base_name = raw.pop("extends", None)
    if base_name is None:
        raise ConfigError(f"{condition_path} に extends がありません")

    base = read_yaml(condition_path.parent / base_name)

    extra = set(raw) - CONDITION_OVERRIDE_KEYS
    if extra:
        raise ConfigError(
            f"条件別 YAML が上書きしてよいのは {sorted(CONDITION_OVERRIDE_KEYS)} のみです。"
            f"次のキーは base.yaml 側に置いてください: {sorted(extra)}"
        )

    cfg = copy.deepcopy(base)
    cfg.update(raw)

    validate_config(cfg)
    return cfg


def validate_config(cfg: dict) -> IdRegistry:
    """起動時検証（§14.3）。不一致があれば ConfigError を送出する。"""
    ids = IdRegistry.from_config(cfg)
    _validate_condition(cfg)
    _validate_id_sets(cfg, ids)
    _validate_distribution_types(cfg)
    _validate_projects(cfg, ids)
    return ids


def _validate_condition(cfg: dict) -> None:
    if cfg.get("condition") not in {"A", "B", "C", "D"}:
        raise ConfigError(f"condition は A/B/C/D のいずれかです: {cfg.get('condition')!r}")
    if cfg.get("topology") not in {"structured", "rewired"}:
        raise ConfigError(
            f"topology は structured / rewired のいずれかです: {cfg.get('topology')!r}"
        )
    if not isinstance(cfg.get("peer_learning_enabled"), bool):
        raise ConfigError("peer_learning_enabled は bool である必要があります")


def _require_key_set(actual, expected: tuple[str, ...], where: str) -> None:
    if set(actual) != set(expected):
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        raise ConfigError(
            f"{where} のキー集合が IdRegistry と一致しません "
            f"(不足={missing}, 余分={unexpected})"
        )


def _validate_id_sets(cfg: dict, ids: IdRegistry) -> None:
    init = cfg["agent_init"]
    _require_key_set(init["skills"], ids.skill_ids, "agent_init.skills")
    _require_key_set(init["assets"], ids.asset_ids, "agent_init.assets")
    for key in ("initial", "inventory_cap", "replenish_rate"):
        _require_key_set(cfg["materials"][key], ids.material_ids, f"materials.{key}")


def _validate_spec(spec, where: str, allowed: set[str]) -> None:
    if not isinstance(spec, dict):
        raise ConfigError(f"{where} は dict である必要があります（決定 V3: 素のスカラー禁止）")
    if "dist" in spec:
        raise ConfigError(f"{where} が dist: を使っています。type: に統一してください（決定 V2）")
    t = spec.get("type")
    if t not in DISTRIBUTION_TYPES:
        raise ConfigError(f"{where}.type が不正です: {t!r}")
    if t not in allowed:
        raise ConfigError(f"{where}.type は {sorted(allowed)} のいずれかです: {t!r}")

    if t == "beta":
        if not (spec.get("a", 0) > 0 and spec.get("b", 0) > 0):
            raise ConfigError(f"{where}: beta の a, b は正である必要があります")
    elif t == "constant":
        if "value" not in spec:
            raise ConfigError(f"{where}: constant は value を持つ必要があります")
    elif t == "bernoulli":
        p = spec.get("p")
        if p is None or not (0.0 <= float(p) <= 1.0):
            raise ConfigError(f"{where}: bernoulli の p は 0.0〜1.0 です")
    elif t == "categorical":
        values, probs = spec.get("values"), spec.get("probs")
        if values is None or probs is None or len(values) != len(probs):
            raise ConfigError(f"{where}: categorical の values と probs は同じ長さが必要です")
        if abs(sum(probs) - 1.0) > 1e-9:
            raise ConfigError(f"{where}: categorical の probs の総和が 1.0 ではありません")


def _validate_distribution_types(cfg: dict) -> None:
    init = cfg["agent_init"]
    for sid, spec in init["skills"].items():
        _validate_spec(spec, f"agent_init.skills.{sid}", {"beta", "constant"})
    for aid, spec in init["assets"].items():
        _validate_spec(spec, f"agent_init.assets.{aid}", {"bernoulli", "categorical"})
    for tid, spec in init["traits"].items():
        _validate_spec(spec, f"agent_init.traits.{tid}", {"beta", "constant"})


def _validate_projects(cfg: dict, ids: IdRegistry) -> None:
    seen: set[str] = set()
    for entry in cfg["projects"]:
        pid = entry["project_id"]
        # 決定 P4: project_ids はカタログ由来なので集合一致は自明。
        # 代わりに一意性と命名規約を検証する。
        if pid in seen:
            raise ConfigError(f"project_id が重複しています: {pid}")
        seen.add(pid)
        if not pid.startswith("proj_") or not pid[len("proj_") :].isdigit():
            raise ConfigError(f"project_id は proj_<連番> の形式です: {pid}")

        proj = Project.from_dict(entry)
        if proj.primary_skill not in ids.skill_ids:
            raise ConfigError(f"{pid}.primary_skill が未知です: {proj.primary_skill}")
        if proj.required_asset is not None and proj.required_asset not in ids.asset_ids:
            raise ConfigError(f"{pid}.required_asset が未知です: {proj.required_asset}")
        unknown = set(proj.material_cost) - set(ids.material_ids)
        if unknown:
            raise ConfigError(f"{pid}.material_cost に未知の材料があります: {sorted(unknown)}")


def load_projects(cfg: dict) -> tuple[Project, ...]:
    return tuple(Project.from_dict(entry) for entry in cfg["projects"])


def config_sha256(cfg: dict) -> str:
    return sha256_of(cfg)
