# Espanso locales

UI translation catalogs live inside the crate:

- [`espanso-i18n/locales/en.yml`](../espanso-i18n/locales/en.yml)
- [`espanso-i18n/locales/zh-CN.yml`](../espanso-i18n/locales/zh-CN.yml)

They are embedded into the binary from that crate path so Nix/`cargo` package
filters that only include `espanso-*` crates still see the files.

See [`espanso-i18n/locales/README.md`](../espanso-i18n/locales/README.md) for
catalog conventions used by sync / auto-translate bots.
