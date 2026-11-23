# Native port launcher standard

The launcher gets users to the main task. An RTS needs campaign or version selection, camera controls, and pointer behavior. An FPS needs content, sensitivity, and aiming. A 3D editor needs open and recent documents and view controls. A port that can start immediately can open the main workflow and keep settings and data selection accessible inside the app.

## Layout standard (use `portkit/nx_launcher_ui.h`)

Every launcher uses the same building blocks so ports look and behave alike, and a dense page stays usable.

- **Hero.** A tinted card on top: logo, title, one-line subtitle, status badges, a large **Play** button (56 design px high, at least 200 wide) and a quieter **Exit**. Wide window: text left, buttons right. Narrow window (content width under 640 design px): the buttons stack full width under the text, Play first. While data is missing, Play becomes the data-selection action, never a dead button.
- **Cards in columns.** Group related options in a card with its title inside the card (header text, then a divider). Cards flow into 1, 2 or 3 columns by the width they get, 300 design px minimum per column (`nx_grid_begin`, `nx_grid_next`, `nx_grid_end`). Do not put a section title outside its card.
- **Tabs.** Overview, Video, Controls, How to play, Files, Logs. Segmented tabs when they fit, a dropdown when they do not (`nx_tabs`).
- **Overview tab.** Two columns. Left: **Quick settings**, with the **Show FPS** switch first (`nx_fps_row`, off by default, one line of hint) and then the few launch choices a player changes every session. Right: **Game folder** with Browse and Verify, the folder path and one coloured result line. Per-file check lists ("found / missing" rows) do not belong here: they go in the **Files** tab, also in two columns. The overview must fit a 720p window without scrolling for a typical port.
- **Calm, Apple-like look.** One accent colour (the OS accent) and one tinted hero; neutral cards; generous padding; short labels in sentence case; a caption line instead of a paragraph; switches for on/off, selects for choices, buttons only for actions. Status uses colour plus a word, never colour alone. No borders inside cards: use a divider or spacing. Animations are never required to understand state.
- **Not too dense.** One primary action per card, three to five rows before a divider, advanced and rarely used options behind a collapsed or secondary tab. Touch targets stay at least 44 design px.
- **Resize.** Use only `nxn_os_s()` and `nxn_os_sp()` sizes (they follow the OS text scale and window size) and the width a container gives you. Never hard-code 1280x720 or pixel positions. Check the launcher at a narrow window, handheld 720p and docked 1080p.
- **Handheld and docked.** Docked has no touch screen: the launcher must be fully usable from the first screen with a gamepad (focus on Play, Tab and card navigation by pad), and nothing may need a tap. Show the Gamepad card first in How to play while docked and the Touchscreen card first in handheld. Layout reads the window width, not the mode, so both resolutions use the same code. Test with `emulator_test.py run ... --mode both`.
- **How to play.** Generated from the port's `experience` block (`nx_howto_draw`): one card per control scheme, one line per action in the preset's order, plus a zoom line when the port maps pinch. Do not hand-write a second copy of the controls.

## Design for the actual workflow

1. Show supported versions and required files. Use the system picker. Show the selection state, identify missing or incompatible files, and let users select again. Detect valid data in a personal package.
2. Give users one primary action such as Play, Resume, New, or Open Recent. Keep settings, controls, and help accessible. Remember the selected data and profile. Report real loading phases and provide a cancel or error path.
3. Expose settings that affect the engine or Nexvyn OS. Record the default, allowed range, when it takes effect, where it is stored, and how it was tested. Explain conditions that disable a setting. Offer video recovery, reset, and reasonable defaults.
4. Use Nexvyn OS appearance tokens, focus navigation, window behavior, system dialogs, and the on-screen keyboard where appropriate. Translate all visible text for the SDK’s required locales, including loading, help, settings, and errors.

## Handheld, dock, and window transitions

Support the automatic profile with measurements. Consider 720p handheld and 1080p dock output. Choose the internal render size, frame limit, and scaling based on measured engine performance. Show the active automatic profile and offer supported manual choices. Use SDK display and resize events. Update the viewport, coordinate mapping, aspect ratio, and HUD together. Preserve the gameplay session or document during dock/undock, window changes, and suspend. Explain when a setting requires a restart.

## Input and remapping

Define meaningful actions first, such as select, cancel, camera, aim, and interact. Map them for gamepad, touch, and physical keyboard and mouse. Choose direct touch or a virtual pointer. Use real multitouch when actions need simultaneous input. A gamepad must navigate menus and perform the primary workflow. Expose deadzone, acceleration, sensitivity, rumble, and axis inversion where implemented.

Provide usable defaults, action-based remapping, conflict and reserved-input notices, per-action and profile resets, current button prompts, and versioned settings. Give input one owner. Clear held buttons and touches on focus loss, system dialogs, disconnect, or suspend. Release mouse and keyboard capture outside the appropriate context.

## Red Alert 2 implementation notes

- The [launcher](../../GamePorts/RedAlert2/src/nx/launcher.cpp) demonstrates data validation, persistent profiles, dock resolution selection, and an overlay for language and mods. The overlay protects original user files.
- Make RTS choices and game state easy to find. Explain which video settings a profile locks and why. Track sources and rights for data, translations, and patches.
- Read the [historical RA2 notes](RA2_LAUNCHER_REFERENCE.md) for project-specific decisions and the [public SDK port guide](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md) for API, input, and lifecycle contracts.
