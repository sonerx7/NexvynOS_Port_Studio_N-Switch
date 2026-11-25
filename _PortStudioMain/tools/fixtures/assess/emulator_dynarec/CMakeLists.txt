project(emu C)
find_package(SDL2 REQUIRED)
add_executable(emu src/main.c src/cpu/dynarec.c)
