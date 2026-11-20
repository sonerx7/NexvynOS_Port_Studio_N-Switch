# Red Alert 2 / Yuri's Revenge Dağıtım Kaydı

| Dosya veya grup | Kaynak ve sürüm | Lisans/izin ve kanıt | App Market / kişisel / harici | Gerekli atıf veya yükümlülük |
| --- | --- | --- | --- | --- |
| Native modül ve başlatıcı (`ra2.nxvmod`) | `redalert2-recomp`, `pcrecomp` (`621860a9d22c9b25ae2be4575b956596f4ddaeeb`) ve Nexvyn Port Studio Switch host/launcher | MIT (host, araçlar ve Nexvyn başlatıcı katmanı); üretilmiş statik rekompilasyon çıktısı için `NOTICE.md` açıklaması mevcut | App Market & Kişisel | `LICENSE` ve `NOTICE.md` pakette yer alır. |
| Başlatıcı yerelleştirme dosyaları (`lang/*.json`) | Nexvyn Port Studio özgün üretim | MIT | App Market & Kişisel | 8 dilde tam yerelleştirme metinleri (`de, en, es, fr, ja, ko, tr, zh`). |
| Başlatıcı görseli ve ikon (`icon.png`, `assets/logo.nximg`) | Port Studio başlatıcı görselleri | Tanıtım / Arayüz bileşeni | App Market & Kişisel | Westwood Studios / Electronic Arts marka hakları saklıdır. |
| Türkçe metin tablosu (`assets/RA2.CSF`) | Yerel Türkçe çeviri tablosu | Yalnızca kişisel paket (`localData`) | Kişisel `--data-root` | Ticari `.csf` uzantısı nedeniyle mağaza paketine dahil edilmez; kişisel pakette veya harici oyun klasöründe overlay olarak kullanılır. |
| Orijinal oyun dosyaları (`gamemd.exe`, `*.mix`, `*.dll`, `*.ini`) | Kullanıcının kendi Red Alert 2 & Yuri's Revenge kurulumu (Steam / EA App / Retail, PE timestamp `0x3BDF544E`) | Ticari mülkiyet (Westwood Studios / Electronic Arts) | Harici / Kişisel `--data-root` | Mağaza paketine hiçbir `.exe`, `.dll` veya `.mix` dosyası dahil edilmez. Kişisel test paketinde yalnızca motorun ihtiyaç duyduğu temel arşivler (1 GiB açılmış paket sınırının altında kalacak şekilde) eşlenir. |

## Harici veri

- **Desteklenen yasal kurulumdan seçilecek klasörler ve temel dosyalar:**
  - Kullanıcı yasal olarak sahip olduğu Yuri's Revenge kurulum klasörünü seçer.
  - Zorunlu dosyalar: `gamemd.exe` (PE timestamp `0x3BDF544E`), `ra2.mix`, `ra2md.mix` ve kurulumdaki diğer standart `.mix` arşivleri (`langmd.mix`, `thememd.mix`, `multimd.mix`, `expandmd01.mix`, `mapsmd03.mix` vb.).
- **Sürüm doğrulaması ve yama uygulama yöntemi:**
  - Başlatıcı `gamemd.exe` dosyasının PE başlığındaki zaman damgasını (`0x3BDF544E`) ve ana `.mix` arşivlerinin varlığını kontrol eder. Eksik dosya ile uyumsuz çalıştırılabilir sürüm durumlarını ayrı raporlar.
  - Orijinal oyun klasörüne yazma yapılmaz; `ra2md.ini`, modlar ve varsa Türkçe `RA2.CSF` dosyası uygulamanın kendi kalıcı veri alanındaki `overlay_active/` dizini üzerinden yönlendirilir.
- **Uygulamanın paketlenmiş ve harici veriyi arama sırası:**
  1. Kullanıcının daha önce seçip kaydettiği geçerli oyun klasörü.
  2. Kişisel pakete gömülü `game/` klasörü (`NXN_DIR_BUNDLE/game`).
  3. SD kart üzerindeki bilinen yerel dizinler veya kullanıcının klasör seçiciyle seçtiği yeni konum.
- **Kişisel verinin mağazaya karışmadığını gösteren paket kontrolü:**
  - `port_studio.py check store GamePorts/RedAlert2` komutu `AppMarket/Store/Games/strategy/redalert2/source/` içinde hiçbir `.exe`, `.dll`, `.mix` veya `.csf` dosyasının bulunmadığını ve `publicFiles` listesiyle birebir eşleştiğini doğrular.
