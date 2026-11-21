# Espanso locales

UI translation catalogs for the Chinese maintenance fork.

## Layout

| File | Role |
|------|------|
| `en.yml` | Source-of-truth English strings (fallback) |
| `zh-CN.yml` | Simplified Chinese translations |
| `README.md` | Conventions for humans and automation |

Add more locales as `xx-YY.yml` (BCP 47-ish tags). Runtime resolves:

1. `ESPANSO_LANG` / `ESPANSO_LOCALE` environment variable
2. Fork default: `zh-CN`

Missing keys always fall back to `en.yml`, then to the key name.

Force English temporarily with:

```bash
ESPANSO_LANG=en espanso
```

Territory tags fall back to language (`zh-CN` → `zh` if present → `en`).

## Rules for sync / auto-translate bots

1. **Never hardcode user-facing UI strings in Rust/C++** for surfaces already covered here. Add a key instead.
2. When upstream introduces new English UI copy, append the key to `en.yml` first, then draft `zh-CN.yml`.
3. Do not rename existing keys without a migration note; automation diffs keys by name.
4. Keep YAML nested under stable groups (`tray`, `notify`, `search`, `builtin`, `welcome`, `wizard`, `troubleshooting`, `cli`, …).
5. Drafted or machine-assisted strings must be marked **`needs-review`** in the sync PR until a human spot-checks them. English/TODO placeholders in `zh-CN.yml` are **not** finalized Chinese.
6. After merging upstream, run:
   - `python3 scripts/extract_locale_keys.py` — report gaps
   - `python3 scripts/extract_locale_keys.py --draft` — append missing nested keys into `en.yml` / `zh-CN.yml` (English or `TODO: needs-review` placeholders)
   - `python3 scripts/extract_locale_keys.py --draft --report /tmp/report.md` — also write a markdown summary for PR bodies
   - `bash scripts/check_locales.sh` — catalog parity + call-site coverage
7. The scheduled workflow [`.github/workflows/sync-upstream.yml`](../../.github/workflows/sync-upstream.yml) runs extract + `--draft`, commits catalog changes onto the same sync branch when needed, and pastes the report into the sync PR. It does **not** auto-merge, auto-translate to final Chinese, or create Releases/tags. Merge conflicts fail the job with a summary (Issues are disabled on this fork).

## Key naming

Use `group.snake_case_key` after flattening. Example: `tray.open_search`.
