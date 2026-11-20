# Sürüm, kişisel paket ve App Market

İki çıktı aynı derlenmiş native modülü, aynı port kodunu ve aynı uygulama kimliğini kullanır. `app.json` içindeki sürüm her iki pakete de girer. Nexvyn OS aynı kimlikteki paketi yerinde güncellediği için iki kanal aynı anda ayrı uygulama olarak kurulmaz. Farklı sürümlerde kişisel ve mağaza paketleri arasında geçişi ve kayıt uyumluluğunu test et.

| Kanal | İçerik | Çıktı |
| --- | --- | --- |
| Kişisel | Dağıtılabilir temel paket ve kullanıcının seçtiği yerel oyun/uygulama dosyaları | `_RealesedBuilds/game/<slug>/<id>-<sürüm>-local.nxvapp` veya `_RealesedBuilds/software/<slug>/<id>-<sürüm>-local.nxvapp` |
| App Market | Dağıtım kaydı bulunan port kodu/modülü, lisansı izin veren varlıklar ve launcher. Özgün ticari veri kullanıcı tarafından seçilir. | `<port>/AppMarket/Store/<Games|Apps>/<kategori>/<slug>/<slug>.nxvapp` |

## Port klasörünü hazırla

```text
<port>/
├── PORT.md                  # Araştırma, karar, build komutu, cihaz kanıtı
├── DISTRIBUTION.md          # Kaynak, lisans, dağıtım kararı ve kullanıcı veri gereksinimi
├── CHANGELOG.md
├── KNOWN_ISSUES.md
├── port.json
└── AppMarket/Store/Games/strategy/<slug>/
    ├── source/              # Yalnızca dağıtıma uygun bundle dosyaları
    │   ├── app.json
    │   ├── main.nxvmod
    │   ├── icon.png
    │   ├── lang/
    │   ├── LICENSE
    │   └── NOTICE.md
    ├── README.md            # İngilizce mağaza kurulum/kullanım rehberi
    ├── store.json           # Sekiz dilde başlık altı/açıklama ve özellikler
    ├── screenshots/         # Çalışan porttan gerçek ekran görüntüleri
    └── <slug>.nxvapp        # Oluşturulan mağaza paketi
```

`port.json` örneği. Her `lang/*.json` dosyasını ayrı satır olarak ekle, joker karakter kullanılmaz.

```json
{
  "slug": "ornek-port",
  "storeCategory": "strategy",
  "publicFiles": ["app.json", "main.nxvmod", "icon.png", "LICENSE", "NOTICE.md"],
  "localData": [{"from": "installed-data", "to": "game"}]
}
```

- `publicFiles` mağaza `source/` klasöründeki dosyaların açık envanteri. Klasörün içeriği bu listeyle birebir eşleşir. Kullanıcı verisi için ayrılmış hedefler, gizli dosyalar, bağlantılar, anahtarlar, yaygın ticari oyun veri uzantıları ve iç içe paketler reddedilir. Bu kontrol hak sahipliği incelemesinin yanında çalışır. `DISTRIBUTION.md` içinde modül, upstream kod, çeviri, yama, ikon, müzik, ekran görüntüsü ve her veri grubunun kaynağını ve dağıtım dayanağını doğrula. Kararı belirsiz girdiyi mağazadan çıkar.
- `localData` yalnızca kişisel pakette işlenir. `from`, kullanıcının sağladığı `--data-root` altındaki dosya veya klasör. `to`, launcher’ın gömülü veri için açtığı paket yolu. Bir klasör eşlemesi bütün alt dosyaları alır. Kurulumun tamamı gerekmiyorsa gereken dosyaları tek tek eşle. Gereken her seçili yol bulunmalı. Bağımsız çalışabilen açık kaynak uygulamada `localData: []` yeterli. Kişisel veriyi repo dışında ya da Git’in yok saydığı `_LocalData/` içinde tut.
- Mağaza launcher’ı ilk çalıştırmada desteklenen veri sürümünü, gereken dosyaları ve mevcut kurulumdan nasıl seçileceğini anlatır. Orijinal dosyaları indiren bir bağlantıyı ancak meşru ve doğrulanmış bir kaynak varsa ekle. Mağaza paketi harici veri olmadan kurulup seçim ekranına ulaşabilmeli.
- Manifest sürümü `MAJOR.MINOR.PATCH` ve kalıcı ters alan adı kimliği kullanır. Yeni sürümde `CHANGELOG.md` ve `KNOWN_ISSUES.md` içinde `## 1.2.0` gibi bir bölüm aç. Etkiyi, koşulu, varsa geçici çözümü ve doğrulanan ortamı yaz. Sorun bulunmadıysa hangi kapsamda bulunmadığını belirt. Uygulama verisi şeması değişirse SDK’nın `dataSchema` ve veri geçişi kurallarını izle. Yayımlanan sürüm metadatasıyla mağaza README’si uyumlu olmalı.

