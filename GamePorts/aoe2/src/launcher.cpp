#include "launcher.h"

#include <cstdio>
#include <cstring>
#include <nexvyn/nexvyn_native.h>
#include "imgui.h"
#include <nexvyn/nxn_os_ui.h>
#include "nx_launcher_ui.h"
#include "nx_howto_ui.h"

static char game_dir[512];
static bool graphics_drs_ready;
static bool empires2_dat_ready;
static bool exe_ready;
static bool show_fps;
static int active_tab;
static uint64_t toast_until;

static bool readable_file(const char* rel, size_t min_size) {
    char path[600];
    const int length = snprintf(path, sizeof(path), "%s/%s", game_dir, rel);
    if (!game_dir[0] || length < 0 || static_cast<size_t>(length) >= sizeof(path)) return false;
    FILE* file = fopen(path, "rb");
    if (!file) return false;
    fseek(file, 0, SEEK_END);
    long size = ftell(file);
    fclose(file);
    return size >= (long)min_size;
}

static void verify() {
    graphics_drs_ready = readable_file("data/graphics.drs", 1024) || readable_file("Data/graphics.drs", 1024);
    empires2_dat_ready = readable_file("data/empires2.dat", 1024) || readable_file("Data/empires2.dat", 1024) ||
                         readable_file("data/empires2_x1.dat", 1024) || readable_file("Data/empires2_x1.dat", 1024);
    exe_ready = readable_file("empires2.exe", 1024) || readable_file("age2_x1/age2_x1.exe", 1024) || readable_file("age2_x1.exe", 1024);
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
        nxn_log(NXN_LOG_WARN, "Could not save the selected Age of Empires II folder.");
}

static void load_settings() {
    char buf[64] = {0};
    size_t read = 0;
    if (nxn_fs_read(NXN_DIR_DATA, "launcher.cfg", buf, sizeof(buf) - 1, &read) == NXN_OK) {
        buf[read] = 0;
        show_fps = strstr(buf, "show_fps=1") != nullptr;
    }
}

static void save_settings() {
    char buf[32];
    int n = snprintf(buf, sizeof(buf), "show_fps=%d\n", show_fps ? 1 : 0);
    if (nxn_fs_write(NXN_DIR_DATA, "launcher.cfg", buf, (size_t)n) != NXN_OK)
        nxn_log(NXN_LOG_WARN, "Could not save the launcher settings.");
}

void aoe2_load_launcher() {
    load_settings();
    game_dir[0] = 0;
    if (nxn_fs_path(NXN_DIR_BUNDLE, "game", game_dir, sizeof(game_dir)) == NXN_OK) {
        verify();
        if (graphics_drs_ready && empires2_dat_ready) return;
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

static bool files_ok() { return graphics_drs_ready && empires2_dat_ready && exe_ready; }

/* Returns true when the player pressed Exit. */
bool aoe2_draw_launcher(const nxn_ui_tokens& tokens) {
    bool quit = false;
    nx_hero_desc hero = {};
    hero.title = nxn_tr("app.title");
    hero.subtitle = nxn_tr("app.subtitle");
    hero.play_label = nxn_tr(files_ok() ? "btn.play" : "btn.browse");
    hero.exit_label = nxn_tr("btn.quit");
    int action = nx_hero(hero, tokens, [&]() {
        nxn_os_badge(nxn_tr(files_ok() ? "status.ready" : "status.data_missing"), files_ok() ? 0xFF2ECC71u : 0xFFE74C3Cu, tokens);
        nxn_os_badge(nxn_tr("status.engine_short"), 0xFFF39C12u, tokens);
    });
    if (action == NX_HERO_PLAY) {
        if (files_ok()) toast_until = nxn_time_ns() + 5000000000ull;
        else choose_folder();
    }
    if (action == NX_HERO_EXIT) quit = true;
    nxn_os_gap(NXN_OS_SP_S);
    if (nxn_time_ns() < toast_until) {
        nxn_os_card_begin("toast", tokens);
        nxn_os_text_colored(NXN_OS_TEXT_BODY, nxn_tr("status.engine_missing"), tokens.accent);
        nxn_os_card_end();
        nxn_os_gap(NXN_OS_SP_XS);
    }

    const char* labels[3] = { nxn_tr("tab.overview"), nxn_tr(NX_HOWTO_TITLE_KEY), nxn_tr("tab.files") };
    nx_tabs("##tabs", labels, 3, &active_tab, tokens);
    nxn_os_gap(NXN_OS_SP_S);
    ImGui::BeginChild("##tab_body", ImVec2(0, 0), false);

    if (active_tab == 0) {
        nx_grid_begin("##ov", 2);
        nx_grid_next();
        nxn_os_section_label(nxn_tr("sec.quick"), tokens);
        nxn_os_card_begin("quick", tokens);
        if (nx_fps_row(&show_fps, nxn_tr("lbl.show_fps"), nxn_tr("lbl.show_fps_hint"))) save_settings();
        nxn_os_card_end();
        nx_grid_next();
        nxn_os_section_label(nxn_tr("sec.game_folder"), tokens);
        nxn_os_card_begin("folder", tokens);
        nxn_os_row_begin();
        if (nxn_os_button(nxn_tr("btn.browse"), NXN_OS_BTN_PRIMARY, tokens)) choose_folder();
        if (nxn_os_button(nxn_tr("btn.verify"), NXN_OS_BTN_DEFAULT, tokens)) verify();
        nxn_os_row_end();
        nxn_os_separator(tokens);
        nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, game_dir[0] ? game_dir : nxn_tr("lbl.no_dir"));
        nxn_os_gap(NXN_OS_SP_XS);
        nxn_os_text_colored(NXN_OS_TEXT_BODY, nxn_tr(files_ok() ? "lbl.verify_ok" : "lbl.verify_fail"),
                            files_ok() ? 0xFF2ECC71u : 0xFFE74C3Cu);
        nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("status.engine_missing"));
        nxn_os_card_end();
        nx_grid_end();
    } else if (active_tab == 1) {
        nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("howto.planned"));
        nxn_os_gap(NXN_OS_SP_XS);
        nx_howto_draw(tokens, false);
    } else {
        nx_grid_begin("##files", 2);
        nx_grid_next();
        nxn_os_card_begin("files_a", tokens);
        nxn_os_kv_row("data/graphics.drs", nxn_tr(graphics_drs_ready ? "file.found" : "file.missing"), tokens, false);
        nxn_os_kv_row("data/empires2.dat", nxn_tr(empires2_dat_ready ? "file.found" : "file.missing"), tokens, false);
        nxn_os_kv_row("empires2.exe", nxn_tr(exe_ready ? "file.found" : "file.missing"), tokens, false);
        nxn_os_card_end();
        nx_grid_next();
        nxn_os_card_begin("files_b", tokens);
        if (game_dir[0]) nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, game_dir);
        nxn_os_text_colored(NXN_OS_TEXT_BODY, nxn_tr(files_ok() ? "lbl.verify_ok" : "lbl.verify_fail"),
                            files_ok() ? 0xFF2ECC71u : 0xFFE74C3Cu);
        nxn_os_card_end();
        nx_grid_end();
    }
    ImGui::EndChild();
    return quit;
}
