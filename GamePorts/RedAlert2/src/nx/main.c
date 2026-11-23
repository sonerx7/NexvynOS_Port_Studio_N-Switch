/*
 * Red Alert 2 and Yuri's Revenge - Native Host for Nintendo Switch & Nexvyn OS (SDK 1.2)
 *
 * Statically recompiled RA2: Yuri's Revenge engine running on win32hle & SDL2 for Switch AArch64.
 * Integrates:
 *   - Nexvyn OS Native SDK 1.2 Launcher (launcher.cpp) with file verification, Turkish RA2.CSF
 *     overlay, Yuri mod selector, Stable Profile, ra2md.ini config, and diagnostics.
 *   - Practical RTS Camera Panning: Right Stick, D-Pad, Two-Finger Touch Drag, and Keyboard WASD.
 *   - Full Touch + Gamepad + USB Keyboard/Mouse support with clean focus-loss handling.
 */
#define _GNU_SOURCE
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <pthread.h>
#include <sys/stat.h>
#include <math.h>
#include <signal.h>

#ifdef __SWITCH__
#include <switch.h>
#endif

#include <SDL.h>

#include "win32hle.h"
#include "pe_loader.h"
#include "host.h"
#include "recomp_target.h"
#include "resolutions.h"
#include "hdvox.h"
#include "mods.h"
#include "launcher.h"

extern volatile uint64_t g_hle_cache_hits;
extern volatile uint64_t g_hle_disk_reads;

#ifdef NEXVYN_ABI
#include <nexvyn/nexvyn_native.h>
#endif

extern const uint32_t ra2_entry_va;   /* recomp_dispatch.c */

/* Missing Nexvyn windowed ABI v1 symbols (defined locally for 0 unresolved imports) */
volatile int g_hle_thread_count = 1;
void __cxa_pure_virtual(void) { abort(); }
FILE *popen(const char *cmd, const char *mode) { (void)cmd; (void)mode; return NULL; }
int pclose(FILE *stream) { (void)stream; return -1; }
long sysconf(int name) { (void)name; return 4096L; }
ssize_t pread(int fd, void *buf, size_t count, off_t offset) {
    off_t cur = lseek(fd, 0, SEEK_CUR);
    if (cur < 0) return -1;
    if (lseek(fd, offset, SEEK_SET) < 0) return -1;
    ssize_t r = read(fd, buf, count);
    lseek(fd, cur, SEEK_SET);
    return r;
}
int posix_memalign(void **memptr, size_t alignment, size_t size) {
    if (!memptr || alignment < sizeof(void *) || (alignment & (alignment - 1)) != 0) return 22;
    void *raw = malloc(size + alignment + sizeof(void *));
    if (!raw) return 12;
    uintptr_t addr = ((uintptr_t)raw + sizeof(void *) + alignment - 1) & ~(uintptr_t)(alignment - 1);
    *memptr = (void *)addr;
    return 0;
}

#define RA2_IMAGE_BASE 0x00400000u

/* Win32 virtual key codes & scan codes for RTS controls */
#define VK_TAB      0x09u
#define VK_RETURN   0x0Du
#define VK_SHIFT    0x10u
#define VK_CONTROL  0x11u
#define VK_ESCAPE   0x1Bu
#define VK_SPACE    0x20u
#define VK_LEFT     0x25u
#define VK_UP       0x26u
#define VK_RIGHT    0x27u
#define VK_DOWN     0x28u
#define VK_1        0x31u
#define VK_2        0x32u
#define VK_D        0x44u
#define VK_H        0x48u
#define VK_P        0x50u
#define VK_S        0x53u
#define VK_T        0x54u
#define VK_X        0x58u

#define WM_MOUSEMOVE   0x0200u
#define WM_LBUTTONDOWN 0x0201u
#define WM_LBUTTONUP   0x0202u
#define WM_RBUTTONDOWN 0x0204u
#define WM_RBUTTONUP   0x0205u

static int g_debuglog = 0;
static ra2_config_t g_cfg;
unsigned ra2_clip_rounds = 0;

/* Stub script / modern controls for Switch */
int  script_arg(int argc, char **argv, int i) { (void)argc; (void)argv; (void)i; return 0; }
int  script_active(void) { return 0; }
void script_log_line(const char *line) { (void)line; }
void script_start(void) {}
void menu_start(void (*save)(void)) { (void)save; }

extern int hle_filetrace_on;
extern int win32hle_trace;

void ra2_hook_debuglog(void) {
    if (g_debuglog) {
        char buf[1024];
        hle_guest_format(buf, sizeof buf, (const char *)hle_ptr(MEM32(g_esp + 4)), g_esp + 8);
        printf("[RA2] %s\n", buf);
        fflush(stdout);
    }
    g_esp += 4;
}

static int compose_hd(const uint8_t *px16, int pitch, int w, int h, uint32_t *out) {
    if (!ra2_vox_hd_on || !ra2_vox_hd_show || ra2_vox_scale() != 2) return 0;
    hdvox_compose(px16, pitch, w, h, out);
    return 1;
}

static int overlay_hd(const uint8_t *px16, int pitch, int w, int h, uint32_t *ov,
                      int *dx, int *dy, int *dw, int *dh) {
    if (!ra2_vox_hd_on || !ra2_vox_hd_show) return 0;
    return hdvox_overlay(px16, pitch, w, h, ov, dx, dy, dw, dh);
}

int ra2_modern_controls(void) { return 0; }
uint32_t ra2_modern_mouse_message(uint32_t message, int special) { (void)special; return message; }
uint32_t ra2_modern_radar_event_flags(uint32_t flags) { return flags; }
uint32_t ra2_modern_left_click_action(uint32_t action, uint32_t target, uint32_t target_vtable,
                                      int selected_in_group, uint32_t selection_count, int special) {
    (void)target; (void)target_vtable; (void)selected_in_group; (void)selection_count; (void)special;
    return action;
}
int ra2_modern_take_type_select(void) { return 0; }
void ra2_modern_end_left_up(void) {}
int ra2_modern_preserve_global_selection_clear(void) { return 0; }
int ra2_modern_preserve_shift_selection(void) { return 0; }
int ra2_modern_consume_right_drag_release(void) { return 0; }
int ra2_modern_shift_box_begin(void) { return 0; }
void ra2_modern_shift_box_decide(void) {}
void ra2_modern_shift_box_end(void) {}
int ra2_modern_box_object(int selected) { (void)selected; return 1; }

