#include <glad/glad.h>
#include <cstdio>
#include <cstring>
#include <cctype>
#include <cstdlib>
#include <cerrno>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <nexvyn/nexvyn_native.h>
#include "imgui.h"
#include "imgui_impl_opengl3.h"
#include <nexvyn/nxn_os_ui.h>

struct Entry {
    std::string kind, name, version, size, hash, path, url;
};
static std::vector<Entry> entries;
static char root[512];
static const char* status_key = "library.choose_hint";
static int filter = 0;
static int selected = -1;

static bool local_path(const std::string& value, const std::string& kind) {
    const std::string prefix = kind + "/";
    if (value.compare(0, prefix.size(), prefix) != 0 || value.size() <= prefix.size() + 7 ||
        value.compare(value.size() - 7, 7, ".nxvapp") != 0) return false;
    const std::string file = value.substr(prefix.size());
    if (file.front() == '.' || file.find("..") != std::string::npos) return false;
    for (unsigned char c : file)
        if (!std::isalnum(c) && c != '.' && c != '-' && c != '_') return false;
    return true;
}

static bool archive_url(const std::string& value) {
    const std::string prefix = "https://archive.org/download/";
    if (value.compare(0, prefix.size(), prefix) != 0 ||
        value.size() <= prefix.size() + 8 ||
        value.compare(value.size() - 7, 7, ".nxvapp") != 0) return false;
    const std::string path = value.substr(prefix.size());
    const auto slash = path.find('/');
    if (slash == 0 || slash == std::string::npos || path.find('/', slash + 1) != std::string::npos ||
        path.find("..") != std::string::npos || path.front() == '.') return false;
    for (unsigned char c : path)
        if (!std::isalnum(c) && c != '.' && c != '-' && c != '_' && c != '/') return false;
    return true;
}

static bool parse_entry(char* line, Entry& out) {
    std::string* dest[] = {&out.kind, &out.name, &out.version, &out.size, &out.hash, &out.path, &out.url};
    char* from = line;
    for (size_t i = 0; i < 7; ++i) {
        char* tab = strchr(from, '\t');
        if ((i < 6) != (tab != nullptr)) return false;
        if (tab) *tab = 0;
        *dest[i] = from;
        if (tab) from = tab + 1;
    }
    if ((out.kind != "game" && out.kind != "software") || out.name.empty() || out.name.size() > 160 ||
        out.version.empty() || out.hash.size() != 64 || out.size.empty() || out.size.size() > 10) return false;
    for (unsigned char c : out.hash) if (!std::isxdigit(c)) return false;
    for (unsigned char c : out.size) if (!std::isdigit(c)) return false;
    for (unsigned char c : out.version) if (!std::isdigit(c) && c != '.') return false;
    return out.url.empty() ? local_path(out.path, out.kind) :
        out.path.empty() && archive_url(out.url);
}

static bool folder_granted() {
    int allowed = 0;
    return root[0] && nxn_grant_check(root, &allowed) == NXN_OK && allowed;
}

static std::string full_path(const std::string& tail) {
    std::string path(root);
    if (!path.empty() && path.back() != '/') path += '/';
    return path + tail;
}

static void refresh() {
    if (!folder_granted()) {
        entries.clear();
        selected = -1;
        status_key = "library.choose_hint";
        return;
    }
    FILE* file = fopen(full_path("port-market.tsv").c_str(), "rb");
    if (!file) {
        entries.clear();
        selected = -1;
        status_key = "library.missing";
        return;
    }
    std::vector<Entry> candidate;
    char line[1024];
    bool valid = fgets(line, sizeof(line), file) && strcmp(line, "NXVPORTMARKET\t1\n") == 0;
    while (valid && fgets(line, sizeof(line), file)) {
        const size_t len = strlen(line);
        if (!len || line[len - 1] != '\n' || candidate.size() == 256) { valid = false; break; }
        line[len - 1] = '\0';
        Entry entry;
        valid = parse_entry(line, entry);
        if (valid) candidate.push_back(entry);
    }
    valid = valid && !ferror(file);
    fclose(file);
    entries.clear();
    selected = -1;
    if (valid) entries.swap(candidate);
    status_key = !valid ? "library.invalid" : entries.empty() ? "library.empty" : nullptr;
}

