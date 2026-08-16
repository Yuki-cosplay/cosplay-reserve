"""T14: config 起動時検証（決定 Z6 / W2 / V2 / V3 / P4）。

不整合な config は実行前に例外で落ちること。
実行後ではなく実行前に落とす。300 run の感度分析が走り終わってから
「mat_4 だけ補充されていなかった」と気付くのが最悪の失敗である。
"""

import copy
from pathlib import Path

import pytest

from src.common.config import ConfigError, load_config, validate_config

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@pytest.fixture()
def cfg():
    return load_config(CONFIG_DIR / "condition_a.yaml")


def test_valid_config_passes(cfg):
    ids = validate_config(cfg)
    assert ids.skill_ids == tuple(f"skill_{i}" for i in range(6))
    assert ids.project_ids == tuple(f"proj_{i}" for i in range(6))


def test_all_four_conditions_load():
    for c in ("a", "b", "c", "d"):
        load_config(CONFIG_DIR / f"condition_{c}.yaml")


def test_skill_key_mismatch_is_rejected(cfg):
    bad = copy.deepcopy(cfg)
    bad["world"]["n_skills"] = 7  # agent_init.skills は6件のまま
    with pytest.raises(ConfigError, match="agent_init.skills"):
        validate_config(bad)


def test_material_key_mismatch_is_rejected(cfg):
    bad = copy.deepcopy(cfg)
    del bad["materials"]["replenish_rate"]["mat_4"]
    with pytest.raises(ConfigError, match="materials.replenish_rate"):
        validate_config(bad)


def test_dist_key_is_rejected(cfg):
    """決定 V2: キー名は type に統一。dist は許さない。"""
    bad = copy.deepcopy(cfg)
    bad["agent_init"]["skills"]["skill_0"] = {"dist": "beta", "a": 1.5, "b": 8.0}
    with pytest.raises(ConfigError, match="dist"):
        validate_config(bad)


def test_bare_scalar_trait_is_rejected(cfg):
    """決定 V3: 固定値も {type: constant, value: ...} 形式に揃える。"""
    bad = copy.deepcopy(cfg)
    bad["agent_init"]["traits"]["time_budget"] = 3.0
    with pytest.raises(ConfigError, match="dict"):
        validate_config(bad)


def test_categorical_probs_must_sum_to_one(cfg):
    bad = copy.deepcopy(cfg)
    bad["agent_init"]["assets"]["asset_2"]["probs"] = [0.3, 0.4, 0.2, 0.2]
    with pytest.raises(ConfigError, match="総和"):
        validate_config(bad)


def test_duplicate_project_id_is_rejected(cfg):
    bad = copy.deepcopy(cfg)
    bad["projects"][1]["project_id"] = "proj_0"
    with pytest.raises(ConfigError, match="重複"):
        validate_config(bad)


def test_unknown_primary_skill_is_rejected(cfg):
    bad = copy.deepcopy(cfg)
    bad["projects"][0]["primary_skill"] = "skill_9"
    with pytest.raises(ConfigError, match="primary_skill"):
        validate_config(bad)


def test_unknown_required_asset_is_rejected(cfg):
    bad = copy.deepcopy(cfg)
    bad["projects"][0]["required_asset"] = "asset_9"
    with pytest.raises(ConfigError, match="required_asset"):
        validate_config(bad)


def test_condition_yaml_cannot_override_learning_params(tmp_path):
    """条件別 YAML が2キー以外を上書きしようとしたら落ちること（比較の妥当性の担保）。"""
    bad = tmp_path / "condition_bad.yaml"
    bad.write_text(
        "extends: base.yaml\ncondition: A\ntopology: structured\n"
        "peer_learning_enabled: true\nlearning:\n  decay_rate: 0.99\n",
        encoding="utf-8",
    )
    (tmp_path / "base.yaml").write_text(
        (CONFIG_DIR / "base.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    with pytest.raises(ConfigError, match="上書き"):
        load_config(bad)
