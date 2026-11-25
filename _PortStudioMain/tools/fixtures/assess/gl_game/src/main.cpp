#include <GLFW/glfw3.h>
// Synthetic fixture: GL 3.3 core game with a player and a level.
static void draw_level() { glUseProgram(1); glBindVertexArray(1); }
int main() {
    GLFWwindow *w = glfwCreateWindow(1280, 720, "t", 0, 0);
    int player_hp = 3;
    while (!glfwWindowShouldClose(w)) { if (glfwGetKey(w, 32)) player_hp--; draw_level(); }
}
