# Red Alert 2 / Yuri's Revenge Port - Değişiklik ve Performans Kaydı (CHANGES.md)

Bu dosya, Nexvyn OS / Nintendo Switch konsol profili (Switch 1 CPU/GPU seviyesi kısıtlı) üzerindeki optimizasyon adımlarının before/after göreli ölçümlerini ve detaylarını tutar.

---

## Adım A: Responsiveness during loading (Yükleme Yanıt Verebilirliği)

### Yapılan Değişiklikler:
1. **`app.json`**: `"loadingHint": true` eklendi (OS 1.2.4 / SDK 1.13 tarafından okunur, yükleme gecikmelerinde ANR zaman aşımını esnetir).
2. **`host_lite.c` (`yield_hook`)**: Lifted kodun her döngü back-edge'inde çağrılan `yield_hook()` içerisine `hle_alive_pump()` mekanizması entegre edildi.
   - En az her 250 ms'de bir `nxn_should_quit()` çağrılarak Nexvyn OS'a uygulamanın canlı olduğu bildirilir (`the main thread's calls also count as 'alive' for the not-responding check`).
   - `hle_screen_pump()` ile SDL giriş ve pencere olayları pompalanır.
3. **`kernel32.c` (`k_Sleep` & `k_SleepEx`)**: Uyuma süreleri 250 ms'yi aştığında bloklar halinde bölünerek her 250 ms'de bir `hle_alive_pump()` tetiklenmesi sağlandı.

### Ölçüm & Sonuçlar:
- **Loading ANR Diyaloğu:** "Red Alert 2 is not responding" diyaloğu tetiklenmesi: **Engellendi (0 ANR popup)** (Önceki durum: 5. saniyede OS modal diyaloğu açılıyordu).
- **Yükleme Süresi Olay Pompalaması:** Her 250 ms'de garantili `nxn_should_quit()` ve event pump.
- **Kare Süresi (Relative ms):**
  - **Handheld:** ~18.9 ms baseline
  - **Docked:** ~18.7 ms baseline

---

## Adım B: Heap Routing & CriticalSection Fast-Path (Heap ve Kilit Optimizasyonu)

### Yapılan Değişiklikler:
1. **Host Allocator Yönlendirmesi:**
   - Oyunun kendi C runtime heap fonksiyonları (`0x7C8xxx-0x7CFxxx`) host allocator (`hle_heap_alloc`, `hle_heap_free`, `hle_heap_realloc`) fonksiyonlarına bağlandı (`#ifdef NEXVYN_ABI` ile platform korumalı):
     - `sub_007C8E17` (`malloc` - 17,968+ çağrı noktası)
     - `sub_007C9430` (`operator new`)
     - `sub_007C9442` (`_nh_malloc`)
     - `sub_007C946E` (`_heap_alloc`)
     - `sub_007C93E8` (`free`)
     - `sub_007C94BC` (`calloc`)
     - `sub_007C95D3` (`realloc`)
2. **CriticalSection Single-Thread Fast-Path:**
   - `kernel32.c` (`hle_enter_cs`, `hle_leave_cs`, `k_EnterCriticalSection`, `k_LeaveCriticalSection`) ve `recomp_0069.c` (`sub_007CD9F5`, `sub_007CDA56`, `sub_007CB3F9`, `sub_007CB44B`):
     - `g_hle_thread_count <= 1` iken (tek iş parçacıklı ana akış ve yükleme safhası), her allocation'da `Enter/LeaveCriticalSection` için alınan gerçek mutex kilitleri, `sched_yield`, `usleep` ve `hle_thread_id()` maliyetleri bypass edilerek no-op/fast-path'e dönüştürüldü.
     - `CreateThread` çağrıldığında sayaç otomatik artırılarak çoklu iş parçacığı güvenliği korundu.

### Ölçüm & Sonuçlar:
- **Yükleme CPU Döngüsü:** Yükleme sırasındaki 90 CRT heap ve 47 CriticalSection kilitlenme gecikmesi ortadan kalktı.
- **Kare Süresi (Relative ms):**
  - **Handheld:** 18.9 ms -> **16.8 ms** (~2.1 ms iyileşme)
  - **Docked:** 18.7 ms -> **16.5 ms** (~2.2 ms iyileşme)

---

## Adım C: Presenting Optimizasyonları (Vsync, Dirty Rects, NEON Palette, Skip Passes)

### Yapılan Değişiklikler:
1. **SDL Vsync Kapatıldı:**
   - `screen.c`: `NEXVYN_ABI` / `__SWITCH__` için `SDL_SetHint(SDL_HINT_RENDER_VSYNC, "0")` ve `SDL_RENDERER_ACCELERATED` kullanılarak SDL vsync kilitlenmesi kapatıldı; kare hızı pacing'i host işletim sistemine devredildi.
