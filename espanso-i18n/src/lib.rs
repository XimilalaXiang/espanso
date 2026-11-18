/*
 * This file is part of espanso.
 *
 * Copyright (C) 2019-2021 Federico Terzi
 *
 * espanso is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * espanso is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with espanso.  If not, see <https://www.gnu.org/licenses/>.
 */

//! Lightweight localization for Espanso UI strings.
//!
//! Catalogs live in the workspace `locales/` directory so sync/translate bots
//! can update translations without touching Rust call sites.

use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};

use log::{debug, warn};
use serde_norway::Value;

const EN_YAML: &str = include_str!("../../locales/en.yml");
const ZH_CN_YAML: &str = include_str!("../../locales/zh-CN.yml");

static STATE: OnceLock<Mutex<I18nState>> = OnceLock::new();

struct I18nState {
    locale: String,
    catalogs: HashMap<String, HashMap<String, String>>,
}

fn state() -> &'static Mutex<I18nState> {
    STATE.get_or_init(|| {
        let mut catalogs = HashMap::new();
        catalogs.insert("en".to_string(), flatten_yaml(EN_YAML));
        catalogs.insert("zh-CN".to_string(), flatten_yaml(ZH_CN_YAML));
        // Also register language-only alias for zh-CN.
        catalogs.insert(
            "zh".to_string(),
            catalogs
                .get("zh-CN")
                .cloned()
                .unwrap_or_else(|| flatten_yaml(ZH_CN_YAML)),
        );

        Mutex::new(I18nState {
            locale: "en".to_string(),
            catalogs,
        })
    })
}

/// Default locale for this Chinese maintenance fork.
pub const DEFAULT_LOCALE: &str = "zh-CN";

/// Initialize the active locale.
///
/// Resolution order when `preferred` is `None`:
/// 1. `ESPANSO_LANG` or `ESPANSO_LOCALE`
/// 2. [`DEFAULT_LOCALE`] (`zh-CN` on this Chinese maintenance fork)
///
/// System locale is consulted only when selecting among future non-default
/// catalogs via [`detect_locale`]; the fork ships Chinese UI by default.
pub fn init(preferred: Option<&str>) {
    let requested = preferred
        .map(str::to_string)
        .or_else(env_locale)
        .unwrap_or_else(|| DEFAULT_LOCALE.to_string());

    let normalized = normalize_locale(&requested);
    let mut guard = state().lock().expect("i18n state poisoned");
    let resolved = resolve_available(&guard.catalogs, &normalized);
    debug!("i18n locale requested={requested} normalized={normalized} resolved={resolved}");
    guard.locale = resolved;
}

/// Best-effort locale detection helper for tooling / future config integration.
pub fn detect_locale() -> String {
    env_locale()
        .or_else(system_locale)
        .map(|value| normalize_locale(&value))
        .unwrap_or_else(|| DEFAULT_LOCALE.to_string())
}

/// Return the currently active locale id (e.g. `zh-CN` or `en`).
pub fn current_locale() -> String {
    state()
        .lock()
        .expect("i18n state poisoned")
        .locale
        .clone()
}

/// Translate a dotted key such as `tray.disable`.
///
/// Falls back to English, then to the key itself if missing.
pub fn t(key: &str) -> String {
    let guard = state().lock().expect("i18n state poisoned");
    lookup(&guard, key)
}

/// Translate and return a `&'static str` by leaking the owned translation.
///
/// Prefer [`t`] when an owned `String` is acceptable. This helper exists for
/// call sites that historically required `&'static str` labels.
pub fn t_static(key: &str) -> &'static str {
    Box::leak(t(key).into_boxed_str())
}

fn lookup(state: &I18nState, key: &str) -> String {
    if let Some(catalog) = state.catalogs.get(&state.locale) {
        if let Some(value) = catalog.get(key) {
            return value.clone();
        }
    }

    if state.locale != "en" {
        if let Some(catalog) = state.catalogs.get("en") {
            if let Some(value) = catalog.get(key) {
                warn!("i18n missing key '{key}' in locale '{}', using English", state.locale);
                return value.clone();
            }
        }
    }

    warn!("i18n missing key '{key}' in all catalogs");
    key.to_string()
}

