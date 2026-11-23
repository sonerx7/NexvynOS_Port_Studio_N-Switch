# Blender Embedded Port Plan

## Phases

### Phase 1: Minimal Headless Build
- Reducing dependencies (slimming down OpenColorIO, OpenImageIO and the Boost libraries).
- Setting up an ARM64 cross-compile environment with devkitA64.
- Running the CLI model converter with the `WITH_HEADLESS=ON` option.

### Phase 2: SDL2 & GLES2 Viewport
- Redirecting the GHOST (Blender's window manager) interface to the SDL2 backend.
- Making fixed-function OpenGL calls GLES-compatible.

### Phase 3: Input and UI Adaptation
- Integrating the `NexvynPortCore` virtual mouse and touch gestures into the Blender interface.
- Assigning viewport navigation to the analog sticks (Left: Pan/Orbit, Right: Zoom).
