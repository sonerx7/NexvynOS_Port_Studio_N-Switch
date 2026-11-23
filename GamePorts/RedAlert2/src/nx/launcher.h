#ifndef RA2_NX_LAUNCHER_H
#define RA2_NX_LAUNCHER_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ra2_config_t {
    char game_dir[512];
    char mod_name[128];

    int stable_profile;      /* 1 = Nexvyn OS Stable Profile (default, locks tuning) */
    int fullscreen;          /* 1 = Fullscreen, 0 = Windowed */
    int auto_dock_res;       /* 0 = Off (default), 1 = Auto 1080p Docked / 720p Handheld */
    int res_index;           /* Index into resolution table (default: 1280x720) */
    int res_w;
    int res_h;
    int scale_index;         /* 0=sharp, 1=smooth, 2=nearest, 3=integer, 4=crt */
    int fit_mode;            /* 0=fill fullscreen (no bars), 1=aspect black, 2=aspect blur */
    int hd_voxels;           /* 0=off, 1=2x, 2=1x smooth */
    int detail_level;        /* 0=low, 1=medium, 2=high */
    int skip_intro;          /* 1=yes */
    int show_fps;            /* 0=off (default), 1=show live FPS counter HUD */

    int game_lang;           /* 0=Auto(System), 1=English, 2=Turkish(RA2.CSF), 3=German(langmd.mix) */
    int use_turkish_csf;     /* Resolved at launch from game_lang */
    char langmd_override[128];   /* Resolved archive override (e.g. langmd_eng.mix) */
    char language_override[128]; /* Resolved archive override (e.g. language_eng.mix) */
    int yuri_modded;         /* 0=unmodded Yuri's Revenge, 1=modded */

    float vol_sfx;           /* 0.0 .. 1.0 */
    float vol_voice;         /* 0.0 .. 1.0 */
    float vol_music;         /* 0.0 .. 1.0 */

    /* RTS Camera Pan & Input Tuning */
    int rstick_pan;          /* Right stick pans map (VK_LEFT/RIGHT/UP/DOWN) */
    int twofinger_pan;       /* 2-finger touch drag pans map */
    int dpad_pan;            /* D-Pad pans map */
    int wasd_pan;            /* Keyboard WASD pans map */
    int edge_scroll;         /* Screen edge scroll */
    int scroll_rate;         /* 1..6 (ra2md.ini ScrollRate) */

    /* Gamepad tuning & button remapping */
    float cursor_speed;      /* 4.0 .. 24.0 px/frame */
    float deadzone;          /* 0.05 .. 0.35 */
    int y_action;            /* 0=Deploy(D), 1=OSK, 2=ForceAttack(Ctrl), 3=Stop(S) */
    int l_action;            /* 0=Precision(slow), 1=MultiSelect(Shift), 2=Group 1 */
    int r_action;            /* 0=FastBoost, 1=ForceAttack(Ctrl), 2=Group 2 */
    int l3_action;           /* 0=Base(H), 1=LastEvent(Space) */
    int r3_action;           /* 0=SameType(T), 1=AllCombat(P), 2=Scatter(X) */

    /* Touch tuning */
    int longpress_rc;        /* 1-finger long press -> right click */
    int twofinger_rc;        /* 2-finger tap -> right click */
    int touch_wheel;         /* pinch and 2-finger drag in the sidebar zone -> mouse wheel (0 = off) */
    float touch_pan_sens;    /* 0.5 .. 2.0 */
    int touch_pan_invert;    /* 1=natural drag, 0=inverted */

    /* Mouse & Keyboard tuning */
    int confine_mouse;       /* 1=confine pointer to picture */
} ra2_config_t;

void ra2_config_set_stable_defaults(ra2_config_t *cfg, int keep_paths);
void ra2_log_append(const char *fmt, ...);

/* Runs the Native SDK 1.2 Launcher UI.
 * Returns 1 if the user clicked PLAY (cfg populated & saved), 0 if exited. */
int ra2_run_launcher(ra2_config_t *cfg);

/* Writes ra2md.ini / ra2.ini and prepares overlay dir (Turkish RA2.CSF and/or mod).
 * Also resolves language archive overrides (langmd_eng.mix / language_eng.mix) in cfg. */
void ra2_apply_ini_and_overlay(ra2_config_t *cfg, char *out_overlay_dir, size_t cap);

/* Updates ScreenWidth/ScreenHeight in active overlay ra2md.ini on live dock/menu change. */
void ra2_write_resolution_ini(const ra2_config_t *cfg, int w, int h);

#ifdef __cplusplus
}
#endif

#endif /* RA2_NX_LAUNCHER_H */