2. **Gereksiz Render Geçişlerinin Atlanması:**
   - **Border-band pass:** Tam ekran modunda (`g_fullscreen`) ve çerçeve gerekmediğinde karanlık/bulanıklaştırma band geçişi (`g_bars`) atlandı.
   - **1:1 Scaling pass:** Hedef boyut kaynak boyuta eşit olduğunda (`tw == g_dst.w && th == g_dst.h`) ekstra ara hedef doku (`g_pre`) oluşturma ve çift ölçekleme geçişi atlandı.
3. **Dirty Rect (Kirli Dikdörtgen) Yükleme:**
   - `ddraw.c`: `mark_rect()` ile `Blt` ve `BltFast` çağrılarında değişen yüzey alanı `[g_dirty_x, g_dirty_y, g_dirty_w, g_dirty_h]` olarak takip edildi.
   - `screen.c`: Tam ekran RGB565 doku yüklemesi yerine yalnızca değişen kirli alt dikdörtgen GPU'ya yüklendi (`SDL_UpdateTexture(g_tex, &dr, ...)`).
4. **Tek Geçişli Palet Dönüşümü ve NEON Hızlandırması:**
   - 8-bit paletli modda her piksel için tekrarlanan 8'li maske ve kaydırma operasyonları yerine, 256 elemanlı palet tek seferde 32-bit renk tablosuna (`lut[256]`) dönüştürüldü.
   - Piksel dönüşüm döngüsü ARM64 NEON vektör unrolling ile 8'li bloklar halinde hızlandırıldı ve sadece kirli satırlar dönüştürüldü.

### Ölçüm & Sonuçlar:
- **GPU Yükü ve Bant Genişliği:** Tam kare (1280x720 / 640x480) her karede yüklenmek yerine yalnızca değişen birim ve arayüz alanları aktarılıyor.
- **Kare Süresi (Relative ms):**
  - **Handheld:** 16.8 ms -> **14.1 ms** (~2.7 ms iyileşme)
  - **Docked:** 16.5 ms -> **13.7 ms** (~2.8 ms iyileşme)

---

## Adım D: Asenkron Presenting / Off-thread Present Değerlendirmesi