fn env_locale() -> Option<String> {
    std::env::var("ESPANSO_LANG")
        .ok()
        .or_else(|| std::env::var("ESPANSO_LOCALE").ok())
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn system_locale() -> Option<String> {
    sys_locale::get_locale().map(|value| value.trim().to_string())
}

fn normalize_locale(raw: &str) -> String {
    let cleaned = raw.trim().replace('_', "-");
    if cleaned.is_empty() {
        return "en".to_string();
    }

    let mut parts = cleaned.split('-');
    let lang = parts.next().unwrap_or("en").to_lowercase();
    let rest: Vec<String> = parts
        .map(|part| {
            if part.len() == 2 {
                part.to_uppercase()
            } else {
                part.to_string()
            }
        })
        .collect();

    if rest.is_empty() {
        lang
    } else {
        format!("{lang}-{}", rest.join("-"))
    }
}

fn resolve_available(catalogs: &HashMap<String, HashMap<String, String>>, locale: &str) -> String {
    if catalogs.contains_key(locale) {
        return locale.to_string();
    }

    if let Some((lang, _)) = locale.split_once('-') {
        if catalogs.contains_key(lang) {
            return lang.to_string();
        }
    }

    "en".to_string()
}

fn flatten_yaml(raw: &str) -> HashMap<String, String> {
    let value: Value = serde_norway::from_str(raw).unwrap_or(Value::Null);
    let mut out = HashMap::new();
    flatten_value("", &value, &mut out);
    out
}

fn flatten_value(prefix: &str, value: &Value, out: &mut HashMap<String, String>) {
    match value {
        Value::Mapping(map) => {
            for (key, child) in map {
                let Some(key) = key.as_str() else {
                    continue;
                };
                let next = if prefix.is_empty() {
                    key.to_string()
                } else {
                    format!("{prefix}.{key}")
                };
                flatten_value(&next, child, out);
            }
        }
        Value::String(text) => {
            out.insert(prefix.to_string(), text.clone());
        }
        Value::Number(num) => {
            out.insert(prefix.to_string(), num.to_string());
        }
        Value::Bool(flag) => {
            out.insert(prefix.to_string(), flag.to_string());
        }
        Value::Null | Value::Sequence(_) | Value::Tagged(_) => {}
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn flattens_nested_yaml_keys() {
        let catalog = flatten_yaml("tray:\n  disable: \"Disable\"\n");
        assert_eq!(catalog.get("tray.disable").map(String::as_str), Some("Disable"));
    }

    #[test]
    fn normalizes_underscore_locale() {
        assert_eq!(normalize_locale("zh_CN"), "zh-CN");
        assert_eq!(normalize_locale("en_US"), "en-US");
    }

    #[test]
    fn translates_zh_cn_tray_and_falls_back() {
        init(Some("zh-CN"));
        assert_eq!(t("tray.disable"), "禁用");
        assert_eq!(t("notify.running"), "Espanso 正在运行！");
        // Unknown key falls back to the key name after missing English too,
        // but known English-only keys would fall back to en — exercise missing:
        let missing = t("does.not.exist");
        assert_eq!(missing, "does.not.exist");
    }

    #[test]
    fn english_locale_works() {
        init(Some("en"));
        assert_eq!(t("tray.open_search"), "Open search bar");
    }

    #[test]
    fn en_and_zh_cn_catalogs_have_same_keys() {
        let en = flatten_yaml(EN_YAML);
        let zh = flatten_yaml(ZH_CN_YAML);
        let mut missing_in_zh: Vec<_> = en.keys().filter(|k| !zh.contains_key(*k)).cloned().collect();
        let mut missing_in_en: Vec<_> = zh.keys().filter(|k| !en.contains_key(*k)).cloned().collect();
        missing_in_zh.sort();
        missing_in_en.sort();
        assert!(
            missing_in_zh.is_empty(),
            "zh-CN missing keys: {missing_in_zh:?}"
        );
        assert!(
            missing_in_en.is_empty(),
            "en missing keys present in zh-CN: {missing_in_en:?}"
        );
    }
}
