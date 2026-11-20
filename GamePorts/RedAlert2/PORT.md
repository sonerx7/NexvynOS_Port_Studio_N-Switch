# Red Alert 2 / Yuri’s Revenge port kaydı

## 1.2.1

Yuri’s Revenge’in Windows x86 sürümü statik yeniden derlenir ve Switch AArch64 üzerinde Nexvyn OS native modülü olarak çalıştırılır. Launcher, bu lift’in beklediği `gamemd.exe` PE damgasını `0x3BDF544E` ile eşleştirir. Kullanıcının yerel kurulumunda bu damgaya sahip bir dosya bulundu.

| Bağımlılık | Doğrulanan kaynak |
| --- | --- |
| Nexvyn OS SDK | `7c6a0bbd2d4dd334f24a9fbbdc922904c9507fc6`, SDK 1.15 / Native 1.2 |
| pcrecomp | Yerel checkout HEAD `621860a9d22c9b25ae2be4575b956596f4ddaeeb`. Derleme checkout’unda yerel değişiklikler mevcut. |
| Derleyici | devkitA64 GCC 15.2.0 |

`PCRECOMP` pcrecomp checkout’unu, `NEXVYN_SYSROOT` Switch windowed SDL2 sysroot’unu gösterir. `bash build_nx.sh` tam derler. `bash build_nx.sh launcher` launcher nesnesini tek başına derler. `PORTSTUDIO_SDK` ile seçilen snapshot, `sdk.lock.json` ile eşleşmelidir.

Oyun açılışında içeriği bulunamadığında ana eylem klasör seçer. Uyumsuz çalıştırılabilir dosya ile eksik verinin durumları ayrıdır. Stabil video profili kontrolleri değiştirmez. Kontrol sıfırlaması ses ve video ayarlarını korur.

| Senaryo | Durum |
| --- | --- |
| Sekiz dilde söz dizimi ve anahtar bütünlüğü | SDK denetimi geçti |
| Desteklenen yerel `gamemd.exe` damgası | Başlık değeri doğrulandı (`0x3BDF544E`) |
| Gerçek Switch, dock geçişi, yeniden atama ve ekran görüntüleri | Cihaz doğrulaması bekliyor |
| Kişisel tek dosya `.nxvapp` (`_RealesedBuilds/game/redalert2/`) | CnCNet / Qt / Map Renderer eklentileri ve mükerrer dil yedekleri dışarıda bırakılarak temel `.mix` arşivleri, `gamemd.exe` ve `RA2.CSF` ile 993.062.529 byte (~947 MiB açılmış boyut < 1 GiB SDK sınırı) olarak üretildi ve doğrulandı |
| App Market mağaza adayı (`AppMarket/Store/Games/strategy/redalert2/`) | Yalnızca dağıtılabilir native modül, başlatıcı ve 8 dil dosyalarıyla (~53,2 MiB) üretildi ve doğrulandı |