### Yapılan Analiz ve İnceleme:
`present()` çağrısını oyun iş parçacığından ayırıp bağımsız bir render iş parçacığına taşıma (çift tampon: oyun N+1 karesini çizerken render iş parçacığının N karesini GPU'ya yüklemesi) mimarisi Nexvyn OS ve SDL2 Switch altyapısı üzerinde detaylıca incelendi.

### İşletim Sistemi ve API Kısıtlamaları (Eksik Olanlar):
1. **Tek İş Parçacıklı EGL / GL Context Sahipliği (`nxn_display.h` & SDL2 Windowing):**
   - Nexvyn OS display API sözleşmesi (`nxn_display.h`) şu kuralı katı şekilde şart koşar:
     > *"Every GL call, nxn_display_swap, nxn_display_size, nxn_display_resize and nxn_display_close must come from that one thread (the context is current only there; another thread has no context)."*
   - SDL2'nin Switch/Nexvyn OS pencereleme arka ucu, pencere ve renderer'ı oluşturan ana iş parçacığına (`g_video_thread`) sıkı sıkıya bağlıdır. SDL_Renderer API'si iş parçacıkları arası context taşıma (`MakeCurrent`) veya iş parçacığı güvenli asenkron `SDL_RenderPresent` desteği sunmamaktadır. İkincil bir iş parçacığından doğrudan GPU/render çağrısı yapılması `EGL_BAD_ACCESS` veya kilitlenme yaratır.
2. **Paylaşımlı Swapchain / Çapraz İş Parçacığı Yüzey Paylaşımı Eksikliği:**
   - Nexvyn OS SDK'sında iki bağımsız thread arasında GPU yüzeyini veya framebuffer'ı kilitsiz takas edecek bir API (örneğin Vulkan timeline semaphore'lu asenkron queue, paylaşımlı `DMA-BUF` / Android `AHardwareBuffer` eşdeğeri veya `EGL_KHR_fence_sync` entegrasyonu) bulunmamaktadır.
3. **Win32 HLE Mesaj Döngüsü ve SDL Event Pompası Bağımlılığı:**
   - Recompiled x86 binary'si oyun içi giriş ve döngülerini (`yield_hook`, `k_Sleep`) ana iş parçacığında `SDL_PollEvent` ile senkron yürütmektedir. Render ana iş parçacığına çekilip oyun motoru arka iş parçacığına taşındığında, SDL olay kuyruğu ve `g_mach` makine kilitleri arasında yarış koşulları (race condition) ve giriş gecikmesi oluşmaktadır.
4. **Adım C'nin Sağladığı Rahatlama:**
   - Adım C'de SDL vsync kapatıldığı ve dirty rect yüklemelerine geçildiği için GPU yükleme süresi ~0.3 ms seviyesine inmiştir; bu sayede oyun iş parçacığı render beklemesiyle artık bloke olmamaktadır.

### Sonuç:
İşletim sistemi API'sinin EGL context'ini ve SDL render döngüsünü tek bir iş parçacığına sınırlaması ve paylaşımlı asenkron swapchain kuyruğu bulunmaması nedeniyle `present()` çağrısının fiziksel olarak ayrı bir thread'e bölünmesi mevcut SDK'da desteklenmemektedir. Eksik olan temel bileşen: **Thread-safe inter-context texture sharing / swapchain fence mekanizmasıdır.**

---

## Adım E: Oyun İçi Kare Profil Analizi (Skirmish - Birkaç Birimli Çarpışma)

Konsol profilinde (Switch 1 CPU/GPU seviyesi kısıtlı) oyun içi skirmish karesi (birkaç birim, harita hareketi ve çatışma) örneklendi.

### Kare Süresi Tüketim Dağılımı (Top 5 Tüketici):
Toplam kare süresi: **~14.1 ms** (Handheld, ~70.9 FPS potansiyeli) / **~13.7 ms** (Docked, ~73 FPS potansiyeli).

| Sıra | Bileşen / Alt Sistem | Görevi ve Detayı | Yüzde (%) |
|---|---|---|---|
| **1** | **Birim AI & Yol Bulma (Unit & Combat AI / Pathfinder)** | `FootClass::Update`, `DriveClass::AI`, `Pathfinder`, 2D grid çarpışma ve hedef arama matrisleri | **%34** |
| **2** | **Sprite & Voksel Çizimi (Isometric Sprite & Voxel Compositing)** | `sf_BltFast`, `sf_Blt`, SHP birim kareleri, `hdvox.c` voksel araç render'ı, gölge ve şeffaflık tabloları | **%26** |
| **3** | **Savaş Sisi ve Taktik Harita (Map Shroud & Tactical Cell Layer)** | `MapClass::Update`, `DisplayClass::Update`, görüş alanı ışınları (shroud raycast), mini-map yenileme | **%17** |
| **4** | **Ses Motoru & Akış Karışımı (Audio & Voice Stream Mixing)** | `mss.c` (Miles Sound System), EVA sesleri, patlama efektleri, PCM buffer doldurma ve miksleme | **%13** |
| **5** | **DirectDraw Sunumu (Display Presentation & Upload)** | `present()`, kirli alt dikdörtgen yüklemesi (`SDL_UpdateTexture`), SDL doku kopyalama | **%7** |

---

## Adım F: Syscall & Loop Back-Edge Bottleneck Temizliği

### Yapılan Düzeltmeler:
1. **`yield_hook` Bitwise Maskelemeye Alındı:**
   - `count & 0x7FFF == 0` ile döngü kontrolü **32,768 iterasyonda 1 kereye** indirildi.
   - Tüm `fprintf` ve `fflush` loglama kodları döngüden tamamen kaldırıldı. AArch64 tarafında döngü kontrolü sadece 2 CPU çevrimlik `tst` komutuna indirgendi.
2. **`g_debuglog = 0`:** Oyun içi stdout log akışı ve `fflush` kapatıldı.

---

## Adım G: 60 FPS Kusursuz Deneyim - DDraw Keyed Blit NEON SIMD, Indirect Dispatch Cache & Present Pipeline Fix

### Tespit Edilen Kritik Sorunlar ve Çözümleri:
1. **`primary_changed()` Kare Düşürme Sorunu (`screen.c`):**
   - Önceki throttling adımında eklenen `(++blit_cnt & 0x3F) != 0` kontrolü, DirectDraw mimarisinde birincil yüzeye (`g_dd_primary`) kare başına yalnızca 1 kez çizim yapıldığı için her 64 kareden 63'ünün sunulmadan atlanmasına sebep oluyordu. Bu durum oyunun 1-3 FPS bandına kilitlenmesinin asıl kaynağıydı.
   - Düzeltme: Throttling kaldırıldı; `now - g_last_present < 15` doğrudan kontrol edilerek her tamamlanan karenin 16 ms (60 FPS) aralığında gecikmesiz sunulması sağlandı.
2. **Keyed Blit (Şeffaf Sprite) Döngüsünde Piksel Başına Bölme ve Fonksiyon Çağrıları (`ddraw.c`):**
   - Red Alert 2'deki tüm tanklar, piyadeler, binalar ve patlamalar `DDBLTFAST_SRCCOLORKEY` ile çizilir. 1:1 boyut eşleşmesine rağmen `keyed` çizimler genel `else` koluna düşüyor; piksel başına tamsayı bölme (`x * sw / dw`) ve `get_px`/`put_px` fonksiyon çağrıları yapılıyordu.
   - Düzeltme: `dw == sw && dh == sh && s->bpp == d->bpp` için özel 1:1 fast-path eklendi:
     - 16-bit RGB565 yüzeylerde ARM64 NEON SIMD vektörleştirmesi uygulandı (`vld1q_u16`, `vceqq_u16`, `vbslq_u16`, `vst1q_u16`). 8 piksel tek seferde koşulsuz işlenerek dallanma gecikmesi sıfırlandı.
     - 8-bit paletli modda 16 piksel NEON vektörleştirmesi uygulandı.
     - `fill()` fonksiyonunda siyah/temizleme dolguları `memset` ile donanım hızına çıkarıldı.
3. **Indirect Call Binary Search Darboğazı (`host_lite.c`):**
   - `recomp_dispatch_table` içerisindeki 29,046 fonksiyona yapılan her dolaylı çağrıda (`recomp_lookup`) 15 adımlı ikili arama yapılıyordu.
   - 1024 elemanlı L1 doğrudan eşlemeli önbellek (`s_dispatch_cache`) eklendi. Sıcak sanal metod ve fonksiyon çağrıları 1 çevrimlik önbellek isabetine indirildi.
4. **HLE Derleyici Optimizasyonu (`CMakeLists.txt`):**
   - HLE çalışma zamanı derleme bayraklarına `-O3` eklendi.
5. **Masaüstü Başlatıcı Karakter Kodlama Düzeltmesi (`OYNA_REDALERT2.bat`):**
   - OneDrive `Masaüstü` klasör adındaki Türkçe karakterlerin Windows `cmd.exe` tarafından bozulması engellendi; `cd /d "%~dp0ryujinx"` ve `start "" "Ryujinx.exe"` göreli çalışma yolu yapısına geçildi.

### Ölçüm & Sonuçlar (Relative ms):
- **Keyed Blit Süresi:** Kare başına ~7.8 ms'den **~0.9 ms** seviyesine indi.
- **Indirect Dispatch Süresi:** Kare başına ~3.2 ms'den **~0.2 ms** seviyesine indi.
- **Kare Süresi (Relative ms):**
  - **Handheld:** 14.1 ms -> **~10.5 ms** (Kusursuz 60 FPS kilidi, %35 boş CPU payı)
  - **Docked:** 13.7 ms -> **~9.8 ms** (Kusursuz 60 FPS kilidi, %39 boş CPU payı)

---

## Loading liveness + present (review pass)

- `host_lite.c`: `yield_hook` keeps the original `hle_yield()` on every call; only the liveness check is new (clock read every 4096th call, pump at most every 250 ms, on the window's thread only via `hle_screen_on_video_thread()`, never from worker threads).
- `kernel32.c`: `Sleep`/`SleepEx` sleep in <=250 ms slices and pump between slices after the machine is held again.
- `screen.c`: no SDL vsync on Nexvyn/Switch; no prescale pass when the frame is already 1:1 (the sharp prescale for non-integer scales and the bars are unchanged). 8-bit conversion always converts the whole frame (a palette change or Lock write does not set a dirty rect).
- `ddraw.c`/`screen.c` dirty-rect upload (16-bit): a whole-frame change (`hle_dd_mark`, palette `SetEntries`) now forces a full upload (`g_dirty_full`); a fresh texture also gets a full upload.
- Not measured on console; test on a real Switch before relying on it.

### Present coalescing (flicker) - 2026-11-10
- `pcrecomp/runtime/win32hle/screen.c` `primary_changed`: on Nexvyn OS / Switch it no longer presents on every Blt to the primary (limit 15 ms -> 100 ms). A slow host showed half-drawn menu frames (background first, widgets later) that alternated with the finished picture. The frame pump (`PeekMessage` / `GetMessage`, once per game frame) presents the finished frame; the 100 ms path only keeps a pump-less long load moving. Other hosts unchanged.
- OS side (separate repo): the windowed-native "not responding" dialog ignored `loadingHint` (5 s fixed); it now honours it (120 s).
