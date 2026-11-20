# Counter-Strike 1.6 Dağıtım Kaydı

| Dosya veya grup | Kaynak ve sürüm | Lisans/izin ve kanıt | App Market / kişisel / harici | Gerekli atıf veya yükümlülük |
| --- | --- | --- | --- | --- |
| Native modül ve launcher (`cs16.nxvmod`) | Nexvyn Port Studio özgün başlatıcı ve WAD doğrulayıcı | GNU GPL v3 | App Market & Kişisel | Kaynak kodu ve lisans metni (`LICENSE`, `NOTICE.md`) pakette sunulur. |
| Arayüz bileşenleri ve çeviriler (`lang/*.json`) | Nexvyn Port Studio özgün üretim | MIT / GPL v3 uyumlu | App Market & Kişisel | 8 dilde tam yerelleştirme metinleri. |
| Mağaza ikonu ve ekran görüntüleri | CS 1.6 özgün ikonundan uyarlanmış 512x512 PNG | Adil kullanım / Tanıtım | App Market | Valve Corporation marka ve telif hakları saklıdır. |
| Kullanıcı tarafından sağlanan veri | Steam / Retail CS 1.6 kurulumu | Ticari mülkiyet (Valve Corp.) | Harici / Kişisel `--data-root` | Mağaza paketine ticari veri dahil edilmez; yalnızca kişisel pakette işlenir. |

## Harici veri

- **Desteklenen yasal kurulumdan seçilecek klasörler ve temel dosyalar:**
  - Kullanıcı yasal olarak sahip olduğu Counter-Strike 1.6 klasörünü seçer.
  - Gerekli dizinler: `cstrike/` ve `valve/`.
  - Zorunlu dosyalar: `cstrike/cstrike.wad`, `valve/halflife.wad`, `cstrike/maps/` altındaki BSP haritaları.
- **Sürüm doğrulaması ve yama uygulama yöntemi:**
  - Başlatıcı `cstrike.wad` ve `halflife.wad` dosyalarının varlığını ve boyutunu doğrular.
  - Orijinal dosyalara ASLA yazma yapılmaz; kullanıcı ayarları ve bot konfigürasyonları Nexvyn OS kullanıcı veri dizininde tutulur.
- **Uygulamanın paketlenmiş ve harici veriyi arama sırası:**
  1. Kişisel pakete gömülü veri (`game/cstrike`, `game/valve`).
  2. Kullanıcının başlatıcıdan seçtiği ve kaydettiği harici klasör (`game_dir`).
  3. SD kart üzerindeki standart kullanıcı dizinleri (`sdmc:/NexvynOS/Users/.../Documents/Game Workshop/CounterStrike1_6`).
- **Kişisel verinin mağazaya karışmadığını gösteren paket kontrolü:**
  - `port_studio.py check store` aracı mağaza `source/` klasöründe hiçbir ticari uzantının (`.wad`, `.bsp`, `.dll`, `.exe`, vb.) bulunmadığını doğrular.
