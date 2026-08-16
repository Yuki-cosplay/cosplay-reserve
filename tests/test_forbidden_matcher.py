"""禁止語マッチャ自体のテスト（陽性コントロール）。

語境界照合へ変えたことで検出力が落ちていないことを保証する。
このテストが緩むと T2 全体が意味を失うため、真っ先に守る。
"""

import pytest

from tests.forbidden import find_forbidden

# 必ず検出しなければならない（本物の漏洩）
MUST_CATCH = [
    "Make PPE for the hospital.",
    "You should build a mask.",
    "This is about COVID.",
    "コスプレ技能を転用せよ",
    "マスクを作れ",
    "医療を助けろ",
    "There is a shortage of supplies.",
    "ppe",
    "PPE.",
    "(mask)",
    "mask-making",
    "the Mask",
]

# 検出してはならない（偽陽性）
MUST_NOT_CATCH = [
    "A requirement has appeared.",      # a-ppe-ared
    "The item is unmasked by design",   # unmasked（語の一部）
    "equipment asset_0",
    "attr_0 >= 0.60",
    "proj_3: attr_0: short by 0.30",
    "Return your intents, most wanted first.",
]


@pytest.mark.parametrize("text", MUST_CATCH)
def test_catches_real_leaks(text):
    assert find_forbidden(text), f"漏洩を検出できていない: {text!r}"


@pytest.mark.parametrize("text", MUST_NOT_CATCH)
def test_no_false_positives(text):
    assert not find_forbidden(text), f"偽陽性: {text!r} -> {find_forbidden(text)}"
