#include "launcher.h"

#include <cstdio>
#include <cstring>
#include <nexvyn/nexvyn_native.h>
#include "imgui.h"
#include <nexvyn/nxn_os_ui.h>

static char game_dir[512];
static bool cstrike_ready;
static bool valve_ready;

static bool readable_wad(const char* name) {
    char path[600];
    const int length = snprintf(path, sizeof(path), "%s/%s", game_dir, name);
    if (!game_dir[0] || length < 0 || static_cast<size_t>(length) >= sizeof(path)) return false;
    FILE* file = fopen(path, "rb");
    if (!file) return false;
    unsigned char header[12];
    const bool read = fread(header, 1, sizeof(header), file) == sizeof(header);
    fclose(file);
    return read && (!memcmp(header, "WAD3", 4) || !memcmp(header, "WAD2", 4));
}

static void verify() {
    cstrike_ready = readable_wad("cstrike/cstrike.wad");
    valve_ready = readable_wad("valve/halflife.wad");
}

static void choose_folder() {
    nxn_pick_params picker = NXN_STRUCT_INIT(nxn_pick_params);
    picker.kind = NXN_PICK_FOLDER;
    picker.flags = NXN_PICK_REMEMBER;
    picker.title = nxn_tr("btn.browse");
    char chosen[sizeof(game_dir)];
    if (nxn_pick(&picker, chosen, sizeof(chosen)) != NXN_OK || !chosen[0]) return;
    snprintf(game_dir, sizeof(game_dir), "%s", chosen);
    verify();
    if (nxn_fs_write(NXN_DIR_DATA, "game_dir.txt", game_dir, strlen(game_dir)) != NXN_OK)
        nxn_log(NXN_LOG_WARN, "Could not save the selected CS 1.6 folder.");
}

void cs16_load_launcher() {
    game_dir[0] = 0;
    if (nxn_fs_path(NXN_DIR_BUNDLE, "game", game_dir, sizeof(game_dir)) == NXN_OK) {
        verify();
        if (cstrike_ready && valve_ready) return;
    }
    game_dir[0] = 0;
    size_t read = 0;
    if (nxn_fs_read(NXN_DIR_DATA, "game_dir.txt", game_dir, sizeof(game_dir) - 1, &read) == NXN_OK) {
        game_dir[read] = 0;
        int granted = 0;
        if (nxn_grant_check(game_dir, &granted) != NXN_OK || !granted) game_dir[0] = 0;
    } else {
        game_dir[0] = 0;
    }
    verify();
}

void cs16_draw_launcher(const nxn_ui_tokens& tokens) {
    nxn_os_text(NXN_OS_TEXT_TITLE, nxn_tr("app.title"));
    nxn_os_text_wrapped(NXN_OS_TEXT_BODY, nxn_tr("status.engine_missing"));
    nxn_os_gap(NXN_OS_SP_S);
    nxn_os_card_begin("game-data", tokens);
    nxn_os_section_label(nxn_tr("sec.game_path"), tokens);
    nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, game_dir[0] ? game_dir : nxn_tr("lbl.no_dir"));
    nxn_os_kv_row("cstrike/cstrike.wad", nxn_tr(cstrike_ready ? "status.ready" : "status.data_missing"), tokens, false);
    nxn_os_kv_row("valve/halflife.wad", nxn_tr(valve_ready ? "status.ready" : "status.data_missing"), tokens, false);
    nxn_os_gap(NXN_OS_SP_S);
    nxn_os_row_begin();
    if (nxn_os_button(nxn_tr("btn.browse"), NXN_OS_BTN_PRIMARY, tokens)) choose_folder();
    if (nxn_os_button(nxn_tr("btn.verify"), NXN_OS_BTN_DEFAULT, tokens)) verify();
    nxn_os_row_end();
    nxn_os_card_end();
}
