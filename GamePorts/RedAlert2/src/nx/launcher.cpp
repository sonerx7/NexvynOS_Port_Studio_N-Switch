/*
 * Red Alert 2: Yuri's Revenge - Nexvyn OS Native SDK 1.2 Launcher (v1.2)
 *
 * Clean, focused Dear ImGui + <nexvyn/nxn_os_ui.h> + <nexvyn/nxn_imgui_input.h> launcher:
 *   - Game folder picker (nxn_pick) + live file & PE timestamp verification
 *   - Built-in Turkish patch (RA2.CSF) non-destructive overlay injection + 8-language UI
 *   - Yuri's Revenge Unmodded / Modded selector
 *   - Nexvyn OS Stable Profile (default ON & locked; uncheck to unlock all tuning + Reset)
 *   - Auto Dock / Handheld Resolution toggle (default OFF) with OS info popup (nxn_dialog)
 *   - Dedicated Controls sub-tabs: Gamepad (full button remapping), Touchscreen, Keyboard & Mouse
 *   - Live diagnostics & log tab with clipboard copy
 */

#include "launcher.h"

#include <glad/glad.h>
#include <ctype.h>
#include <dirent.h>
#include <errno.h>
#include <math.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <sys/stat.h>
#include <unistd.h>

#include <nexvyn/nexvyn_native.h>
#include "imgui.h"
#include "imgui_impl_opengl3.h"
#include <nexvyn/nxn_os_ui.h>
#include "nx_launcher_ui.h" /* hero, grid, tabs: the Port Studio launcher standard */
#include "nx_howto_ui.h" /* shared how-to tab; data generated from port.json by port_studio.py experience */

#define RA2_WANT_STAMP 0x3BDF544Eu

/* ---- Resolution & option tables ---- */
static const int k_res_list[][2] = {
    { 1280, 720  }, /* 0: Switch Handheld Native 16:9 (Default) */
    { 1920, 1080 }, /* 1: Switch Docked Native 16:9 */
    { 1024, 768  }, /* 2: Classic 4:3 High */
    { 800,  600  }, /* 3: Classic 4:3 */
    { 1366, 768  }, /* 4: 16:9 Mid */
    { 1600, 900  }  /* 5: 16:9 High */
};
static const char* const k_res_labels[] = {
    "1280 x 720 (Switch Native 16:9)",
    "1920 x 1080 (Docked Full HD 16:9)",
    "1024 x 768 (4:3)",
    "800 x 600 (4:3 Classic)",
    "1366 x 768 (16:9)",
    "1600 x 900 (16:9)"
};
static const int k_res_count = (int)(sizeof(k_res_list) / sizeof(k_res_list[0]));

static const char* const k_scale_labels[] = {
    "Sharp (Default)", "Smooth (Bilinear)", "Nearest (Pixel)", "Integer", "CRT Scanlines"
};

/* ---- Ring-buffer diagnostics log ---- */
#define RA2_LOG_MAX_LINES 160
#define RA2_LOG_LINE_LEN  220
static char g_log_lines[RA2_LOG_MAX_LINES][RA2_LOG_LINE_LEN];
static int  g_log_head = 0;
static int  g_log_count = 0;

extern "C" void ra2_log_append(const char *fmt, ...) {
    char buf[RA2_LOG_LINE_LEN];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);

    int slot = (g_log_head + g_log_count) % RA2_LOG_MAX_LINES;
    if (g_log_count == RA2_LOG_MAX_LINES) {
        g_log_head = (g_log_head + 1) % RA2_LOG_MAX_LINES;
    } else {
        g_log_count++;
    }
    snprintf(g_log_lines[slot], RA2_LOG_LINE_LEN, "%s", buf);
    nxn_log(NXN_LOG_INFO, "[RA2] %s", buf);
}

/* ---- Defaults & stable profile ---- */
static void set_control_defaults(ra2_config_t *cfg) {
    cfg->rstick_pan = 1;
    cfg->twofinger_pan = 1;
    cfg->dpad_pan = 1;
    cfg->wasd_pan = 1;
    cfg->edge_scroll = 1;
    cfg->scroll_rate = 4;
    cfg->cursor_speed = 12.0f;
    cfg->deadzone = 0.16f;
    cfg->y_action = 0;  /* Deploy (D) */
    cfg->l_action = 0;  /* Precision Cursor */
    cfg->r_action = 0;  /* Fast Cursor Boost */
    cfg->l3_action = 0; /* Jump to Base (H) */
    cfg->r3_action = 0; /* Select Same Type (T) */
    cfg->longpress_rc = 1;
    cfg->twofinger_rc = 1;
    cfg->touch_wheel = 0;   /* untested in the running game: opt in */
    cfg->touch_pan_sens = 1.0f;
    cfg->touch_pan_invert = 1;
    cfg->confine_mouse = 1;
}

extern "C" void ra2_config_set_stable_defaults(ra2_config_t *cfg, int keep_paths) {
    char saved_dir[512] = {0};
    char saved_mod[128] = {0};
    int saved_lang = 0;
    int saved_modded = 0;
    if (keep_paths) {
        snprintf(saved_dir, sizeof(saved_dir), "%s", cfg->game_dir);
        snprintf(saved_mod, sizeof(saved_mod), "%s", cfg->mod_name);
        saved_lang = cfg->game_lang;
        saved_modded = cfg->yuri_modded;
    }
    memset(cfg, 0, sizeof(*cfg));
    if (keep_paths) {
        snprintf(cfg->game_dir, sizeof(cfg->game_dir), "%s", saved_dir);
        snprintf(cfg->mod_name, sizeof(cfg->mod_name), "%s", saved_mod);
        cfg->game_lang = saved_lang;
        cfg->yuri_modded = saved_modded;
    }

    cfg->stable_profile = 1;
    cfg->fullscreen = 1;
    cfg->auto_dock_res = 0; /* Default OFF per user request */
    cfg->res_index = 0;     /* 1280x720 16:9 Switch Native */
    cfg->res_w = k_res_list[0][0];
    cfg->res_h = k_res_list[0][1];
    cfg->scale_index = 0;   /* sharp */
    cfg->fit_mode = 0;      /* fill fullscreen (no bars) */
    cfg->hd_voxels = 0;     /* off for rock-solid 60 FPS */
    cfg->detail_level = 2;
    cfg->skip_intro = 1;

    cfg->vol_sfx = 0.65f;
    cfg->vol_voice = 0.70f;
    cfg->vol_music = 0.45f;

    set_control_defaults(cfg);
}

static void apply_stable_lock(ra2_config_t *cfg) {
    if (!cfg->stable_profile) return;
    cfg->fullscreen = 1;
    if (!cfg->auto_dock_res) {
        cfg->res_index = 0;
        cfg->res_w = 1280;
        cfg->res_h = 720;
    }
    cfg->scale_index = 0;
    cfg->fit_mode = 0;
    cfg->hd_voxels = 0;
    cfg->detail_level = 2;
    cfg->skip_intro = 1;
}

