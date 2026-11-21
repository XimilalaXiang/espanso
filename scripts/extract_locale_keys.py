#!/usr/bin/env python3
"""Extract i18n keys from Rust/C++ call sites and compare with locale catalogs.

Usage:
  python3 scripts/extract_locale_keys.py
      # report missing/extra keys (exit 1 if catalogs are incomplete)
  python3 scripts/extract_locale_keys.py --draft
      # add missing keys into en.yml / zh-CN.yml (English placeholders; needs-review)
  python3 scripts/extract_locale_keys.py --draft --report /tmp/report.md
      # also write a markdown summary for sync PRs

No network / paid APIs — drafts copy English (or a TODO placeholder) so humans
can refine later. Drafted zh-CN values are NOT finalized translations.
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

TODO_PLACEHOLDER = "TODO: needs-review"


def _load_yaml_module():
    try:
        import yaml  # type: ignore

        return yaml
    except ImportError:
        return None


def flatten_yaml(path: Path) -> dict[str, str]:
    # Minimal nested YAML string map flattener (same shape as espanso-i18n).
    yaml = _load_yaml_module()
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
    else:
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


def _escape_yaml_double(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _append_nested_keys(path: Path, entries: dict[str, str], banner: str) -> None:
    """Append missing dotted keys as nested YAML without rewriting existing lines.

    Merges into existing top-level groups (and nested maps when present) so a
    second `tray:` / `cli:` block is never appended (that would replace the
    whole group under PyYAML).
    """
    if not entries:
        return

    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    lines = text.splitlines(keepends=True)

    def line_indent(idx: int) -> int:
        raw = lines[idx]
        return len(raw) - len(raw.lstrip(" "))

    def trim_trailing_noise(start: int, end: int) -> int:
        """Keep inserts beside real keys, not after trailing blanks/comments."""
        while end > start + 1:
            prev = lines[end - 1]
            if prev.strip() == "":
                end -= 1
                continue
            if prev.lstrip().startswith("#") and line_indent(end - 1) == 0:
                end -= 1
                continue
            break
        return end

    def find_map_child_span(parent_start: int, parent_end: int, child: str, child_indent: int):
        pattern = re.compile(
            rf"^{' ' * child_indent}{re.escape(child)}:\s*(?:#.*)?$"
        )
        start = None
        for idx in range(parent_start + 1, parent_end):
            if pattern.match(lines[idx].rstrip("\n")):
                start = idx
                break
        if start is None:
            return None
        end = parent_end
        for idx in range(start + 1, parent_end):
            raw = lines[idx]
            if raw.strip() == "" or raw.lstrip().startswith("#"):
                continue
            if line_indent(idx) <= child_indent:
                end = idx
                break
        return start, trim_trailing_noise(start, end)

    def find_top_level_span(section: str):
        pattern = re.compile(rf"^{re.escape(section)}:\s*(?:#.*)?$")
        start = None
        for idx, line in enumerate(lines):
            if pattern.match(line.rstrip("\n")):
                start = idx
                break
        if start is None:
            return None
        end = len(lines)
        for idx in range(start + 1, len(lines)):
            raw = lines[idx]
            if raw.strip() == "" or raw.lstrip().startswith("#"):
                continue
            if re.match(r"^[A-Za-z0-9_.-]+:\s*(?:#.*)?$", raw.rstrip("\n")):
                end = idx
                break
        return start, trim_trailing_noise(start, end)

    def ensure_path(parts: list[str]) -> tuple[int, int, int]:
        """Return (map_start, map_end, value_indent) for the parent map of the leaf."""
        if not parts:
            raise SystemExit("empty key path")

        section = parts[0]
        span = find_top_level_span(section)
        if span is None:
            if lines and lines[-1].strip() != "":
                lines.append("\n")
            lines.append(f"{section}:\n")
            span = find_top_level_span(section)
            if span is None:
                raise SystemExit(f"failed to create top-level section {section!r}")
        start, end = span

        # Walk intermediate maps; create missing ones at the end of each parent.
        for depth, name in enumerate(parts[1:-1], start=1):
            child_indent = depth * 2
            child = find_map_child_span(start, end, name, child_indent)
            if child is None:
                insert_at = end
                lines[insert_at:insert_at] = [f"{' ' * child_indent}{name}:\n"]
                # Parent span grew by one line; refresh child span.
                end += 1
                child = find_map_child_span(start, end, name, child_indent)
                if child is None:
                    raise SystemExit(f"failed to create nested map {'.'.join(parts[: depth + 1])}")
            start, end = child

        value_indent = (len(parts) - 1) * 2
        return start, end, value_indent

    # Stable order for readable diffs.
    for dotted in sorted(entries):
        value = entries[dotted]
        parts = dotted.split(".")
        if len(parts) == 1:
            parts = ["auto_draft", parts[0]]
        _start, end, value_indent = ensure_path(parts)
        leaf = parts[-1]
        leaf_line = (
            f'{" " * value_indent}{leaf}: "{_escape_yaml_double(value)}"  # needs-review\n'
        )
        lines[end:end] = [leaf_line]

    if banner and banner not in "".join(lines):
        if lines and lines[-1].strip() != "":
            lines.append("\n")
        lines.append(banner.rstrip() + "\n")

    path.write_text("".join(lines), encoding="utf-8")


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


def draft_missing_keys(
    missing_in_en: list[str],
    missing_in_zh: list[str],
    en_flat: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Insert missing keys into nested catalogs. Returns (drafted_en, drafted_zh)."""
    drafted_en: list[str] = []
    drafted_zh: list[str] = []

    if missing_in_en:
        en_entries = {key: TODO_PLACEHOLDER for key in missing_in_en}
        _append_nested_keys(
            EN,
            en_entries,
            "# AUTO-DRAFT: keys below may need English copy; needs-review before release.",
        )
        drafted_en = list(missing_in_en)
        en_flat.update(en_entries)

    # Recompute zh gaps after en drafts so parity includes new en keys.
    zh_flat = flatten_yaml(ZH)
    zh_missing = sorted(set(missing_in_zh) | {k for k in en_flat if k not in zh_flat})
    if zh_missing:
        zh_entries = {
            key: en_flat.get(key, TODO_PLACEHOLDER) for key in zh_missing
        }
        _append_nested_keys(
            ZH,
            zh_entries,
            "# AUTO-DRAFT: English/TODO placeholders; needs-review (not final zh-CN).",
        )
        drafted_zh = list(zh_missing)

    return drafted_en, drafted_zh


