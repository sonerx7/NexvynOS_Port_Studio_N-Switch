/* How to play: one card per control scheme, one line per action.
 * Shared by every port launcher. Needs imgui.h and nxn_os_ui.h included first, and the
 * port's generated nx_experience.h (python _PortStudioMain/tools/port_studio.py experience generate <port>).
 * The text is looked up with nxn_tr() from lang keys the same command generates
 * (--merge-lang lang), so a changed binding or a new gesture shows up without editing this file. */
#ifndef NX_HOWTO_UI_H
#define NX_HOWTO_UI_H

#include <stdio.h>
#include <string.h>
#include "nx_experience.h"
#include "nx_launcher_ui.h"

/* zoom_on: false hides the pinch/zoom line while the port's zoom setting is switched off. */
static inline void nx_howto_draw(const nxn_ui_tokens &tok, bool zoom_on = true) {
    static const char *scheme_keys[3] = { "howto.scheme.gamepad", "howto.scheme.touch", "howto.scheme.kbm" };
    nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr(NX_HOWTO_INTRO_KEY));
    nxn_os_gap(NXN_OS_SP_S);
    /* One card per scheme with its title inside the card; 3 columns when wide, 1 when narrow. */
    /* Docked has no touch screen: gamepad first, then keyboard and mouse, touch last. Handheld: touch first. */
    static const int order_docked[3] = { 0, 2, 1 };
    static const int order_handheld[3] = { 1, 0, 2 };
    const int *order = nx_ui_docked() ? order_docked : order_handheld;
    nx_grid_begin("##nx_howto_grid", 3);
    for (int slot = 0; slot < 3; ++slot) {
        const int scheme = order[slot];
        nx_grid_next();
        char card_id[32];
        snprintf(card_id, sizeof(card_id), "howto_card_%d", scheme);
        nxn_os_card_begin(card_id, tok);
        nxn_os_text(NXN_OS_TEXT_HEADER, nxn_tr(scheme_keys[scheme]));
        nxn_os_gap(NXN_OS_SP_XS);
        nxn_os_separator(tok);
        nxn_os_gap(NXN_OS_SP_XS);
        for (int row = 0; row < NX_HOWTO_ROW_COUNT; ++row) {
            if (nx_howto_rows[row].key[scheme]) {
                nxn_os_text_wrapped(NXN_OS_TEXT_BODY, nxn_tr(nx_howto_rows[row].key[scheme]));
                nxn_os_gap(NXN_OS_SP_XS);
            }
        }
        if (scheme == 1 && zoom_on && strcmp(NX_ZOOM_METHOD, "none") != 0) {
            nxn_os_separator(tok);
            nxn_os_gap(NXN_OS_SP_XS);
            nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr(NX_HOWTO_ZOOM_KEY));
        }
        nxn_os_card_end();
    }
    nx_grid_end();
}

#endif
