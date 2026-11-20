# Diablo 1 Port - Nexvyn Port Studio

Bu proje, Blizzard'ın efsanevi aksiyon RPG'si **Diablo 1** (ve genişleme paketi Hellfire) oyununun Nintendo Switch ve modern gömülü platformlara taşınması projesidir.

---

## 🎯 Port Yaklaşımı & Motor Seçimi

- **Motor:** **DevilutionX** (Diablo 1'in tersine mühendislikle yeniden yazılmış, orijinal oyun mantığını %100 koruyan açık kaynaklı C++ motoru).
- **Varlıklar:** Orijinal `DIABDAT.MPQ` dosyası (kullanıcı tarafından sağlanır; shareware/demo `spawn.mpq` desteği ile test edilebilir).
- **Grafik & Ekran:** 640x480 orijinal çözünürlük yerine Switch'in 720p/1080p ekranına tam uyumlu geniş ekran (Widescreen) ve 60 FPS desteği.

---

## 🕹️ Hedef Özellikler

- **Modern Gamepad Kontrolleri:** Doğrudan karakter yönlendirme, analog çubuk ile hedef seçimi, hızlı yetenek atamaları.
- **Dokunmatik Arayüz:** Envanter yönetimi, büyü kitabı ve eşya kuşanma için tam dokunmatik ekran kullanımı.
- **Otomatik Altın Toplama & Koşma:** Modern yaşam kalitesi (QoL) iyileştirmeleri.
- **Çok Oyunculu:** TCP/IP ve ZeroTier entegrasyonu ile yerel ağ veya internet üzerinden co-op zindan keşfi.

---

## 📁 Dizin Yapısı

- `docs/`
  - `ARCHITECTURE.md`: DevilutionX derleme ve libnx entegrasyon detayları.
- `data/`: `DIABDAT.MPQ` veya `spawn.mpq` dosyalarının yerleşeceği dizin.
- `saves/`: Karakter ve ilerleme kayıtları.
