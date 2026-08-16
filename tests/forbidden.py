"""禁止語の照合（T2 の共通実装）。

単純な部分文字列照合は偽陽性を生む。実際に "ppe" が "a-ppe-ared" に一致した。
ASCII 語は**語境界**で照合し、日本語は境界がないため部分一致のままとする。

検出力を下げていないことは tests/test_forbidden_matcher.py の陽性コントロールが保証する。
"""

from __future__ import annotations

import re

# CLAUDE.md 絶対ルールの禁止語 + 答えに直結する語
ASCII_TERMS = (
    "cosplay", "ppe", "mask", "covid", "medical", "hospital",
    "pandemic", "shortage", "crisis", "emergency", "sewing",
)
JA_TERMS = ("コスプレ", "マスク", "医療", "縫製", "感染", "防護")


def find_forbidden(text: str) -> list[str]:
    """テキストに含まれる禁止語を返す。空なら clean。"""
    low = text.lower()
    hits = [t for t in ASCII_TERMS if re.search(rf"\b{re.escape(t)}\b", low)]
    hits += [t for t in JA_TERMS if t in text]
    return hits


def assert_clean(text: str, where: str) -> None:
    hits = find_forbidden(text)
    assert not hits, f"{where} に禁止語 {hits}"