/* ---- Atomic settings load/save via nxn_fs ---- */
static void config_save(const ra2_config_t *c) {
    char buf[2560];
    int n = snprintf(buf, sizeof(buf),
        "version=3\n"
        "game_dir=%s\n"
        "mod_name=%s\n"
        "stable_profile=%d\n"
        "fullscreen=%d\n"
        "auto_dock_res=%d\n"
        "res_index=%d\n"
        "scale_index=%d\n"
        "fit_mode=%d\n"
        "hd_voxels=%d\n"
        "detail_level=%d\n"
        "skip_intro=%d\n"
        "show_fps=%d\n"
        "game_lang=%d\n"
        "yuri_modded=%d\n"
        "vol_sfx=%.3f\n"
        "vol_voice=%.3f\n"
        "vol_music=%.3f\n"
        "rstick_pan=%d\n"
        "twofinger_pan=%d\n"
        "dpad_pan=%d\n"
        "wasd_pan=%d\n"
        "edge_scroll=%d\n"
        "scroll_rate=%d\n"
        "cursor_speed=%.2f\n"
        "deadzone=%.3f\n"
        "y_action=%d\n"
        "l_action=%d\n"
        "r_action=%d\n"
        "l3_action=%d\n"
        "r3_action=%d\n"
        "longpress_rc=%d\n"
        "twofinger_rc=%d\n"
        "touch_wheel=%d\n"
        "touch_pan_sens=%.2f\n"
        "touch_pan_invert=%d\n"
        "confine_mouse=%d\n",
        c->game_dir, c->mod_name,
        c->stable_profile, c->fullscreen, c->auto_dock_res, c->res_index, c->scale_index, c->fit_mode,
        c->hd_voxels, c->detail_level, c->skip_intro, c->show_fps,
        c->game_lang, c->yuri_modded,
        c->vol_sfx, c->vol_voice, c->vol_music,
        c->rstick_pan, c->twofinger_pan, c->dpad_pan, c->wasd_pan, c->edge_scroll, c->scroll_rate,
        c->cursor_speed, c->deadzone,
        c->y_action, c->l_action, c->r_action, c->l3_action, c->r3_action,
        c->longpress_rc, c->twofinger_rc, c->touch_wheel, c->touch_pan_sens, c->touch_pan_invert, c->confine_mouse
    );
    if (n > 0) {
        if (nxn_fs_write(NXN_DIR_DATA, "ra2_launcher.cfg", buf, (size_t)n) != NXN_OK) {
            ra2_log_append("WARN: failed to save ra2_launcher.cfg");
        }
    }
}

static void config_load(ra2_config_t *c) {
    ra2_config_set_stable_defaults(c, 0);
    char buf[2560] = {0};
    size_t got = 0;
    if (nxn_fs_read(NXN_DIR_DATA, "ra2_launcher.cfg", buf, sizeof(buf) - 1, &got) != NXN_OK || !got) {
        ra2_log_append("First launch: loaded Nexvyn OS Stable Profile defaults.");
        return;
    }
    buf[got] = 0;
    char *p = buf;
    while (*p) {
        char *e = strchr(p, '\n');
        if (e) *e = 0;
        size_t len = strlen(p);
        if (len > 0 && p[len - 1] == '\r') p[len - 1] = 0;
        char *eq = strchr(p, '=');
        if (eq) {
            *eq = 0;
            const char *k = p;
            const char *v = eq + 1;
            if (!strcmp(k, "game_dir")) snprintf(c->game_dir, sizeof(c->game_dir), "%s", v);
            else if (!strcmp(k, "mod_name")) snprintf(c->mod_name, sizeof(c->mod_name), "%s", v);
            else if (!strcmp(k, "stable_profile")) c->stable_profile = atoi(v) != 0;
            else if (!strcmp(k, "fullscreen")) c->fullscreen = atoi(v) != 0;
            else if (!strcmp(k, "auto_dock_res")) c->auto_dock_res = atoi(v) != 0;
            else if (!strcmp(k, "res_index")) c->res_index = atoi(v);
            else if (!strcmp(k, "scale_index")) c->scale_index = atoi(v);
            else if (!strcmp(k, "fit_mode")) c->fit_mode = atoi(v);
            else if (!strcmp(k, "hd_voxels")) c->hd_voxels = atoi(v);
            else if (!strcmp(k, "detail_level")) c->detail_level = atoi(v);
            else if (!strcmp(k, "skip_intro")) c->skip_intro = atoi(v) != 0;
            else if (!strcmp(k, "show_fps")) c->show_fps = atoi(v) != 0;
            else if (!strcmp(k, "game_lang")) c->game_lang = atoi(v);
            else if (!strcmp(k, "use_turkish_csf")) { if (atoi(v)) c->game_lang = 2; }
            else if (!strcmp(k, "yuri_modded")) c->yuri_modded = atoi(v) != 0;
            else if (!strcmp(k, "vol_sfx")) c->vol_sfx = (float)atof(v);
            else if (!strcmp(k, "vol_voice")) c->vol_voice = (float)atof(v);
            else if (!strcmp(k, "vol_music")) c->vol_music = (float)atof(v);
            else if (!strcmp(k, "rstick_pan")) c->rstick_pan = atoi(v) != 0;
            else if (!strcmp(k, "twofinger_pan")) c->twofinger_pan = atoi(v) != 0;
            else if (!strcmp(k, "dpad_pan")) c->dpad_pan = atoi(v) != 0;
            else if (!strcmp(k, "wasd_pan")) c->wasd_pan = atoi(v) != 0;
            else if (!strcmp(k, "edge_scroll")) c->edge_scroll = atoi(v) != 0;
            else if (!strcmp(k, "scroll_rate")) c->scroll_rate = atoi(v);
            else if (!strcmp(k, "cursor_speed")) c->cursor_speed = (float)atof(v);
            else if (!strcmp(k, "deadzone")) c->deadzone = (float)atof(v);
            else if (!strcmp(k, "y_action")) c->y_action = atoi(v);
            else if (!strcmp(k, "l_action")) c->l_action = atoi(v);
            else if (!strcmp(k, "r_action")) c->r_action = atoi(v);
            else if (!strcmp(k, "l3_action")) c->l3_action = atoi(v);
            else if (!strcmp(k, "r3_action")) c->r3_action = atoi(v);
            else if (!strcmp(k, "longpress_rc")) c->longpress_rc = atoi(v) != 0;
            else if (!strcmp(k, "twofinger_rc")) c->twofinger_rc = atoi(v) != 0;
            else if (!strcmp(k, "touch_wheel")) c->touch_wheel = atoi(v) != 0;
            else if (!strcmp(k, "touch_pan_sens")) c->touch_pan_sens = (float)atof(v);
            else if (!strcmp(k, "touch_pan_invert")) c->touch_pan_invert = atoi(v) != 0;
            else if (!strcmp(k, "confine_mouse")) c->confine_mouse = atoi(v) != 0;
        }
        if (!e) break;
        p = e + 1;
    }
    if (c->res_index < 0 || c->res_index >= k_res_count) c->res_index = 0;
    c->res_w = k_res_list[c->res_index][0];
    c->res_h = k_res_list[c->res_index][1];
    if (c->scale_index < 0 || c->scale_index > 4) c->scale_index = 0;
    if (c->fit_mode < 0 || c->fit_mode > 2) c->fit_mode = 0;
    if (c->hd_voxels < 0 || c->hd_voxels > 2) c->hd_voxels = 0;
    if (c->detail_level < 0 || c->detail_level > 2) c->detail_level = 2;
    if (c->game_lang < 0 || c->game_lang > 3) c->game_lang = 0;
    if (c->scroll_rate < 1 || c->scroll_rate > 6) c->scroll_rate = 4;
    if (c->cursor_speed < 4.0f || c->cursor_speed > 24.0f) c->cursor_speed = 12.0f;
    if (c->deadzone < 0.05f || c->deadzone > 0.35f) c->deadzone = 0.16f;
    if (c->y_action < 0 || c->y_action > 3) c->y_action = 0;
    if (c->l_action < 0 || c->l_action > 2) c->l_action = 0;
    if (c->r_action < 0 || c->r_action > 2) c->r_action = 0;
    if (c->l3_action < 0 || c->l3_action > 1) c->l3_action = 0;
    if (c->r3_action < 0 || c->r3_action > 2) c->r3_action = 0;
    if (c->touch_pan_sens < 0.5f || c->touch_pan_sens > 2.0f) c->touch_pan_sens = 1.0f;
    apply_stable_lock(c);
    ra2_log_append("Loaded saved launcher configuration.");
}

/* ---- Case-insensitive file check & PE timestamp verification ---- */
struct VerifyState {
    bool checked = false;
    bool ok = false;
    bool has_gamemd = false;
    bool stamp_ok = false;
    uint32_t stamp = 0;
    bool has_ra2_mix = false;
    bool has_ra2md_mix = false;
    bool has_langmd_mix = false;
    bool has_thememd_mix = false;
    bool has_tr_csf_bundle = false;
};

