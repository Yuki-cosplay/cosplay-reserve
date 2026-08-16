"""run のオーケストレーションと再現性メタデータ（docs/DESIGN_M1.md §10.3）。

SPEC §23 の要求（seed / model / prompt version / config / timestamp /
simulation parameters / Agent initial states）を満たす metadata.json を書き出す。
M1 では llm と prompt_version は null。M2 でここが埋まる。
"""

from __future__ import annotations

import csv
import datetime as dt
import platform
import subprocess
import sys
from pathlib import Path

from src.agents.agent import pre_network_state
from src.common.io import sha256_of, write_json, write_text
from src.common.config import config_sha256
from src.simulation.metrics import MetricsRecorder
from src.world.step import step
from src.world.world import build_world

REACHABILITY_EVERY = 10


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or None
    except Exception:
        return None


def _package_versions() -> dict:
    versions = {}
    for name in ("numpy", "networkx", "pandas", "yaml", "pytest"):
        try:
            mod = __import__(name)
            versions[name] = getattr(mod, "__version__", "unknown")
        except Exception:
            versions[name] = "not installed"
    return versions


def final_state_sha256(world) -> str:
    """T1（決定論性）が比較する最終状態のハッシュ。"""
    payload = []
    for aid in sorted(world.agents):
        a = world.agents[aid]
        payload.append(
            {
                "id": a.id,
                "skills": {k: repr(v) for k, v in sorted(a.skills.items())},
                "materials": {k: repr(v) for k, v in sorted(a.materials.items())},
                "stage": a.maker_stage.value,
                "completed": len(a.completed_projects),
                "methods": sorted(a.methods),
                "success": dict(sorted(a.success_count.items())),
                "failure": dict(sorted(a.failure_count.items())),
            }
        )
    return sha256_of(payload)


def run_one(
    condition_path: str | Path,
    seed: int,
    steps: int | None = None,
    output_dir: str | Path | None = None,
    overrides: dict | None = None,
) -> dict:
    """1条件 × 1seed を実行し、結果サマリを返す。"""
    world = build_world(condition_path, seed=seed)
    if overrides:
        for section, values in overrides.items():
            world.cfg[section].update(values)
    n_steps = steps if steps is not None else world.cfg["run"]["steps"]

    recorder = MetricsRecorder()
    world.metrics = recorder
    recorder.record_reachability(world)

    for _ in range(n_steps):
        stats = step(world)
        recorder.record(world, stats)
        if world.step % REACHABILITY_EVERY == 0:
            recorder.record_reachability(world)

    summary = {
        **world.provenance,
        "steps": n_steps,
        "final_state_sha256": final_state_sha256(world),
    }

    if output_dir is not None:
        _write_outputs(world, recorder, summary, Path(output_dir), n_steps)
    return summary


def _write_outputs(world, recorder, summary, out_dir: Path, n_steps: int) -> None:
    run_id = (
        f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}"
        f"_{world.cfg['condition']}_seed{world.cfg['run']['seed']}"
    )
    run_dir = out_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "run_id": run_id,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "milestone": "M1",
        "phase": world.cfg["run"]["phase"],
        "steps": n_steps,
        "step_hours": world.cfg["run"]["step_hours"],
        "llm": None,
        "prompt_version": None,
        "config_sha256": config_sha256(world.cfg),
        "code_git_commit": _git_commit(),
        "python_version": platform.python_version(),
        "package_versions": _package_versions(),
        **summary,
    }
    write_json(run_dir / "metadata.json", metadata)

    fieldnames = recorder.fieldnames()
    with open(run_dir / "timeseries.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        writer.writerows(recorder.rows)

    write_json(run_dir / "config_resolved.json", world.cfg)
    write_text(
        run_dir / "agents_initial.json",
        __import__("json").dumps(pre_network_state(world.agents), ensure_ascii=False, indent=2),
    )


def run_all_conditions(
    config_dir: str | Path, seed: int, steps: int | None = None,
    output_dir: str | Path | None = None, overrides: dict | None = None,
) -> dict[str, dict]:
    config_dir = Path(config_dir)
    return {
        c: run_one(
            config_dir / f"condition_{c.lower()}.yaml",
            seed=seed,
            steps=steps,
            output_dir=output_dir,
            overrides=overrides,
        )
        for c in ("A", "B", "C", "D")
    }


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    results = run_all_conditions("configs", seed=seed, output_dir="outputs")
    for c, r in results.items():
        print(f"{c}: final={r['final_state_sha256'][:12]} cultural={r['cultural_edge_count']}")