static void report(const char *why) {
    fprintf(stderr, "\n=== %s ===\n  in lifted sub_%08X, last import %s\n", why, g_cur_func,
            g_cur_import ? g_cur_import : "(none)");
    fprintf(stderr, "  eax=%08X ecx=%08X edx=%08X ebx=%08X esp=%08X ebp=%08X esi=%08X edi=%08X\n",
            g_eax, g_ecx, g_edx, g_ebx, g_esp, g_ebp, g_esi, g_edi);
    fprintf(stderr, "last indirect calls (newest first):\n");
    for (int i = 1; i <= 40 && i <= (int)g_icall_trace_idx; i++) {
        uint32_t k = (g_icall_trace_idx - i) & (ICALL_TRACE_SIZE - 1);
        const char *nm = hle_name(g_icall_trace[k]);
        fprintf(stderr, "  0x%08X  from 0x%08X  %s\n", g_icall_trace[k], g_icall_from[k], nm ? nm : "");
    }
    fprintf(stderr, "\n");
}

static void on_fault(int sig) {
    static volatile int once;
    if (__sync_lock_test_and_set(&once, 1)) _exit(3);
    char why[64];
    snprintf(why, sizeof why, "fault: signal %d", sig);
    report(why);
    fflush(stderr);
    _exit(3);
}

static void ra2_MessageBoxA(void) {
    fprintf(stderr, "[messagebox] %s: %s\n", ASTR(2) ? ASTR(2) : "", ASTR(1) ? ASTR(1) : "");
    RET(1u, 4);
}

static const win32hle_shim g_ra2_shims[] = {
    { "MessageBoxA", ra2_MessageBoxA },
    { 0, 0 }
};

static const uint8_t CLSID_Blowfish[16] = { 0x10, 0xAD, 0x40, 0x14, 0xA8, 0x6A, 0xD1, 0x11,
                                            0xB6, 0xF9, 0x00, 0xA0, 0x24, 0xDD, 0xAF, 0xD1 };
uint32_t ra2_blowfish_create(const uint8_t *iid, uint32_t *out);

#ifdef RA2_TARGET_GAME
#define RA2_MOUSE_VA 0x00B2AF5Cu
#else
#define RA2_MOUSE_VA 0x00B78164u
#endif

static int menus_use_windows_cursor(void) {
    uint32_t mouse = MEM32(RA2_MOUSE_VA);
    int game_draws_cursor = mouse && MEM8(mouse + 0x10);
    return !game_draws_cursor;
}

/* ============================================================================
 * Practical RTS Control & Camera Panning System (Gamepad + Multi-Touch + KB)
 * ============================================================================ */

static float g_cursor_x = 640.0f;
static float g_cursor_y = 360.0f;
static SDL_Joystick *g_joy = NULL;

/* Camera pan directional state (bit 0=Left, 1=Right, 2=Up, 3=Down) */
static int g_pan_held[4] = { 0, 0, 0, 0 };
static int g_touch_pan_want[4] = { 0, 0, 0, 0 };
static uint32_t g_touch_pan_expire_ms = 0;

/* Gamepad button latch states */
static int g_prev_lmb = 0;
static int g_prev_rmb = 0;
static int g_prev_esc = 0;
static int g_prev_y   = 0;
static int g_prev_l3  = 0;
static int g_prev_r3  = 0;
static int g_prev_minus = 0;
static uint32_t g_minus_down_ms = 0;

/* Multi-touch stable finger tracking for 2-finger camera pan */
typedef struct {
    int active;
    int64_t id;
    float x, y;
} touch_slot_t;
static touch_slot_t g_fingers[8];
static int g_2f_active = 0;
static int64_t g_2f_id0 = -1, g_2f_id1 = -1;
static float g_2f_last_cx = 0.0f, g_2f_last_cy = 0.0f;
/* Two fingers become one of three gestures and stay that gesture until a finger lifts:
 * pan (camera), pinch (mouse wheel: zoom) or scroll (mouse wheel: lists and the sidebar).
 * Off unless the player turns on "Touch Mouse Wheel"; the game's reaction to the wheel is untested. */
enum { G2_UNDECIDED = 0, G2_PAN, G2_PINCH, G2_SCROLL };
static int g_2f_mode = G2_UNDECIDED;
static float g_2f_last_dist = 0.0f, g_2f_start_cx = 0.0f;
static float g_2f_wheel_acc = 0.0f;
/* Classified from the net change since the two fingers landed, and only once both fingers have moved:
 * finger events arrive one finger at a time, so a parallel drag looks like a pinch until the second finger follows. */
static float g_2f_start_cy = 0.0f, g_2f_start_dist = 0.0f;
static float g_2f_ax0 = 0.0f, g_2f_ay0 = 0.0f, g_2f_bx0 = 0.0f, g_2f_by0 = 0.0f;
#define G2_DECIDE_AT   0.03f   /* finger travel (fraction of the screen) before the gesture is chosen */
#define G2_NOTCH       0.05f   /* finger travel per wheel notch */
#define G2_SIDEBAR_X   0.80f   /* two-finger drags that start right of this scroll instead of panning */

static void set_pan_key(int dir, int down) {
    static const uint32_t vk[4]   = { VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN };
    static const uint32_t scan[4] = { 75, 77, 72, 80 };
    if (g_pan_held[dir] != down) {
        g_pan_held[dir] = down;
        hle_input_key(down, vk[dir], scan[dir]);
    }
}

static void release_all_virtual_inputs(void) {
    for (int i = 0; i < 4; i++) {
        g_touch_pan_want[i] = 0;
        set_pan_key(i, 0);
    }
    if (g_prev_lmb) {
        g_prev_lmb = 0;
        hle_input_mouse(WM_LBUTTONUP, (int)g_cursor_x, (int)g_cursor_y);
    }
    if (g_prev_rmb) {
        g_prev_rmb = 0;
        hle_input_mouse(WM_RBUTTONUP, (int)g_cursor_x, (int)g_cursor_y);
    }
    if (g_prev_esc) { g_prev_esc = 0; hle_input_key(0, VK_ESCAPE, 1); }
    if (g_prev_y)   { g_prev_y = 0;   hle_input_key(0, VK_D, 32); hle_input_key(0, VK_CONTROL, 29); }
    if (g_prev_l3)  { g_prev_l3 = 0;  hle_input_key(0, VK_H, 35); }
    if (g_prev_r3)  { g_prev_r3 = 0;  hle_input_key(0, VK_T, 20); }
    g_prev_minus = 0;
    g_2f_active = 0;
    memset(g_fingers, 0, sizeof(g_fingers));
}

static void on_focus_lost(void) {
    release_all_virtual_inputs();
}