## Mağaza görselleri ve denetim

Çalışan sürümden **üç ila beş** gerçek görüntü al. Oyun için sıralama önerisi  
**1.** Yoğun veya karakteristik gameplay, **2.** içerik hazır gösteren launcher, **3.** gerçek oyun menüsü veya kontrol/ayar ekranı, **4–5.** farklı sahne ve oynanış özelliği. Uygulama için ana iş akışı, belge/proje açma ekranı ve kullanışlı bir sonuç veya ayar ekranı göster. Launcher ekranı yoksa var olan gerçek bir ekranı kullan.

İngilizce UI, uygulama sınırlarına kırpılmış PNG ve aynı sürümün görsellerini kullan. `screenshots/1.png` ile başla. Masaüstünü, kişisel dosya yollarını, hesap adlarını, bildirimleri ve debug katmanlarını görüntüye alma. Dağıtımı gözden geçirilmiş içerikle çek. Mockup, temsili veya üretilmiş görüntüyü çalışan ürün kanıtı olarak koyma. Cihaz/emülatör çekimi mümkün değilse `store.json` içinde 3–5 tekrarlanabilir SDK çekim senaryosu oluştur ve çekim/doğrulamanın beklediğini kaydet.

Kurulu bir emülatör ve mevcut Nexvyn OS build’i varsa [SDK nxvtest](../nexvyn_sdk/Tools/nxvtest/README.md) ile tekrarlanabilir bir port senaryosu oluştur. `screenshot` adımlarını launcher, menü ve gameplay/ana iş için ekle. `expect_screenshot`, `expect_screenshots_differ` ve kapanış kontrollerini kullan. Sonuçtaki PNG’leri açıp içerik ve kırpımı gözle doğrula. İzole test çalışma klasörünü `build_nxvtest/` gibi Git dışında kalan bir dizine koy ve yalnız seçilen mağaza görsellerini kopyala.

```powershell
python _PortStudioMain/tools/port_studio.py check store "GamePorts/Ornek"
python _PortStudioMain/tools/port_studio.py pack local "GamePorts/Ornek" --data-root "D:/Oyunlar/Ornek"
python _PortStudioMain/tools/port_studio.py pack store "GamePorts/Ornek"
```

Araç public SDK ile kaynak, sekiz dil, native modül kimliği/relocation/import, paket ve SHA-256 doğrulaması yapar. Native denetim için devkitA64 araçları gerekir. Windows’ta varsayılan devkitPro dizini dışında kurulum varsa `DEVKITPRO_WIN`, diğer sistemlerde `DEVKITPRO` ayarla. SDK en çok 20.000 dosya ve 1 GiB açılmış içerik kabul eder. Büyük oyunlarda bu sınırı baştan ölç. Tek paket sığmıyorsa sınırı aşan dosyayı üretmek yerine engeli kaydet.

Mağaza tesliminde portun `AppMarket/Store/…/<slug>/` klasöründeki gönderi kaynakları kullanılır. Yerelde üretilen `<slug>.nxvapp` adayı cihaz testi içindir. Resmi depo paketi ve kataloğu kendisi üretir. Gerçek gönderiden önce [yayın kılavuzu](../nexvyn_sdk/Publishing/PUBLISHING.md), [mağaza incelemesi](../nexvyn_sdk/Publishing/REVIEW.md) ve public Nexvyn OS kaynak ağacındaki resmi mağaza kontrolleri uygulanır. Yerelde paket oluşması, cihaz testi veya mağaza onayı anlamına gelmez.
