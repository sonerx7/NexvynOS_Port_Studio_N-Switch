#!/usr/bin/env python3
"""Inventory of the evidence and package outputs present in port folders."""

import json
from pathlib import Path

from port_studio import PORT_TYPES, RELEASE_ROOT, ROOT, config_for


def inspect_studio(root_dir):
    root = Path(root_dir)
    for category, (channel, store_type) in PORT_TYPES.items():
        base = root / category
        print(f"\n{category}")
        if not base.is_dir():
            print("  Category folder not found.")
            continue
        for port in sorted(base.iterdir()):
            if port.name.startswith(".") or not port.is_dir() or port.is_symlink():
                continue
            print(f"  {port.name}")
            indicators = (
                ("Port file", (port / "PORT.md").is_file()),
                ("Belgeler", (port / "README.md").is_file() or (port / "docs").is_dir()),
                ("Source folder", (port / "src").is_dir()),
                ("Release records", all((port / name).is_file() for name in ("CHANGELOG.md", "KNOWN_ISSUES.md"))),
            )
            print("    " + " | ".join(f"{name}: {'var' if value else 'yok'}" for name, value in indicators))
            if (port / "port.json").is_file():
                try:
                    slug, genre, _, _ = config_for(port)
                    item = port / "AppMarket" / "Store" / store_type / genre / slug
                    store = item / f"{slug}.nxvapp"
                    app = json.loads((item / "source" / "app.json").read_text(encoding="utf-8-sig"))
                    personal = root / RELEASE_ROOT / channel / slug / f"{app['id']}-{app['version']}-local.nxvapp"
                    print(f"    Manifest version: {app['version']} | Personal: {'yes' if personal.is_file() else 'no'}"
                          f" | Store candidate: {'yes' if store.is_file() else 'no'}")
                except (KeyError, OSError, TypeError, ValueError) as error:
                    print(f"    Packaging definition in progress: {error}")
            else:
                manifest = (port / "app.json").is_file()
                builds = sum(1 for path in (port / "dist").glob("*.nxvapp") if path.is_file())
                print(f"    Mevcut manifest: {'var' if manifest else 'yok'} | Mevcut .nxvapp: {builds}"
                      " | New packaging definition: none")


if __name__ == "__main__":
    inspect_studio(ROOT)
