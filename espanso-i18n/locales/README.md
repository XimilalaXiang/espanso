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
5. Machine translations for new keys should be marked in the PR body as `needs-review` until a human spot-checks them.
6. Run `python3 scripts/extract_locale_keys.py` (and optionally `--draft`) after syncing upstream to find missing keys. Use `scripts/check_locales.sh` in CI-like checks.

## Key naming

Use `group.snake_case_key` after flattening. Example: `tray.open_search`.