#ifdef NEXVYN_ABI
enum {
    MENU_ID_PAUSE       = 101,
    MENU_ID_HOME        = 102,
    MENU_ID_EVENT       = 103,
    MENU_ID_COMBAT      = 104,
    MENU_ID_SCATTER     = 105,
    MENU_ID_OSK         = 106,
    MENU_ID_QUIT        = 109,
    MENU_ID_FULLSCREEN  = 201,
    MENU_ID_FILL        = 202,
    MENU_ID_SCALE       = 203,
    MENU_ID_RES720      = 204,
    MENU_ID_RES1080     = 205,
    MENU_ID_RES1024     = 206,
    MENU_ID_AUTODOCK    = 207,
    MENU_ID_HDVOX       = 208,
    MENU_ID_FPS         = 209,
    MENU_ID_RSTICK      = 301,
    MENU_ID_TWOFINGER   = 302,
    MENU_ID_DPAD        = 303,
    MENU_ID_WASD        = 304,
    MENU_ID_SPD_SLOW    = 305,
    MENU_ID_SPD_NORM    = 306,
    MENU_ID_SPD_FAST    = 307,
    MENU_ID_CONFINE     = 308,
    MENU_ID_HELP_CTRL   = 401,
    MENU_ID_HELP_PERF   = 402,
    MENU_ID_HELP_ABOUT  = 403
};

static void apply_live_resolution(int w, int h) {
    g_cfg.res_w = w;
    g_cfg.res_h = h;
    ra2_write_resolution_ini(&g_cfg, w, h);
    if (res_plausible((int)MEM32(RA2_OPT_W_VA), (int)MEM32(RA2_OPT_H_VA))) {
        MEM32(RA2_OPT_W_VA) = (uint32_t)w;
        MEM32(RA2_OPT_H_VA) = (uint32_t)h;
    }
    nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
    if (nxn_caps_get(&caps) == NXN_OK && (caps.features & NXN_CAP_WINDOW_CTL)) {
        char sub[64];
        snprintf(sub, sizeof(sub), "%dx%d%s", w, h, g_cfg.use_turkish_csf ? " (TR)" : "");
        nxn_window_set_title("RA2 Yuri Port", sub);
    }
}

static void update_os_menu_bar(void) {
    nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
    if (nxn_caps_get(&caps) != NXN_OK || !(caps.features & NXN_CAP_MENU)) return;

    nxn_menu_item game_items[] = {
        { sizeof(nxn_menu_item), MENU_ID_PAUSE,   "menu.game.pause",   "Esc",   0, 0 },
        { sizeof(nxn_menu_item), 0,               NULL,                NULL,    NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_HOME,    "menu.game.home",    "H",     0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_EVENT,   "menu.game.event",   "Space", 0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_COMBAT,  "menu.game.combat",  "P",     0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_SCATTER, "menu.game.scatter", "X",     0, 0 },
        { sizeof(nxn_menu_item), 0,               NULL,                NULL,    NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_OSK,     "menu.game.osk",     NULL,    0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_QUIT,    "menu.game.quit",    NULL,    0, 0 }
    };
    nxn_menu_item view_items[] = {
        { sizeof(nxn_menu_item), MENU_ID_FULLSCREEN, "menu.view.fullscreen", "F11", g_cfg.fullscreen ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_FILL,       "menu.view.fill",       NULL,  g_cfg.fit_mode == 0 ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_SCALE,      "menu.view.scale",      "F12", 0, 0 },
        { sizeof(nxn_menu_item), 0,                  NULL,                   NULL,  NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_RES720,     "menu.view.res720",     NULL,  (g_cfg.res_w == 1280 && g_cfg.res_h == 720) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_RES1080,    "menu.view.res1080",    NULL,  (g_cfg.res_w == 1920 && g_cfg.res_h == 1080) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_RES1024,    "menu.view.res1024",    NULL,  (g_cfg.res_w == 1024 && g_cfg.res_h == 768) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_AUTODOCK,   "menu.view.autodock",   NULL,  g_cfg.auto_dock_res ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), 0,                  NULL,                   NULL,  NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_HDVOX,      "menu.view.hdvox",      NULL,  ra2_vox_hd_show ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_FPS,        "menu.view.fps",        NULL,  g_cfg.show_fps ? NXN_MENU_CHECKED : 0u, 0 }
    };
    nxn_menu_item ctrl_items[] = {
        { sizeof(nxn_menu_item), MENU_ID_RSTICK,    "menu.controls.rstick",    NULL, g_cfg.rstick_pan ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_TWOFINGER, "menu.controls.twofinger", NULL, g_cfg.twofinger_pan ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_DPAD,      "menu.controls.dpad",      NULL, g_cfg.dpad_pan ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_WASD,      "menu.controls.wasd",      NULL, g_cfg.wasd_pan ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), 0,                 NULL,                      NULL, NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_SPD_SLOW,  "menu.controls.spd_slow",  NULL, (g_cfg.cursor_speed <= 9.0f) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_SPD_NORM,  "menu.controls.spd_norm",  NULL, (g_cfg.cursor_speed > 9.0f && g_cfg.cursor_speed < 15.0f) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), MENU_ID_SPD_FAST,  "menu.controls.spd_fast",  NULL, (g_cfg.cursor_speed >= 15.0f) ? NXN_MENU_CHECKED : 0u, 0 },
        { sizeof(nxn_menu_item), 0,                 NULL,                      NULL, NXN_MENU_SEPARATOR, 0 },
        { sizeof(nxn_menu_item), MENU_ID_CONFINE,   "menu.controls.confine",   NULL, g_cfg.confine_mouse ? NXN_MENU_CHECKED : 0u, 0 }
    };
    nxn_menu_item help_items[] = {
        { sizeof(nxn_menu_item), MENU_ID_HELP_CTRL,  "menu.help.controls", NULL, 0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_HELP_PERF,  "menu.help.perf",     NULL, 0, 0 },
        { sizeof(nxn_menu_item), MENU_ID_HELP_ABOUT, "menu.help.about",    NULL, 0, 0 }
    };

    nxn_menu_menu menus[] = {
        { sizeof(nxn_menu_menu), "menu.game",     game_items, (uint32_t)(sizeof(game_items)/sizeof(game_items[0])), sizeof(nxn_menu_item) },
        { sizeof(nxn_menu_menu), "menu.view",     view_items, (uint32_t)(sizeof(view_items)/sizeof(view_items[0])), sizeof(nxn_menu_item) },
        { sizeof(nxn_menu_menu), "menu.controls", ctrl_items, (uint32_t)(sizeof(ctrl_items)/sizeof(ctrl_items[0])), sizeof(nxn_menu_item) },
        { sizeof(nxn_menu_menu), "menu.help",     help_items, (uint32_t)(sizeof(help_items)/sizeof(help_items[0])), sizeof(nxn_menu_item) }
    };
    nxn_menu_spec spec = { sizeof(nxn_menu_spec), menus, 4u, sizeof(nxn_menu_menu) };
    nxn_menu_set(&spec);
}

