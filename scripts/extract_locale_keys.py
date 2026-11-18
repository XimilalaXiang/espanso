#!/usr/bin/env python3
"""Extract i18n keys from Rust/C++ call sites and compare with locale catalogs.

Usage:
  python3 scripts/extract_locale_keys.py           # report missing/extra keys
  python3 scripts/extract_locale_keys.py --draft   # append missing keys to zh-CN as English drafts

No network / paid APIs — drafts copy English so humans/MT can refine later.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EN = ROOT / "espanso-i18n" / "locales" / "en.yml"
ZH = ROOT / "espanso-i18n" / "locales" / "zh-CN.yml"

CALL_PATTERNS = [
    re.compile(r'\bt(?:_static)?!\(\s*"([^"]+)"'),
    re.compile(r'\bt(?:_static)?\(\s*"([^"]+)"'),
    re.compile(r'\bTr\(\s*"([^"]+)"'),
]


def flatten_yaml(path: Path) -> dict[str, str]:
    # Minimal nested YAML string map flattener (same shape as espanso-i18n).
    try:
        import yaml  # type: ignore
    except ImportError:
        yaml = None

    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
    else:
        # Fallback: only support our simple quoted maps via a tiny parser.
        data = _parse_simple_yaml(text)

    out: dict[str, str] = {}

    def walk(prefix: str, node):
        if isinstance(node, dict):
            for k, v in node.items():
                nxt = f"{prefix}.{k}" if prefix else str(k)
                walk(nxt, v)
        elif isinstance(node, (str, int, float, bool)):
            out[prefix] = str(node)

    walk("", data)
    return out


def _parse_simple_yaml(text: str) -> dict:
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if rest == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            if rest.startswith('"') and rest.endswith('"'):
                rest = bytes(rest[1:-1], "utf-8").decode("unicode_escape")
            parent[key] = rest
    return root


def extract_keys_from_source() -> set[str]:
    keys: set[str] = set()
    for path in ROOT.rglob("*"):
        if path.suffix not in {".rs", ".cpp", ".h", ".mm"}:
            continue
        if "target" in path.parts or "vendor" in path.parts:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        # Drop Rust unit-test modules so intentional missing-key assertions
        # are not treated as production call sites.
        content = re.sub(
            r"#\[cfg\(test\)\][\s\S]*",
            "",
            content,
            count=1,
        )
        for pat in CALL_PATTERNS:
            keys.update(pat.findall(content))
    return keys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Append missing English keys into zh-CN.yml as English drafts",
    )
    args = parser.parse_args()

    used = extract_keys_from_source()
    en = flatten_yaml(EN)
    zh = flatten_yaml(ZH)

    missing_in_en = sorted(k for k in used if k not in en)
    missing_in_zh = sorted(k for k in en if k not in zh)
    unused_en = sorted(k for k in en if k not in used and not k.startswith("cli."))
    # cli.* keys are referenced dynamically via t_static in main.rs — counted in used.

    print(f"call-site keys: {len(used)}")
    print(f"en.yml keys:    {len(en)}")
    print(f"zh-CN.yml keys: {len(zh)}")

    status = 0
    if missing_in_en:
        status = 1
        print("\nMissing from en.yml (used in code):")
        for k in missing_in_en:
            print(f"  - {k}")
    if missing_in_zh:
        status = 1
        print("\nMissing from zh-CN.yml:")
        for k in missing_in_zh:
            print(f"  - {k}")
    if unused_en:
        print("\nPossibly unused en.yml keys (excluding cli.* check above):")
        for k in unused_en[:50]:
            print(f"  - {k}")
        if len(unused_en) > 50:
            print(f"  ... and {len(unused_en) - 50} more")

    if args.draft and missing_in_zh:
        # Append drafts under a dedicated section comment.
        with ZH.open("a", encoding="utf-8") as fh:
            fh.write("\n# AUTO-DRAFT: copied from English; needs-review\n")
            for k in missing_in_zh:
                # Flat append is not nested YAML — prefer telling the user to add nested.
                # For scaffold, write a sibling drafts file instead.
                pass
        drafts = ROOT / "espanso-i18n" / "locales" / "zh-CN.drafts.yml"
        with drafts.open("w", encoding="utf-8") as fh:
            fh.write("# Draft zh-CN entries (English placeholders). needs-review\n")
            for k in missing_in_zh:
                val = en[k].replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                fh.write(f'{k}: "{val}"\n')
        print(f"\nWrote draft placeholders to {drafts.relative_to(ROOT)}")

    return status


if __name__ == "__main__":
    sys.exit(main())
