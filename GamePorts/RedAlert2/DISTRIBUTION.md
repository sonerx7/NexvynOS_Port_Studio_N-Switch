# Red Alert 2 / Yuri’s Revenge distribution record

| File or group | Source | License and channel |
| --- | --- | --- |
| Native host, launcher, and pcrecomp patches | redalert2-recomp, pcrecomp at `621860a9d22c9b25ae2be4575b956596f4ddaeeb`, and Nexvyn Port Studio code | MIT for the host and tools. See [NOTICE.md](NOTICE.md) and the [pcrecomp license](patches/LICENSE-pcrecomp.txt). |
| Generated code in `ra2.nxvmod` | Statically recompiled from the retail `gamemd.exe` | Personal testing. App Market distribution clearance is pending. |
| Launcher locales and Dear ImGui | Nexvyn Port Studio and the public SDK | Port Studio translations and [Dear ImGui MIT license](LICENSE-IMGUI.txt). |
| Icon, launcher art, and screenshots | Port Studio assets and game captures | Redistribution clearance is pending. Westwood Studios and Electronic Arts retain their original rights. |
| `RA2.CSF` translation | Locally supplied Turkish text table | Personal or external data. |
| Original `gamemd.exe`, `.mix`, DLLs, and configuration files | User-owned Steam, EA App, or retail installation matching the supported executable | Personal package or external directory. No original data is included in the store payload. |

## External data

Select a licensed Yuri’s Revenge installation containing `gamemd.exe` with PE timestamp `0x3BDF544E`, `ra2.mix`, `ra2md.mix`, and the standard archives for that version. The launcher reports unsupported executables and missing files separately. Changes to game settings, mods, and the optional translation are written to the app’s `overlay_active/` directory.

The launcher checks the previously selected valid directory, then bundled `game/`, then known local directories or the folder selected by the user. `check store` checks the public bundle inventory for private data. Distribution clearance for generated code and visuals is a separate release requirement.
