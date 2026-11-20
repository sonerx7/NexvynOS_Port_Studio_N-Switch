# Red Alert 2 — mevcut launcher uygulamasından teknik referans

Bu belge Red Alert 2 çalışmasının tarihsel notlarını korur. Yeni portlar için
[Port Launcher Standardı](PORT_LAUNCHER_STANDARD.md) ve yerel public SDK geçerlidir.

> **Belge Türü:** AI System Prompt — Game Port Projesi  
> **SDK:** Nexvyn OS SDK 1.15+ / Native SDK 1.2+ / ABI v1  
> **Referans Uygulama:** Red Alert 2: Yuri's Revenge Port v1.2.0

---

## Giriş

Bu belge, herhangi bir oyunun Nexvyn OS'a port edilmesi sürecinde AI ajanlarının takip edeceği kapsamlı standart prompt'tur. Amaç: her port projesi için tutarlı, yüksek kaliteli bir launcher UI, kontrol yapılandırması, performans profili, yerelleştirme ve OS entegrasyonu sağlamaktır.

Bu belgeyi AI system prompt'u olarak yükleyin. Ajan, oyuna özel detayları (tür, motor, dosya yapısı) analiz ederek bu standartları oyuna uyarlayacaktır.

---

## 1. Proje Yapısı ve Dizin Düzeni

Her port projesi aşağıdaki dizin yapısını takip etmelidir:

```
<proje_kök>/
├── app.json                    # Nexvyn OS uygulama manifestosu
├── icon.png                    # 512×512 uygulama ikonu
├── CMakeLists.txt              # Build sistemi
├── build.sh                    # Otomatik build scripti
├── assets/
│   ├── logo.nximg              # Launcher hero card logosu
│   └── <oyuna_özel_dosyalar>   # Dil yamaları, overlay dosyaları vb.
├── lang/
│   ├── en.json                 # İngilizce
│   ├── tr.json                 # Türkçe
│   ├── de.json                 # Almanca
│   ├── es.json                 # İspanyolca
│   ├── fr.json                 # Fransızca
│   ├── ja.json                 # Japonca
│   ├── ko.json                 # Korece
│   └── zh.json                 # Çince (Basitleştirilmiş)
├── src/
│   └── nx/
│       ├── main.c              # nxn_run giriş noktası + oyun içi kontrol + OS menü
│       ├── launcher.cpp        # Dear ImGui launcher UI
│       └── launcher.h          # Config struct + API tanımları
├── game/                       # Oyun dosyaları (kullanıcı tarafından sağlanır)
└── dist/                       # Build çıktıları
    └── <oyun>.nxvapp            # Paketlenmiş uygulama
```

---

## 2. app.json — Uygulama Manifestosu

Her port projesi aşağıdaki alanları **zorunlu** olarak içermelidir:

```json
{
  "id": "com.<geliştirici>.<oyun_kısa_adı>",
  "name": {
    "en": "<Oyun Adı>",
    "tr": "<Oyun Adı>",
    "de": "<Oyun Adı>",
    "es": "<Oyun Adı>",
    "fr": "<Oyun Adı>",
    "ja": "<Oyun Adı>",
    "ko": "<Oyun Adı>",
    "zh": "<Oyun Adı>"
  },
  "version": "1.0.0",
  "author": "<Orijinal Stüdyo> / <Porter>",
  "category": "games",
  "minSdk": "1.10",
  "targetSdk": "1.15",
  "minNative": "1.2",
  "targetNative": "1.2",
  "minOs": "1.3.26",
  "runtime": "native",
  "main": "<oyun>.nxvmod",
  "icon": "icon.png",
  "mode": "window",
  "window": {
    "width": 1280,
    "height": 720,
    "resizable": true
  },
  "liveResize": true,
  "gamepad": true,
  "loadingHint": true,
  "description": {
    "en": "<8 dilde açıklama>",
    "tr": "...",
    "de": "...",
    "es": "...",
    "fr": "...",
    "ja": "...",
    "ko": "...",
    "zh": "..."
  },
  "permissions": ["files"]
}
```

> [!IMPORTANT]
> - **8 dil zorunludur:** en, tr, de, es, fr, ja, ko, zh
> - Online özellik varsa `"permissions"` dizisine `"net"` ekleyin
> - `"gamepad": true` tüm portlarda zorunludur

---

## 3. Launcher UI Mimarisi

Launcher, **Dear ImGui** ve **`<nexvyn/nxn_os_ui.h>`** frame layer kullanılarak oluşturulur. Nexvyn OS'un tema ve tasarım sistemiyle tam uyumlu olmalıdır.

### 3.1 Hero Card (Üst Başlık Kartı)

Launcher'ın en üstünde her zaman bir Hero Card yer alır:

```
┌─────────────────────────────────────────────────────────┐
│  [LOGO]  Oyun Adı                          [Exit] [PLAY]│
│          Nexvyn OS Native Port · SDK 1.2                │
│  [Files Verified]  [Nexvyn Stable Profile]  [Mod:Auto]  │
└─────────────────────────────────────────────────────────┘
```

