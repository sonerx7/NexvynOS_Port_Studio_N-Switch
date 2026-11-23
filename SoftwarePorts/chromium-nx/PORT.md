# Chromium NX Port Record

## Target
- **Product**: Chromium NX (Chromium web browser on Nintendo Switch)
- **Upstream Author**: shodowlo
- **Upstream Repository**: https://github.com/shodowlo/chromium-nx
- **Target Version**: v0.2.0 (Chromium 156.0.8078.79)
- **Primary Workflow**: Web browsing, HTML5, video playback (H.264), touch / gamepad pointer navigation
- **Required Data**: `chromium-full.ext4` (411 MB rootfs) and `profile.ext4` (user profile data)

## Research and Feasibility

| Source and Revision | Evidence | Effect on Decision |
| --- | --- | --- |
| `shodowlo/chromium-nx` @ `8652bc7fdf3f26989377cf8e07c51fb3bf057a2e` | LKL + stock Debian ARM64 Chromium 156 on Horizon OS | Viable on hardware via forwarder; limited in standard homebrew sandbox |
| Direct Mode Patch | NRO binary patch at `0x6a6d4` (`browser_mode = 1`) and `0x449b8` (`nop` ASLR check) | Removes launcher screen, directly enters browser |

## Direct Startup Implementation
- **Patch 1**: `0x6a6d4` changed from `mov w1, #0` + `cbz x0` to `mov w1, #1` + `b 0x6a6f0`. Sets `browser_mode = 1` permanently.
- **Patch 2**: `0x449b8` changed from `b.ls #0x44b90` to `nop`. Bypasses 39-bit ASLR requirement screen for emulator loading.

## Verification
- **Host / Build**: Toolchain validated, patched NRO verified with Capstone disassembler.
- **Emulator (Ryujinx 1.3.3)**:
  - LKL booted successfully (`starting the kernel (mem=192M loglevel=4 nohz=off)`).
  - Network interface initialized and the socket listens on port 6100.
  - SD card mounted: `profile.ext4` created (256 MB), `chromium-full.ext4` verified.
  - Syscall limitation: Ryujinx HLE returns `InvalidHandle` on `svcMapProcessCodeMemory` because homebrew NRO loader does not grant a process handle. Requires Atmosphère title forwarder on real Switch.
