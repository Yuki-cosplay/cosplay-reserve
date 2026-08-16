"""UTF-8 を明示した読み書きヘルパ（docs/REVIEW.md I3、Windows 環境対策）。

すべてのファイル入出力で encoding="utf-8" / newline="" を明示する。
Windows の既定エンコーディング（cp932）に落ちると、
中立コードネームしか出力しない設計であっても、
研究者向けの日本語ログが壊れる。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def read_yaml(path: str | Path) -> dict:
    return yaml.safe_load(read_text(path))


def write_json(path: str | Path, obj: Any) -> None:
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def canonical_json(obj: Any) -> str:
    """ハッシュ計算用の正準表現。

    キー順を固定し、浮動小数を repr で安定化する。
    dict の挿入順に依存すると、無関係な実装変更でハッシュが変わる。
    """
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_of(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()