static bool find_file_ci(const char *dir, const char *want, char *out_full, size_t cap) {
    if (!dir || !dir[0]) return false;
    DIR *d = opendir(dir);
    if (!d) return false;
    struct dirent *e;
    bool found = false;
    while ((e = readdir(d)) != NULL) {
        if (!strcasecmp(e->d_name, want)) {
            if (out_full && cap) snprintf(out_full, cap, "%s/%s", dir, e->d_name);
            found = true;
            break;
        }
    }
    closedir(d);
    return found;
}

static uint32_t read_pe_stamp(const char *path) {
    uint8_t head[4096] = {0};
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    size_t n = fread(head, 1, sizeof(head), f);
    fclose(f);
    if (n < 0x40 || head[0] != 'M' || head[1] != 'Z') return 0;
    uint32_t nt = *(const uint32_t *)(head + 0x3C);
    if (!nt || nt + 12 >= n) return 0;
    return *(const uint32_t *)(head + nt + 8);
}

static bool find_bundle_asset(const char *rel, char *out, size_t cap) {
    if (nxn_fs_path(NXN_DIR_BUNDLE, rel, out, cap) == NXN_OK && access(out, R_OK) == 0) return true;
    if (access(rel, R_OK) == 0) { snprintf(out, cap, "%s", rel); return true; }
    return false;
}

static void verify_game_dir(const char *dir, VerifyState &vs) {
    vs = VerifyState();
    vs.checked = true;
    char tr_path[512];
    vs.has_tr_csf_bundle = find_bundle_asset("assets/RA2.CSF", tr_path, sizeof(tr_path)) ||
                           find_bundle_asset("RA2.CSF", tr_path, sizeof(tr_path));

    if (!dir || !dir[0]) {
        ra2_log_append("Verify: no game directory configured.");
        return;
    }
    char exe_path[600] = {0};
    vs.has_gamemd = find_file_ci(dir, "gamemd.exe", exe_path, sizeof(exe_path));
    if (vs.has_gamemd) {
        vs.stamp = read_pe_stamp(exe_path);
        vs.stamp_ok = (vs.stamp == RA2_WANT_STAMP);
    }
    vs.has_ra2_mix = find_file_ci(dir, "ra2.mix", NULL, 0);
    vs.has_ra2md_mix = find_file_ci(dir, "ra2md.mix", NULL, 0);
    vs.has_langmd_mix = find_file_ci(dir, "langmd.mix", NULL, 0);
    vs.has_thememd_mix = find_file_ci(dir, "thememd.mix", NULL, 0);

    const bool complete = vs.has_gamemd && vs.has_ra2_mix && vs.has_ra2md_mix;
    vs.ok = complete && vs.stamp_ok;
    ra2_log_append("Verify [%s]: gamemd=%d (0x%08X) ra2.mix=%d ra2md.mix=%d langmd=%d -> %s",
                   dir, vs.has_gamemd, vs.stamp, vs.has_ra2_mix, vs.has_ra2md_mix,
                   vs.has_langmd_mix, vs.ok ? "OK" : complete ? "UNSUPPORTED EXECUTABLE" : "MISSING FILES");
}

static void autodetect_game_dir(ra2_config_t *cfg) {
    if (cfg->game_dir[0]) {
        VerifyState tmp;
        verify_game_dir(cfg->game_dir, tmp);
        if (tmp.ok) return;
    }
    char bundle_game[512] = {0};
    nxn_fs_path(NXN_DIR_BUNDLE, "game", bundle_game, sizeof(bundle_game));
    const char *candidates[] = {
        bundle_game,
        "sdmc:/NexvynOS/Applications/com.sonerx7.redalert2.nxvapp/game",
        "sdmc:/switch/openra2",
        "sdmc:/switch/ra2",
        "sdmc:/games/ra2",
        "game"
    };
    for (int i = 0; i < (int)(sizeof(candidates) / sizeof(candidates[0])); i++) {
        if (!candidates[i] || !candidates[i][0]) continue;
        if (find_file_ci(candidates[i], "gamemd.exe", NULL, 0)) {
            snprintf(cfg->game_dir, sizeof(cfg->game_dir), "%s", candidates[i]);
            ra2_log_append("Auto-detected game folder: %s", cfg->game_dir);
            return;
        }
    }
}

/* ---- Mod discovery ---- */
#define MAX_LAUNCHER_MODS 32
static char g_mod_list[MAX_LAUNCHER_MODS][128];
static const char* g_mod_ptrs[MAX_LAUNCHER_MODS];
static int g_mod_count = 0;

static void scan_mods(const char *game_dir) {
    g_mod_count = 0;
    char roots[3][512];
    int nroots = 0;
    if (game_dir && game_dir[0]) {
        snprintf(roots[nroots++], 512, "%s/mods/yr", game_dir);
        snprintf(roots[nroots++], 512, "%s/mods", game_dir);
    }
    char data_mods[512] = {0};
    if (nxn_fs_path(NXN_DIR_DATA, "mods/yr", data_mods, sizeof(data_mods)) == NXN_OK) {
        snprintf(roots[nroots++], 512, "%s", data_mods);
    }
    for (int r = 0; r < nroots; r++) {
        DIR *d = opendir(roots[r]);
        if (!d) continue;
        struct dirent *e;
        while ((e = readdir(d)) != NULL && g_mod_count < MAX_LAUNCHER_MODS) {
            if (e->d_name[0] == '.' || !strcasecmp(e->d_name, "yr") || !strcasecmp(e->d_name, "ra2")) continue;
            char full[800];
            struct stat st;
            int length = snprintf(full, sizeof(full), "%s/%s", roots[r], e->d_name);
            if (length < 0 || (size_t)length >= sizeof(full)) continue;
            if (stat(full, &st) == 0 && S_ISDIR(st.st_mode)) {
                bool dup = false;
                for (int k = 0; k < g_mod_count; k++) {
                    if (!strcasecmp(g_mod_list[k], e->d_name)) { dup = true; break; }
                }
                if (!dup) {
                    snprintf(g_mod_list[g_mod_count], 128, "%.127s", e->d_name);
                    g_mod_ptrs[g_mod_count] = g_mod_list[g_mod_count];
                    g_mod_count++;
                }
            }
        }
        closedir(d);
    }
}

/* ---- GL Texture loader for logo.nximg ---- */
struct GlImage {
    GLuint tex = 0;
    int w = 0, h = 0;
};

static void load_nximg(const char *rel, GlImage &img) {
    char path[512];
    if (!find_bundle_asset(rel, path, sizeof(path))) return;
    FILE *f = fopen(path, "rb");
    if (!f) return;
    uint8_t hdr[12];
    if (fread(hdr, 1, 12, f) != 12 || memcmp(hdr, "NXIM", 4) != 0) {
        fclose(f);
        return;
    }
    uint32_t w = *(const uint32_t *)(hdr + 4);
    uint32_t h = *(const uint32_t *)(hdr + 8);
    if (w == 0 || h == 0 || w > 1024 || h > 1024) { fclose(f); return; }
    size_t sz = (size_t)w * (size_t)h * 4;
    uint8_t *px = (uint8_t *)malloc(sz);
    if (!px) { fclose(f); return; }
    if (fread(px, 1, sz, f) != sz) { free(px); fclose(f); return; }
    fclose(f);

    GLuint t = 0;
    glGenTextures(1, &t);
    glBindTexture(GL_TEXTURE_2D, t);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, (GLsizei)w, (GLsizei)h, 0, GL_RGBA, GL_UNSIGNED_BYTE, px);
    glBindTexture(GL_TEXTURE_2D, 0);
    free(px);

    img.tex = t;
    img.w = (int)w;
    img.h = (int)h;
}

static void free_glimg(GlImage &img) {
    if (img.tex) { glDeleteTextures(1, &img.tex); img.tex = 0; }
    img.w = img.h = 0;
}