**Zorunlu Öğeler:**
- Uygulama ikonu/logosu (`assets/logo.nximg`)
- Oyun başlığı (`nxn_tr("app.title")`)
- SDK sürüm etiketi
- Durum rozetleri (badges):
  - **Dosya Doğrulama:** `Files Verified` (yeşil) veya `Files Missing` (kırmızı)
  - **Profil Durumu:** `Nexvyn Stable Profile` (accent) veya `Custom Settings` (amber)
  - **Dock/Handheld Modu:** Pil yüzdesiyle birlikte
- **Exit** butonu (`NXN_OS_BTN_DEFAULT`)
- **PLAY** butonu (`NXN_OS_BTN_PRIMARY`) — dosyalar doğrulanmamışsa `BeginDisabled`

**Compact/Responsive Mod:**
- Dar ekranlarda (fb_w / scale < 680px) butonlar alt satıra geçer

### 3.2 Tab Yapısı

Ana sekmeler `nxn_os_segmented_tabs` ile oluşturulur. **Minimum 4 standart sekme zorunludur:**

| Sekme | İçerik |
|-------|--------|
| **Overview** | Oyun klasörü seçimi, dosya doğrulama, oyuna özel seçenekler (mod, dil, kampanya) |
| **Video & Perf** | Çözünürlük, ekran modu, ölçekleme, performans profili, motor ayarları |
| **Controls** | Gamepad / Touchscreen / KB+Mouse alt sekmeleri |
| **Logs** | Canlı tanılama logları |

Oyunun türüne göre ek sekmeler eklenebilir:
- **Online** (çok oyunculu oyunlar için)
- **Mods** (kapsamlı mod desteği varsa)
- **Audio** (ayrıntılı ses yapılandırması gerekiyorsa)

---

## 4. Overview Sekmesi

### 4.1 Oyun Klasörü ve Dosya Doğrulama

```c
// Klasör seçimi
nxn_pick_params p = NXN_STRUCT_INIT(nxn_pick_params);
p.kind = NXN_PICK_FOLDER;
p.flags = NXN_PICK_REMEMBER;
p.title = nxn_tr("btn.browse");
char picked[512] = {0};
nxn_pick(&p, picked, sizeof(picked));
```

**Dosya Doğrulama Kuralları:**
1. Oyunun çalışması için gerekli tüm dosyaları bir `required_files[]` listesinde tanımlayın
2. Her dosya için varlık kontrolü yapın (`access()` veya `stat()`)
3. Mümkünse PE timestamp veya dosya boyutu doğrulaması yapın
4. Her dosya için yeşil/kırmızı rozet gösterin: `nxn_os_badge("dosya.exe OK", k_green, tok)`
5. Tüm dosyalar doğruysa: `"All required game files are verified and ready to play!"`

**Otomatik Klasör Algılama:**
- Önce `nxn_fs_path(NXN_DIR_DATA, ...)` kontrol edin (önceki kayıtlı yol)
- Sonra bilinen kurulum yollarını tarayın: `sdmc:/NexvynOS/Applications/<id>/game`
- Bulunamazsa kullanıcıdan seçmesini isteyin

### 4.2 Oyuna Özel Seçenekler

Oyunun türüne göre Overview sekmesine eklenmesi gereken seçenekler:

| Oyun Türü | Olası Seçenekler |
|-----------|-----------------|
| RTS | Kampanya seçimi, mod seçimi, harita editörü erişimi |
| FPS | Kampanya/Çok Oyunculu seçimi, zorluk seviyesi |
| RPG | Kayıt dosyası seçimi, DLC durumu |
| Yarış | Araç paketi seçimi, pist seti |
| Emülasyon | ROM seçimi, BIOS doğrulama |
| Strateji | Senaryo/sandbox modu, yapay zeka seviyesi |

### 4.3 Mod Desteği

Mod desteği olan oyunlar için:

```
mods/
├── <mod_adı_1>/
│   └── <mod dosyaları>
├── <mod_adı_2>/
│   └── <mod dosyaları>
```

- `mods/` klasörünü otomatik tarayın (`opendir` / `readdir`)
- Modded / Unmodded seçeneği sunun
- Mod seçim dropdown'u gösterin
- Mod dosyalarını overlay dizinine kopyalayın (orijinal dosyalara dokunmayın)

### 4.4 Dil Seçimi

**Zorunlu kurallar:**
1. **Varsayılan: Otomatik (Sistem Dili)** — `nxn_imgui_language(sys_lang)` ile sistem dilini al
2. Oyunun desteklediği tüm dilleri listele
3. Oyun dil dosyalarını (`langmd_<xx>.mix`, `language_<xx>.mix`, `*.csf`, `*.lng` vb.) oyun klasöründe ara
4. Dil değişikliği non-destructive olmalı: overlay dosyası kopyalanır, orijinale dokunulmaz
5. Dil etiketleri tam yazılır: "English", "Türkçe", "Deutsch", "Español", "Français", "日本語", "한국어", "中文"

```c
// Otomatik dil çözümleme
char sys_lang[4] = {0};
nxn_imgui_language(sys_lang);  // "tr", "en", "de", vb.
// sys_lang'a göre oyun dilini seç
```

---

## 5. Video & Performance Sekmesi

### 5.1 Nexvyn OS Stable Profile (Stabil Profil)

**En kritik özellik.** Her port'ta zorunlu.

