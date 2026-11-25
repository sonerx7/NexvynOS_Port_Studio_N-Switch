/* Vulkan path for @NAME@. Vulkan is on by default from Nexvyn OS 1.4.0 (SDK 1.16); OS 1.3.x has no Vulkan.
 * GL fallback path (always keep it): the game template creates the GL context (nxn_display_proc + glad). Select it
 * whenever nx_vulkan_usable() returns 0: older OS, the driver check at start failed, or native.vulkanOff=1.
 * Never make Vulkan the only path. Resolve Vulkan entry points with nxn_vk_proc("vkGetInstanceProcAddr"). */
#ifndef NX_VULKAN_PATH_H
#define NX_VULKAN_PATH_H

#include <nexvyn/nxn_vk.h>

/* 1 when this OS offers Vulkan to the app (NXN_CAP_VULKAN, the Vulkan graphics API and the nxn_vk_proc import).
 * Also create the device and present one frame before trusting it; on any failure fall back to GL. */
static inline int nx_vulkan_usable(void) {
    return nxn_vk_available();
}

#endif