/* ---- INI writer & Turkish RA2.CSF / Mod overlay builder ---- */
static void ini_set_key(const char *path, const char *sec, const char *key, const char *val) {
    FILE *f = fopen(path, "rb");
    char *in = NULL;
    size_t n = 0;
    if (f) {
        fseek(f, 0, SEEK_END);
        long sz = ftell(f);
        rewind(f);
        in = (char *)malloc(sz > 0 ? (size_t)sz + 1 : 1);
        n = in ? fread(in, 1, sz > 0 ? (size_t)sz : 0, f) : 0;
        if (in) in[n] = 0;
        fclose(f);
    }
    char tmp_path[640];
    snprintf(tmp_path, sizeof(tmp_path), "%s.tmp", path);
    FILE *o = fopen(tmp_path, "wb");
    if (!o) { free(in); return; }
    size_t kl = strlen(key), sl = strlen(sec);
    int in_sec = 0, done = 0;
    for (char *p = in; p && *p;) {
        char *e = strchr(p, '\n');
        size_t len = e ? (size_t)(e - p + 1) : strlen(p);
        if (*p == '[') {
            if (in_sec && !done) { fprintf(o, "%s=%s\r\n", key, val); done = 1; }
            in_sec = !strncasecmp(p + 1, sec, sl) && p[1 + sl] == ']';
        }
        if (in_sec && !done && !strncasecmp(p, key, kl) && p[kl] == '=') {
            fprintf(o, "%s=%s\r\n", key, val);
            done = 1;
        } else {
            fwrite(p, 1, len, o);
        }
        p += len;
    }
    if (!done) {
        if (n && in[n - 1] != '\n') fputs("\r\n", o);
        if (!in_sec) fprintf(o, "[%s]\r\n", sec);
        fprintf(o, "%s=%s\r\n", key, val);
    }
    fclose(o);
    free(in);
    rename(tmp_path, path);
}

static bool copy_file_bin(const char *src, const char *dst) {
    FILE *in = fopen(src, "rb");
    if (!in) return false;
    FILE *out = fopen(dst, "wb");
    if (!out) { fclose(in); return false; }
    uint8_t buf[32768];
    size_t r;
    while ((r = fread(buf, 1, sizeof(buf), in)) > 0) {
        fwrite(buf, 1, r, out);
    }
    fclose(in);
    fclose(out);
    return true;
}

static void copy_dir_shallow(const char *src_dir, const char *dst_dir) {
    DIR *d = opendir(src_dir);
    if (!d) return;
    struct dirent *e;
    while ((e = readdir(d)) != NULL) {
        if (e->d_name[0] == '.') continue;
        char sp[800], dp[800];
        struct stat st;
        snprintf(sp, sizeof(sp), "%s/%s", src_dir, e->d_name);
        snprintf(dp, sizeof(dp), "%s/%s", dst_dir, e->d_name);
        if (stat(sp, &st) == 0 && S_ISREG(st.st_mode)) {
            copy_file_bin(sp, dp);
        }
    }
    closedir(d);
}

extern "C" void ra2_write_resolution_ini(const ra2_config_t *cfg, int w, int h) {
    char ov_dir[512] = {0};
    if (nxn_fs_path(NXN_DIR_DATA, "overlay_active", ov_dir, sizeof(ov_dir)) != NXN_OK) {
        snprintf(ov_dir, sizeof(ov_dir), "%s", cfg->game_dir);
    }
    char ini_path[640];
    snprintf(ini_path, sizeof(ini_path), "%s/ra2md.ini", ov_dir);
    char v[32];
    snprintf(v, sizeof(v), "%d", w); ini_set_key(ini_path, "Video", "ScreenWidth", v);
    snprintf(v, sizeof(v), "%d", h); ini_set_key(ini_path, "Video", "ScreenHeight", v);
}

extern "C" void ra2_apply_ini_and_overlay(ra2_config_t *cfg, char *out_overlay_dir, size_t cap) {
    if (out_overlay_dir && cap) out_overlay_dir[0] = 0;

    /* 0. Resolve game language (0=Auto/System, 1=English, 2=Turkish RA2.CSF, 3=German) */
    int eff_lang = cfg->game_lang;
    if (eff_lang == 0) {
        char sys_lang[4] = {0};
        nxn_imgui_language(sys_lang);
        if (!strncasecmp(sys_lang, "tr", 2)) eff_lang = 2;
        else if (!strncasecmp(sys_lang, "de", 2)) eff_lang = 3;
        else eff_lang = 1;
        ra2_log_append("Auto language: system='%s' -> mode=%d", sys_lang[0] ? sys_lang : "en", eff_lang);
    }

    cfg->use_turkish_csf = (eff_lang == 2) ? 1 : 0;
    cfg->langmd_override[0] = 0;
    cfg->language_override[0] = 0;

    /* For English and Turkish, prefer langmd_eng.mix / language_eng.mix if present
     * so menus, logos and voices are English instead of German (DODI repack default). */
    if (eff_lang == 1 || eff_lang == 2) {
        char found[600];
        if (find_file_ci(cfg->game_dir, "langmd_eng.mix", found, sizeof(found))) {
            snprintf(cfg->langmd_override, sizeof(cfg->langmd_override), "langmd_eng.mix");
        }
        if (find_file_ci(cfg->game_dir, "language_eng.mix", found, sizeof(found))) {
            snprintf(cfg->language_override, sizeof(cfg->language_override), "language_eng.mix");
        }
        if (cfg->langmd_override[0]) {
            ra2_log_append("Language archive redirect: langmd.mix -> %s", cfg->langmd_override);
        }
    }

    char ov_dir[512] = {0};
    nxn_fs_mkdirs(NXN_DIR_DATA, "overlay_active");
    if (nxn_fs_path(NXN_DIR_DATA, "overlay_active", ov_dir, sizeof(ov_dir)) != NXN_OK) {
        snprintf(ov_dir, sizeof(ov_dir), "%s", cfg->game_dir);
    } else {
        char f1[600], f2[600];
        snprintf(f1, sizeof(f1), "%s/ra2.csf", ov_dir);
        snprintf(f2, sizeof(f2), "%s/ra2md.csf", ov_dir);
        remove(f1);
        remove(f2);
    }

    if (cfg->yuri_modded && cfg->mod_name[0]) {
        char mod_path[700] = {0};
        char try1[700], try2[700];
        snprintf(try1, sizeof(try1), "%s/mods/yr/%s", cfg->game_dir, cfg->mod_name);
        snprintf(try2, sizeof(try2), "%s/mods/%s", cfg->game_dir, cfg->mod_name);
        struct stat st;
        if (stat(try1, &st) == 0 && S_ISDIR(st.st_mode)) snprintf(mod_path, sizeof(mod_path), "%s", try1);
        else if (stat(try2, &st) == 0 && S_ISDIR(st.st_mode)) snprintf(mod_path, sizeof(mod_path), "%s", try2);
        if (mod_path[0]) {
            copy_dir_shallow(mod_path, ov_dir);
            ra2_log_append("Overlay: loaded Yuri mod '%s'", cfg->mod_name);
        }
    }

    if (cfg->use_turkish_csf) {
        char src_csf[512] = {0};
        if (find_bundle_asset("assets/RA2.CSF", src_csf, sizeof(src_csf)) ||
            find_bundle_asset("RA2.CSF", src_csf, sizeof(src_csf))) {
            char dst1[600], dst2[600];
            snprintf(dst1, sizeof(dst1), "%s/ra2.csf", ov_dir);
            snprintf(dst2, sizeof(dst2), "%s/ra2md.csf", ov_dir);
            if (copy_file_bin(src_csf, dst1) && copy_file_bin(src_csf, dst2)) {
                ra2_log_append("Overlay: Turkish RA2.CSF injected -> ra2.csf & ra2md.csf");
            }
        }
    }

    char ini_path[640];
    snprintf(ini_path, sizeof(ini_path), "%s/ra2md.ini", ov_dir);
    if (access(ini_path, R_OK) != 0) {
        char orig_ini[640];
        if (find_file_ci(cfg->game_dir, "ra2md.ini", orig_ini, sizeof(orig_ini))) {
            copy_file_bin(orig_ini, ini_path);
        }
    }

    char v[32];
    snprintf(v, sizeof(v), "%d", cfg->res_w); ini_set_key(ini_path, "Video", "ScreenWidth", v);
    snprintf(v, sizeof(v), "%d", cfg->res_h); ini_set_key(ini_path, "Video", "ScreenHeight", v);
    ini_set_key(ini_path, "Video", "AllowHiResModes", "Yes");
    ini_set_key(ini_path, "Video", "UseGraphicsPatch", "Yes");
    ini_set_key(ini_path, "Video", "VideoBackBuffer", "Yes");
    ini_set_key(ini_path, "Intro", "Play", cfg->skip_intro ? "no" : "yes");
    snprintf(v, sizeof(v), "%d", cfg->detail_level); ini_set_key(ini_path, "Options", "DetailLevel", v);
    snprintf(v, sizeof(v), "%d", cfg->scroll_rate);  ini_set_key(ini_path, "Options", "ScrollRate", v);
    snprintf(v, sizeof(v), "%.2f", cfg->vol_sfx);    ini_set_key(ini_path, "Audio", "SoundVolume", v);
    snprintf(v, sizeof(v), "%.2f", cfg->vol_voice);  ini_set_key(ini_path, "Audio", "VoiceVolume", v);
    snprintf(v, sizeof(v), "%.2f", cfg->vol_music);  ini_set_key(ini_path, "Audio", "ScoreVolume", v);

    ra2_log_append("Config written: %dx%d (AutoDock=%d, ScrollRate=%d, Detail=%d, TR=%d)",
                   cfg->res_w, cfg->res_h, cfg->auto_dock_res, cfg->scroll_rate,
                   cfg->detail_level, cfg->use_turkish_csf);

    if (out_overlay_dir && cap) {
        snprintf(out_overlay_dir, cap, "%s", ov_dir);
    }
}

