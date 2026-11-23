# Known Issues & Limitations

## 1. Emulator Limitation (Ryujinx / Yuzu)
- **`svcMapProcessCodeMemory`**: Ryujinx's homebrew loader runs NRO files in a restricted sandbox without an open process handle. When LKL attempts to map Chromium's code pages (`code_map`), Ryujinx returns `KernelSvc: MapProcessCodeMemory() = InvalidHandle (0xe401)`.
- **Hardware Requirement**: On physical Nintendo Switch consoles running Atmosphère, Chromium NX must be launched using a title forwarder (such as Sphaira with 39-bit address space enabled) from the HOME menu, which provides the full process handle and 512 GB virtual address space needed for Chromium's renderer.

## 2. Memory Requirements
- Chromium requires ~2 GB of RAM. Closing background titles before launching is recommended.
