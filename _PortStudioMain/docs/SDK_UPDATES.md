# Nexvyn SDK güncellemeleri

SDK sürümü, Native SDK sürümü ve OS sürümü farklı alanlardır. Yeniden derlenebilir bir port için public kaynak commit’ini `sdk.lock.json` içinde ve `PORT.md` dosyasında kaydet. Derleme aracını ve paketleyiciyi aynı snapshot’tan çalıştır.

```powershell
python _PortStudioMain/tools/port_studio.py doctor --json --upstream "../Nexvyn-OS-NX-pub128b"
python _PortStudioMain/tools/sync_nexvyn_sdk.py --from-checkout "<temiz public checkout>" --stage
python _PortStudioMain/tools/port_studio.py doctor --json --sdk "<aday snapshot>"
```

`doctor` yerel bir checkout ile karşılaştırır. Ağ kullanmaz. Kaynağı henüz kanıtlanmamış snapshot için commit alanı boş görünür. `sync_nexvyn_sdk.py --from-checkout "<checkout>" --record-active` etkin snapshot’ın izlenen dosyalarını karşılaştırıp eşleştiğinde kaynağı kaydeder. İki checkout’un sürüm numarası aynı olsa bile commit ve ağaç farklı olabilir.

Aday için SDK giriş araçları çalışmalı. Aynı adayla temiz native modül derlemesi, `check-win`, sekiz dil kontrolü, kişisel ve mağaza paketleri ve hedef OS cihaz testi yapılır. İçe aktarma komutunu `--stage` olmadan açıkça çalıştırmak etkin snapshot’ı değiştirir ve eski kopyayı `_SdkBackups/` altında saklar. Bir port mevcut commit’ine bağlı kaldığında `check` ve `pack` işlemlerine `--sdk "<eski snapshot>"` verilir. Port Market ve stüdyo sürüm kayıtlarına doğrulanan geçişi ekle.