/* ---- Helper: resolve Auto Dock / Handheld resolution ---- */
static void sync_dock_resolution(ra2_config_t *cfg, const nxn_caps &caps) {
    if (!cfg->auto_dock_res) return;
    if (caps.features & NXN_CAP_POWER_STATE) {
        nxn_power pwr = NXN_STRUCT_INIT(nxn_power);
        if (nxn_power_get(&pwr) == NXN_OK) {
            cfg->res_index = pwr.docked ? 1 : 0; /* 1=1920x1080, 0=1280x720 */
            cfg->res_w = k_res_list[cfg->res_index][0];
            cfg->res_h = k_res_list[cfg->res_index][1];
        }
    }
}

/* ---- Main Launcher UI Loop ---- */
extern "C" int ra2_run_launcher(ra2_config_t *cfg) {
    nxn_display *disp = NULL;
    if (nxn_display_open(NULL, &disp) != NXN_OK) {
        nxn_log(NXN_LOG_ERROR, "[RA2] nxn_display_open failed for launcher");
        return 0;
    }
    gladLoadGLLoader((GLADloadproc)nxn_display_proc);
    uint32_t fb_w = 1280, fb_h = 720;
    nxn_display_size(disp, &fb_w, &fb_h);

    nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
    nxn_caps_get(&caps);
    if (caps.features & NXN_CAP_WINDOW_CTL) {
        nxn_window_set_title(nxn_tr("app.title"), "Launcher");
    }

    config_load(cfg);
    sync_dock_resolution(cfg, caps);
    autodetect_game_dir(cfg);
    VerifyState vs;
    verify_game_dir(cfg->game_dir, vs);
    scan_mods(cfg->game_dir);
    const auto choose_game = [&]() {
        nxn_pick_params pick = NXN_STRUCT_INIT(nxn_pick_params);
        pick.kind = NXN_PICK_FOLDER;
        pick.flags = NXN_PICK_REMEMBER;
        pick.title = nxn_tr("btn.browse");
        char path[sizeof(cfg->game_dir)] = {};
        if (nxn_pick(&pick, path, sizeof(path)) != NXN_OK || !path[0]) return;
        snprintf(cfg->game_dir, sizeof(cfg->game_dir), "%s", path);
        verify_game_dir(cfg->game_dir, vs);
        scan_mods(cfg->game_dir);
        config_save(cfg);
    };

    GlImage img_logo;
    load_nximg("assets/logo.nximg", img_logo);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.LogFilename = nullptr;
    nxn_imgui_enable_gamepad(io);

    nxn_ui_tokens tok = NXN_STRUCT_INIT(nxn_ui_tokens);
    nxn_ui_tokens_get(&tok);
    ImGui_ImplOpenGL3_Init("#version 330 core");

    nxn_imgui_input_state input_backend;
    nxn_input_state pad_in = NXN_STRUCT_INIT(nxn_input_state);

    int active_tab = 0;
    int ctrl_sub_tab = 0; /* 0=Gamepad, 1=Touchscreen, 2=KB & Mouse */
    char toast_msg[192] = {0};
    uint64_t toast_until = 0;

    int result = 0;
    bool done = false;
    uint64_t last_ns = nxn_time_ns();

    const uint32_t k_green = 0xFF2ECC71u;
    const uint32_t k_red   = 0xFFE74C3Cu;
    const uint32_t k_amber = 0xFFF39C12u;

    while (!done && !nxn_should_quit()) {
        nxn_event ev = NXN_STRUCT_INIT(nxn_event);
        while (nxn_event_poll(&ev) > 0) {
            nxn_imgui_input_event(ev);
            if (ev.type == NXN_EVENT_RESIZE) {
                if (nxn_display_resize(disp, ev.width, ev.height) == NXN_OK) {
                    nxn_display_size(disp, &fb_w, &fb_h);
                }
            } else if (ev.type == NXN_EVENT_THEME || ev.type == NXN_EVENT_LANGUAGE) {
                nxn_ui_tokens_get(&tok);
            } else if (ev.type == NXN_EVENT_DOCK || ev.type == NXN_EVENT_POWER) {
                sync_dock_resolution(cfg, caps);
            } else if (ev.type == NXN_EVENT_QUIT) {
                done = true;
                result = 0;
            }
            ev = NXN_STRUCT_INIT(nxn_event);
        }

        pad_in = NXN_STRUCT_INIT(nxn_input_state);
        nxn_input_poll(&pad_in);

        uint64_t now_ns = nxn_time_ns();
        float dt = (float)((now_ns - last_ns) / 1e9);
        if (dt <= 0.0f || dt > 0.1f) dt = 0.016f;
        last_ns = now_ns;

        nxn_imgui_input(input_backend, pad_in, dt);
        nxn_os_frame_begin(&tok, (int)fb_w, (int)fb_h);


        /* ---- Hero: the Port Studio launcher standard (portkit/nx_launcher_ui.h) ---- */
        nx_hero_desc hero = {};
        hero.title = nxn_tr("app.title");
        hero.subtitle = nxn_tr("app.subtitle");
        hero.logo = img_logo.tex ? (ImTextureID)(intptr_t)img_logo.tex : (ImTextureID)0;
        hero.play_label = nxn_tr(vs.ok ? "btn.play" : "btn.browse");
        hero.exit_label = nxn_tr("btn.quit");
        int hero_action = nx_hero(hero, tok, [&]() {
            nxn_os_badge(nxn_tr(vs.ok ? "status.ready" : vs.has_gamemd && !vs.stamp_ok
                ? "status.unsupported" : "status.missing"),
                         vs.ok ? k_green : k_red, tok);
            nxn_os_badge(cfg->stable_profile ? nxn_tr("status.stable") : nxn_tr("status.custom"),
                         cfg->stable_profile ? tok.accent : k_amber, tok);
            if (caps.features & NXN_CAP_POWER_STATE) {
                nxn_power pwr = NXN_STRUCT_INIT(nxn_power);
                if (nxn_power_get(&pwr) == NXN_OK) {
                    char pbuf[48];
                    if (pwr.percent >= 0) {
                        snprintf(pbuf, sizeof(pbuf), "%s · %d%%",
                                 pwr.docked ? nxn_tr("status.docked") : nxn_tr("status.handheld"),
                                 (int)pwr.percent);
                    } else {
                        snprintf(pbuf, sizeof(pbuf), "%s",
                                 pwr.docked ? nxn_tr("status.docked") : nxn_tr("status.handheld"));
                    }
                    nxn_os_badge(pbuf, 0xFF6B7280u, tok);
                }
            }
        });
        if (hero_action == NX_HERO_EXIT) {
            done = true;
            result = 0;
        } else if (hero_action == NX_HERO_PLAY) {
            if (vs.ok) {
                sync_dock_resolution(cfg, caps);
                config_save(cfg);
                done = true;
                result = 1;
            } else choose_game();
        }

        nxn_os_gap(NXN_OS_SP_S);

        if (toast_msg[0] && now_ns < toast_until) {
            nxn_os_card_begin("toast_card", tok);
            nxn_os_text_colored(NXN_OS_TEXT_BODY, toast_msg, tok.accent);
            nxn_os_card_end();
            nxn_os_gap(NXN_OS_SP_XS);
        }

        const char *tab_labels[6] = {
            nxn_tr("tab.overview"),
            nxn_tr("tab.video"),
            nxn_tr("tab.controls"),
            nxn_tr(NX_HOWTO_TITLE_KEY),
            nxn_tr("tab.files"),
            nxn_tr("tab.logs")
        };
        nx_tabs("##main_tabs", tab_labels, 6, &active_tab, tok);
        nxn_os_gap(NXN_OS_SP_S);

        ImGui::BeginChild("##tab_scroll", ImVec2(0, 0), false);

        if (active_tab == 0) {
            /* === TAB 0: OVERVIEW. Two columns: quick settings (FPS first) and the game folder. File checks live in the Files tab. === */
            nx_grid_begin("##ov_grid", 2);

            nx_grid_next();
            nxn_os_section_label(nxn_tr("sec.quick"), tok);
            nxn_os_card_begin("quick_card", tok);
            {
                bool sfps = cfg->show_fps != 0;
                if (nx_fps_row(&sfps, nxn_tr("lbl.show_fps"), nxn_tr("lbl.show_fps_hint"))) {
                    cfg->show_fps = sfps ? 1 : 0;
                    config_save(cfg);
                }
                nxn_os_separator(tok);

                const char *yuri_opts[2] = { nxn_tr("opt.yuri_unmodded"), nxn_tr("opt.yuri_modded") };
                int ym = cfg->yuri_modded ? 1 : 0;
                nxn_os_labeled(nxn_tr("lbl.yuri_mode"), [&]() {
                    if (nxn_os_select("##yuri_mode", yuri_opts, 2, &ym, nxn_os_fill())) {
                        cfg->yuri_modded = ym;
                        if (ym && g_mod_count > 0 && !cfg->mod_name[0]) {
                            snprintf(cfg->mod_name, sizeof(cfg->mod_name), "%s", g_mod_list[0]);
                        }
                        config_save(cfg);
                    }
                });

                if (cfg->yuri_modded) {
                    if (g_mod_count > 0) {
                        int sel = 0;
                        for (int i = 0; i < g_mod_count; i++) {
                            if (!strcasecmp(g_mod_list[i], cfg->mod_name)) { sel = i; break; }
                        }
                        nxn_os_labeled(nxn_tr("lbl.select_mod"), [&]() {
                            if (nxn_os_select("##mod_sel", g_mod_ptrs, g_mod_count, &sel, nxn_os_fill())) {
                                snprintf(cfg->mod_name, sizeof(cfg->mod_name), "%s", g_mod_list[sel]);
                                config_save(cfg);
                            }
                        });
                    } else {
                        nxn_os_text(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.no_mods"));
                    }
                }

                const char *lang_opts[4] = {
                    nxn_tr("opt.lang_auto"),
                    nxn_tr("opt.lang_en"),
                    nxn_tr("opt.lang_tr"),
                    nxn_tr("opt.lang_de")
                };
                nxn_os_labeled(nxn_tr("lbl.game_lang"), [&]() {
                    if (nxn_os_select("##game_lang", lang_opts, 4, &cfg->game_lang, nxn_os_fill())) {
                        config_save(cfg);
                    }
                });
                char sys_lang[4] = {0};
                nxn_imgui_language(sys_lang);
                if (cfg->game_lang == 2 || (cfg->game_lang == 0 && !strncasecmp(sys_lang, "tr", 2))) {
                    nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("msg.tr_active"));
                }
                nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.ui_lang_note"));
            }
            nxn_os_card_end();

            nx_grid_next();
            nxn_os_section_label(nxn_tr("sec.game_folder"), tok);
            nxn_os_card_begin("path_card", tok);
            {
                nxn_os_row_begin();
                if (nxn_os_button(nxn_tr("btn.browse"), NXN_OS_BTN_PRIMARY, tok)) {
                    choose_game();
                }
                if (nxn_os_button(nxn_tr("btn.verify"), NXN_OS_BTN_DEFAULT, tok)) {
                    verify_game_dir(cfg->game_dir, vs);
                    scan_mods(cfg->game_dir);
                }
                nxn_os_row_end();
                nxn_os_separator(tok);
                if (cfg->game_dir[0]) {
                    nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, cfg->game_dir);
                } else {
                    nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.no_dir"));
                }
                nxn_os_gap(NXN_OS_SP_XS);
                nxn_os_text_colored(NXN_OS_TEXT_BODY,
                                    nxn_tr(vs.ok ? "lbl.verify_ok" : vs.has_gamemd && !vs.stamp_ok
                                        ? "lbl.verify_unsupported" : "lbl.verify_fail"),
                                    vs.ok ? k_green : k_red);
                nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.files_hint"));
            }
            nxn_os_card_end();

            nx_grid_end();

        } else if (active_tab == 1) {
            /* === TAB 1: VIDEO, AUTO DOCK RESOLUTION & PERFORMANCE === */
            nxn_os_section_label(nxn_tr("sec.profile"), tok);
            nxn_os_card_begin("profile_card", tok);
            {
                bool st = cfg->stable_profile != 0;
                if (nxn_os_switch_row(nxn_tr("lbl.stable_profile"), &st)) {
                    cfg->stable_profile = st ? 1 : 0;
                    if (cfg->stable_profile) apply_stable_lock(cfg);
                    config_save(cfg);
                }
                nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.stable_hint"));
                nxn_os_gap(NXN_OS_SP_XS);
                if (nxn_os_button(nxn_tr("btn.reset_defaults"), NXN_OS_BTN_DEFAULT, tok)) {
                    ra2_config_set_stable_defaults(cfg, 1);
                    config_save(cfg);
                    snprintf(toast_msg, sizeof(toast_msg), "%s", nxn_tr("msg.reset_done"));
                    toast_until = now_ns + 3500000000ULL;
                }
            }
            nxn_os_card_end();

            nxn_os_gap(NXN_OS_SP_S);
            nxn_os_section_label(nxn_tr("sec.display"), tok);
            nxn_os_card_begin("display_card", tok);
            {
                /* Auto Dock / Handheld Resolution toggle (default OFF, shows info popup when enabled) */
                bool ad = cfg->auto_dock_res != 0;
                if (nxn_os_switch_row(nxn_tr("lbl.auto_dock_res"), &ad)) {
                    cfg->auto_dock_res = ad ? 1 : 0;
                    if (cfg->auto_dock_res) {
                        sync_dock_resolution(cfg, caps);
                        if (caps.features & NXN_CAP_DIALOG) {
                            const char *btns[1] = { "dlg.ok" };
                            nxn_dialog_params dp = NXN_STRUCT_INIT(nxn_dialog_params);
                            dp.title = "dlg.autodock.title";
                            dp.message = "dlg.autodock.msg";
                            dp.buttons = btns;
                            dp.button_count = 1;
                            dp.cancel_button = 0;
                            dp.danger_button = NXN_DIALOG_NONE;
                            uint32_t picked = 0;
                            nxn_dialog(&dp, &picked);
                        }
                    }
                    config_save(cfg);
                }
                nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, nxn_tr("lbl.auto_dock_hint"));
                char resolution[48];
                snprintf(resolution, sizeof(resolution), "%d × %d", cfg->res_w, cfg->res_h);
                nxn_os_kv_row(nxn_tr("lbl.current_resolution"), resolution, tok, false);
                nxn_os_separator(tok);

                ImGui::BeginDisabled(cfg->stable_profile != 0);
                const char *dm_opts[2] = { nxn_tr("opt.windowed"), nxn_tr("opt.fullscreen") };
                int fs = cfg->fullscreen ? 1 : 0;
                nxn_os_labeled(nxn_tr("lbl.display_mode"), [&]() {
                    if (nxn_os_select("##disp_mode", dm_opts, 2, &fs, nxn_os_fill())) {
                        cfg->fullscreen = fs;
                        config_save(cfg);
                    }
                });

                ImGui::BeginDisabled(cfg->auto_dock_res != 0);
                nxn_os_labeled(nxn_tr("lbl.resolution"), [&]() {
                    if (nxn_os_select("##res_sel", k_res_labels, k_res_count, &cfg->res_index, nxn_os_fill())) {
                        cfg->res_w = k_res_list[cfg->res_index][0];
                        cfg->res_h = k_res_list[cfg->res_index][1];
                        config_save(cfg);
                    }
                });
                ImGui::EndDisabled();

                nxn_os_labeled(nxn_tr("lbl.scaling"), [&]() {
                    if (nxn_os_select("##scale_sel", k_scale_labels, 5, &cfg->scale_index, nxn_os_fill())) {
                        config_save(cfg);
                    }
                });

                const char *fit_opts[3] = { nxn_tr("opt.fit_fill"), nxn_tr("opt.fit_aspect"), nxn_tr("opt.fit_blur") };
                nxn_os_labeled(nxn_tr("lbl.fit_mode"), [&]() {
                    if (nxn_os_select("##fit_sel", fit_opts, 3, &cfg->fit_mode, nxn_os_fill())) {
                        config_save(cfg);
                    }
                });
                ImGui::EndDisabled();
            }
            nxn_os_card_end();

            nxn_os_gap(NXN_OS_SP_S);
            nxn_os_section_label(nxn_tr("sec.engine"), tok);
            nxn_os_card_begin("engine_card", tok);
            {
                ImGui::BeginDisabled(cfg->stable_profile != 0);
                const char *hd_opts[3] = { nxn_tr("opt.hd_off"), nxn_tr("opt.hd_2x"), nxn_tr("opt.hd_smooth") };
                nxn_os_labeled(nxn_tr("lbl.hd_voxels"), [&]() {
                    if (nxn_os_select("##hd_vox", hd_opts, 3, &cfg->hd_voxels, nxn_os_fill())) config_save(cfg);
                });

                const char *det_opts[3] = { nxn_tr("opt.low"), nxn_tr("opt.medium"), nxn_tr("opt.high") };
                nxn_os_labeled(nxn_tr("lbl.detail"), [&]() {
                    if (nxn_os_select("##detail_lvl", det_opts, 3, &cfg->detail_level, nxn_os_fill())) config_save(cfg);
                });

                bool si = cfg->skip_intro != 0;
                if (nxn_os_switch_row(nxn_tr("lbl.skip_intro"), &si)) {
                    cfg->skip_intro = si ? 1 : 0;
                    config_save(cfg);
                }
                ImGui::EndDisabled();

                nxn_os_separator(tok);
                nxn_os_labeled(nxn_tr("lbl.vol_sfx"), [&]() {
                    if (nxn_os_slider("##vol_sfx", &cfg->vol_sfx, 0.0f, 1.0f, tok, nxn_os_fill())) config_save(cfg);
                });
                nxn_os_labeled(nxn_tr("lbl.vol_voice"), [&]() {
                    if (nxn_os_slider("##vol_voice", &cfg->vol_voice, 0.0f, 1.0f, tok, nxn_os_fill())) config_save(cfg);
                });
                nxn_os_labeled(nxn_tr("lbl.vol_music"), [&]() {
                    if (nxn_os_slider("##vol_music", &cfg->vol_music, 0.0f, 1.0f, tok, nxn_os_fill())) config_save(cfg);
                });
            }
            nxn_os_card_end();

        } else if (active_tab == 2) {
            /* === TAB 2: ORGANIZED CONTROLS (GAMEPAD / TOUCHSCREEN / KEYBOARD & MOUSE) === */
            nxn_os_card_begin("ctrl_header_card", tok);
            {
                bool st = cfg->stable_profile != 0;
                if (nxn_os_switch_row(nxn_tr("lbl.stable_profile"), &st)) {
                    cfg->stable_profile = st ? 1 : 0;
                    if (cfg->stable_profile) apply_stable_lock(cfg);
                    config_save(cfg);
                }
                nxn_os_gap(NXN_OS_SP_XS);
                const char *sub_labels[3] = {
                    nxn_tr("ctrl.sub.gamepad"),
                    nxn_tr("ctrl.sub.touch"),
                    nxn_tr("ctrl.sub.kbmouse")
                };
                nxn_os_segmented_tabs("##ctrl_sub_tabs", sub_labels, 3, &ctrl_sub_tab, tok);
            }
            nxn_os_card_end();

            nxn_os_gap(NXN_OS_SP_S);

            if (ctrl_sub_tab == 0) {
                /* --- Gamepad Settings & Button Remapping --- */
                nxn_os_card_begin("gp_card", tok);
                {
                    bool b_rs = cfg->rstick_pan != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.rstick_pan"), &b_rs)) { cfg->rstick_pan = b_rs; config_save(cfg); }
                    bool b_dp = cfg->dpad_pan != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.dpad_pan"), &b_dp)) { cfg->dpad_pan = b_dp; config_save(cfg); }

                    nxn_os_separator(tok);
                    nxn_os_labeled(nxn_tr("lbl.cursor_speed"), [&]() {
                        if (nxn_os_slider("##cur_spd", &cfg->cursor_speed, 4.0f, 24.0f, tok, nxn_os_fill())) config_save(cfg);
                    });
                    nxn_os_labeled(nxn_tr("lbl.deadzone"), [&]() {
                        if (nxn_os_slider("##deadzone", &cfg->deadzone, 0.05f, 0.35f, tok, nxn_os_fill())) config_save(cfg);
                    });

                    nxn_os_separator(tok);
                    const char *y_opts[4] = { nxn_tr("opt.y_deploy"), nxn_tr("opt.y_osk"), nxn_tr("opt.y_attack"), nxn_tr("opt.y_stop") };
                    nxn_os_labeled(nxn_tr("lbl.y_action"), [&]() {
                        if (nxn_os_select("##y_act", y_opts, 4, &cfg->y_action, nxn_os_fill())) config_save(cfg);
                    });
                    const char *l_opts[3] = { nxn_tr("opt.l_precision"), nxn_tr("opt.l_shift"), nxn_tr("opt.l_grp1") };
                    nxn_os_labeled(nxn_tr("lbl.l_action"), [&]() {
                        if (nxn_os_select("##l_act", l_opts, 3, &cfg->l_action, nxn_os_fill())) config_save(cfg);
                    });
                    const char *r_opts[3] = { nxn_tr("opt.r_boost"), nxn_tr("opt.r_ctrl"), nxn_tr("opt.r_grp2") };
                    nxn_os_labeled(nxn_tr("lbl.r_action"), [&]() {
                        if (nxn_os_select("##r_act", r_opts, 3, &cfg->r_action, nxn_os_fill())) config_save(cfg);
                    });
                    const char *l3_opts[2] = { nxn_tr("opt.l3_home"), nxn_tr("opt.l3_event") };
                    nxn_os_labeled(nxn_tr("lbl.l3_action"), [&]() {
                        if (nxn_os_select("##l3_act", l3_opts, 2, &cfg->l3_action, nxn_os_fill())) config_save(cfg);
                    });
                    const char *r3_opts[3] = { nxn_tr("opt.r3_type"), nxn_tr("opt.r3_combat"), nxn_tr("opt.r3_scatter") };
                    nxn_os_labeled(nxn_tr("lbl.r3_action"), [&]() {
                        if (nxn_os_select("##r3_act", r3_opts, 3, &cfg->r3_action, nxn_os_fill())) config_save(cfg);
                    });
                }
                nxn_os_card_end();
            } else if (ctrl_sub_tab == 1) {
                /* --- Touchscreen Settings --- */
                nxn_os_card_begin("touch_card", tok);
                {
                    bool b_2f = cfg->twofinger_pan != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.twofinger_pan"), &b_2f)) { cfg->twofinger_pan = b_2f; config_save(cfg); }
                    nxn_os_labeled(nxn_tr("lbl.touch_pan_sens"), [&]() {
                        if (nxn_os_slider("##t_sens", &cfg->touch_pan_sens, 0.5f, 2.0f, tok, nxn_os_fill())) config_save(cfg);
                    });
                    bool b_inv = cfg->touch_pan_invert != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.touch_invert"), &b_inv)) { cfg->touch_pan_invert = b_inv; config_save(cfg); }
                    nxn_os_separator(tok);
                    bool b_lp = cfg->longpress_rc != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.longpress_rc"), &b_lp)) { cfg->longpress_rc = b_lp; config_save(cfg); }
                    bool b_2t = cfg->twofinger_rc != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.twofinger_rc"), &b_2t)) { cfg->twofinger_rc = b_2t; config_save(cfg); }
                    bool b_tw = cfg->touch_wheel != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.touch_wheel"), &b_tw)) { cfg->touch_wheel = b_tw; config_save(cfg); }
                }
                nxn_os_card_end();
            } else {
                /* --- Keyboard & Mouse Settings --- */
                nxn_os_card_begin("kbm_card", tok);
                {
                    bool b_ws = cfg->wasd_pan != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.wasd_pan"), &b_ws)) { cfg->wasd_pan = b_ws; config_save(cfg); }
                    bool b_es = cfg->edge_scroll != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.edge_scroll"), &b_es)) { cfg->edge_scroll = b_es; config_save(cfg); }
                    bool b_cf = cfg->confine_mouse != 0;
                    if (nxn_os_switch_row(nxn_tr("lbl.confine_mouse"), &b_cf)) { cfg->confine_mouse = b_cf; config_save(cfg); }
                    nxn_os_separator(tok);
                    nxn_os_labeled(nxn_tr("lbl.scroll_rate"), [&]() {
                        if (nxn_os_slider_int("##scroll_rate", &cfg->scroll_rate, 1, 6, nxn_os_fill())) config_save(cfg);
                    });
                }
                nxn_os_card_end();
            }
            nxn_os_gap(NXN_OS_SP_S);
            nxn_os_card_begin("ctrl_reset_card", tok);
            {
                if (nxn_os_button(nxn_tr("btn.reset_defaults"), NXN_OS_BTN_DEFAULT, tok)) {
                    set_control_defaults(cfg);
                    config_save(cfg);
                    snprintf(toast_msg, sizeof(toast_msg), "%s", nxn_tr("msg.reset_done"));
                    toast_until = now_ns + 3500000000ULL;
                }
                nxn_os_separator(tok);
                nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION,
                    ctrl_sub_tab == 0 ? nxn_tr("guide.gamepad") :
                    ctrl_sub_tab == 1 ? nxn_tr("guide.touch") : nxn_tr("guide.kbmouse"));
            }
            nxn_os_card_end();

        } else if (active_tab == 3) {
            /* === TAB 3: HOW TO PLAY (generated from the port's experience block) ===
             * One card per control scheme, one line per action. The text comes from lang keys
             * the Studio generates, so a new gesture or a changed binding shows up here
             * without touching this code. */
            nx_howto_draw(tok, cfg->touch_wheel != 0);

        } else if (active_tab == 4) {
            /* === TAB 4: FILES. The per-file check result, two columns, out of the overview. === */
            nxn_os_section_label(nxn_tr("sec.game_path"), tok);
            nx_grid_begin("##files_grid", 2);
            nx_grid_next();
            nxn_os_card_begin("files_core", tok);
            {
                nxn_os_kv_row("gamemd.exe", nxn_tr(!vs.has_gamemd ? "file.missing"
                    : vs.stamp_ok ? "file.found" : "status.unsupported"), tok, false);
                nxn_os_kv_row("ra2.mix", nxn_tr(vs.has_ra2_mix ? "file.found" : "file.missing"), tok, false);
                nxn_os_kv_row("ra2md.mix", nxn_tr(vs.has_ra2md_mix ? "file.found" : "file.missing"), tok, false);
            }
            nxn_os_card_end();
            nx_grid_next();
            nxn_os_card_begin("files_result", tok);
            {
                if (cfg->game_dir[0]) nxn_os_kv_row(nxn_tr("lbl.game_dir"), cfg->game_dir, tok, false);
                nxn_os_text_colored(NXN_OS_TEXT_BODY,
                                    nxn_tr(vs.ok ? "lbl.verify_ok" : vs.has_gamemd && !vs.stamp_ok
                                        ? "lbl.verify_unsupported" : "lbl.verify_fail"),
                                    vs.ok ? k_green : k_red);
                if (nxn_os_button(nxn_tr("btn.verify"), NXN_OS_BTN_DEFAULT, tok)) {
                    verify_game_dir(cfg->game_dir, vs);
                    scan_mods(cfg->game_dir);
                }
            }
            nxn_os_card_end();
            nx_grid_end();

        } else if (active_tab == 5) {
            /* === TAB 4: LOGS & DIAGNOSTICS === */
            nxn_os_section_label(nxn_tr("sec.logs"), tok);
            nxn_os_card_begin("logs_card", tok);
            {
                nxn_os_row_begin();
                if (nxn_os_button(nxn_tr("btn.copy_logs"), NXN_OS_BTN_DEFAULT, tok)) {
                    char all[8192];
                    size_t off = 0;
                    for (int i = 0; i < g_log_count && off + 4 < sizeof(all); i++) {
                        int idx = (g_log_head + i) % RA2_LOG_MAX_LINES;
                        int w = snprintf(all + off, sizeof(all) - off, "%s\n", g_log_lines[idx]);
                        if (w > 0) off += (size_t)w;
                    }
                    nxn_clipboard_set(all);
                    snprintf(toast_msg, sizeof(toast_msg), "%s", nxn_tr("msg.copied"));
                    toast_until = now_ns + 2500000000ULL;
                }
                if (nxn_os_button(nxn_tr("btn.clear_logs"), NXN_OS_BTN_DESTRUCTIVE, tok)) {
                    g_log_head = 0;
                    g_log_count = 0;
                }
                nxn_os_row_end();

                nxn_os_separator(tok);
                ImGui::BeginChild("##log_lines", ImVec2(0, NXN_S(320)), false);
                for (int i = 0; i < g_log_count; i++) {
                    int idx = (g_log_head + i) % RA2_LOG_MAX_LINES;
                    nxn_os_text(NXN_OS_TEXT_MONO, g_log_lines[idx]);
                }
                ImGui::EndChild();
            }
            nxn_os_card_end();
        }

        ImGui::EndChild();
        nxn_os_frame_end();

        glViewport(0, 0, (GLsizei)fb_w, (GLsizei)fb_h);
        glDisable(GL_SCISSOR_TEST);
        ImVec4 bg = nxn_os_clear_color(tok);
        glClearColor(bg.x, bg.y, bg.z, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        nxn_display_swap(disp);
    }

    free_glimg(img_logo);
    ImGui_ImplOpenGL3_Shutdown();
    ImGui::DestroyContext();
    nxn_display_close(disp);

    return result;
}
