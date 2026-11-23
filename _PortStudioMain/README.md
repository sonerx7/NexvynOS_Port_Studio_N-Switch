# Nexvyn Port Studio tools and SDK

Start with [FIRST_RUN.md](../FIRST_RUN.md) after cloning the repository.

- The [porting playbook](docs/INSTANT_PORT_PLAYBOOK.md) covers feasibility, native integration, and acceptance tests.
- The [launcher standard](docs/PORT_LAUNCHER_STANDARD.md) covers port-specific settings, controls, and presentation.
- The [release workflow](docs/RELEASE_WORKFLOW.md) covers personal and App Market packages. Use the [templates](templates) to record the port decision, distribution rights, changes, and issues.
- The [shared C/C++ helpers](sdk/include/nexvyn_port_core.h) support existing ports. See the [helper guide](docs/SDK_GUIDE.md). Use the public SDK for OS APIs and behavior.

## Public Nexvyn OS SDK

[`nexvyn_sdk/`](nexvyn_sdk/README.md) contains the snapshot of the public Nexvyn OS `SDK/` tree. [VERSION.json](nexvyn_sdk/VERSION.json) records the OS, SDK, Native SDK, and locale contract. Each port records its SDK commit in `sdk.lock.json`.

See [SDK updates](docs/SDK_UPDATES.md) to retrieve a pinned commit, prepare an update candidate, and test it with a port.
