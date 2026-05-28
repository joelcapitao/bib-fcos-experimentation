#!/usr/bin/env python3
"""Merge multiple image-builder blueprint TOML files into one.

Standard deep-merge (last-wins) with one special rule:
  customizations.kernel.append values are concatenated (space-separated)
  rather than overridden, so kernel arguments accumulate across layers.

Usage:
    merge-blueprints.py [-o OUTPUT] BLUEPRINT [BLUEPRINT ...]

Examples:
    # Print merged result to stdout
    merge-blueprints.py shared/blueprint.toml shared/x86_64.toml qemu/x86_64.toml

    # Write to a file
    merge-blueprints.py -o merged.toml shared/blueprint.toml qemu/aarch64.toml
"""

from __future__ import annotations

import argparse
import copy
import sys
import tomllib

# Pairs of (parent_path, key) whose string values should be concatenated
# (space-separated) instead of overridden.
_CONCAT_STRING_KEYS: list[tuple[tuple[str, ...], str]] = [
    (("customizations", "kernel"), "append"),
]


def _is_concat_key(path: tuple[str, ...], key: str) -> bool:
    return (path, key) in _CONCAT_STRING_KEYS


def _deep_merge(
    base: dict, overlay: dict, path: tuple[str, ...] = ()
) -> dict:
    """Recursively merge *overlay* into *base* (mutates *base*)."""
    for key, new_val in overlay.items():
        old_val = base.get(key)

        if isinstance(old_val, dict) and isinstance(new_val, dict):
            _deep_merge(old_val, new_val, path + (key,))

        elif (
            _is_concat_key(path, key)
            and isinstance(old_val, str)
            and isinstance(new_val, str)
        ):
            base[key] = f"{old_val} {new_val}"

        elif isinstance(old_val, list) and isinstance(new_val, list):
            base[key] = old_val + new_val

        else:
            base[key] = copy.deepcopy(new_val)

    return base


def merge_blueprints(paths: list[str]) -> dict:
    """Load and merge blueprint files in order."""
    result: dict = {}
    for path in paths:
        with open(path, "rb") as f:
            data = tomllib.load(f)
        _deep_merge(result, data)
    return result


def _format_toml(data: dict, indent: int = 0) -> str:
    """Minimal TOML serialiser — supports the subset used by blueprints."""
    lines: list[str] = []
    _emit(data, lines, path=())
    return "\n".join(lines) + "\n"


def _emit(
    data: dict,
    lines: list[str],
    path: tuple[str, ...],
) -> None:
    # Emit simple key/value pairs first, then sub-tables.
    tables: list[tuple[str, dict]] = []

    for key, val in data.items():
        if isinstance(val, dict):
            tables.append((key, val))
        else:
            lines.append(f"{_quote_key(key)} = {_format_value(val)}")

    for key, sub in tables:
        sub_path = path + (key,)
        header = ".".join(_quote_key(k) for k in sub_path)
        lines.append("")
        lines.append(f"[{header}]")
        _emit(sub, lines, sub_path)


def _quote_key(key: str) -> str:
    """Quote a TOML key only when necessary."""
    # Bare keys: A-Za-z0-9 and - _
    if all(c.isalnum() or c in "-_" for c in key) and key:
        return key
    return f'"{_escape(key)}"'


def _format_value(val: object) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, float):
        return repr(val)
    if isinstance(val, str):
        return f'"{_escape(val)}"'
    if isinstance(val, list):
        inner = ", ".join(_format_value(v) for v in val)
        return f"[{inner}]"
    raise TypeError(f"unsupported TOML value type: {type(val)}")


def _escape(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge image-builder blueprint TOML files."
    )
    parser.add_argument(
        "blueprints",
        nargs="+",
        metavar="BLUEPRINT",
        help="blueprint TOML files in merge order (first = base)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="write merged blueprint to OUTPUT (default: stdout)",
    )
    args = parser.parse_args()

    merged = merge_blueprints(args.blueprints)
    toml_str = _format_toml(merged)

    if args.output:
        with open(args.output, "w") as f:
            f.write(toml_str)
    else:
        sys.stdout.write(toml_str)


if __name__ == "__main__":
    main()
