# Port Market known issues

## 0.2.1

- For Internet Archive items, the first 500 file records are read. The live download and install acceptance test on the device is pending.

## 0.2.0

- For selected Internet Archive items, the first 500 file records are read. A file may not appear immediately while an upload is being processed.
- The byte count of the downloaded file is checked. The Internet Archive SHA-1 value is used in the cache identifier. Nexvyn OS checks the inner manifest when unpacking the package.
- The SDK and desktop checks are not proof of the real network/install flow on the device.

## 0.1.0

- The package path or download address is copied to the clipboard. Use the Nexvyn OS Files app for inspection and installation.
- The app checks the size of the local file. The SHA-256 value can also be shown in the catalog; full file verification is done on the desktop when the catalog is generated.
- The SDK build and static checks do not count as proof of the on-device screen layout or install flow.
