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

pub mod form;
pub mod search;
mod sys;
pub mod textview;
pub mod troubleshooting;
pub mod welcome;
pub mod wizard;

// Keep espanso-i18n linked so wx/C++ `Tr()` can call the FFI exports.
use espanso_i18n::{espanso_i18n_ensure_initialized, espanso_i18n_string_free, espanso_i18n_t};

#[used]
static _FORCE_LINK_ESPANSO_I18N: (
    extern "C" fn(),
    unsafe extern "C" fn(*const std::os::raw::c_char) -> *mut std::os::raw::c_char,
    unsafe extern "C" fn(*mut std::os::raw::c_char),
) = (
    espanso_i18n_ensure_initialized,
    espanso_i18n_t,
    espanso_i18n_string_free,
);
