#!/usr/bin/env python3
"""Merge multiple image-builder blueprint TOML files into one.

Standard deep-merge (last-wins) with one special rule:
  customizations.kernel.append values are concatenated (space-separated)
  rather than overridden, so kernel arguments accumulate across layers.

Usage:
    merge-blueprints.py [-o OUTPUT] BLUEPRINT [BLUEPRINT ...]
    merge-blueprints.py --generate-all [-d OUTDIR] [--repo-root ROOT]

Examples:
    # Print merged result to stdout
    merge-blueprints.py shared/blueprint.toml shared/x86_64.toml qemu/x86_64.toml

    # Write to a file
    merge-blueprints.py -o merged.toml shared/blueprint.toml qemu/aarch64.toml

    # Generate all artifact/arch combinations
    merge-blueprints.py --generate-all
"""

from __future__ import annotations

import argparse
import copy
from pathlib import Path
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


# Platform directories that contain per-arch blueprint layers.
_PLATFORM_DIRS = [
    "applehv",
    "aws",
    "azure",
    "gcp",
    "hetzner",
    "ibmcloud",
    "kubevirt",
    "metal",
    "openstack",
    "oraclecloud",
    "proxmoxve",
    "qemu",
    "virtualbox",
    "vmware",
]

# Known architectures (filenames without .toml extension).
_KNOWN_ARCHES = ["aarch64", "ppc64le", "riscv64", "s390x", "x86_64"]


def generate_all(repo_root: Path, out_dir: Path) -> list[Path]:
    """Generate merged blueprints for every platform/arch combination.

    For each (platform, arch) pair where
    ``blueprints/sources/<platform>/<arch>.toml`` exists, the following
    layers are merged:

      blueprints/sources/shared/base.toml    — always included (base)
      blueprints/sources/shared/<arch>.toml   — included if it exists
      blueprints/sources/<platform>/<arch>.toml — platform + arch layer

    Output files are written to ``out_dir/<platform>-<arch>.toml``.
    Returns the list of files written.
    """
    sources = repo_root / "blueprints" / "sources"
    shared_base = sources / "shared" / "base.toml"
    if not shared_base.exists():
        print(f"ERROR: shared base blueprint not found: {shared_base}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for platform in _PLATFORM_DIRS:
        for arch in _KNOWN_ARCHES:
            arch_file = sources / platform / f"{arch}.toml"
            if not arch_file.exists():
                continue

            # Build the ordered list of blueprint layers.
            layers = [str(shared_base)]
            shared_arch = sources / "shared" / f"{arch}.toml"
            if shared_arch.exists():
                layers.append(str(shared_arch))
            layers.append(str(arch_file))

            merged = merge_blueprints(layers)
            out_file = out_dir / f"{platform}-{arch}.toml"
            with open(out_file, "w") as f:
                f.write(_format_toml(merged))

            print(f"  {out_file}")
            written.append(out_file)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge image-builder blueprint TOML files."
    )
    parser.add_argument(
        "blueprints",
        nargs="*",
        metavar="BLUEPRINT",
        help="blueprint TOML files in merge order (first = base)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="write merged blueprint to OUTPUT (default: stdout)",
    )
    parser.add_argument(
        "--generate-all",
        action="store_true",
        help="generate merged blueprints for every artifact/arch combination",
    )
    parser.add_argument(
        "-d",
        "--outdir",
        default=None,
        help="output directory for --generate-all (default: blueprints/generated)",
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="repository root (default: parent of directory containing this script)",
    )
    args = parser.parse_args()

    if args.generate_all:
        repo_root = Path(args.repo_root) if args.repo_root else Path(__file__).resolve().parent.parent
        out_dir = Path(args.outdir) if args.outdir else repo_root / "blueprints" / "generated"
        print(f"Generating all merged blueprints into {out_dir}/")
        written = generate_all(repo_root, out_dir)
        if not written:
            print("WARNING: no blueprint combinations found.", file=sys.stderr)
            sys.exit(1)
        print(f"Done — {len(written)} file(s) written.")
    else:
        if not args.blueprints:
            parser.error("the following arguments are required: BLUEPRINT (or use --generate-all)")

        merged = merge_blueprints(args.blueprints)
        toml_str = _format_toml(merged)

        if args.output:
            with open(args.output, "w") as f:
                f.write(toml_str)
        else:
            sys.stdout.write(toml_str)


if __name__ == "__main__":
    main()
