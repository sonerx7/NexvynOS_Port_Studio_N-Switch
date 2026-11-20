# Diablo 1 (DevilutionX) Port Mimarisi

## Katman Şeması

```
+-------------------------------------------------------+
|                    DIABDAT.MPQ / Hellfire             |
+-------------------------------------------------------+
|               DevilutionX Engine (C++17)              |
|   +-----------------------+  +---------------------+  |
|   | Controller Navigation |  | Widescreen Scaler   |  |
|   +-----------------------+  +---------------------+  |
|   | Touch Inventory UI    |  | Simple-DirectMedia  |  |
+-------------------------------------------------------+
|     SDL2 / SDL2_mixer / libsmackerdec / libnx         |
+-------------------------------------------------------+
|                 Nintendo Switch (NRO)                 |
+-------------------------------------------------------+
```

## Derleme Parametreleri
```bash
cmake -B build_nx -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=$DEVKITPRO/cmake/Switch.cmake \
  -DNONET=OFF \
  -DHELLFIRE=ON \
  -DVERSION_NUM="1.5.0"
ninja -C build_nx devilutionx.nro
```
