# Red Alert 2 / Yuri’s Revenge known issues

## 1.2.3

- Emulator, skirmish map: injected two-finger gestures were classified correctly (pinch out/in, sidebar scroll, pan) and the log shows the wheel events, but Yuri's Revenge does not zoom on the mouse wheel, so pinch does nothing in the game and is swallowed. There is no zoom on touch. Whether sidebar scroll moves a build list is untested (the sidebar was empty without a construction yard), Two-finger camera pan does move the map in the emulator (skirmish, injected drag: screenshots `pan_before.png` and `pan_after_left.png`, the view scrolled from the base into the dark map edge). How it feels with real fingers, and how far one drag scrolls, is untested: the camera moves by held arrow keys at the game's scroll rate, not 1:1 with the finger.
- Overview, Files and the zoom-line change were checked in the emulator only (handheld and docked screenshots), not on a physical Switch.

## 1.2.2

- Two-finger gestures (`Touch Mouse Wheel`, off by default) are implemented but unverified in a match: in an emulator run all three injected two-finger drags were classified as pan. The pinch threshold was loosened afterwards and the new classification has not been confirmed. Whether the game reacts to the mouse wheel is unknown.
- The emulator run reached the main menu with local game data; no skirmish or in-game test has been done. Emulator only, physical Switch untested.

## 1.2.1

- The launcher recognizes the Yuri’s Revenge executable with PE timestamp `0x3BDF544E`. Other executables need their own engine validation.
- Including CnCNet, Qt, Map Renderer, and duplicate language backups exceeds the 1 GiB unpacked package limit. The personal package uses the explicit `localData` list in `port.json` for the original executable, archives, and supporting files. The external-data workflow uses the selected installation directory.
- Physical Switch acceptance of dock transitions and the current controls is pending.
- The controls screen can assign selected RTS actions. Full action-based remapping is pending.
- App Market distribution is on hold while rights for the lifted game code and game visuals are reviewed.
