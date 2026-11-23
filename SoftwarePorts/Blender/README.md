# Blender Port - Nexvyn Port Studio

This project is a research effort and prototype for porting the open-source 3D modeling and animation software **Blender** to portable/embedded platforms (especially the Nintendo Switch architecture).

---

## 🎯 Port Strategy

- **Target Version:** **Blender 2.79b** (lightweight C/C++ architecture with low RAM use).
  - *Why 2.79b?* Modern Blender 4.x versions need Vulkan/modern OpenGL and at least 8-16 GB of RAM. Given the Switch's 4 GB of total shared memory (~3.2 GB usable after the operating system) and GLES limits, the 2.79b architecture is the most realistic and optimizable version.
- **Window & Input Layer:** SDL2 (display, gamepad, touchscreen, virtual keyboard).
- **Graphics Backend:** GLES2 / OpenGL Legacy emulation (glad/deko3d or Mesa Gallium).
- **Python Engine:** Embedded Python 3.5/3.6 (minimal modules).

---

## 🕹️ Target Use Cases

- Portable 3D model viewer / inspector.
- Simple low-poly model editing and vertex tweaking.
- Render tests and scene inspection.
- 3D viewport navigation (Orbit, Pan, Zoom) with the touchscreen and Joy-Con analog sticks.

---

## 📁 Directory Structure

- `docs/`
  - `PORT_PLAN.md`: Build steps, dependencies and the GLES map.
- `src/`: Patches and the wrapper code needed for the port.
