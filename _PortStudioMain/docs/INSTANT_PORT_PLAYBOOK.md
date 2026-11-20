# “Bunu portla” çalışma kılavuzu

Hedef, mevcut oyun veya programı Nintendo Switch üzerinde Nexvyn OS’un entegre AArch64 native uygulaması olarak çalıştırmaktır. Kılavuz PC, konsol ve diğer platformlardan gelen projeler için aynı sırayı kullanır.

## 1. Hedefi ve mevcut seçenekleri araştır

Önce tam adı, hedef sürümü, sürüm varyantlarını, kaynak platformu ve beklenen asıl kullanım senaryosunu belirle. Varsa mevcut port klasörünü kullan. Yeni hedef için `port_studio.py init game <slug> <kategori>` veya `init software <slug> <kategori>` çalıştır. Kategorileri [public SDK yayın kılavuzundan](../nexvyn_sdk/Publishing/PUBLISHING.md) seç.

Birincil kaynaklara bak. Geliştiricinin kaynak deposu, lisans dosyası, sürüm notları, derleme belgeleri, çalışan upstream port ve Nexvyn SDK örneklerini incele. Her kaynak için URL, sürüm veya commit ve desteklediği bulguyu `PORT.md` içinde yaz. Ticari oyun dosyalarının kaynağını ve sürümünü kullanıcıya anlaşılır biçimde tarif et.

| Yaklaşım | Kararı verecek kanıt |
| --- | --- |
| Upstream kaynak veya açık motor | Uygun lisans, desteklenen veri sürümleri, derlenebilen AArch64 bağımlılıkları, grafik ve ses arka uçları |
| Uyumlu yeniden uygulama veya statik yeniden derleme | Doğru veri/sürüm, taşınabilir çalışma zamanı, gereken import ve özellikler için prototip sonucu, çıktıların dağıtım durumu |
| Uyumluluk katmanı veya emülasyon | Gerçek SDK desteği, performans/izin ölçümü ve kullanıcı beklentisine uygunluk. Uyumluluk çözümü olarak kaydet. |

Grafik API ve uzantıları, CPU/mimari, iş parçacığı ve bellek, giriş aygıtları, ses, dosya sistemi, ağ/TLS, DRM ve harici servisleri incele. Eksik özelliklerin kullanıcı üzerindeki etkisini yaz. Fizibilite sonucunu `uygun`, `kısıtlı` veya `engelli` olarak gerekçelendir. Belirsiz import, render veya veri açma davranışı kararı etkiliyorsa küçük bir native prototiple sınayıp sonucu kaydet. DRM ve lisans doğrulama mekanizmalarını koru.

## 2. SDK’yı sabitle ve çalışan çekirdeği üret

- Ortak [public SDK](../nexvyn_sdk/README.md) içindeki [native port](../nexvyn_sdk/Guides/PORT_AND_LAUNCHER.md), [girdi](../nexvyn_sdk/Guides/INPUT_CONTRACT.md), [uyumluluk](../nexvyn_sdk/Guides/COMPATIBILITY.md), [kalite](../nexvyn_sdk/Guides/PRODUCT_QUALITY.md) ve [çeviri](../nexvyn_sdk/Guides/LOCALIZATION_CONTRACT.md) belgelerini oku.
- İlk derlemeyi [Switch native derleme adımlarından](CROSS_COMPILATION_CHEATSHEET.md) başlat.
- Upstream commit, SDK snapshot, derleyici sürümü, build komutları, native ABI, minimum ve hedef SDK/OS sürümlerini kaydet. Ortak SDK’yı kullan, yerel yolları değişkenlerle ver. Sahiplik ve lisans bilgilerini `DISTRIBUTION.md` içine yaz.
- İlk çalışan dilim veri açıp gerçek bir sahne veya uygulamanın ana işini çalıştırmalı, sonra kaynakları bırakıp masaüstüne dönmeli. Gerçek SDK import’larını ve isteğe bağlı kabiliyetleri kontrol et. Kısıtlı fonksiyon için açık durum bilgisi ve mümkünse geri dönüş ekle.
- Paket kaynaklarından kullanıcı verisini ayır. Oyuncunun seçtiği klasör dışındaki yolları tarama. Desteklenen sürümü, zorunlu dosyaları ve kullanıcıya gösterilecek hata nedenlerini belirle. Kayıt ve profil dosyalarını uygulamanın kalıcı veri alanında tut.

## 3. Hedefe özel deneyimi tamamla

[Launcher standardını](PORT_LAUNCHER_STANDARD.md) uygula. Önce oyuna veya programa özgü eylemleri ve gerçekten değiştirilebilen seçenekleri çıkar, sonra ekranı tasarla. Varsayılanlar, handheld ve dock profilleri, giriş şeması, yeniden atamalar, kullanıcı verisinin bulunması ve kalıcı ayarlar aynı uygulama akışında beraber çalışmalı. Kod ve test yükünü ölçerek önce temel kullanım yolunu tamamla.

## 4. Test et ve kanıt topla

| Senaryo | Kaydedilecek sonuç |
| --- | --- |
| İlk açılış, eksik/yanlış veri, yeniden seçme, iptal | Sürüm doğrulaması, anlaşılır hata, menüye veya masaüstüne güvenli dönüş |
| Gerçek oyun sahnesi veya uygulama işi | Yükleme süresi, yoğun sahnede kare süresi/performans, tepe bellek, ses ve grafik doğruluğu |
| Handheld → dock → handheld ve pencere değişimi | Çözünürlük, render ölçeği, oran, netlik ve dokunma koordinatları. Oyunun durumunu koru. |
| Gamepad, dokunmatik, klavye/fare ve yeniden atama | Menü ve gerçek kullanım, aygıt geçişi, odak kaybı, takılı kalan giriş, ayarların kalıcılığı |
| Askıya al/devam, kapat/yeniden aç, güncelle | Ses ve giriş yakalama temizliği, kayıtların korunması, uzun çalışmada kaynak kullanımı |
| Yerelleştirme | Sekiz dilde launcher, ayarlar ve hata metinleri. Uzun metin, CJK ve gerçek ekran yerleşimi. |

Her test için cihaz/emülatör ve sürüm, paket sürümü, girdi/veri varyantı ve sonucu `PORT.md` içine yaz. Fiziksel Switch gözlemini emülatör sonucundan ayır. Testi yapamadıysan ve SDK denetimi geçtiyse iki sonucu da açıkça yaz.

## 5. İki çıktıyı ve mağaza gönderisini hazırla

[Yayın akışı](RELEASE_WORKFLOW.md) kişisel tek dosyayı, temiz mağaza paketini, mağaza ekran görüntülerini ve sürüm kayıtlarını tanımlar. Beklenen çıktıların konumlarını, doğrulama sonuçlarını ve kalan bilinen sorunları teslimde belirt.
