# Sürüm geçmişi

## 1.0.1

- Başlatıcı durumu gerçek kapsamı yansıtacak şekilde netleştirildi: paket şu anda Nexvyn OS üzerinde çalışan native başlatıcı önizlemesini ve WAD başlık doğrulayıcısını (`cstrike/cstrike.wad`, `valve/halflife.wad`) içerir; Xash3D FWGS oyun motoru henüz modüle bağlanmamıştır.
- WAD dosyaları yalnızca varlığına göre değil, gerçek `WAD2` / `WAD3` başlığına göre doğrulanır.
- Kişisel test paketi `_RealesedBuilds/game/cs16/` alt klasörüne üretilir.

## 1.0.0

- İlk Counter-Strike 1.6 native başlatıcı ve doğrulayıcı yapısı (Nexvyn OS 1.3.28-beta.2 / Native SDK 1.2 / ABI 1).
- Dear ImGui başlatıcı ve 8 dilde yerelleştirme (en, tr, de, es, fr, ja, ko, zh).
