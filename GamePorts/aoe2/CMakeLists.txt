cmake_minimum_required(VERSION 3.13)
project(aoe2 VERSION 1.0.1 LANGUAGES C CXX)

if(NOT DEFINED NEXVYN_KIT)
  get_filename_component(NEXVYN_KIT "${CMAKE_CURRENT_LIST_DIR}/../../_PortStudioMain/nexvyn_sdk/Languages/c/native-kit/sdk/native" ABSOLUTE)
endif()
set(NEXVYN_ABI ON CACHE BOOL "" FORCE)
include(${NEXVYN_KIT}/toolchain/nexvyn-native.cmake)

set(IMGUI_DIR ${NEXVYN_KIT}/sysroot/vendor/imgui)
set(IMGUI_SRC ${IMGUI_DIR}/imgui.cpp ${IMGUI_DIR}/imgui_draw.cpp ${IMGUI_DIR}/imgui_tables.cpp ${IMGUI_DIR}/imgui_widgets.cpp
              src/imgui_gl_glue.cpp)
set_source_files_properties(${IMGUI_SRC} PROPERTIES COMPILE_OPTIONS "-w")

set(GLAD_LIB "$ENV{DEVKITPRO}/portlibs/switch/lib/libglad.a")
if(NOT EXISTS "${GLAD_LIB}")
  message(FATAL_ERROR "libglad.a not found: install the devkitPro switch-glad package")
endif()

nexvyn_add_windowed(aoe2_win NAME aoe2 SOURCES src/main.cpp src/launcher.cpp ${IMGUI_SRC} LINK ${GLAD_LIB})
target_include_directories(aoe2_win_objects PRIVATE src generated ${CMAKE_CURRENT_SOURCE_DIR}/../../_PortStudioMain/portkit ${IMGUI_DIR} ${IMGUI_DIR}/backends
                           "$ENV{DEVKITPRO}/portlibs/switch/include" ${NEXVYN_KIT}/include)
target_compile_definitions(aoe2_win_objects PRIVATE IMGUI_DISABLE_DEFAULT_SHELL_FUNCTIONS)
target_compile_options(aoe2_win_objects PRIVATE -Wall -Wextra -Wno-unused-parameter "$<$<COMPILE_LANGUAGE:CXX>:-fno-rtti;-fno-exceptions>")
