# Counter-Strike 1.6 distribution record

| File or group | Source | License and channel |
| --- | --- | --- |
| Launcher and WAD validator | Nexvyn Port Studio | GPL-3.0. [LICENSE](LICENSE) includes the full text and [NOTICE.md](NOTICE.md) identifies the corresponding source. |
| Launcher locales and Dear ImGui | Nexvyn Port Studio and the public SDK | Port Studio translations and [Dear ImGui MIT license](LICENSE-IMGUI.txt). |
| Store icon and future screenshots | Adapted Counter-Strike artwork and planned game captures | Redistribution clearance is pending. Valve retains its original rights. |
| User data | User-owned Counter-Strike 1.6 installation | Personal package or external directory. |
| Candidate engine and client | Xash3D FWGS and CS16Client | Future integration. Record pinned revisions, obligations, and the distribution basis in this file before including their code. |

## External data

The preview checks the WAD2 or WAD3 headers in `cstrike/cstrike.wad` and `valve/halflife.wad`. It checks bundled data before the previously selected external folder. Use the system picker to select a different installation. The preview saves the selection in the app’s persistent data and does not write to the original game files.

The personal package includes only those two WADs from the user-selected installation. Review the required maps, models, audio, and other data before adding engine support.

`check store` rejects commercial data from the public source bundle. The preview’s launch and technical checks do not establish gameplay compatibility or rights for artwork.
