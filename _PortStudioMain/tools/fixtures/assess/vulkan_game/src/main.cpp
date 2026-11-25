#include <vulkan/vulkan.h>
#include <thread>
// Synthetic fixture: Vulkan renderer for a game with an enemy list.
int main() {
    VkInstance inst; vkCreateInstance(0, 0, &inst);
    std::thread loader([] {});
    int enemy_count = 4;
    vkCmdDraw(0, 3, 1, 0, 0);
    loader.join();
}