static void choose_folder() {
    nxn_pick_params pick = NXN_STRUCT_INIT(nxn_pick_params);
    pick.kind = NXN_PICK_FOLDER;
    pick.flags = NXN_PICK_REMEMBER;
    pick.title = nxn_tr("library.choose");
    char path[sizeof(root)];
    if (nxn_pick(&pick, path, sizeof(path)) != NXN_OK) return;
    snprintf(root, sizeof(root), "%s", path);
    const bool saved = nxn_fs_write(NXN_DIR_DATA, "library.txt", root, strlen(root)) == NXN_OK;
    refresh();
    if (!saved) status_key = "library.save_failed";
}

static void copy_value(const std::string& value) {
    status_key = nxn_clipboard_set(value.c_str()) == NXN_OK ? "action.copied" : "action.copy_failed";
}

static void draw(nxn_ui_tokens& tokens) {
    nxn_os_text(NXN_OS_TEXT_TITLE, nxn_tr("app.title"));
    nxn_os_text(NXN_OS_TEXT_CAPTION, nxn_tr("app.subtitle"));
    nxn_os_gap(NXN_OS_SP_S);
    nxn_os_row_begin();
    if (nxn_os_button(nxn_tr("library.choose"), NXN_OS_BTN_PRIMARY, tokens)) choose_folder();
    if (nxn_os_button(nxn_tr("library.refresh"), NXN_OS_BTN_DEFAULT, tokens)) refresh();
    nxn_os_row_end();
    if (root[0]) nxn_os_text_wrapped(NXN_OS_TEXT_CAPTION, root);
    if (status_key) nxn_os_text_wrapped(NXN_OS_TEXT_BODY, nxn_tr(status_key));
    if (entries.empty()) return;

    nxn_os_gap(NXN_OS_SP_S);
    const char* filters[] = {nxn_tr("filter.all"), nxn_tr("filter.game"), nxn_tr("filter.software")};
    if (nxn_os_segmented_tabs("filter", filters, 3, &filter, tokens)) selected = -1;
    nxn_os_gap(NXN_OS_SP_S);
    if (selected >= 0 && static_cast<size_t>(selected) < entries.size()) {
        const Entry& entry = entries[selected];
        nxn_os_card_begin("details", tokens);
        nxn_os_text_wrapped(NXN_OS_TEXT_TITLE, entry.name.c_str());
        nxn_os_kv_row(nxn_tr("item.version"), entry.version.c_str(), tokens, false);
        const double mib = strtod(entry.size.c_str(), nullptr) / 1048576.0;
        char size[32];
        snprintf(size, sizeof(size), "%.1f MiB", mib);
        nxn_os_kv_row(nxn_tr("item.size"), size, tokens, false);
        if (entry.url.empty()) {
            const std::string file = full_path(entry.path);
            struct stat info;
            const bool present = folder_granted() && stat(file.c_str(), &info) == 0 && S_ISREG(info.st_mode)
                && static_cast<unsigned long long>(info.st_size) == strtoull(entry.size.c_str(), nullptr, 10);
            nxn_os_text_wrapped(NXN_OS_TEXT_BODY, nxn_tr(present ? "item.local_hint" : "item.local_missing"));
            ImGui::BeginDisabled(!present);
            if (nxn_os_button(nxn_tr("item.copy_path"), NXN_OS_BTN_PRIMARY, tokens)) copy_value(file);
            ImGui::EndDisabled();
        } else {
            nxn_os_text_wrapped(NXN_OS_TEXT_BODY, nxn_tr("item.archive_hint"));
            if (nxn_os_button(nxn_tr("item.copy_url"), NXN_OS_BTN_PRIMARY, tokens)) copy_value(entry.url);
        }
        ImGui::SameLine();
        if (nxn_os_button(nxn_tr("item.copy_hash"), NXN_OS_BTN_DEFAULT, tokens)) copy_value(entry.hash);
        nxn_os_card_end();
        nxn_os_gap(NXN_OS_SP_S);
    }
    bool visible = false;
    for (size_t i = 0; i < entries.size(); ++i) {
        const Entry& entry = entries[i];
        if (filter && entry.kind != (filter == 1 ? "game" : "software")) continue;
        visible = true;
        char id[24];
        snprintf(id, sizeof(id), "entry-%u", static_cast<unsigned>(i));
        const std::string subtitle = entry.version + " / " + nxn_tr(entry.url.empty() ? "item.local" : "item.archive");
        if (nxn_os_list_row(id, entry.name.c_str(), subtitle.c_str(), nullptr, selected == static_cast<int>(i)))
            selected = static_cast<int>(i);
    }
    if (!visible) nxn_os_text(NXN_OS_TEXT_CAPTION, nxn_tr("library.empty"));
}