**Davranış:**
- **Varsayılan: AÇIK** (tüm performans ayarları kilitli, en güvenli değerler)
- Kullanıcı kapattığında ayarlar düzenlenebilir olur
- Tekrar açıldığında tüm ayarlar safe değerlere döner (`apply_stable_lock`)
- "Varsayılana Dön" butonu her zaman görünür

**Stabil Profil Varsayılan Değerleri:**

| Ayar | Değer | Gerekçe |
|------|-------|---------|
| Çözünürlük | 1280×720 | Switch handheld native |
| Ekran Modu | Fullscreen | Tam ekran performans |
| Ölçekleme | Sharp (Default) | En düşük GPU yükü |
| Auto Dock | OFF | Kullanıcı bilinçli açmalı |
| FPS HUD | OFF | Temiz görünüm |
| Oyun detayı | Oyuna göre en uygun | 60 FPS hedefi |

### 5.2 Auto Dock / Handheld Resolution

```c
// Dock olayını dinle
if (ev.type == NXN_EVENT_DOCK && cfg->auto_dock_res) {
    int w = ev.docked ? 1920 : 1280;
    int h = ev.docked ? 1080 : 720;
    apply_live_resolution(w, h);
}
```

**Kurallar:**
- **Varsayılan: KAPALI**
- Açıldığında bilgi popup'u göster (`nxn_dialog`):
  - "Docked modda 1920×1080, handheld modda 1280×720 kullanılır. Mod değiştirme anında çözünürlük otomatik değişir."
- `NXN_EVENT_DOCK` ve `NXN_EVENT_POWER` olaylarını dinle
- Canlı geçiş (live resolution change) destekle: `nxn_window_set_title` ile başlık güncelle

### 5.3 FPS Sayacı (HUD Overlay)

- Toggle switch: "Show FPS Counter"
- `hle_screen_fps_overlay(cfg->show_fps)` ile HW overlay
- OS menü çubuğundan da açılıp kapatılabilmeli

### 5.4 Çözünürlük Tablosu

Her port için uygun çözünürlükler tanımlanmalıdır:

```c
static const int k_res_list[][2] = {
    { 1280, 720  },  // Switch Handheld Native 16:9 (Varsayılan)
    { 1920, 1080 },  // Switch Docked Native 16:9
    { 1024, 768  },  // Classic 4:3 (eski oyunlar için)
    { 800,  600  },  // Classic 4:3 düşük
    { 1366, 768  },  // 16:9 Orta
    { 1600, 900  },  // 16:9 Yüksek
};
```

### 5.5 Ölçekleme Filtreleri

Standart ölçekleme seçenekleri:

| Filtre | Açıklama | Ne Zaman |
|--------|----------|----------|
| Sharp (Default) | Keskin kenarlar | Piksel sanat, 2D, düşük res |
| Smooth (Bilinear) | Yumuşak geçiş | 3D oyunlar, HD |
| Nearest (Pixel) | Piksel-mükemmel | Retro, pixel art |
| Integer | Tam sayı katları | GBA/NES tarzı |
| CRT Scanlines | Tarama çizgileri | Retro nostalji |

### 5.6 Motor-Özel Ayarlar

Oyunun motoruna göre eklenmesi gereken ayarlar:

| Kategori | Örnekler |
|----------|---------|
| Grafik Kalitesi | Low / Medium / High |
| Gölge Kalitesi | Off / Low / High |
| Anti-Aliasing | Off / FXAA / 2x / 4x |
| Doku Kalitesi | Low / Medium / High |
| Görüş Mesafesi | Slider (1-10) |
| Intro/Video | Skip ON/OFF |
| V-Sync | ON/OFF |

### 5.7 Ses Ayarları

Minimum 3 ses slider'ı:

```c
nxn_os_slider("##vol_sfx",   &cfg->vol_sfx,   0.0f, 1.0f, tok, nxn_os_fill());
nxn_os_slider("##vol_voice", &cfg->vol_voice,  0.0f, 1.0f, tok, nxn_os_fill());
nxn_os_slider("##vol_music", &cfg->vol_music,  0.0f, 1.0f, tok, nxn_os_fill());
```

---

## 6. Controls Sekmesi

### 6.1 Alt Sekme Yapısı

Her port'ta 3 kontrol alt sekmesi zorunludur:

```
[Gamepad]  [Touchscreen]  [Keyboard & Mouse]
```

`nxn_os_segmented_tabs("##ctrl_sub_tabs", sub_labels, 3, &ctrl_sub_tab, tok);`

### 6.2 Gamepad Ayarları

**Zorunlu öğeler:**
- Analog stick dead zone slider (0.05 – 0.35)
- İmleç/kamera hızı slider
- Tuş eşleme (remapping) — oyun türüne göre

**RTS Oyunları İçin:**
| Tuş | Varsayılan Fonksiyon | Alternatifler |
|-----|---------------------|---------------|
| A | Sol tık (seçim/komut) | — |
| B | Sağ tık (hareket/saldırı) | ESC |
| X | Çoklu seçim (Shift) | — |
| Y | Deploy / Özel | OSK, Force Attack, Stop |
| L | Hassas imleç (yavaş) | Multi-Select, Grup 1 |
| R | Hızlı imleç boost | Force Attack, Grup 2 |
| L3 | Üsse git (H) | Son olay (Space) |
| R3 | Aynı türü seç (T) | Tüm savaş birimleri, Dağıl |
| Right Stick | Kamera pan | — |
| D-Pad | Kamera pan | Menü navigasyonu |
| + | Oyun menüsü / Pause | — |
| - | Minimap toggle / Tab | — |

