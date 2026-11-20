# Nexvyn OS native port launcher standardı

Launcher, kullanıcıyı içeriğini tanıtarak oyunun veya programın ana işine ulaştırır. Bir RTS için sürüm/kampanya, kamera ve fare davranışı öne çıkar. Bir FPS için içerik, hassasiyet ve nişan ayarları öne çıkar. Bir 3D düzenleyici için belge açma, son dosyalar ve görünüm kontrolleri öne çıkar. Ek ayara ihtiyaç duymadan başlayabilen port açılışta doğrudan ana deneyimi gösterebilir. Ayarlar ve içerik seçimi içeriden erişilebilir kalır.

## Ekranı gerçek iş akışına göre tasarla

1. İlk açılışta desteklenen veri sürümlerini ve gereken ana dosyaları göster. Sistem klasör/dosya seçicisini kullan. Seçimin durumunu göster, eksik ve uyumsuz dosyaları isimlendir ve tekrar seçmeyi mümkün kıl. Kişisel paketin gömülü verisini tanı ve hazır durumda aç.
2. Tek bir ana eylem kullan. Oyunda Oyna/Devam Et, uygulamada son belgeyi aç ya da yeni belge oluştur gibi. Ayarlar, kontroller ve yardım erişilebilir olsun. Son seçim ve profili hatırla. Başlatma sırasında gerçek yükleme evrelerini, hata ve iptal yollarını göster.
3. Yalnızca motor veya Nexvyn OS üzerinde etkisi olan ayarları göster. Bir seçenek için varsayılanı, izin verilen aralığı, canlı uygulanıp uygulanmadığını, nasıl saklandığını ve testini kaydet. Seçenek koşulluysa sebebini kullanıcıya söyle. Video ayarlarında geri dönüş, ayar sıfırlama ve makul varsayılanlar sun.
4. Nexvyn OS tema/görünüm tokenlarını, odak dolaşımını, pencere davranışını, sistem diyaloglarını ve gerektiğinde ekran klavyesini kullan. Launcher, yükleme, hata, yardım ve ayarlar dahil görünen bütün metinleri SDK’nın sekiz diliyle tamamla.

## Handheld, dock ve pencere geçişleri

Otomatik profil varsayılanı portun ölçümleriyle desteklenmeli. 720p handheld / 1080p dock çıkışını hedef olarak değerlendir. İç render çözünürlüğünü, kare hızı sınırını ve ölçeklemeyi motorun ölçülen performansına göre seç. “Otomatik” durumunda geçerli profili göster. Kullanıcıya desteklenen manuel geçişleri ver. SDK ekran/resize ve kullanılabilir sistem durum olaylarını kullan. Viewport, eşleştirilmiş giriş koordinatları, oran ve HUD aynı geçişte güncellensin. Dock/undock, fullscreen/pencere ve askıya alma işlerinde aynı oyun oturumunu veya belgeyi koru. Yeniden başlatma gerektiren seçenekleri uygulamadan önce belirt.

## Kontrol şeması ve özelleştirme

Önce `seç`, `iptal`, `kamera`, `nişan`, `etkileşim` gibi oyuna özgü anlamlı eylemleri tanımla. Sonra gamepad, dokunmatik ve fiziksel klavye/fare için eylem tablosu çıkar. Touch tasarımında doğrudan dokunma ile sanal imleç farkını belirle. Eşzamanlı eylemler gerekiyorsa gerçek çoklu dokunma kullan. Gamepad menüyü ve ana işi tamamlayabilmeli. Analog deadzone, hızlanma, hassasiyet, titreşim ve eksen ters çevirme gibi seçenekleri yalnızca uygulandıkları portlarda sun.

İşlevsel varsayılan şema, eylem bazında yeniden atama, çakışma ve ayrılmış tuş bildirimi, tek eylem ve profil sıfırlama, ekranda güncel tuş göstergeleri ve sürümlü ayar kaydı sun. Girdi akışının tek sahibi olmalı. Odak kaybı, sistem diyalogu, cihaz ayrılması veya suspend sırasında basılı tuş/temas durumunu temizle. Klavye/fare yakalamayı giriş gerektiren bağlamlar dışında bırak.

## Red Alert 2’den alınacak somut dersler

- [Mevcut launcher](../../GamePorts/RedAlert2/src/nx/launcher.cpp) veri doğrulaması, kalıcı profil, dock çözünürlük seçimi, oyun dilinin ve modların üst katmanla uygulanması için referans kod içeriyor. Kullanıcının özgün dosyasını değiştirmeden ayar ve ekleri ayrı katmanda tutma yaklaşımı diğer portlara uyarlanabilir.
- RTS’ye özgü seçimleri ve durumu öne çıkar. Profil, gelişmiş video seçeneklerini gerçekten etkilediğinde hangi ayarların neden sabitlendiğini göster. İçerik/çeviri/yama dağıtımı için ayrı kaynak ve izin kaydı tut.
- [Tarihsel teknik notlar](RA2_LAUNCHER_REFERENCE.md) RA2 uygulamasına özgü örnekler içerir. Bağlayıcı API, yaşam döngüsü ve girdi davranışı için [public SDK port rehberine](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md) dön.
