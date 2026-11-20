# Counter-Strike 1.6 Nexvyn OS Native Port Dosyası

## Hedef

- **Ürün:** Counter-Strike 1.6 (GoldSrc / Valve Corporation)
- **Kaynak Platform:** PC Windows x86
- **Hedef Platform:** Nintendo Switch / Nexvyn OS (ARM64 AArch64)
- **Hedef Sürüm:** CS 1.6 v3 (Build 8684 uyumlu)
- **Kullanıcının Gerçek Kullanım Senaryosu:** Hem Nintendo Switch el modunda dokunmatik ve çift analog + jiroskop nişan alma ile, hem de TV dock modunda Pro Controller veya fare/klavye ile akıcı 60 FPS çevrimdışı bot maçları veya yerel ağ çok oyunculu oynanış.
- **Desteklenecek İçerik ve Veri Sürümleri:** Standart Steam veya orijinal CD/Retail CS 1.6 veri klasörleri (`cstrike` ve `valve`). Zorunlu dosyalar: `cstrike/cstrike.wad`, `valve/halflife.wad`, haritalar (`maps/de_dust2.bsp` vb.), modeller ve sesler.

## Araştırma ve fizibilite

| Kaynak URL / revizyon | Kanıt | Karara etkisi |
| --- | --- | --- |
| FWGS / Xash3D FWGS (commit: `master-aarch64`) | Açık kaynak GPL-3.0 GoldSrc uyumlu motor; Linux/AArch64 ve Switch libnx/SDL2 backend desteği mevcut. | Uygun motor tabanı |
| CS16Client (commit: `master-arm64`) | CS 1.6 istemci/sunucu DLL'lerinin taşınabilir açık kaynak C/C++ yeniden uygulaması. | Native istemci ve sunucu mantığı |
| Nexvyn OS Native Kit (commit: `7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`) | Dear ImGui, OpenGL ES/GL, AArch64 dinamik modül (`.nxvmod`) desteği, dokunmatik ve gamepad olayları. | Native launcher ve pencere entegrasyonu |

- **Değerlendirilen motor ve alternatifler:** Orijinal GoldSrc kapalı kaynaklı ve x86 derlemesi olduğundan doğrudan emülasyon veya statik rekompilasyon yerine, doğrudan doğrulanmış ve tüm platformlarda çalışan açık kaynak Xash3D FWGS + CS16Client motoru seçildi.
- **AArch64, ABI/import, grafik, bellek, ses, depolama, giriş, DRM ve ağ gereksinimleri:**
  - AArch64 ELF dynamic module (`.nxvmod`), Native ABI 1.
  - Grafik: GLES2 / OpenGL ile Switch üzerinde 60 FPS kilitli render.
  - Bellek: Maksimum 250 MB RAM kullanımı (Switch'in 4 GB belleği için oldukça hafif).
  - Giriş: Çift analog, Joy-Con jiroskop (gyro aiming), çoklu dokunmatik ekran, USB klavye ve fare.
  - DRM: Orijinal oyun dosyaları kullanıcının kendi yasal kopyasından sağlanır, motor tamamen DRM-free.
  - Ağ: POSIX soketleri üzerinden yerel ağ (LAN) ve doğrudan IP bağlantısı.
- **Prototip sonucu ve karar:** `kısıtlı` (başlatıcı ve veri doğrulama prototipi hazır; Xash3D FWGS + CS16Client motor derlemesi henüz bağlanmadı). AArch64 native başlatıcı derlemesi ve Nexvyn OS pencere protokolü uyumludur.
- **Upstream ve SDK revizyonu:**
  - SDK: 1.15 (`7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`)
  - Native ABI: 1.2 / ABI 1
  - OS Hedefi: Nexvyn OS 1.3.28-beta.2+
  - Derleyici: aarch64-none-elf-gcc (devkitA64) + CMake 3.20+ + Ninja.

## Launcher, ayarlar ve kontroller

- **Mevcut 1.0.1 kapsamı:** Başlatıcı gömülü `game/` verisini veya kullanıcının sistem klasör seçicisiyle seçtiği CS 1.6 klasörünü açar, `cstrike/cstrike.wad` ve `valve/halflife.wad` dosyalarının `WAD2`/`WAD3` başlığını kontrol eder ve Xash3D motorunun henüz pakette yer almadığını açıkça bildirir.
- **Hedeflenen motor kontrol şeması (Xash3D bağlandığında):**

| Eylem veya ayar | Gamepad | Dokunma | Klavye/fare | Varsayılan / geçiş / kalıcılık |
| --- | --- | --- | --- | --- |
| Ateş (+attack) | ZR | Dokunmatik Ateş Butonu | Sol Tık | Planlanan |
| İkincil Fonksiyon (+attack2) | ZL | Dürbün Butonu | Sağ Tık | Planlanan |
| Şarjör Değiştir (+reload) | R | Şarjör Butonu | R tuşu | Planlanan |
| Zıpla (+jump) | L | Zıplama Butonu | Boşluk (Space) | Planlanan |
| Çömel (+duck) | B | Çömel Butonu | Ctrl | Planlanan |
| Kullan (+use) | A | Etkileşim Butonu | E tuşu | Planlanan |
| Satın Alma Menüsü (buy) | X | Hızlı Alışveriş Butonu | B tuşu | Planlanan |
| Son Silaha Geç (invprev) | Y | Silah Butonu | Q tuşu | Planlanan |
| Hareket (WASD) | Sol Çubuk | Sanal D-Pad | WASD | Planlanan |
| Bakış / Nişan Alma | Sağ Çubuk + Gyro | Dokunmatik Kaydırma | Fare Hareketi | Planlanan |
| Oyun Menüsü / Duraklat | Plus (+) | Menü Butonu | Esc | Planlanan |
| Skor Tablosu (Scoreboard) | Minus (-) | Skor Butonu | Tab | Planlanan |

## Doğrulama

| Senaryo | Cihaz / OS / paket / veri | Sonuç ve kanıt |
| --- | --- | --- |
| Native modül ve ABI denetimi | Masaüstü / SDK 1.15 `check-win` / cs16 v1.0.1 | `cs16.nxvmod` AArch64 ELF, relocation ve import kontrolünden geçti. |
| Yerelleştirme ve paket bütünlüğü | Masaüstü / `port_studio.py check store` & `pack` | 8 dil (`tr, en, de, es, fr, ja, ko, zh`) ve SHA-256 manifest doğrulaması geçti. |
| Cihaz üzerinde başlatıcı ve tam motor oynanışı | Gerçek Switch / Emülatör | Cihaz doğrulaması ve Xash3D motor entegrasyonu bekliyor. |