static void tap_vk(uint32_t vk, uint32_t scan) {
    hle_input_key(1, vk, scan);
    hle_input_key(0, vk, scan);
}

static void show_info_dialog(const char *title_key, const char *msg) {
    nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
    if (nxn_caps_get(&caps) == NXN_OK && (caps.features & NXN_CAP_DIALOG)) {
        const char *btns[1] = { "dlg.ok" };
        nxn_dialog_params dp = NXN_STRUCT_INIT(nxn_dialog_params);
        dp.title = title_key;
        dp.message = msg;
        dp.buttons = btns;
        dp.button_count = 1;
        dp.cancel_button = 0;
        dp.danger_button = NXN_DIALOG_NONE;
        uint32_t picked = 0;
        nxn_dialog(&dp, &picked);
    }
}

static void handle_os_menu_action(uint32_t id) {
    static const char *const k_scales[] = { "sharp", "smooth", "nearest", "integer", "crt" };
    switch (id) {
        case MENU_ID_PAUSE:   tap_vk(VK_ESCAPE, 1); break;
        case MENU_ID_HOME:    tap_vk(VK_H, 35); break;
        case MENU_ID_EVENT:   tap_vk(VK_SPACE, 57); break;
        case MENU_ID_COMBAT:  tap_vk(VK_P, 25); break;
        case MENU_ID_SCATTER: tap_vk(VK_X, 45); break;
        case MENU_ID_OSK:
            if (SDL_IsTextInputActive()) SDL_StopTextInput();
            else SDL_StartTextInput();
            break;
        case MENU_ID_QUIT: {
            uint32_t h = hle_first_hwnd();
            if (h) hle_post_message(h, 0x0010u /* WM_CLOSE */, 0, 0);
            else hle_exit(0);
            break;
        }
        case MENU_ID_FULLSCREEN: {
            g_cfg.fullscreen = !g_cfg.fullscreen;
            hle_screen_fullscreen(g_cfg.fullscreen);
            nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
            if (nxn_caps_get(&caps) == NXN_OK && (caps.features & NXN_CAP_WINDOW_CTL)) {
                nxn_window_set_mode(g_cfg.fullscreen ? NXN_WIN_FULLSCREEN : NXN_WIN_NORMAL);
            }
            update_os_menu_bar();
            break;
        }
        case MENU_ID_FILL:
            g_cfg.fit_mode = (g_cfg.fit_mode == 0) ? 1 : 0;
            hle_screen_stretch(g_cfg.fit_mode == 0 ? 1 : 0);
            update_os_menu_bar();
            break;
        case MENU_ID_SCALE:
            g_cfg.scale_index = (g_cfg.scale_index + 1) % 5;
            hle_screen_scale(k_scales[g_cfg.scale_index]);
            update_os_menu_bar();
            break;
        case MENU_ID_RES720:  g_cfg.auto_dock_res = 0; apply_live_resolution(1280, 720);  update_os_menu_bar(); break;
        case MENU_ID_RES1080: g_cfg.auto_dock_res = 0; apply_live_resolution(1920, 1080); update_os_menu_bar(); break;
        case MENU_ID_RES1024: g_cfg.auto_dock_res = 0; apply_live_resolution(1024, 768);  update_os_menu_bar(); break;
        case MENU_ID_AUTODOCK: {
            g_cfg.auto_dock_res = !g_cfg.auto_dock_res;
            if (g_cfg.auto_dock_res) {
                nxn_power pwr = NXN_STRUCT_INIT(nxn_power);
                if (nxn_power_get(&pwr) == NXN_OK) {
                    apply_live_resolution(pwr.docked ? 1920 : 1280, pwr.docked ? 1080 : 720);
                }
            }
            update_os_menu_bar();
            break;
        }
        case MENU_ID_HDVOX:
            if (ra2_vox_hd_show) {
                ra2_vox_hd_show = 0;
            } else {
                ra2_vox_set_scale(2);
                ra2_vox_aa = 0;
                ra2_vox_hd_show = 1;
            }
            update_os_menu_bar();
            break;
        case MENU_ID_FPS:
            g_cfg.show_fps = !g_cfg.show_fps;
            hle_screen_fps_overlay(g_cfg.show_fps);
            update_os_menu_bar();
            break;
        case MENU_ID_RSTICK:    g_cfg.rstick_pan    = !g_cfg.rstick_pan;    update_os_menu_bar(); break;
        case MENU_ID_TWOFINGER: g_cfg.twofinger_pan = !g_cfg.twofinger_pan; update_os_menu_bar(); break;
        case MENU_ID_DPAD:      g_cfg.dpad_pan      = !g_cfg.dpad_pan;      update_os_menu_bar(); break;
        case MENU_ID_WASD:      g_cfg.wasd_pan      = !g_cfg.wasd_pan;      update_os_menu_bar(); break;
        case MENU_ID_SPD_SLOW:  g_cfg.cursor_speed  = 8.0f;                 update_os_menu_bar(); break;
        case MENU_ID_SPD_NORM:  g_cfg.cursor_speed  = 12.0f;                update_os_menu_bar(); break;
        case MENU_ID_SPD_FAST:  g_cfg.cursor_speed  = 18.0f;                update_os_menu_bar(); break;
        case MENU_ID_CONFINE:
            g_cfg.confine_mouse = !g_cfg.confine_mouse;
            hle_screen_confine(g_cfg.confine_mouse);
            update_os_menu_bar();
            break;
        case MENU_ID_HELP_CTRL: {
            char msg[1024];
            snprintf(msg, sizeof(msg), "%s\n\n%s\n\n%s",
                     nxn_tr("guide.gamepad"), nxn_tr("guide.touch"), nxn_tr("guide.kbmouse"));
            show_info_dialog("dlg.controls.title", msg);
            break;
        }
        case MENU_ID_HELP_PERF: {
            nxn_power pwr = NXN_STRUCT_INIT(nxn_power);
            int docked = 0, pct = -1;
            if (nxn_power_get(&pwr) == NXN_OK) { docked = (int)pwr.docked; pct = (int)pwr.percent; }
            uint64_t hits = g_hle_cache_hits;
            uint64_t disk = g_hle_disk_reads;
            double ratio = (hits + disk) > 0 ? (100.0 * (double)hits / (double)(hits + disk)) : 0.0;
            char msg[640];
            snprintf(msg, sizeof(msg),
                     "FPS: %d | Mode: %s | Battery: %d%%\n"
                     "Resolution: %dx%d (Auto Dock: %s)\n"
                     "Fast I/O Cache: %llu RAM hits / %llu SD reads (%.1f%% cached)\n"
                     "Language: %s | Mod: %s",
                     hle_screen_get_fps(),
                     docked ? "Docked (TV)" : "Handheld", pct,
                     g_cfg.res_w, g_cfg.res_h, g_cfg.auto_dock_res ? "ON" : "OFF",
                     (unsigned long long)hits, (unsigned long long)disk, ratio,
                     g_cfg.use_turkish_csf ? "Turkish (RA2.CSF)" : "Original",
                     (g_cfg.yuri_modded && g_cfg.mod_name[0]) ? g_cfg.mod_name : "Unmodded");
            show_info_dialog("dlg.perf.title", msg);
            break;
        }
        case MENU_ID_HELP_ABOUT: {
            char msg[512];
            snprintf(msg, sizeof(msg),
                     "RA2 Yuri Port v1.2.0 (Nexvyn OS Native SDK 1.2)\n"
                     "Resolution: %dx%d | Mode: %s\n"
                     "Language: %s | Mod: %s",
                     g_cfg.res_w, g_cfg.res_h,
                     g_cfg.fullscreen ? "Fullscreen" : "Windowed",
                     g_cfg.use_turkish_csf ? "Turkish (RA2.CSF)" : "Original",
                     (g_cfg.yuri_modded && g_cfg.mod_name[0]) ? g_cfg.mod_name : "Unmodded");
            show_info_dialog("dlg.about.title", msg);
            break;
        }
        default: break;
    }
}

