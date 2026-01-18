#!/usr/bin/env python3
"""
Benchmark serial vs parallel video composition.

Example:
  python scripts/benchmark-compose.py \
    --source /path/to/source.mp4 \
    --bar /path/to/bar.mp4 \
    --output-dir ./benchmark-output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import subprocess
import sys
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from vmarker.video_composer import (  # noqa: E402
    CompositionConfig,
    OverlayPosition,
    compose_vstack,
)
from vmarker.video_composer_parallel import (  # noqa: E402
    ParallelConfig,
    compose_vstack_parallel,
)

    
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark serial vs parallel video composition.",
    )
    parser.add_argument("--source", type=Path, required=True, help="Source video path.")
    parser.add_argument("--bar", type=Path, required=True, help="Bar video path.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("benchmark-output"),
        help="Directory to place benchmark outputs.",
    )
    parser.add_argument(
        "--position",
        choices=("top", "bottom"),
        default="bottom",
        help="Overlay position.",
    )
    parser.add_argument(
        "--chunk-seconds",
        type=int,
        default=ParallelConfig().chunk_seconds,
        help="Chunk duration for parallel composition.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=ParallelConfig().max_workers,
        help="Max workers for parallel composition.",
    )
    parser.add_argument(
        "--gop-multiplier",
        type=int,
        default=ParallelConfig().gop_multiplier,
        help="GOP multiplier for parallel composition.",
    )
    parser.add_argument(
        "--output-ext",
        default="mp4",
        help="Output file extension (default: mp4).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--mode",
        choices=("serial", "parallel"),
        help="Run a single mode (used by the wrapper).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (combined if no --mode).",
    )
    return parser.parse_args()


def _ensure_inputs(source: Path, bar: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"source video not found: {source}")
    if not bar.exists():
        raise FileNotFoundError(f"bar video not found: {bar}")


def _ensure_output_path(path: Path, overwrite: bool) -> None:
    if path.exists():
        if overwrite:
            path.unlink()
        else:
            raise FileExistsError(f"output already exists: {path}")


def _collect_usage() -> tuple[resource.struct_rusage, resource.struct_rusage]:
    return (
        resource.getrusage(resource.RUSAGE_SELF),
        resource.getrusage(resource.RUSAGE_CHILDREN),
    )


def _delta_usage(
    before: tuple[resource.struct_rusage, resource.struct_rusage],
    after: tuple[resource.struct_rusage, resource.struct_rusage],
) -> dict[str, float]:
    before_self, before_children = before
    after_self, after_children = after
    return {
        "cpu_user_seconds": (
            (after_self.ru_utime - before_self.ru_utime)
            + (after_children.ru_utime - before_children.ru_utime)
        ),
        "cpu_system_seconds": (
            (after_self.ru_stime - before_self.ru_stime)
            + (after_children.ru_stime - before_children.ru_stime)
        ),
        "self_max_rss_kb": float(after_self.ru_maxrss),
        "children_max_rss_kb": float(after_children.ru_maxrss),
    }


def _run_serial(
    source: Path,
    bar: Path,
    output_path: Path,
    position: OverlayPosition,
) -> Path:
    config = CompositionConfig(position=position)
    return compose_vstack(source, bar, output_path, config)


def _run_parallel(
    source: Path,
    bar: Path,
    output_path: Path,
    position: OverlayPosition,
    chunk_seconds: int,
    max_workers: int,
    gop_multiplier: int,
) -> Path:
    config = ParallelConfig(
        position=position,
        chunk_seconds=chunk_seconds,
        max_workers=max_workers,
        gop_multiplier=gop_multiplier,
    )
    return asyncio.run(compose_vstack_parallel(source, bar, output_path, config))


def _run_mode(args: argparse.Namespace) -> dict[str, object]:
    _ensure_inputs(args.source, args.bar)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_ext = args.output_ext.lstrip(".")
    output_path = args.output_dir / f"{args.mode}-output.{output_ext}"
    _ensure_output_path(output_path, args.overwrite)

    position = (
        OverlayPosition.TOP if args.position == "top" else OverlayPosition.BOTTOM
    )

    usage_before = _collect_usage()
    start = time.perf_counter()
    if args.mode == "serial":
        _run_serial(args.source, args.bar, output_path, position)
    else:
        _run_parallel(
            args.source,
            args.bar,
            output_path,
            position,
            args.chunk_seconds,
            args.max_workers,
            args.gop_multiplier,
        )
    end = time.perf_counter()
    usage_after = _collect_usage()

    usage_delta = _delta_usage(usage_before, usage_after)
    output_size = output_path.stat().st_size if output_path.exists() else 0
    max_rss_kb = max(
        usage_delta["self_max_rss_kb"],
        usage_delta["children_max_rss_kb"],
    )

    return {
        "mode": args.mode,
        "output_path": str(output_path),
        "output_bytes": output_size,
        "wall_seconds": end - start,
        "cpu_user_seconds": usage_delta["cpu_user_seconds"],
        "cpu_system_seconds": usage_delta["cpu_system_seconds"],
        "self_max_rss_kb": usage_delta["self_max_rss_kb"],
        "children_max_rss_kb": usage_delta["children_max_rss_kb"],
        "max_rss_kb": max_rss_kb,
        "position": args.position,
        "chunk_seconds": args.chunk_seconds,
        "max_workers": args.max_workers,
        "gop_multiplier": args.gop_multiplier,
    }


def _run_subprocess(args: argparse.Namespace, mode: str) -> dict[str, object]:
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--mode",
        mode,
        "--json",
        "--source",
        str(args.source),
        "--bar",
        str(args.bar),
        "--output-dir",
        str(args.output_dir),
        "--position",
        args.position,
        "--chunk-seconds",
        str(args.chunk_seconds),
        "--max-workers",
        str(args.max_workers),
        "--gop-multiplier",
        str(args.gop_multiplier),
        "--output-ext",
        args.output_ext,
    ]
    if args.overwrite:
        cmd.append("--overwrite")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "benchmark subprocess failed")
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("failed to parse benchmark output") from exc


def _print_human(serial: dict[str, object], parallel: dict[str, object]) -> None:
    serial_wall = float(serial["wall_seconds"])
    parallel_wall = float(parallel["wall_seconds"])
    serial_cpu = float(serial["cpu_user_seconds"]) + float(serial["cpu_system_seconds"])
    parallel_cpu = float(parallel["cpu_user_seconds"]) + float(parallel["cpu_system_seconds"])

    speedup_wall = serial_wall / parallel_wall if parallel_wall else 0.0
    speedup_cpu = serial_cpu / parallel_cpu if parallel_cpu else 0.0

    def _fmt_bytes(value: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024:
                return f"{value:.1f}{unit}"
            value /= 1024
        return f"{value:.1f}TB"

    print("Benchmark results")
    print(
        f"- serial: wall={serial_wall:.2f}s, cpu={serial_cpu:.2f}s, "
        f"max_rss_kb={int(serial['max_rss_kb'])}, "
        f"output={_fmt_bytes(int(serial['output_bytes']))}, "
        f"path={serial['output_path']}"
    )
    print(
        f"- parallel: wall={parallel_wall:.2f}s, cpu={parallel_cpu:.2f}s, "
        f"max_rss_kb={int(parallel['max_rss_kb'])}, "
        f"output={_fmt_bytes(int(parallel['output_bytes']))}, "
        f"path={parallel['output_path']}"
    )
    print(f"- speedup: wall={speedup_wall:.2f}x, cpu={speedup_cpu:.2f}x")


def _print_single(result: dict[str, object]) -> None:
    wall = float(result["wall_seconds"])
    cpu = float(result["cpu_user_seconds"]) + float(result["cpu_system_seconds"])

    def _fmt_bytes(value: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024:
                return f"{value:.1f}{unit}"
            value /= 1024
        return f"{value:.1f}TB"

    print(
        f"{result['mode']}: wall={wall:.2f}s, cpu={cpu:.2f}s, "
        f"max_rss_kb={int(result['max_rss_kb'])}, "
        f"output={_fmt_bytes(int(result['output_bytes']))}, "
        f"path={result['output_path']}"
    )


def main() -> int:
    args = _parse_args()
    try:
        if args.mode:
            result = _run_mode(args)
            if args.json:
                print(json.dumps(result, ensure_ascii=True))
            else:
                _print_single(result)
            return 0

        serial = _run_subprocess(args, "serial")
        parallel = _run_subprocess(args, "parallel")
        if args.json:
            output = {
                "serial": serial,
                "parallel": parallel,
                "speedup": {
                    "wall": (
                        float(serial["wall_seconds"]) / float(parallel["wall_seconds"])
                        if float(parallel["wall_seconds"])
                        else 0.0
                    ),
                    "cpu": (
                        (
                            float(serial["cpu_user_seconds"])
                            + float(serial["cpu_system_seconds"])
                        )
                        / (
                            float(parallel["cpu_user_seconds"])
                            + float(parallel["cpu_system_seconds"])
                        )
                        if (
                            float(parallel["cpu_user_seconds"])
                            + float(parallel["cpu_system_seconds"])
                        )
                        else 0.0
                    ),
                },
            }
            print(json.dumps(output, ensure_ascii=True))
        else:
            _print_human(serial, parallel)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
