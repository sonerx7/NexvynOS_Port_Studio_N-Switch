# Known issues

## 1.0.1

- Everything from 1.0.0 still applies: the Genie engine is not linked, so the game cannot be played. This package is a launcher and file checker only.
- The Show FPS switch is saved but has no effect until an engine runs. The How to play tab lists planned controls, not working ones.
- Checked in the emulator only (see PORT.md), not on a physical Switch.

## 1.0.0

- Upstream decompilation repository `samuelcaldas/age-of-empires-2-decomp` PC editions (`AGE2_X1_1_0C_EN` / `EMPIRES2_2_0A_EN`) currently have 0% matched splits and no registered build units in `configure.py`. Full Genie engine execution is not yet integrated.
- Copy protection is unresolved: an `EMPIRES2.ICD` file ships beside the executable and may be a SafeDisc wrapper. A lift may need the core binary unpacked first.
- This version contains the native launcher preview, DRS/DAT data verification, and RTS input scheme (touch gestures, dual-stick cursor/box selection, keyboard and mouse).
- Full gameplay on physical Switch or emulator remains pending until engine integration is complete.