static void pump_os_events_in_game(void) {
    nxn_event ev = NXN_STRUCT_INIT(nxn_event);
    while (nxn_event_poll(&ev) > 0) {
        if (ev.type == NXN_EVENT_MENU) {
            handle_os_menu_action(ev.item_id);
        } else if (ev.type == NXN_EVENT_DOCK && g_cfg.auto_dock_res) {
            apply_live_resolution(ev.docked ? 1920 : 1280, ev.docked ? 1080 : 720);
            update_os_menu_bar();
        } else if (ev.type == NXN_EVENT_QUIT) {
            uint32_t h = hle_first_hwnd();
            if (h) hle_post_message(h, 0x0010u /* WM_CLOSE */, 0, 0);
            else hle_exit(0);
        } else if (ev.type == NXN_EVENT_FOCUS && !ev.focused) {
            on_focus_lost();
        }
        memset(&ev, 0, sizeof(ev));
        ev.size = sizeof(ev);
    }
}
#endif

/* Optional keyboard WASD -> Arrow camera panning */
static int on_key_hook(int sdl_scancode, int down) {
    if (!g_cfg.wasd_pan) return 0;
    /* Do not hijack WASD when Ctrl/Alt is held */
    SDL_Keymod mod = SDL_GetModState();
    if (mod & (KMOD_CTRL | KMOD_ALT)) return 0;
    switch (sdl_scancode) {
        case SDL_SCANCODE_W: hle_input_key(down, VK_UP,    72); return 1;
        case SDL_SCANCODE_S: hle_input_key(down, VK_DOWN,  80); return 1;
        case SDL_SCANCODE_A: hle_input_key(down, VK_LEFT,  75); return 1;
        case SDL_SCANCODE_D: hle_input_key(down, VK_RIGHT, 77); return 1;
        default: return 0;
    }
}

