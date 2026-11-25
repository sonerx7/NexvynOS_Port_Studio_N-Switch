project(sdl2_game C)
find_package(SDL2 REQUIRED)
add_executable(sdl2_game src/main.c)