**FPS Oyunları İçin:**
| Tuş | Varsayılan | Alternatifler |
|-----|-----------|---------------|
| Left Stick | Hareket | — |
| Right Stick | Nişan/Bakış | — |
| L | Nişan (ADS) | Koşma |
| R | Ateş | — |
| A | Zıplama | — |
| B | Çömelme / Eğilme | Melee |
| X | Silah değiştir | — |
| Y | Yeniden doldur | Etkileşim |

**Platformer Oyunları İçin:**
| Tuş | Varsayılan | Alternatifler |
|-----|-----------|---------------|
| A | Zıplama | — |
| B | Koşma / Saldırı | — |
| X | Özel güç | — |
| Y | Etkileşim | — |
| D-Pad | Hareket (dijital) | — |
| Left Stick | Hareket (analog) | — |

### 6.3 Touchscreen Ayarları

**Zorunlu öğeler:**
- 2 parmak pan/kaydırma toggle
- Dokunma hassasiyeti slider (0.5 – 2.0)
- Pan yönü ters çevirme (Natural/Inverted)
- Uzun basma → sağ tık toggle
- 2 parmak dokunma → sağ tık toggle

**Oyun Türüne Özel:**
- **RTS:** 2 parmak sürükleme ile kamera pan (en önemli!)
- **FPS:** Sanal joystick (sol taraf: hareket, sağ taraf: nişan), ateş butonu
- **Platformer:** Sanal D-pad + aksiyon butonları
- **Point & Click:** Dokunma = tık, uzun basma = sağ tık

### 6.4 Keyboard & Mouse Ayarları

**Zorunlu öğeler:**
- WASD kamera/hareket pan toggle
- Ekran kenarı kaydırma (edge scroll) toggle
- Fare hapsi (confine pointer) toggle
- Kaydırma hızı slider

### 6.5 "Varsayılana Dön" Butonu

Her kontrol sayfasının altında:

```c
if (nxn_os_button(nxn_tr("btn.reset_defaults"), NXN_OS_BTN_DEFAULT, tok)) {
    config_set_stable_defaults(cfg, 1);  // keep_paths = 1
    config_save(cfg);
}
```

### 6.6 Kontrol Özeti

Her alt sekmenin altında kısa kontrol rehberi metni gösterilmelidir:

```
"Gamepad: Left stick = cursor, A = select, B = command, Right stick = camera pan..."
```

---

## 7. Logs Sekmesi

**Zorunlu öğeler:**

1. **Ring buffer log sistemi** (160 satır, 220 karakter/satır)
2. **"Copy to Clipboard"** butonu (`nxn_clipboard_set`)
3. **"Clear Logs"** butonu (`NXN_OS_BTN_DESTRUCTIVE`)
4. **Monospace font** ile log gösterimi (`NXN_OS_TEXT_MONO`)
5. **Otomatik scroll** (en yeni log altta)

**Loglanması gereken olaylar:**
- Uygulama başlatma
- Dosya doğrulama sonuçları
- Dil seçimi ve çözümleme
- Overlay/mod yükleme
- Config okuma/yazma
- Çözünürlük değişiklikleri
- Hata ve uyarılar
- I/O cache istatistikleri

---

## 8. OS Menü Çubuğu (Oyun İçi)

Oyun çalışırken Nexvyn OS üst menü çubuğuna oyuna özel menüler eklenir.

### 8.1 Menü Yapısı

`nxn_menu_set(&spec)` ile 4 standart menü oluşturulur:

```
[Game]  [View]  [Controls]  [Help]
```

### 8.2 Game Menüsü

| Öğe | Kısayol | Tüm Oyunlarda |
|-----|---------|---------------|
| Pause / Resume | Esc | ✅ |
| — (ayırıcı) | | |
| <Oyuna özel komutlar> | | Oyun türüne göre |
| — (ayırıcı) | | |
| On-Screen Keyboard | | ✅ |
| Quit Game | | ✅ |

**Oyuna özel komutlar örnekleri:**
- **RTS:** Home Base (H), Last Event (Space), All Combat (P), Scatter (X)
- **FPS:** Quick Save (F5), Quick Load (F9), Toggle Flashlight
- **RPG:** Inventory (I), Map (M), Journal (J)

### 8.3 View Menüsü

| Öğe | Kısayol | Zorunlu |
|-----|---------|---------|
| Fullscreen Toggle | F11 | ✅ |
| Fill / Aspect Ratio | | ✅ |
| Cycle Scaling Filter | F12 | ✅ |
| — (ayırıcı) | | |
| 1280×720 | | ✅ |
| 1920×1080 | | ✅ |
| Auto Dock/Handheld | | ✅ |
| — (ayırıcı) | | |
| <Motor özel toggle'lar> | | Opsiyonel |
| FPS Counter | | ✅ |

### 8.4 Controls Menüsü