/* Two-finger touch drag -> direct RTS camera panning (stable finger IDs) */
static int on_finger_hook(int type, int64_t finger_id, float x, float y, float dx, float dy) {
    (void)dx; (void)dy;
    if (!g_cfg.twofinger_pan) return 0;

    if (type == 1) { /* DOWN */
        for (int i = 0; i < 8; i++) {
            if (!g_fingers[i].active) {
                g_fingers[i].active = 1;
                g_fingers[i].id = finger_id;
                g_fingers[i].x = x;
                g_fingers[i].y = y;
                break;
            }
        }
    } else if (type == 2) { /* MOTION */
        for (int i = 0; i < 8; i++) {
            if (g_fingers[i].active && g_fingers[i].id == finger_id) {
                g_fingers[i].x = x;
                g_fingers[i].y = y;
                break;
            }
        }
    } else if (type == 3) { /* UP */
        for (int i = 0; i < 8; i++) {
            if (g_fingers[i].active && g_fingers[i].id == finger_id) {
                g_fingers[i].active = 0;
                break;
            }
        }
    }

    int idx[2] = { -1, -1 };
    int count = 0;
    for (int i = 0; i < 8; i++) {
        if (g_fingers[i].active) {
            if (count < 2) idx[count] = i;
            count++;
        }
    }

    if (count >= 2) {
        int a = idx[0], b = idx[1];
        float cx = (g_fingers[a].x + g_fingers[b].x) * 0.5f;
        float cy = (g_fingers[a].y + g_fingers[b].y) * 0.5f;
        if (!g_2f_active || g_2f_id0 != g_fingers[a].id || g_2f_id1 != g_fingers[b].id) {
            g_2f_active = 1;
            g_2f_id0 = g_fingers[a].id;
            g_2f_id1 = g_fingers[b].id;
            g_2f_last_cx = cx;
            g_2f_last_cy = cy;
            g_2f_mode = G2_UNDECIDED;
            g_2f_start_cx = cx;
            g_2f_last_dist = hypotf(g_fingers[a].x - g_fingers[b].x, g_fingers[a].y - g_fingers[b].y);
            g_2f_wheel_acc = 0.0f;
            g_2f_start_cy = cy;
            g_2f_start_dist = g_2f_last_dist;
            g_2f_ax0 = g_fingers[a].x; g_2f_ay0 = g_fingers[a].y;
            g_2f_bx0 = g_fingers[b].x; g_2f_by0 = g_fingers[b].y;
        } else {
            if (g_cfg.touch_wheel) {
                float dist = hypotf(g_fingers[a].x - g_fingers[b].x, g_fingers[a].y - g_fingers[b].y);
                float dd = dist - g_2f_last_dist;
                float mvx = cx - g_2f_last_cx, mvy = cy - g_2f_last_cy;
                g_2f_last_dist = dist;
                if (g_2f_mode == G2_UNDECIDED) {
                    float net_dd = dist - g_2f_start_dist;
                    float net_dx = cx - g_2f_start_cx, net_dy = cy - g_2f_start_cy;
                    float net_mv = hypotf(net_dx, net_dy);
                    float a_moved = hypotf(g_fingers[a].x - g_2f_ax0, g_fingers[a].y - g_2f_ay0);
                    float b_moved = hypotf(g_fingers[b].x - g_2f_bx0, g_fingers[b].y - g_2f_by0);
                    float travel = fabsf(net_dd) + net_mv;
                    int both = a_moved > G2_DECIDE_AT * 0.5f && b_moved > G2_DECIDE_AT * 0.5f;
                    if ((both && travel > G2_DECIDE_AT) || travel > 3.0f * G2_DECIDE_AT) {
                        if (fabsf(net_dd) > 1.5f * net_mv) g_2f_mode = G2_PINCH;
                        else if (g_2f_start_cx > G2_SIDEBAR_X && fabsf(net_dy) > 0.5f * net_mv) g_2f_mode = G2_SCROLL;
                        else g_2f_mode = G2_PAN;
                        ra2_log_append("touch gesture: %s", g_2f_mode == G2_PINCH ? "pinch" : g_2f_mode == G2_SCROLL ? "scroll" : "pan");
                    }
                }
                if (g_2f_mode == G2_PINCH || g_2f_mode == G2_SCROLL) {
                    /* spread = zoom in = wheel away from the user (+); a finger moving down scrolls up (+) */
                    /* Yuri's Revenge ignores the wheel for zoom (checked in the emulator), so a pinch is swallowed, not sent. */
                    g_2f_wheel_acc += (g_2f_mode == G2_PINCH) ? 0.0f : mvy;
                    while (fabsf(g_2f_wheel_acc) >= G2_NOTCH) {
                        int notch = g_2f_wheel_acc > 0.0f ? 120 : -120;
                        hle_input_wheel(notch);
                        ra2_log_append("touch wheel %+d", notch);
                        g_2f_wheel_acc -= (notch > 0 ? G2_NOTCH : -G2_NOTCH);
                    }
                    g_2f_last_cx = cx;
                    g_2f_last_cy = cy;
                    for (int i = 0; i < 4; i++) g_touch_pan_want[i] = 0;
                    return 1;
                }
            }
            float dcx = cx - g_2f_last_cx;
            float dcy = cy - g_2f_last_cy;
            float sens = g_cfg.touch_pan_sens > 0.1f ? g_cfg.touch_pan_sens : 1.0f;
            float thresh = 0.008f / sens;
            if (fabsf(dcx) > thresh || fabsf(dcy) > thresh) {
                float sx = g_cfg.touch_pan_invert ? dcx : -dcx;
                float sy = g_cfg.touch_pan_invert ? dcy : -dcy;
                g_touch_pan_want[0] = (sx >  thresh); /* Left */
                g_touch_pan_want[1] = (sx < -thresh); /* Right */
                g_touch_pan_want[2] = (sy >  thresh); /* Up */
                g_touch_pan_want[3] = (sy < -thresh); /* Down */
                g_touch_pan_expire_ms = hle_ticks_ms() + 140u;
                g_2f_last_cx = cx;
                g_2f_last_cy = cy;
            }
        }
        return 1;
    } else {
        if (g_2f_active) {
            g_2f_active = 0;
            g_2f_mode = G2_UNDECIDED;
            for (int i = 0; i < 4; i++) g_touch_pan_want[i] = 0;
        }
    }
    return 0;
}

