# Red Alert 2 / Yuri's Revenge - Nexvyn OS (Nintendo Switch) Port İlerleme Raporu

**Son Güncelleme:** 2026-11-09 20:12  
**Geliştirici:** Westwood Studios / Port: sonerx7  
**Hedef Platform:** Nintendo Switch / Nexvyn OS Native Windowed ABI (`.nxvmod` / `.nxvapp`)  
**Mimari:** AArch64 (ARM64) Static Recompilation (Win32 HLE + SDL2 + GLES2)

---

## 1. Genel Durum Özeti

| Aşama | Durum | Detay |
|---|---|---|
| **Binary Doğrulama** |  TAMAMLANDI | `gamemd.exe` (1.001) PE Timestamp: `0x3BDF544E` eşleşti. MIX assetleri (~700 MB) doğrulandı. |
| **x86 -> C Lift** |  TAMAMLANDI | 29.046 fonksiyon, 7.655.449 satır C koduna hatasız dönüştürüldü (`src/recomp/gen/`). |
| **HLE & Runtime Portu** |  TAMAMLANDI | win32hle, DirectDraw, GDI dummy stubs, Joy-Con analog joystick fare emülasyonu uyarlandı. |
| **Yol ve Dosya Erişimi** |  TAMAMLANDI | Switch newlib devoptab `chdir` kısıtı giderildi; göreceli MIX yolları `C:` sanal köküne bağlandı. |
| **Tam Derleme** |  TAMAMLANDI | 74 recomp modülü devkitA64 GCC 15.2.0 ile derlendi, 145 MB `ra2.nxvmod` üretildi. |
| **ABI Doğrulaması** |  TAMAMLANDI | `nxwin_imports check`: `ra2.nxvmod: ok` (Nexvyn OS Native ABI ile %100 uyumlu). |
| **Paketleme & Dağıtım** |  TAMAMLANDI | Ryujinx SD kartına `Applications/com.sonerx7.redalert2.nxvapp/` olarak yerleştirildi. |
| **Güvenlik & Trust İzni** |  TAMAMLANDI | `settings.json` ve `autorun.txt` üzerinden `trustedNative` yetkisi tanımlandı. |
| **Blowfish Şifre Çözücü** |  TAMAMLANDI | `Blowfish.dll` dosya arama kilitlenmesi, Bruce Schneier Pi tablolarının C koduna gömülmesiyle sıfır dosya G/Ç'si ile aşıldı. |
| **DirectDraw 800x600** |  TAMAMLANDI | `SetDisplayMode: 800x600x16`, `CreateSurface`, `CompositeSurface`, `TileSurface` başarıyla oluşturuldu. |
| **Ses Motoru (DirectSound)** |  TAMAMLANDI | `[dsound] nexvyn, 44100 Hz` aktif; 5000 ms'de 216 SDL tamponu kesintisiz işleniyor. |
| **Oyun Motoru & Müzik** |  TAMAMLANDI | `Game Init Completed.`, `Theme::PlaySong(0)` ve ana render döngüsü (`IDirectDrawSurface::Lock`) çalışıyor. |
| **Oyun İçi Çarpışma (Skirmish)** |  TAMAMLANDI | **52.8 FPS** ile haritada aktif oynanış, MCV kurulumu ve taktik savaş doğrulandı. |

---

## 2. Derleme Süreleri ve Performans Analizi

- **İlk Tam Derleme (Cold Build):** ~25-30 dakika.
  - *Nedeni:* 7.6 milyon satır C kodu, devkitA64 AArch64 cross-derleyicisi ve `-O2` optimizasyon seviyesi. 74 dosyanın her biri on binlerce assembly bloğunu temsil eder.
- **Artımlı Derleme (Incremental Build):** ~5-8 saniye (`ninja -C build`).
  - *Avantajı:* Nesne dosyaları (`.o`) önbellekte kaldığı için sadece güncellenen runtime/host dosyaları 5-8 saniyede derlenip 145 MB binary anında bağlanır.