Oyun türüne göre en sık değiştirilen kontrol toggle'ları:

**RTS örneği:**
- Right Stick Camera Pan ✓
- Two-Finger Camera Pan ✓  
- D-Pad Camera Pan ✓
- Keyboard WASD Pan ✓
- Cursor Speed: Slow (8) / Normal (12) ✓ / Fast (18)
- Confine Mouse Pointer ✓

### 8.5 Help Menüsü

| Öğe | İçerik |
|-----|--------|
| Control Guide | Kontrol rehberi dialog'u (`nxn_dialog`) |
| Performance Stats | FPS, mod, pil, çözünürlük, I/O cache oranı |
| About | Versiyon, motor, geliştirici bilgileri |

### 8.6 Menü Olaylarını İşleme

```c
static void pump_os_events_in_game(void) {
    nxn_event ev = NXN_STRUCT_INIT(nxn_event);
    while (nxn_event_poll(&ev) > 0) {
        if (ev.type == NXN_EVENT_MENU) {
            handle_os_menu_action(ev.item_id);
        } else if (ev.type == NXN_EVENT_DOCK && cfg->auto_dock_res) {
            apply_live_resolution(ev.docked ? 1920 : 1280, ev.docked ? 1080 : 720);
            update_os_menu_bar();
        } else if (ev.type == NXN_EVENT_QUIT) {
            // Temiz çıkış
        } else if (ev.type == NXN_EVENT_FOCUS && !ev.focused) {
            on_focus_lost();  // Ses/oyun durdurma
        }
    }
}
```

---

## 9. Config Yapısı ve Kalıcılık

### 9.1 Config Struct Şablonu

Her port'un kendine özel bir `<oyun>_config_t` struct'ı olmalıdır:

```c
typedef struct game_config_t {
    // Yollar
    char game_dir[512];
    char mod_name[128];
    
    // Profil
    int stable_profile;      // 1 = Nexvyn Stable Profile (varsayılan, kilitli)
    
    // Görüntü
    int fullscreen;          // 1 = Fullscreen
    int auto_dock_res;       // 0 = OFF (varsayılan)
    int res_index;           // Çözünürlük tablosu indeksi
    int res_w, res_h;        // Aktif çözünürlük
    int scale_index;         // Ölçekleme filtresi
    int fit_mode;            // 0=fill, 1=aspect bars, 2=aspect blur
    int show_fps;            // FPS HUD
    
    // Dil
    int game_lang;           // 0=Auto(System), 1=English, 2+=oyuna özel
    
    // Ses
    float vol_sfx;
    float vol_voice;
    float vol_music;
    
    // <Oyuna özel ayarlar buraya>
    
    // Kontrol - Gamepad
    float cursor_speed;      // veya kamera hassasiyeti
    float deadzone;
    int <tuş_eşleme_alanları>;
    
    // Kontrol - Touch
    int twofinger_pan;
    float touch_pan_sens;
    int touch_pan_invert;
    int longpress_rc;
    int twofinger_rc;
    
    // Kontrol - KB+Mouse
    int wasd_pan;            // veya oyuna uygun hareket
    int edge_scroll;
    int confine_mouse;
    int scroll_rate;
} game_config_t;
```

### 9.2 Config Dosyası Formatı

INI-benzeri key=value formatı, `nxn_fs_write / nxn_fs_read` ile `NXN_DIR_DATA` dizinine kaydedilir:

```
version=3
game_dir=/sdmc/NexvynOS/Applications/com.dev.game/game
stable_profile=1
fullscreen=1
auto_dock_res=0
res_index=0
...
```

### 9.3 Kaydetme/Yükleme

- **İlk çalışma:** Stable Profile varsayılanları yüklenir, log'a kaydedilir
- **Her değişiklik:** Hemen kaydedilir (`config_save` çağrılır)
- **Versiyon numarası:** Config formatı değişirse `version` alanıyla geriye uyumluluk

---

## 10. Online / Çok Oyunculu Özellikler

Online özelliği olan oyunlar için ek sekme veya Overview'a ek bölüm:

### 10.1 Bağlantı Testi

```c
nxn_net_status status = NXN_STRUCT_INIT(nxn_net_status);
if (nxn_net_check(&status) == NXN_OK) {
    if (status.online) {
        // "Bağlantı OK" rozeti göster
    } else {
        // "Çevrimdışı" uyarısı
    }
}
```

### 10.2 Online Seçenekler

| Öğe | Açıklama |
|-----|----------|
| Kullanıcı Adı / Nickname | Text input (nxn_text_input) |
| Sunucu Seçimi | Dropdown (otomatik / manuel) |
| NAT Türü | Bilgi etiketi (Açık / Orta / Kapalı) |
| Bağlantı Testi Butonu | Ping testi + sonuç |
| LAN Modu | Toggle (yerel ağ oyunu) |
| Port Yönlendirme | Bilgi dialog'u |

### 10.3 İzinler

`app.json`'da `"permissions": ["files", "net"]` olmalıdır.

---

## 11. Yerelleştirme (i18n) Sistemi

### 11.1 Launcher UI Dil Dosyaları

Her dil için `lang/<xx>.json` dosyası oluşturulur. Minimum key set:

