# Port Market releases

The Port Market app is developed and published in the main Nexvyn OS project, not in Port Studio. It reads one catalog, `https://archive.org/download/nexvyn-port-market/catalog.json`, and downloads each `.nxvapp` from its own Archive item. Port Studio produces the personal SD catalog and checked release candidates, and the owner publishes them from here.

## Personal SD catalog

The app's Local tab opens a personal Studio catalog including packages under `game/<port>/` and `software/<port>/`.

```powershell
python -X utf8 _PortStudioMain/tools/port_market.py catalog
```

Copy `_RealesedBuilds/port-market.tsv` and the adjacent `game/` and `software/` folders to the SD card, preserving their layout. Choose their parent directory in the app. Keep local builds, catalogs, and archive candidates under the ignored `_RealesedBuilds/` directory.

## Prepare an Internet Archive release candidate

Follow the [release workflow](RELEASE_WORKFLOW.md) and record redistribution rights for the current manifest version. Set `release.status` to `ready` and `release.version` to the reviewed version. To distribute a full personal package, record clearance for all included data, set `archiveFullData: true`, and pass `--full-package`.

```powershell
python -X utf8 _PortStudioMain/tools/port_market.py prepare-archive "GamePorts/my-game" --item "my-nexvyn-port" --license MIT --output "_RealesedBuilds/archive/my-game"
```

The command uses the port’s locked SDK, checks package contents against the current `source/` and declared data paths, and writes the versioned package, upload metadata (`internet-archive.json`), the SD catalog row (`port-market-entry.json`), the distribution record, `icon.png`, `screenshot-1.png`…`screenshot-5.png` and the store listing `listing.json`. Use `--sdk` to select a matching SDK snapshot explicitly, and `--source-url` (or `sourceUrl` in `port.json`) for the source code link shown in the store.

`listing.json` is one entry of the Port Market catalog (schema 1): `item`, `appId`, `kind`, `category`, `name`, `version`, `file`, `size`, `sha256`, `icon`, `screenshots`, `subtitle` and `description` per language, `tags`, `features`, `age`, `license`, `source`, `sdk` (`sdk`, `native`, `repository`, `commit`) and `updated`. `catalog.json` is `{schema, updated, apps: [listing…]}`. `market_publish.py` defines and checks this format; change it there and in the app together.

The OS limits a single package to 1 GiB unpacked. Use explicit data mappings such as the [Red Alert 2 personal package configuration](../../GamePorts/RedAlert2/port.json) to include just the needed files.

## Publish, update and withdraw (owner only)

Automation for open-source ports: `python -X utf8 _PortStudioMain/tools/market_release.py <port> --approve` runs verify (no FAIL), copies 3-5 real shots from the newest emulator run whose automatic and visual review passed into the store screenshots, and, with `--approve` (the owner's rights decision), writes DISTRIBUTION.md, the version sections of CHANGELOG.md and KNOWN_ISSUES.md and `release.status: ready`. It then prepares the data-free candidate (item `nexvyn-os-nx-<port>-game-port`), shows the publish dry run and prints the `--yes` command for the owner. It refuses an unrecognised licence and a module with lifted or recompiled commercial code (evidence in port.json or PORT.md, unless `"codeRedistributable": true`). `--all` lists what every port still needs. It never uploads.

Only the owner publishes. An Archive item can be changed only by the account that created it, and the keys exist only on the owner's machine. Agents and contributors prepare a candidate and stop; they never pass `--yes`.

One-time setup on the owner's machine:

```powershell
python -m pip install internetarchive
ia configure
```

`ia configure` asks for the archive.org e-mail and password and stores the S3 keys in the user profile, outside the repository. `IA_ACCESS_KEY` and `IA_SECRET_KEY` also work for one session. Never put the keys in the repository, a log or a package.

```powershell
# Show what would change; nothing is sent. Writes the merged catalog.json into the candidate folder.
python -X utf8 _PortStudioMain/tools/port_market.py publish "_RealesedBuilds/archive/my-game"
# Upload the package, icon, screenshots and listing, then update the catalog.
python -X utf8 _PortStudioMain/tools/port_market.py publish "_RealesedBuilds/archive/my-game" --yes
# Remove from the store (catalog only), or also delete the uploaded files.
python -X utf8 _PortStudioMain/tools/port_market.py unpublish my-nexvyn-port [--delete-files] --yes
```

A new version is the same `publish` on a new candidate with a higher version: the catalog entry is replaced and the item title is updated; earlier package files stay in the item. Archive cannot delete an item for its owner, only its files. A new upload may take minutes to hours to appear while Archive processes it.