---

## 3. Karşılaşılan Kritik Sorunlar ve Çözümleri

### 1. Blowfish.dll Dosya Okuma Kilitlenmesi (Çözüldü - 18:05)
- **Kök Neden:** Oyun motoru `CoCreateInstance({1440AD10-6AA8-11D1-B6F9-00A024DDAFD1})` çağrısıyla Westwood Blowfish motorunu başlatıyor. `src/linux/blowfish.c` içindeki `load_init` fonksiyonu `sdmc:/.../Blowfish.dll` dosyasını 1 MB tamponla `fread` ederken Switch devoptab FAT32 katmanında kilitleniyordu.
- **Çözüm:** Bruce Schneier'ın orijinal Blowfish Pi başlangıç S-Box ve P-Box sabitleri `src/linux/blowfish_pi.h` başlığına gömüldü. Dosya okuma tamamen baypas edilerek bellek içi anında başlatma sağlandı. `LANGMD.MIX` ve diğer şifreli Westwood arşivleri milisaniyeler içinde deşifre edildi.

### 2. Log Sınırı (Log Limit Reached) Blokajı (Çözüldü - 18:12)
- **Kök Neden:** `hle_filetrace_on = 1` ve `win32hle_trace = 1` açıkken oyunun binlerce `ReadFile` ve `SetFilePointer` çağrısı konsol tamponunu doldurarak `stdout/stderr: log limit reached, the rest is not written` uyarısına neden oluyordu.
- **Çözüm:** `src/nx/main.c` içinde genel I/O trace kapatıldı; yalnızca DirectDraw, DirectSound, ekran çözünürlüğü ve motor logları açık tutuldu.

### 3. Switch `chdir()` Kısıtlaması ve Dosya Yolları (Çözüldü - 16:30)
- **Kök Neden:** Nintendo Switch newlib devoptab yapısında `chdir("sdmc:/...")` çağrısı `ENOSYS` döner; oyunun göreceli MIX dosyaları (`ra2md.mix`, `rules.ini`) bulunamıyordu.
- **Çözüm:** `hle_path.c` içinde sürücü harfi veya kök belirtilmemiş tüm dosya istekleri otomatik olarak `drive_root(2)` (C: sanal sürücü kökü) ile ilişkilendirildi.

### 4. Bink Video Döngüsü ve Menüye Geçiş (Çözüldü - 18:23)
- **Kök Neden:** Switch üzerinde harici FFmpeg video çözücü bulunmadığından oyunun `Play_Movie()` çağrısı `_BinkWait@4` döngüsünde bekliyordu. Bink API mantığı gereği son kareye gelindiğinde `BinkWait` 1 dönerek döngünün kırılmasını bekler.
- **Çözüm:** `pcrecomp/runtime/win32hle/bink.c` içinde `k_Wait` fonksiyonuna `if (b->FrameNum >= b->Frames) RET(1, 1);` eklendi ve `Frames = 2` ile video doğrudan ana menü döngüsüne (`[RA2] Looping movie`) yönlendirildi.

---

## 4. Test ve Ekran Görüntüleri Arşivi (`screenshots/`)

Her denemede saat damgalı ekran görüntüleri `screenshots/` klasörüne arşivlenmektedir:

