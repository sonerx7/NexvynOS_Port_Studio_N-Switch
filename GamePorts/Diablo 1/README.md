# Diablo 1 Port - Nexvyn Port Studio

This project ports Blizzard's legendary action RPG **Diablo 1** (and its Hellfire expansion) to the Nintendo Switch and modern embedded platforms.

---

## 🎯 Port Approach & Engine Choice

- **Engine:** **DevilutionX** (an open-source C++ engine reverse-engineered from Diablo 1 that preserves the original game logic 100%).
- **Assets:** The original `DIABDAT.MPQ` file (supplied by the user; can be tested with the shareware/demo `spawn.mpq`).
- **Graphics & Display:** Widescreen support and 60 FPS fully fitted to the Switch's 720p/1080p screen, instead of the original 640x480 resolution.

---

## 🕹️ Target Features

- **Modern Gamepad Controls:** Direct character steering, target selection with the analog stick, quick skill assignments.
- **Touch Interface:** Full touchscreen use for inventory management, the spell book and equipping items.
- **Automatic Gold Pickup & Running:** Modern quality-of-life (QoL) improvements.
- **Multiplayer:** Co-op dungeon exploration over a local network or the internet with TCP/IP and ZeroTier integration.

---

## 📁 Directory Structure

- `docs/`
  - `ARCHITECTURE.md`: DevilutionX build and libnx integration details.
- `data/`: Directory where the `DIABDAT.MPQ` or `spawn.mpq` files go.
- `saves/`: Character and progress saves.