def write_report(
    path: Path,
    *,
    used: int,
    en_count: int,
    zh_count: int,
    missing_in_en: list[str],
    missing_in_zh: list[str],
    drafted_en: list[str],
    drafted_zh: list[str],
    unused_en: list[str],
) -> None:
    lines = [
        "## Locale extract / draft summary",
        "",
        f"- Call-site keys: `{used}`",
        f"- `en.yml` keys: `{en_count}`",
        f"- `zh-CN.yml` keys: `{zh_count}`",
        "",
    ]
    if drafted_en:
        lines.append(f"### Drafted into `en.yml` ({len(drafted_en)})")
        lines.append("")
        lines.append("English placeholders (`TODO: needs-review`):")
        lines.append("")
        for key in drafted_en:
            lines.append(f"- `{key}`")
        lines.append("")
    if drafted_zh:
        lines.append(f"### Drafted into `zh-CN.yml` ({len(drafted_zh)})")
        lines.append("")
        lines.append(
            "Copied English (or TODO) placeholders — **needs-review**, not finalized Chinese:"
        )
        lines.append("")
        for key in drafted_zh:
            lines.append(f"- `{key}`")
        lines.append("")
    if not drafted_en and not drafted_zh:
        lines.append("No catalog drafts were required.")
        lines.append("")
    if missing_in_en and not drafted_en:
        lines.append("### Still missing from `en.yml`")
        lines.append("")
        for key in missing_in_en:
            lines.append(f"- `{key}`")
        lines.append("")
    if missing_in_zh and not drafted_zh:
        lines.append("### Still missing from `zh-CN.yml`")
        lines.append("")
        for key in missing_in_zh:
            lines.append(f"- `{key}`")
        lines.append("")
    if unused_en:
        lines.append(
            f"### Possibly unused `en.yml` keys (first 50 of {len(unused_en)}; excludes cli.*)"
        )
        lines.append("")
        for key in unused_en[:50]:
            lines.append(f"- `{key}`")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Insert missing keys into en.yml / zh-CN.yml as English/TODO drafts (needs-review)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write a markdown summary to this path (for sync PR bodies)",
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

    drafted_en: list[str] = []
    drafted_zh: list[str] = []

    if args.draft and (missing_in_en or missing_in_zh):
        drafted_en, drafted_zh = draft_missing_keys(missing_in_en, missing_in_zh, en)
        # Reload after draft for accurate final counts / status.
        en = flatten_yaml(EN)
        zh = flatten_yaml(ZH)
        missing_in_en = sorted(k for k in used if k not in en)
        missing_in_zh = sorted(k for k in en if k not in zh)
        print(f"drafted en.yml keys:    {len(drafted_en)}")
        print(f"drafted zh-CN.yml keys: {len(drafted_zh)}")

    if missing_in_en:
        print("\nMissing from en.yml (used in code):")
        for k in missing_in_en:
            print(f"  - {k}")
    if missing_in_zh:
        print("\nMissing from zh-CN.yml:")
        for k in missing_in_zh:
            print(f"  - {k}")
    if unused_en:
        print("\nPossibly unused en.yml keys (excluding cli.* check above):")
        for k in unused_en[:50]:
            print(f"  - {k}")
        if len(unused_en) > 50:
            print(f"  ... and {len(unused_en) - 50} more")

    if args.report:
        write_report(
            args.report,
            used=len(used),
            en_count=len(en),
            zh_count=len(zh),
            missing_in_en=missing_in_en,
            missing_in_zh=missing_in_zh,
            drafted_en=drafted_en,
            drafted_zh=drafted_zh,
            unused_en=unused_en,
        )
        print(f"\nWrote report to {args.report}")

    if missing_in_en or missing_in_zh:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
