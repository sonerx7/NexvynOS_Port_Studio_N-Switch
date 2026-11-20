# Nexvyn Port Studio ortak çalışma alanı

- [Portlama kılavuzu](docs/INSTANT_PORT_PLAYBOOK.md) araştırma, fizibilite, native çekirdek ve kabul testlerinin sırasını belirler.
- [Launcher standardı](docs/PORT_LAUNCHER_STANDARD.md) portun kendi ayarları, girdi ve görünüm davranışını tanımlar. [Red Alert 2 notları](docs/RA2_LAUNCHER_REFERENCE.md) uygulama deneyimini korur.
- [Yayın akışı](docs/RELEASE_WORKFLOW.md) kişisel ve mağaza paketlerini üretir. [Şablonlar](templates) port dosyası, dağıtım kaynakları, sürüm geçmişi ve bilinen sorunları başlatır.
- [Port yardımcı başlığı](sdk/include/nexvyn_port_core.h) ve [rehberi](docs/SDK_GUIDE.md) eski portlarda kullanılan ortak C/C++ yardımcılarını açıklıyor. OS API ve davranışı için public SDK esas alınır.

## Public Nexvyn OS SDK

[`nexvyn_sdk/`](nexvyn_sdk/README.md), Nexvyn OS public kaynak deposunun `SDK/` ağacından alınan yerel snapshot. [VERSION.json](nexvyn_sdk/VERSION.json) mevcut OS, SDK, Native SDK ve dil sözleşmesini kaydeder. Paketleme araçları bu snapshot’ı kullanır. Portların kullandığı upstream ve SDK revizyonunu `PORT.md` içinde kaydet.

SDK güncellemesi için kullanıcının sağladığı temiz public kaynak checkout’unu kullan:

```powershell
python _PortStudioMain/tools/sync_nexvyn_sdk.py --from-checkout "<Nexvyn-OS-NX checkout>"
```

Araç SDK ağacını denetler, kaynağın commit kimliğini yazar ve önceki snapshot’ı Git dışındaki `_SdkBackups/` altında saklar. Güncelleme port klasörlerini değiştirmez.