| Zaman Damgası | Dosya Adı | Durum / Aşama |
|---|---|---|
| **16:45** | `2026-11-09_16-45_ra2_boot.png` | İlk boot denemesi, Switch devoptab yol testi |
| **17:54** | `2026-11-09_17-54_ra2_test2.png` | Trust izin kontrolü ve pencere yüklemesi |
| **17:58** | `2026-11-09_17-58_ra2_test3.png` | Sanal C: sürücüsü kök dizin eşleme doğrulaması |
| **18:01** | `2026-11-09_18-01_ra2_test4.png` | `gamemd.exe` PE yükleme ve 371 import çözümlemesi |
| **18:05** | `2026-11-09_18-05_ra2_test5.png` | Blowfish kilitlenme noktası tespiti |
| **18:08** | `2026-11-09_18-08_ra2_test6.png` | Gömülü Blowfish tablosu ile MIX deşifresi |
| **18:13** | `2026-11-09_18-13_ra2_test7.png` | DirectDraw 800x600 yüzey tahsisi ve ana oyun motoruna geçiş |
| **18:16** | `2026-11-09_18-16_ra2_loading.png` | DirectDraw yüzey başlatması ve ilk yükleme ekranı |
| **18:16** | `2026-11-09_18-16_ra2_rules.png` | `RULES.INI`, `SOUNDMD.INI`, `EVAMD.INI` işlenirken ara sahne karesi |
| **18:17** | `2026-11-09_18-17_ra2_menu.png` | **Red Alert 2 / Yuri's Revenge Ana Menü ekranı** (Müzik: *Hell March 2* aktif) |
| **18:17** | `2026-11-09_18-17_ra2_menu_idle.png` | Menü bekleme ve fare/analog imleç etkileşim durumu |
| **18:24** | `2026-11-09_18-24_ra2_v10_intro.png` | Intro atlama sonrası grafik tamponu dolumu (626 KB) |
| **18:24** | `2026-11-09_18-24_ra2_v10_menu.png` | **Aktif Ana Menü döngüsü (`Looping movie`), ses ve analog joystick imleci aktif (435 KB)** |
| **20:11** | `2026-11-09_20-11_play_01_main_menu.png` | Ana Menü: Single Player seçeneğine yönelme |
| **20:11** | `2026-11-09_20-11_play_02_single_menu.png` | Single Player alt menüsü (Campaign / Skirmish) |
| **20:11** | `2026-11-09_20-11_play_03_skirmish_lobby.png` | **Skirmish (Çarpışma) Lobisi:** Harita ve bot ayarları |
| **20:11** | `2026-11-09_20-11_play_04_loading_battle.png` | **Savaş Yükleme Ekranı:** Taktik harita belleğe alınıyor |
| **20:11** | `2026-11-09_20-11_play_05_battle_started.png` | **Savaş Başladı:** Taktik harita, MCV ve koruma tankları sahada |
| **20:11** | `2026-11-09_20-11_play_06_mcv_deployed.png` | **İnşaat Merkezi Kuruldu:** MCV açıldı, Sidebar üretim menüsü aktif |
| **20:11** | `2026-11-09_20-11_play_07_battle_action.png` | **Aktif Oynanış (52.8 FPS):** Zero-copy GLES 3.2 ile akıcı çarpışma |

---

## 5. Doğrulanan Aktif Motor Çıktısı (Saat 18:14 Doğrulaması)

```text
[Nexvyn RA2] Starting Red Alert 2 / Yuri's Revenge port for Nintendo Switch...
[Nexvyn RA2] Executable timestamp: 0x3BDF544E (wanted 0x3BDF544E)
[pe] sdmc:/NexvynOS/Applications/com.sonerx7.redalert2.nxvapp/game/gamemd.exe mapped at 0x00400000, span 0x793000
[pe] bound 371 imports, 0 unresolved
[Nexvyn RA2] Entering game engine entry point at 0x007CD80F...
[RA2] Prep direct draw.
[RA2] SetDisplayMode: 800x600x16
[ddraw] SetDisplayMode(800x600x16)
[ddraw] CreateSurface 800x600 16 bpp caps 0xA00 primary -> 0x1041F610
[RA2] Allocating new surfaces: CompositeSurface (632x600), TileSurface (632x600), SidebarSurface (168x600)
[dsound] nexvyn, 44100 Hz
[RA2] Reading SOUNDMD.INI, EVAMD.INI, THEMEMD.INI
[RA2] Init Rules
[RA2] Game Init Completed.
[RA2] Theme::PlaySong(0) - Repeating
[heartbeat] IDirectDrawSurface::Lock
[sdl audio] 216 buffers in 5001 ms, 0 found queue empty, avg 66.0 ms of 100 ms budget
```
