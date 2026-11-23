# Age of Empires II distribution record

| File or group | Source | License and channel |
| --- | --- | --- |
| Launcher and data validator | Nexvyn Port Studio | GPL-3.0. [LICENSE](LICENSE) includes the full text and [NOTICE.md](NOTICE.md) identifies the corresponding source. |
| Launcher locales and Dear ImGui | Nexvyn Port Studio and the public SDK | Port Studio translations and [Dear ImGui MIT license](LICENSE-IMGUI.txt). |
| Store icon and artwork | Designed symbol icon and planned game captures | Redistribution clearance is pending. Microsoft and Ensemble Studios retain their original rights. |
| User data | User-owned Age of Empires II PC installation | Personal package or external directory. |
| Candidate engine and decompilation | `samuelcaldas/age-of-empires-2-decomp` / `aoe2-ps2-recomp` | Future engine integration. Pinned revisions, licenses, and distribution rights must be audited before bundling compiled code. |

## External data

The preview checks for the existence and validity of `data/graphics.drs`, `data/empires2.dat`, and `empires2.exe` / `age2_x1.exe`. It checks bundled data before the previously selected external folder. Use the system picker to select a different installation. The preview saves the selection in the app's persistent data and does not write to the original game files.

`check store` rejects commercial data from the public source bundle. The preview's launch and technical checks do not establish gameplay compatibility or rights for commercial artwork.
