# Port Market 0.2.1 beta

Port Market checks selected Internet Archive items on startup and every five minutes while open. Save an item URL or identifier using **Add archive item**. Newly uploaded `.nxvapp` files appear first. **Download** shows progress and moves the completed file into the app’s private area after checking its size. **Open installer** opens the Nexvyn OS package review. Each device profile owns its watch list and downloads.

## Personal SD catalog

The Local tab opens a personal Studio catalog including packages under `game/<port>/` and `software/<port>/`.

```powershell
python -X utf8 _PortStudioMain/tools/port_market.py catalog
```

Copy `_RealesedBuilds/port-market.tsv` and the adjacent `game/` and `software/` folders to the SD card, preserving their layout. Choose their parent directory in the app. The beta package ships without personal files. Keep local builds, catalogs, and archive candidates under the ignored `_RealesedBuilds/` directory.

## Prepare an Internet Archive release

Follow the [release workflow](RELEASE_WORKFLOW.md) and record redistribution rights for the current manifest version. Set `release.status` to `ready` and `release.version` to the reviewed version. To distribute a full personal package, record clearance for all included data, set `archiveFullData: true`, and pass `--full-package`.

```powershell
python -X utf8 _PortStudioMain/tools/port_market.py prepare-archive "GamePorts/my-game" --item "my-nexvyn-port" --license MIT --output "_RealesedBuilds/archive/my-game"
```

The command uses the port’s locked SDK, checks package contents against the current `source/` and declared data paths, and writes the versioned package, upload metadata, and distribution record. Use `--sdk` to select a matching SDK snapshot explicitly. Port Market detects a later version uploaded with a new file name to the same Archive item. Access is governed by the item’s settings.

The OS limits a single package to 1 GiB unpacked. Use explicit data mappings such as the [Red Alert 2 personal package configuration](../../GamePorts/RedAlert2/port.json) to include just the needed files.

## Build the local beta

```powershell
python -X utf8 _PortStudioMain/tools/build_port_market_beta.py --checkout "../Nexvyn-OS-NX" --checker-checkout "../SnxOS-NX" --install-local
```

The official store tool builds the Port Market listing. `--install-local` updates the local Nexvyn OS checkout. The package is also written to Port Market’s `build/beta-0.2.1/` directory.