static int app_main(int, char**) {
    nxn_display* display = nullptr;
    if (nxn_display_open(nullptr, &display) != NXN_OK) {
        nxn_request_return(NXN_RETURN_ERROR, 1, nxn_tr("error.display"));
        return 1;
    }
    if (!gladLoadGLLoader((GLADloadproc)nxn_display_proc)) {
        nxn_display_close(display);
        nxn_request_return(NXN_RETURN_ERROR, 1, nxn_tr("error.display"));
        return 1;
    }
    uint32_t w = 0, h = 0;
    nxn_display_size(display, &w, &h);
    size_t read = 0;
    if (nxn_fs_read(NXN_DIR_DATA, "library.txt", root, sizeof(root) - 1, &read) == NXN_OK) root[read] = 0;
    else root[0] = 0;
    refresh();

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO& io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.LogFilename = nullptr;
    nxn_imgui_enable_gamepad(io);
    ImGui_ImplOpenGL3_Init("#version 330 core");
    nxn_ui_tokens tokens = NXN_STRUCT_INIT(nxn_ui_tokens);
    nxn_input_state input = NXN_STRUCT_INIT(nxn_input_state);
    nxn_imgui_input_state bridge;
    uint64_t last = nxn_time_ns();
    bool quit = false;
    while (!quit && !nxn_should_quit()) {
        nxn_event event = NXN_STRUCT_INIT(nxn_event);
        while (nxn_event_poll(&event) > 0) {
            nxn_imgui_input_event(event);
            if (event.type == NXN_EVENT_RESIZE &&
                nxn_display_resize(display, event.width, event.height) == NXN_OK) nxn_display_size(display, &w, &h);
            if (event.type == NXN_EVENT_QUIT) quit = true;
            event = NXN_STRUCT_INIT(nxn_event);
        }
        if (quit) break;
        nxn_input_poll(&input);
        const uint64_t now = nxn_time_ns();
        nxn_imgui_input(bridge, input, (float)((now - last) / 1e9));
        last = now;
        nxn_ui_tokens_get(&tokens);
        nxn_os_frame_begin(&tokens, (int)w, (int)h);
        draw(tokens);
        nxn_os_frame_end();
        glViewport(0, 0, (GLsizei)w, (GLsizei)h);
        glDisable(GL_SCISSOR_TEST);
        ImVec4 bg = nxn_os_clear_color(tokens);
        glClearColor(bg.x, bg.y, bg.z, 1.f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        nxn_display_swap(display);
    }
    entries.clear();
    ImGui_ImplOpenGL3_Shutdown();
    ImGui::DestroyContext();
    nxn_display_close(display);
    return 0;
}

int main(int argc, char** argv) { return nxn_run(argc, argv, app_main, nullptr); }
