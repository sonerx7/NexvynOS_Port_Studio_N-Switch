/* Nexvyn Port Studio launcher layout standard (C++, ImGui + nxn_os_ui.h).
 *
 * One look for every port launcher, built from the OS widgets so it follows the system theme,
 * text scale and window size. Include after imgui.h and <nexvyn/nxn_os_ui.h>.
 *
 *   hero    A tinted card on top: logo, title, subtitle, status badges, a large PLAY button and a
 *           quieter Exit. Wide window: text on the left, buttons on the right. Narrow window
 *           (< NX_UI_NARROW_PX): buttons stack full width under the text, PLAY first.
 *   grid    Cards flow into 1, 2 or 3 columns by the width they get (NX_UI_COL_MIN_PX each).
 *           A dense page stays short on a TV and readable in a small window.
 *   tabs    Segmented tabs when they fit, a dropdown when they do not.
 *
 * Sizes are design pixels; nxn_os_s() scales them with the OS text scale and window size, so
 * nothing here hard-codes 1280x720. Targets stay at least 44 design px (NXN_OS_TOUCH_MIN).
 * Rules and the reasons are in _PortStudioMain/docs/PORT_LAUNCHER_STANDARD.md. */
#ifndef NX_LAUNCHER_UI_H
#define NX_LAUNCHER_UI_H

#include <math.h>
#include <stdint.h>

#define NX_UI_NARROW_PX   640.0f   /* below this content width the hero and tabs switch to the narrow layout */
#define NX_UI_COL_MIN_PX  300.0f   /* narrowest card column */
#define NX_UI_PLAY_H_PX    56.0f   /* the PLAY button is clearly taller than the 30 px OS button */
#define NX_UI_PLAY_MIN_W   200.0f

enum nx_hero_action { NX_HERO_NONE = 0, NX_HERO_PLAY = 1, NX_HERO_EXIT = 2 };

typedef struct nx_hero_desc {
    const char *title;
    const char *subtitle;
    ImTextureID logo;          /* 0 = no logo */
    const char *play_label;    /* "Play", or "Select game folder" while data is missing */
    const char *exit_label;
} nx_hero_desc;

/* Docked: TV, no touch screen. Handheld: touch screen and attached pad. Read from the OS power state;
 * false (handheld) when the OS does not say. Layout never depends on this, only the order of hints. */
static inline bool nx_ui_docked(void) {
    nxn_power pwr = NXN_STRUCT_INIT(nxn_power);
    return nxn_power_get(&pwr) == NXN_OK && pwr.docked;
}

static inline bool nx_ui_narrow(void) {
    return ImGui::GetContentRegionAvail().x < nxn_os_s(NX_UI_NARROW_PX);
}

static inline ImU32 nx_ui_tint(uint32_t accent_argb, uint32_t base_argb, float amount) {
    ImVec4 a = nxn_os_imvec4(accent_argb), b = nxn_os_imvec4(base_argb);
    ImVec4 m(b.x + (a.x - b.x) * amount, b.y + (a.y - b.y) * amount, b.z + (a.z - b.z) * amount, 1.0f);
    return ImGui::ColorConvertFloat4ToU32(m);
}

/* The hero. `badges` is a callable that draws the status badges (nxn_os_badge calls) inside one row.
 * Returns which button was pressed this frame. */
