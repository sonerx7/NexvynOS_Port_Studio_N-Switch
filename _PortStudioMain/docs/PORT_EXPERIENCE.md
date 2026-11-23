# Port experience layer

One declaration in `port.json` describes how a port feels on Nexvyn OS: input modes, touch gestures, performance profiles and the launcher. The Studio validates it and generates files your port code reads. Presets live in `_PortStudioMain/profiles/` (`rts`, `fps`, `editor`, `generic`).

```bash
python _PortStudioMain/tools/port_studio.py experience init GamePorts/<port> rts   # adds the block
python _PortStudioMain/tools/port_studio.py experience check GamePorts/<port>      # validates
python _PortStudioMain/tools/port_studio.py experience generate GamePorts/<port>   # generated/experience.json + generated/nx_experience.h
python _PortStudioMain/tools/port_studio.py experience migrate GamePorts/<port>    # after a Studio update
```

## Start from the game, not the preset

```bash
python _PortStudioMain/tools/port_studio.py analyze <game-data-or-source-dir>
```

It reads file names, executable import names and source files (never runs anything) and prints engine hints, input and graphics signals, a genre guess with its evidence, and what the port must add (touch, gamepad mapping, pointer choice). The genre guess is the weakest part: confirm it in the running game. `bootstrap --port <port>` also warns about a missing `experience` block, a long Windows path and a missing Ryujinx.

## What you write

```json
"experience": {
  "schema": 1,
  "profile": "rts",
  "input": { "gestures": { "two_finger_pan": "camera_pan" } },
  "performance": { "docked": { "fpsCap": 60 } }
}
```

Only list what differs from the preset. The Studio merges the rest.

Presets describe a typical genre; the engine decides what is real. Mark what the game cannot do and record how you know:

```json
"input": {
  "unsupported": ["camera_zoom"],
  "gestures": { "two_finger_tap": "command", "pinch": null },
  "engineFacts": "Verified in src/nx/main.c: two-finger drag pans, nothing handles pinch."
}
```

`unsupported` removes the action and every gesture that pointed to it. A gesture set to `null` is dropped. Red Alert 2 is the worked example: it uses real multitouch (two-finger pan, long press and two-finger tap both send a right click) and has no pinch zoom.

## What a preset gives you

- **Modes**: `auto`, `gamepad`, `touch`, `kbm`. Each action needs a binding for every declared device mode.
- **Gestures** (`rts`): tap = select, long press = command, one-finger drag = box select, two-finger pan = camera pan, pinch = zoom, two-finger tap = cancel. Gesture to action map is data, change it per port.
- **Performance**: `handheld` (720p) and `docked` (1080p) with `renderScale`, `fpsCap`, `msaa`. Measure on the engine before changing defaults and record it in `PORT.md`.
- **Launcher**: primary action, sections, what is remembered.
- Rules enforced by `check`: `select`, `cancel`, `menu` exist; touch targets at least 44 px; no binding of HOME, L+R hold, `-` hold or the top-edge swipe (owned by Nexvyn OS).

## What it does not do

It declares and validates. Your engine code still has to read touch contacts (`nxn_input_touch`), recognise the gestures and call the action. Follow [INPUT_CONTRACT.md](../nexvyn_sdk/Guides/INPUT_CONTRACT.md). `nx_experience.h` gives you `nx_action`, `nx_gesture`, the gesture to action table and the two performance profiles so the numbers live in one place. A gesture recogniser and runtime remapping UI are not provided yet.

## Updates and compatibility

- `schema` is the block layout version. The Studio refuses a schema newer than it knows ("Update the Studio") and upgrades older ones through `MIGRATIONS` in `experience.py`. When the layout changes: bump `CURRENT_SCHEMA`, add one migration, keep old ports working.
- When the OS adds an input or framework feature: add the vocabulary (gesture, mode, key) to `experience.py` and the presets, add a test, bump the schema only if existing blocks would break.
- `doctor --json` reports the Studio's `experienceSchema` and the port's `portExperience`.
- SDK updates stay separate: follow [SDK_UPDATES.md](SDK_UPDATES.md).
