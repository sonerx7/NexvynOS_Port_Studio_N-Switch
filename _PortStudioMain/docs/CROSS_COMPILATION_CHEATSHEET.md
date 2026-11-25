# Cross-compile native Nexvyn OS modules for the console

Native ports build as AArch64 ELF modules with the `.nxvmod` extension. The manifest sets the initial window or fullscreen mode, and the port handles display changes during its lifecycle. Follow the [Native Kit installation guide](../nexvyn_sdk/Guides/NATIVE_KIT.md#install) and start with the public SDK snapshot locked to the port.

For a small native prototype, install the devkitPro `switch-glad` package and run these commands from the Studio root in PowerShell. For an existing port, use its build steps in `PORT.md`.

```powershell
$nativeKit = "_PortStudioMain/nexvyn_sdk/Languages/c/native-kit"
$prototype = "_LocalData/native-prototype"
python -X utf8 "$nativeKit/tools/nxv_native" doctor
python -X utf8 "$nativeKit/tools/nxv_native" new native-prototype --template app --dir "_LocalData"
python -X utf8 "$nativeKit/tools/nxv_native" build "$prototype"
python -X utf8 "$nativeKit/tools/nxv_native" check-win "$prototype/build/native-prototype.nxvmod"
```

Point `$nativeKit` to the Native Kit in the selected snapshot if the port uses an SDK other than the default. Set `DKP_BASH` for direct Native Kit commands when devkitPro MSYS2 is outside its default Windows location. On Linux, set `DEVKITPRO` and make the build tools available on `PATH`.

For a CMake-based upstream engine, use the Native Kit `port` template as a reference for the Nexvyn toolchain and module target. Its sample uses SDL2. Build the windowed SDL2 sysroot from the same SDK snapshot and pass its root to `build --sysroot <path>`. Keep external dependency and sysroot paths configurable. Record the build command and dependency versions in `PORT.md`. [Windowed SDL2 setup](../nexvyn_sdk/Guides/NATIVE_KIT.md#sdl2-in-a-window)

## Platform rules every port meets

[`platform/capabilities.json`](../platform/capabilities.json) has each rule's evidence level.

- **Loader:** the module imports only from the fixed host table (`nxn_*`, newlib, pthreads, a small libnx subset). Anything else fails as `missing symbol X`, so run `check-win` after every link change. No EGL, no libnx services, no raw `vk*`.
- **Process:** one process, one window, one GL context. There is no `fork`, `exec`, `system` or `popen`, and no Linux `.so` (use static builds or `.nxvlib`). Join every thread before `main` returns.
- **Graphics:** GL 4.3 core or GLES 3.2, loaded through `nxn_display_proc` or SDL. Turn `ARB_buffer_storage` off. Do not rely on `glMapBufferRange` reads or transform feedback (Mesa 20.1 nouveau). Vulkan is optional and off on release OS builds: check `nxn_vk_available()` and keep a GL path. SPIR-V is compiled offline with `nxv_native shader --target vulkan`.
- **CPU and memory:** the main thread plus up to two worker cores (1 and 2; core 0 runs the shell, core 3 the system), and 4 GiB shared with the OS. Set `app.json` `memory` and check every allocation. There are no fixed or sparse mappings: compat `mmap` is heap-backed.
- **JIT:** `nxn_jit_*` only, opt-in. The kernel has 10 code-memory objects system-wide, and each module uses 2. Start with an interpreter path.
- **Thread-local storage:** global-dynamic TLS only, at most 16 objects. The clang profile cannot use `thread_local`.
- **Loading:** call `nxn_should_quit()` at least every 250 ms and set `"loadingHint": true`. Read files in 256 KB-1 MB chunks.
- **Newer APIs:** `nxn_memory_budget_*`, `nxn_thread_hint_request` and `nxn_vk.h` exist in the OS source but are not yet in the public SDK snapshot (`doctor --json` → `platformFacts.missingInSnapshot`). Use them through weak imports, and only after an SDK update.

## Checks

- Verify file versions and case handling on the target. Match user data without renaming or changing it.
- Test alignment, memory access, and byte order when porting x86 serialization code. Verify graphics, audio, and system APIs in the first prototype.
- Use `stage <port> --module <path>` to validate the module's identity, relocations, and imports and place it in the package's `source/` directory. [Release workflow](RELEASE_WORKFLOW.md)