static void update_switch_input(void) {
    if (!g_joy && SDL_NumJoysticks() > 0) {
        g_joy = SDL_JoystickOpen(0);
    }

    int want_pan[4] = { 0, 0, 0, 0 };
    uint32_t now_ms = hle_ticks_ms();

    /* Merge active 2-finger touch pan */
    if (g_cfg.twofinger_pan && now_ms <= g_touch_pan_expire_ms) {
        for (int i = 0; i < 4; i++) want_pan[i] |= g_touch_pan_want[i];
    }

    if (g_joy) {
        int gw = g_cfg.res_w > 0 ? g_cfg.res_w : 1280;
        int gh = g_cfg.res_h > 0 ? g_cfg.res_h : 720;
        int cur_w = 0, cur_h = 0, bpp = 0;
        hle_dd_mode(&cur_w, &cur_h, &bpp);
        if (cur_w >= 640 && cur_h >= 400) { gw = cur_w; gh = cur_h; }

        /* Sync cursor with game position in case touch or USB mouse moved it */
        int cur_gx = 0, cur_gy = 0;
        hle_input_position(&cur_gx, &cur_gy);

        /* Switch SDL Joystick button mapping:
         * 0=A, 1=B, 2=X, 3=Y, 4=L3, 5=R3, 6=L, 7=R, 8=ZL, 9=ZR, 10=Plus, 11=Minus,
         * 12=DLeft, 13=DUp, 14=DRight, 15=DDown */
        int btn_a     = SDL_JoystickGetButton(g_joy, 0);
        int btn_b     = SDL_JoystickGetButton(g_joy, 1);
        int btn_x     = SDL_JoystickGetButton(g_joy, 2);
        int btn_y     = SDL_JoystickGetButton(g_joy, 3);
        int btn_l3    = SDL_JoystickGetButton(g_joy, 4);
        int btn_r3    = SDL_JoystickGetButton(g_joy, 5);
        int btn_l     = SDL_JoystickGetButton(g_joy, 6);
        int btn_r     = SDL_JoystickGetButton(g_joy, 7);
        int btn_zl    = SDL_JoystickGetButton(g_joy, 8);
        int btn_zr    = SDL_JoystickGetButton(g_joy, 9);
        int btn_plus  = SDL_JoystickGetButton(g_joy, 10);
        int btn_minus = SDL_JoystickGetButton(g_joy, 11);

        /* 1. Left Stick -> Precision Cursor (with L slow-precision / R fast-boost) */
        float lx = (float)SDL_JoystickGetAxis(g_joy, 0) / 32768.0f;
        float ly = (float)SDL_JoystickGetAxis(g_joy, 1) / 32768.0f;
        float dz = g_cfg.deadzone;
        float mag = sqrtf(lx * lx + ly * ly);
        if (mag > dz) {
            float norm = (mag - dz) / (1.0f - dz);
            if (norm > 1.0f) norm = 1.0f;
            /* Smooth quadratic curve for pinpoint micro + fast macro movement */
            float curve = norm * (0.45f + 0.55f * norm);
            float spd = g_cfg.cursor_speed;
            if (btn_l && g_cfg.l_action == 0) spd *= 0.45f; /* Precision aim */
            if (btn_r && g_cfg.r_action == 0) spd *= 1.75f; /* Fast sweep */

            g_cursor_x = (float)cur_gx + (lx / mag) * curve * spd;
            g_cursor_y = (float)cur_gy + (ly / mag) * curve * spd;
            if (g_cursor_x < 0.0f) g_cursor_x = 0.0f;
            if (g_cursor_y < 0.0f) g_cursor_y = 0.0f;
            if (g_cursor_x > (float)(gw - 1)) g_cursor_x = (float)(gw - 1);
            if (g_cursor_y > (float)(gh - 1)) g_cursor_y = (float)(gh - 1);

            hle_input_mouse(WM_MOUSEMOVE, (int)g_cursor_x, (int)g_cursor_y);
        } else {
            g_cursor_x = (float)cur_gx;
            g_cursor_y = (float)cur_gy;
        }

        /* 2. Right Stick -> Practical 8-Way RTS Camera Pan! */
        if (g_cfg.rstick_pan && SDL_JoystickNumAxes(g_joy) >= 4) {
            float rx = (float)SDL_JoystickGetAxis(g_joy, 2) / 32768.0f;
            float ry = (float)SDL_JoystickGetAxis(g_joy, 3) / 32768.0f;
            float rdz = dz + 0.06f;
            if (rx < -rdz) want_pan[0] = 1;
            if (rx >  rdz) want_pan[1] = 1;
            if (ry < -rdz) want_pan[2] = 1;
            if (ry >  rdz) want_pan[3] = 1;
        }

        /* 3. D-Pad -> RTS Camera Pan (supports both button 12..15 and Hat 0) */
        if (g_cfg.dpad_pan) {
            if (SDL_JoystickGetButton(g_joy, 12)) want_pan[0] = 1;
            if (SDL_JoystickGetButton(g_joy, 14)) want_pan[1] = 1;
            if (SDL_JoystickGetButton(g_joy, 13)) want_pan[2] = 1;
            if (SDL_JoystickGetButton(g_joy, 15)) want_pan[3] = 1;
            if (SDL_JoystickNumHats(g_joy) > 0) {
                Uint8 hat = SDL_JoystickGetHat(g_joy, 0);
                if (hat & SDL_HAT_LEFT)  want_pan[0] = 1;
                if (hat & SDL_HAT_RIGHT) want_pan[1] = 1;
                if (hat & SDL_HAT_UP)    want_pan[2] = 1;
                if (hat & SDL_HAT_DOWN)  want_pan[3] = 1;
            }
        }

        /* 4. Mouse Buttons: A/ZR = Left Click (supports drag-box select!), X/ZL = Right Click */
        int lmb = (btn_a || btn_zr) ? 1 : 0;
        if (lmb != g_prev_lmb) {
            g_prev_lmb = lmb;
            hle_input_mouse(lmb ? WM_LBUTTONDOWN : WM_LBUTTONUP, (int)g_cursor_x, (int)g_cursor_y);
        }
        int rmb = (btn_x || btn_zl) ? 1 : 0;
        if (rmb != g_prev_rmb) {
            g_prev_rmb = rmb;
            hle_input_mouse(rmb ? WM_RBUTTONDOWN : WM_RBUTTONUP, (int)g_cursor_x, (int)g_cursor_y);
        }

        /* 5. B / Plus -> Escape */
        int esc = (btn_b || btn_plus) ? 1 : 0;
        if (esc != g_prev_esc) {
            g_prev_esc = esc;
            hle_input_key(esc, VK_ESCAPE, 1);
        }

        /* 6. Y -> Configurable: Deploy (D) / OSK / Force Attack (Ctrl) / Stop (S) */
        if (btn_y != g_prev_y) {
            g_prev_y = btn_y;
            if (g_cfg.y_action == 0)      hle_input_key(btn_y, VK_D, 32);
            else if (g_cfg.y_action == 2) hle_input_key(btn_y, VK_CONTROL, 29);
            else if (g_cfg.y_action == 3) hle_input_key(btn_y, VK_S, 31);
            else if (btn_y) {
                if (SDL_IsTextInputActive()) SDL_StopTextInput();
                else SDL_StartTextInput();
            }
        }

        /* 6b. L / R extra button bindings when not in precision/boost mode */
        static int s_prev_l = 0, s_prev_r = 0;
        if (btn_l != s_prev_l) {
            s_prev_l = btn_l;
            if (g_cfg.l_action == 1)      hle_input_key(btn_l, VK_SHIFT, 42);
            else if (g_cfg.l_action == 2) hle_input_key(btn_l, VK_1, 2);
        }
        if (btn_r != s_prev_r) {
            s_prev_r = btn_r;
            if (g_cfg.r_action == 1)      hle_input_key(btn_r, VK_CONTROL, 29);
            else if (g_cfg.r_action == 2) hle_input_key(btn_r, VK_2, 3);
        }

        /* 7. L3 / R3 configurable bindings */
        if (btn_l3 != g_prev_l3) {
            g_prev_l3 = btn_l3;
            if (g_cfg.l3_action == 0) hle_input_key(btn_l3, VK_H, 35);
            else                      hle_input_key(btn_l3, VK_SPACE, 57);
        }
        if (btn_r3 != g_prev_r3) {
            g_prev_r3 = btn_r3;
            if (g_cfg.r3_action == 0)      hle_input_key(btn_r3, VK_T, 20);
            else if (g_cfg.r3_action == 1) hle_input_key(btn_r3, VK_P, 25);
            else                           hle_input_key(btn_r3, VK_X, 45);
        }

        /* 8. Minus -> Short press (< 450 ms) sends TAB; long press (1s) belongs to Nexvyn OS Exit Fullscreen */
        if (btn_minus && !g_prev_minus) {
            g_minus_down_ms = now_ms;
        } else if (!btn_minus && g_prev_minus) {
            if (now_ms - g_minus_down_ms < 450u) {
                hle_input_key(1, VK_TAB, 15);
                hle_input_key(0, VK_TAB, 15);
            }
        }
        g_prev_minus = btn_minus;
    }

    /* Apply final camera pan arrow states */
    for (int i = 0; i < 4; i++) {
        set_pan_key(i, want_pan[i]);
    }
}