```json
{
  "app.title": "Game Title: Port",
  "app.subtitle": "Nexvyn OS Native Port · SDK 1.2",
  
  "btn.play": "PLAY",
  "btn.quit": "Exit",
  "btn.browse": "Select Game Folder",
  "btn.verify": "Verify Files",
  "btn.reset_defaults": "Reset to Defaults",
  "btn.copy_logs": "Copy to Clipboard",
  "btn.clear_logs": "Clear",
  
  "tab.overview": "Overview",
  "tab.video": "Video & Perf",
  "tab.controls": "Controls",
  "tab.logs": "Logs",
  
  "status.ready": "Files Verified",
  "status.missing": "Files Missing",
  "status.stable": "Nexvyn Stable Profile",
  "status.custom": "Custom Settings",
  "status.docked": "Docked",
  "status.handheld": "Handheld",
  
  "sec.game_path": "Game Path & Verification",
  "sec.launch_mode": "Launch Mode & Language",
  "sec.profile": "Nexvyn Stable Profile",
  "sec.display": "Display & Resolution",
  "sec.engine": "Engine & Audio Config",
  "sec.logs": "Diagnostics",
  
  "lbl.game_dir": "Game Path",
  "lbl.no_dir": "No game folder selected. Tap 'Select Game Folder'.",
  "lbl.verify_ok": "All required game files are verified and ready to play!",
  "lbl.verify_fail": "Some game files are missing. Verify your game path.",
  "lbl.stable_profile": "Nexvyn Stable Profile",
  "lbl.stable_hint": "Locks settings to safe, tested values for smooth gameplay. Disable to customize.",
  "lbl.auto_dock_res": "Auto Dock / Handheld Resolution",
  "lbl.auto_dock_hint": "1920×1080 when docked, 1280×720 in handheld mode.",
  "lbl.show_fps": "FPS Counter (HUD)",
  "lbl.display_mode": "Display Mode",
  "lbl.resolution": "Game Resolution",
  "lbl.scaling": "Scaling Filter",
  "lbl.fit_mode": "Fullscreen Fit",
  "lbl.game_lang": "In-Game Language",
  "lbl.ui_lang_note": "Launcher UI follows Nexvyn OS language setting.",
  
  "ctrl.sub.gamepad": "Gamepad",
  "ctrl.sub.touch": "Touchscreen",
  "ctrl.sub.kbmouse": "Keyboard & Mouse",
  
  "msg.reset_done": "Settings reset to Nexvyn Stable Profile defaults.",
  "msg.copied": "Logs copied to clipboard.",
  
  "menu.game": "Game",
  "menu.view": "View",
  "menu.controls": "Controls",
  "menu.help": "Help",
  
  "dlg.ok": "OK",
  "dlg.controls.title": "Control Guide",
  "dlg.perf.title": "Performance Stats",
  "dlg.about.title": "About",
  "dlg.autodock.title": "Auto Resolution",
  "dlg.autodock.msg": "Resolution will automatically switch: 1920×1080 (Docked TV) ↔ 1280×720 (Handheld)."
}
```

### 11.2 Oyun İçi Dil Çözümleme

```
1. Kullanıcı seçimi kontrol et (cfg->game_lang)
2. game_lang == 0 ise: sistem dilini al (nxn_imgui_language)
3. Sistem diline göre oyun dil dosyasını bul
4. Dil dosyasını overlay dizinine kopyala (non-destructive)
5. Log: "Auto language: system='tr' -> mode=Turkish"
```

---

## 12. Performans Optimizasyon Kontrol Listesi

Port geliştirme sürecinde uygulanması gereken optimizasyonlar:

### 12.1 I/O Optimizasyonu

