# Nexvyn Port SDK Rehberi

Bu belge mevcut port yardımcı başlığını anlatır. Yeni portlarda OS giriş sahipliği, sistem diyalogları ve kalıcı uygulama verisi için [public SDK’nın native port sözleşmesini](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md) kullan.

Nexvyn Port SDK (`nexvyn_port_core`), klasik PC oyunlarını ve yazılımlarını Nintendo Switch (libnx) ve modern platformlara taşırken karşılaşılan ortak zorlukları standartlaştıran C/C++ kütüphanesidir.

## Çözülen Temel Sorunlar

1. **Giriş Dönüşümü (Input Translation):**
   - Fare ve klavye gerektiren PC oyunlarına analog stick ile imleç yönetimi (`Virtual Mouse`).
   - Dokunmatik ekran girdilerini sol/sağ fare tıklamalarına ve sürüklemeye çevirme (`Touch to Mouse`).
   - Sanal klavye veya Switch yazılım klavyesi (swkbd) entegrasyonu.

2. **Görüntü ve Çözünürlük Ölçekleme:**
   - 640x480, 800x600 gibi sabit eski çözünürlüklerin Switch elde modu (720p) ve dock modu (1080p) için aspect-ratio korunarak ölçeklenmesi.

3. **Dosya Yolu ve Depolama Standartları:**
   - Dosya yollarının büyük/küçük harf duyarsızlığı (Case-sensitivity) emülasyonu.
   - Save dosyalarının `sdmc:/switch/nexvyn/<app_id>/saves` altında güvenli saklanması.

4. **Ses ve Senkronizasyon:**
   - Eski DirectSound / WinMM ses çağrılarının SDL2_mixer veya libnx hardware audio pipeline'ına yönlendirilmesi.