static void frame_pump(void) {
#ifdef NEXVYN_ABI
    pump_os_events_in_game();
#endif
    update_switch_input();
    hle_screen_pump();
}

static uint32_t exe_stamp(const char *path) {
    uint8_t head[4096] = { 0 };
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    size_t n = fread(head, 1, sizeof head, f);
    fclose(f);
    uint32_t nt = n >= 0x40 ? *(const uint32_t *)(head + 0x3C) : 0;
    return nt && nt < sizeof head - 12 ? *(const uint32_t *)(head + nt + 8) : 0;
}

static int ra2_app_main(int argc, char **argv) {
    (void)argc; (void)argv;
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);
    hle_filetrace_on = 0;
    win32hle_trace = 0;

    ra2_log_append("RA2 Yuri Port v1.1.0 (Nexvyn OS Native SDK 1.2)");

    /* 1. Run the Native Launcher UI first */
    memset(&g_cfg, 0, sizeof(g_cfg));
    if (!ra2_run_launcher(&g_cfg)) {
        ra2_log_append("User exited from launcher.");
        return 0;
    }

    /* 2. Apply ra2md.ini config, Turkish RA2.CSF overlay, and Yuri mod overlay */
    char overlay_dir[512] = { 0 };
    ra2_apply_ini_and_overlay(&g_cfg, overlay_dir, sizeof(overlay_dir));

    const char *game_dir = g_cfg.game_dir[0] ? g_cfg.game_dir : "game";
    printf("[Nexvyn RA2] Launching from: %s (overlay: %s)\n", game_dir, overlay_dir[0] ? overlay_dir : "none");

    hle_set_drive('C', game_dir);
    if (g_cfg.langmd_override[0] || g_cfg.language_override[0]) {
        hle_set_lang_override(g_cfg.langmd_override, g_cfg.language_override);
    }
    if (overlay_dir[0] && strcmp(overlay_dir, game_dir) != 0) {
        hle_set_overlay(game_dir, overlay_dir);
    }

    char exe_host[PATH_MAX + 16];
    if (!hle_host_path("C:\\" RA2_EXE_NAME, exe_host, sizeof exe_host)) {
        fprintf(stderr, "cannot locate " RA2_EXE_NAME " in %s\n", game_dir);
        return 1;
    }

    uint32_t stamp = exe_stamp(exe_host);
    printf("[Nexvyn RA2] Executable timestamp: 0x%08X (wanted 0x%08X)\n", stamp, RA2_EXE_STAMP);

    win32hle_register(g_ra2_shims);
    signal(SIGPIPE, SIG_IGN);
    signal(SIGSEGV, on_fault);
    signal(SIGFPE, on_fault);
    signal(SIGILL, on_fault);
    recomp_host_init();
    hle_com_register_class(CLSID_Blowfish, ra2_blowfish_create);

    pe_image img;
    if (recomp_pe_map(exe_host, &img) != 0 || img.base != RA2_IMAGE_BASE) {
        fprintf(stderr, "cannot map %s at 0x%08X\n", exe_host, RA2_IMAGE_BASE);
        return 1;
    }
    hle_module_add("C:\\" RA2_EXE_NAME, img.base, img.resource_rva, img.resource_size, 1);
    int unresolved = recomp_pe_bind(&img, hle_resolve_or_stub);
    printf("  mapped %s: 0x%08X-0x%08X, %d imports unresolved\n", exe_host, img.base, img.base + img.span, unresolved);
    hle_set_command_line("\"C:\\" RA2_EXE_NAME "\"");

    chdir(game_dir);

    /* 3. Apply display, scaling, HD voxels & Nexvyn OS Native SDK 1.2 window mode */
    static const char *const k_scales[] = { "sharp", "smooth", "nearest", "integer", "crt" };
    const char *scale_name = (g_cfg.scale_index >= 0 && g_cfg.scale_index < 5) ? k_scales[g_cfg.scale_index] : "sharp";
    hle_screen_scale(scale_name);
    hle_screen_stretch(g_cfg.fit_mode == 0 ? 1 : 0);
    hle_screen_bars(g_cfg.fit_mode == 2 ? 1 : 0);
    hle_screen_fps_overlay(g_cfg.show_fps);
    hle_screen_confine(g_cfg.confine_mouse);
    hle_screen_cursor_hook = menus_use_windows_cursor;
    hle_screen_key_hook = on_key_hook;
    hle_screen_finger_hook = on_finger_hook;
    hle_screen_focus_lost_hook = on_focus_lost;

    if (g_cfg.hd_voxels == 0) {
        ra2_vox_hd_show = 0;
    } else if (g_cfg.hd_voxels == 2) {
        ra2_vox_set_scale(2);
        ra2_vox_aa = 1;
        ra2_vox_hd_show = 1;
    } else {
        ra2_vox_set_scale(2);
        ra2_vox_aa = 0;
        ra2_vox_hd_show = 1;
    }

    SDL_SetHint("NEXVYN_LONG_PRESS_RIGHT", g_cfg.longpress_rc ? "1" : "0");

#ifdef NEXVYN_ABI
    {
        nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
        if (nxn_caps_get(&caps) == NXN_OK && (caps.features & NXN_CAP_WINDOW_CTL)) {
            nxn_window_set_title("RA2 Yuri Port", g_cfg.use_turkish_csf ? "Yuri's Revenge (TR)" : "Yuri's Revenge");
            nxn_window_set_mode(g_cfg.fullscreen ? NXN_WIN_FULLSCREEN : NXN_WIN_NORMAL);
        }
    }
#endif

    if (hle_screen_open(RA2_TITLE, g_cfg.fullscreen, 0) != 0) {
        fprintf(stderr, "hle_screen_open failed\n");
        return 1;
    }
    SDL_StopTextInput(); /* Do not pop up OSK automatically on game launch */

    hle_set_pump_hook(frame_pump);
    hle_screen_compose_hook = compose_hd;
    hle_screen_overlay_hook = overlay_hd;
#ifdef NEXVYN_ABI
    update_os_menu_bar();
#endif

    printf("[Nexvyn RA2] Entering game engine entry point at 0x%08X...\n", ra2_entry_va);
    uint32_t rc = hle_call_guest(ra2_entry_va, 0, NULL);
    printf("[Nexvyn RA2] Game loop ended with code %u\n", rc);

    release_all_virtual_inputs();
    hle_exit((int)rc);
    return 0;
}

int main(int argc, char **argv) {
#ifdef NEXVYN_ABI
    return nxn_run(argc, argv, ra2_app_main, NULL);
#else
    return ra2_app_main(argc, argv);
#endif
}