template <class BadgeFn>
static inline int nx_hero(const nx_hero_desc &d, const nxn_ui_tokens &tok, BadgeFn &&badges) {
    int action = NX_HERO_NONE;
    const bool narrow = nx_ui_narrow();
    const float pad = nxn_os_sp(NXN_OS_SP_L);
    nxn_os_card_begin_ex("nx_hero", 0.0f, pad, pad, tok,
                         nx_ui_tint(tok.accent, tok.content_bg, 0.10f), nx_ui_tint(tok.accent, tok.border, 0.55f));

    float play_w = ImGui::CalcTextSize(d.play_label ? d.play_label : "").x + nxn_os_sp(NXN_OS_SP_XL) * 2.0f;
    if (play_w < nxn_os_s(NX_UI_PLAY_MIN_W)) play_w = nxn_os_s(NX_UI_PLAY_MIN_W);
    const float exit_w = nxn_os_s(96.0f);
    const float play_h = nxn_os_s(NX_UI_PLAY_H_PX);
    const float gap = nxn_os_sp(NXN_OS_SP_S);

    bool table = false;
    if (!narrow && ImGui::BeginTable("##nx_hero_t", 2, ImGuiTableFlags_NoSavedSettings)) {
        table = true;
        ImGui::TableSetupColumn("##text", ImGuiTableColumnFlags_WidthStretch);
        ImGui::TableSetupColumn("##act", ImGuiTableColumnFlags_WidthFixed, play_w + exit_w + gap + nxn_os_sp(NXN_OS_SP_L));
        ImGui::TableNextRow();
        ImGui::TableNextColumn();
    }

    ImGui::BeginGroup();
    if (d.logo) {
        float sz = nxn_os_s(56.0f);
        ImGui::Image(d.logo, ImVec2(sz, sz));
        ImGui::SameLine(0.0f, nxn_os_sp(NXN_OS_SP_M));
    }
    ImGui::BeginGroup();
    nxn_os_text(NXN_OS_TEXT_TITLE, d.title ? d.title : "");
    if (d.subtitle) nxn_os_text(NXN_OS_TEXT_CAPTION, d.subtitle);
    ImGui::EndGroup();
    ImGui::EndGroup();
    nxn_os_gap(NXN_OS_SP_S);
    nxn_os_row_begin();
    badges();
    nxn_os_row_end();

    if (table) {
        ImGui::TableNextColumn();
        /* vertically centre the buttons against the text block */
        float room = ImGui::GetContentRegionAvail().y;
        (void)room;
        nxn_os_gap(NXN_OS_SP_XS);
    } else {
        nxn_os_gap(NXN_OS_SP_M);
    }

    const bool full = narrow;
    if (nxn_os_button(d.play_label ? d.play_label : "", NXN_OS_BTN_PRIMARY, tok,
                      ImVec2(full ? -1.0f : play_w, play_h))) action = NX_HERO_PLAY;
    if (full) {
        nxn_os_gap(NXN_OS_SP_XS);
        if (nxn_os_button(d.exit_label ? d.exit_label : "", NXN_OS_BTN_DEFAULT, tok, ImVec2(-1.0f, 0.0f))) action = NX_HERO_EXIT;
    } else {
        ImGui::SameLine(0.0f, gap);
        if (nxn_os_button(d.exit_label ? d.exit_label : "", NXN_OS_BTN_DEFAULT, tok, ImVec2(exit_w, play_h))) action = NX_HERO_EXIT;
    }

    if (table) ImGui::EndTable();
    nxn_os_card_end();
    return action;
}

/* ---- card grid ------------------------------------------------------------------------------ */

static int g_nx_grid_cols = 1;

/* Start a grid. Returns the column count chosen from the width available (1 .. max_cols). */
static inline int nx_grid_begin(const char *id, int max_cols = 3, float min_col_px = NX_UI_COL_MIN_PX) {
    int n = (int)floorf(ImGui::GetContentRegionAvail().x / nxn_os_s(min_col_px));
    if (n < 1) n = 1;
    if (n > max_cols) n = max_cols;
    g_nx_grid_cols = 1;
    if (n > 1 && ImGui::BeginTable(id, n, ImGuiTableFlags_NoSavedSettings | ImGuiTableFlags_SizingStretchSame)) {
        g_nx_grid_cols = n;
        ImGui::TableNextRow();
    }
    return g_nx_grid_cols;
}

/* Move to the next cell (or just add a gap when there is one column). Call before each card. */
static inline void nx_grid_next(void) {
    if (g_nx_grid_cols > 1) ImGui::TableNextColumn();
    else nxn_os_gap(NXN_OS_SP_S);
}

static inline void nx_grid_end(void) {
    if (g_nx_grid_cols > 1) ImGui::EndTable();
    g_nx_grid_cols = 1;
}

/* ---- standard rows ---------------------------------------------------------------------------- */

/* The "Show FPS" switch every launcher puts first on its overview tab (standard, see PORT_LAUNCHER_STANDARD.md).
 * Returns true when the player flipped it; the caller saves the setting. */
static inline bool nx_fps_row(bool *on, const char *label, const char *hint) {
    bool changed = nxn_os_switch_row(label, on);
    if (hint && hint[0]) nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, hint);
    return changed;
}

/* ---- tabs ------------------------------------------------------------------------------------ */

/* Segmented tabs when they fit, a full-width dropdown when the window is narrow. */
static inline void nx_tabs(const char *id, const char *const *labels, int count, int *active, const nxn_ui_tokens &tok) {
    if (nx_ui_narrow()) {
        nxn_os_dropdown(id, labels, count, active, ImGui::GetContentRegionAvail().x, tok);
    } else {
        nxn_os_segmented_tabs(id, labels, count, active, tok);
    }
}

#endif
