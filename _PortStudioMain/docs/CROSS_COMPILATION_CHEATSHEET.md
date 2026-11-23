# Cross-compile native Nexvyn OS modules for Nintendo Switch

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

- Verify file versions and case handling on the target. Match user data without renaming or changing it.
- Test alignment, memory access, and byte order when porting x86 serialization code. Verify graphics, audio, and system APIs in the first prototype.
- Use `stage <port> --module <path>` to validate the module's identity, relocations, and imports and place it in the package's `source/` directory. [Release workflow](RELEASE_WORKFLOW.md)
