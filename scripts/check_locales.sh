#!/usr/bin/env bash
# Fail if en.yml and zh-CN.yml diverge in key set.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

cargo test -p espanso-i18n en_and_zh_cn_catalogs_have_same_keys -- --exact
