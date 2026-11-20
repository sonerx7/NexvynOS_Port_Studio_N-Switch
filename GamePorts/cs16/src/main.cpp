#include <glad/glad.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <sys/stat.h>
#include <unistd.h>
#include <nexvyn/nexvyn_native.h>
#include "imgui.h"
#include "imgui_impl_opengl3.h"
#include <nexvyn/nxn_os_ui.h>
#include "launcher.h"

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

    uint32_t w = 1280, h = 720;
    nxn_display_size(display, &w, &h);

    cs16_load_launcher();

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
                nxn_display_resize(display, event.width, event.height) == NXN_OK) {
                nxn_display_size(display, &w, &h);
            }
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

        cs16_draw_launcher(tokens);

        nxn_os_frame_end();

        glViewport(0, 0, (GLsizei)w, (GLsizei)h);
        glDisable(GL_SCISSOR_TEST);
        ImVec4 bg = nxn_os_clear_color(tokens);
        glClearColor(bg.x, bg.y, bg.z, 1.f);
        glClear(GL_COLOR_BUFFER_BIT);
        ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());
        nxn_display_swap(display);
    }

    ImGui_ImplOpenGL3_Shutdown();
    ImGui::DestroyContext();
    nxn_display_close(display);
    return 0;
}

int main(int argc, char** argv) {
    return nxn_run(argc, argv, app_main, nullptr);
}
