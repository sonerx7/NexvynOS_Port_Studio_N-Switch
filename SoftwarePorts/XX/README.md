# Future Software Port Template (SoftwarePorts/XX)

This folder is the standard template area for new PC software, productivity tools or emulators to be added to Nexvyn Port Studio.

---

## 🚀 Steps When Starting a New Software Port:

1. Duplicate this folder and name it after the target software (e.g. `SoftwarePorts/DosBox-X`).
2. Create `docs/ARCHITECTURE.md` and define the memory, display and architecture constraints.
3. Include the `_PortStudioMain/sdk/include/nexvyn_port_core.h` library and hook up the virtual mouse and display scaler.
4. Place the software's standalone source code under `src/`.
5. If present, add launcher or configuration files under `config/`.