- [ ] **Fast I/O cache** uygulandı mı? (RAM cache ≤8MB + 256KB read-ahead)
- [ ] Sıralı okuma read-ahead buffer'ı var mı?
- [ ] Dosya erişim deseni optimize edildi mi? (büyük dosyalar ilk yüklenmede cache'lenir)

### 12.2 Yükleme Süresi

- [ ] Intro video atlanabilir mi? (skip_intro seçeneği)
- [ ] Splash screen süresi minimumda mı?
- [ ] Lazy loading uygulandı mı? (tüm asset'ler başta yüklenmez)
- [ ] Yükleme ekranı/progress bar var mı?

### 12.3 Frame Time

- [ ] Stabil profilde 60 FPS hedefine ulaşılıyor mu?
- [ ] Handheld modda 720p'de 30+ FPS garanti mi?
- [ ] Docked modda 1080p'de 30+ FPS garanti mi?
- [ ] Frame time spike'lar giderildi mi?

### 12.4 Bellek

- [ ] Toplam bellek kullanımı Switch RAM limitlerinde mi?
- [ ] Bellek sızıntısı (leak) yok mu?
- [ ] Texture/asset boyutları optimize mi?

---

## 13. Build ve Paketleme

### 13.1 CMakeLists.txt Şablonu

```cmake
cmake_minimum_required(VERSION 3.18)
project(<oyun>_port C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Nexvyn OS Native SDK
include($ENV{NXN_SDK}/cmake/NexvynNative.cmake)

# Kaynak dosyalar
file(GLOB_RECURSE SOURCES src/nx/*.c src/nx/*.cpp)

# Hedef
nxn_add_module(<oyun> ${SOURCES})
target_link_libraries(<oyun> PRIVATE nexvyn_native imgui SDL2)
```

### 13.2 Build Doğrulama Kontrol Listesi

Build sonrası şu kontroller geçmelidir:

```bash
# 1. Import kontrolü (0 missing olmalı)
nxwin_imports build/<oyun>.nxvmod
# Beklenen: "1773/0 missing" gibi

# 2. i18n kontrolü (8 dil geçmeli)  
nxv_i18n check .
# Beklenen: "PASS (8 lang)"

# 3. Tasarım kontrolü
python3 tools/design_check.py .
# Beklenen: "0 FAIL 0 WARN"

# 4. Paketleme
nxvapp_pack . dist/<oyun>.nxvapp
```

---

## 14. Store Yayınlama

### 14.1 store.json

```json
{
  "id": "com.<geliştirici>.<oyun>",
  "version": "1.0.0",
  "channel": "beta",
  "category": "games/strategy",
  "rating": "T",
  "size_mb": 50,
  "screenshots": [
    "screenshots/01_gameplay.png",
    "screenshots/02_launcher.png",
    "screenshots/03_controls.png"
  ],
  "changelog": {
    "en": "Initial release with full launcher, stable profile, 8 language support.",
    "tr": "İlk sürüm: tam launcher, stabil profil, 8 dil desteği."
  }
}
```

### 14.2 Screenshot Gereksinimleri

- Minimum 3, maksimum 8 screenshot
- İlk screenshot: **oyun içi gameplay** (en dikkat çekici sahne)
- Launcher Overview sekmesi
- Launcher Video/Controls sekmesi
- 1280×720 veya 1920×1080 çözünürlük
- PNG formatı

---

## 15. Kalite Kontrol ve Yayın Öncesi Checklist

### Zorunlu (BLOCKER)

- [ ] `nxwin_imports`: 0 missing import
- [ ] `nxv_i18n`: PASS (8 lang)
- [ ] `design_check`: 0 FAIL 0 WARN
- [ ] Launcher PLAY butonu oyunu başlatıyor
- [ ] Dosya doğrulama doğru sonuç veriyor
- [ ] Stable Profile varsayılan AÇIK ve kilitli
- [ ] Config kaydediliyor/yükleniyor
- [ ] OS menü çubuğu aktif
- [ ] Fullscreen düzgün çalışıyor
- [ ] Gamepad ile tam kontrol mümkün
- [ ] Touch ile temel kontrol mümkün
- [ ] KB+Mouse ile tam kontrol mümkün
- [ ] 720p Handheld'de 30+ FPS
- [ ] Temiz çıkış (`NXN_EVENT_QUIT` işlenir)

### Önerilen (SHOULD)

- [ ] 1080p Docked'da 30+ FPS
- [ ] Auto Dock resolution çalışıyor
- [ ] FPS HUD overlay çalışıyor
- [ ] Mod desteği (varsa) çalışıyor
- [ ] Dil otomatik algılanıyor
- [ ] I/O cache oranı %80+ 
- [ ] Focus kaybında oyun duraklatılıyor
- [ ] Help > Performance Stats dialog doğru bilgi gösteriyor
- [ ] Help > About dialog doğru versiyon gösteriyor
- [ ] Log tab'ında anlamlı loglar var

### Güzel Olur (NICE)

- [ ] 60 FPS stabil (hem handheld hem docked)
- [ ] CRT scanline filtre çalışıyor
- [ ] Birden fazla kayıt profili
- [ ] Oyuna özel başarımlar/istatistikler
- [ ] Screenshot alma özelliği

---

## 16. Oyun Türüne Göre Hızlı Referans

### RTS (Real-Time Strategy)
- **Öncelik:** Kamera pan (çok yöntemli: stick, d-pad, 2-finger touch, WASD, edge scroll)
- **İmleç:** Gamepad analog → fare eşleme, hassasiyet ayarı kritik
- **Tuş eşleme:** Birim komutları (deploy, scatter, guard, force attack)
- **Minimap:** Dokunmatik ile minimap tıklanabilmeli

### FPS (First-Person Shooter)
- **Öncelik:** Nişan hassasiyeti, gyro aiming desteği (varsa)
- **Kontrol:** Dual-stick standart, ADS toggle/hold
- **Performans:** 30 FPS minimum, input lag minimumda
- **Touch:** Virtual dual-stick + fire button

### RPG (Role-Playing Game)
- **Öncelik:** UI navigasyonu gamepad ile, metin okunabilirliği
- **Kontrol:** Menü navigasyonu (bumper ile tab değiştirme)
- **Font:** Handheld'de okunabilir boyut
- **Save/Load:** Launcher'dan save management

### Platformer
- **Öncelik:** Input lag (< 2 frame), hassas zıplama
- **Kontrol:** D-pad veya analog (kullanıcı seçimi)
- **Performans:** 60 FPS kesinlikle gerekli

### Yarış (Racing)
- **Öncelik:** Analog tetik hassasiyeti (gaz/fren), vibrasyon
- **Kontrol:** Analog steering sensitivity slider
- **Performans:** 30 FPS minimum stabil

### Turn-Based Strategy / Tactical
- **Öncelik:** UI navigasyonu, grid seçimi
- **Kontrol:** Gamepad ile grid navigasyonu (d-pad ideal)
- **Touch:** Doğrudan grid hücresine dokunma
- **Performans:** FPS çok kritik değil, response time önemli

---

## 17. Kod Şablonları

### 17.1 main.c Giriş Noktası

```c
#include <nexvyn/nexvyn_native.h>
#include "launcher.h"

static game_config_t g_cfg;

int nxn_run(int argc, char **argv) {
    (void)argc; (void)argv;
    
    // 1. Launcher'ı çalıştır
    if (!game_run_launcher(&g_cfg)) {
        return 0;  // Kullanıcı Exit'e bastı
    }
    
    // 2. Config'i uygula ve overlay hazırla
    char overlay_dir[512];
    game_apply_config(&g_cfg, overlay_dir, sizeof(overlay_dir));
    
    // 3. OS menü çubuğunu kur
    update_os_menu_bar();
    
    // 4. Oyun motorunu başlat
    game_engine_init(&g_cfg, overlay_dir);
    
    // 5. Ana oyun döngüsü
    while (!nxn_should_quit()) {
        pump_os_events_in_game();
        game_engine_tick(&g_cfg);
    }
    
    // 6. Temiz çıkış
    config_save(&g_cfg);
    game_engine_shutdown();
    return 0;
}
```

### 17.2 Overlay Dizini Mantığı

Orijinal oyun dosyalarına **asla** dokunulmaz. Tüm değişiklikler overlay dizininde yapılır:

```c
// NXN_DIR_DATA altında overlay dizini oluştur
nxn_fs_mkdirs(NXN_DIR_DATA, "overlay_active");
nxn_fs_path(NXN_DIR_DATA, "overlay_active", ov_dir, sizeof(ov_dir));

// Dil dosyası, mod dosyası vb. bu dizine kopyalanır
copy_file_bin(src_csf, dst_csf);  // Orijinal dizine değil!
```

### 17.3 Dock Olayı ile Canlı Çözünürlük Değişimi

```c
static void apply_live_resolution(int w, int h) {
    g_cfg.res_w = w;
    g_cfg.res_h = h;
    game_write_resolution_config(&g_cfg, w, h);
    
    nxn_caps caps = NXN_STRUCT_INIT(nxn_caps);
    if (nxn_caps_get(&caps) == NXN_OK && (caps.features & NXN_CAP_WINDOW_CTL)) {
        char sub[64];
        snprintf(sub, sizeof(sub), "%dx%d", w, h);
        nxn_window_set_title("Game Title", sub);
    }
}
```

---

## 18. Sık Yapılan Hatalar ve Çözümler

| Hata | Çözüm |
|------|-------|
| `nxn_imgui_language` geri dönüş tipi yanlış | `char sys_lang[4]={0}; nxn_imgui_language(sys_lang);` — `const char*` döndürmez! |
| Orijinal oyun dosyaları değiştiriliyor | Overlay dizini kullanın, orijinale dokunmayın |
| Config kayboluyorsa | `nxn_fs_write(NXN_DIR_DATA, ...)` kullanın, relative path değil |
| Dock geçişinde crash | `NXN_EVENT_DOCK` event handler'da null check yapın |
| Gamepad çalışmıyor | `"gamepad": true` app.json'da olmalı |
| Touch çalışmıyor | `nxn_imgui_input_event(ev)` event loop'ta çağrılmalı |
| Menü çubuğu görünmüyor | `NXN_CAP_MENU` capability check yapın |
| FPS HUD görünmüyor | `hle_screen_fps_overlay()` fonksiyon varlığını kontrol edin |

---

## 19. Referans Uygulama

Bu standart, **Red Alert 2: Yuri's Revenge Port v1.2.0** baz alınarak oluşturulmuştur.

**Referans kaynak kodları:**
- `launcher.cpp` — 1286 satır, tam Dear ImGui launcher
- `launcher.h` — Config struct ve API tanımları
- `main.c` — 946 satır, oyun entegrasyonu + OS menü + kontrol sistemi
- `app.json` — 8 dilli manifest
- `lang/*.json` — 8 dil dosyası

**Referans özellikler:**
- 4 sekmeli launcher (Overview, Video & Perf, Controls, Logs)
- Nexvyn Stable Profile ile kilitlenen ayarlar
- RTS kamera pan: Right stick, D-pad, 2-finger touch, WASD, edge scroll
- Gamepad tuş remapping (Y, L, R, L3, R3)
- Auto Dock/Handheld çözünürlük geçişi
- FPS HUD overlay
- Turkish RA2.CSF dil yaması overlay
- Yuri's Revenge mod seçici
- OS menü çubuğu: Game, View, Controls, Help
- Fast I/O cache (%90+ cache hit)
- 8 dilde launcher UI

---

> [!TIP]
> Bu belgeyi AI system prompt'unuza ekleyerek her port projesi için tutarlı kalite elde edin. Oyuna özel detayları (tür, motor, dosya yapısı) analiz ederek bu şablonu uyarlayın. Her zaman önce Stable Profile'ı doğru kurun — bu, kullanıcı deneyiminin temelidir.
