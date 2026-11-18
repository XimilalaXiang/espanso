/*
 * This file is part of modulo.
 *
 * Copyright (C) 2020-2021 Federico Terzi
 *
 * modulo is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * modulo is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with modulo.  If not, see <https://www.gnu.org/licenses/>.
 */

#ifndef MODULO_COMMON
#define MODULO_COMMON

#define _UNICODE

#include <wx/wxprec.h>
#ifndef WX_PRECOMP
#include <wx/wx.h>
#endif

#include "i18n.h"

void setFrameIcon(wxString iconPath, wxFrame *frame);

void Activate(wxFrame *frame);

void SetupWindowStyle(wxFrame *frame);

// Translate a catalog key via espanso-i18n (UTF-8).
inline wxString Tr(const char *key) {
    espanso_i18n_ensure_initialized();
    char *translated = espanso_i18n_t(key);
    if (!translated) {
        return wxString::FromUTF8(key);
    }
    wxString result = wxString::FromUTF8(translated);
    espanso_i18n_string_free(translated);
    return result;
}

#endif