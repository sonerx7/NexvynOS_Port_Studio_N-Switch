# Nexvyn Port Studio

Nexvyn Port Studio, PC ve diğer platformlar için geliştirilmiş oyunları ve uygulamaları Nintendo Switch üzerinde **Nexvyn OS native** deneyimine dönüştürmek için kullanılan portlama çalışma alanı. Fizibiliteyi araştırır, uygun motoru ve SDK yolunu belirler, oyuna veya programa özel launcher ve kontrolleri tasarlar ve aynı porttan iki farklı kurulum paketi üretir.

| Dizin | İşlev |
| --- | --- |
| `GamePorts/` | Bağımsız oyun portları |
| `SoftwarePorts/` | Bağımsız yazılım portları |
| [`_PortStudioMain/`](_PortStudioMain/README.md) | Public SDK, ortak araçlar, şablonlar ve çalışma kılavuzları |
| `_RealesedBuilds/game/` ve `_RealesedBuilds/software/` | Oyun veya uygulama verisini içeren, yalnızca kişisel test için üretilmiş tek dosya paketleri |
| `<port>/AppMarket/Store/` | Portun mağaza kaynakları, ekran görüntüleri ve test edilebilir mağaza paketi |

## Bir port başlat

Python 3.10 ve üzeri ile depo kökünden çalıştır:

```powershell
python _PortStudioMain/tools/port_inspector.py
python _PortStudioMain/tools/port_studio.py init game ornek-oyun strategy
python _PortStudioMain/tools/port_studio.py init software ornek-arac utilities
```

- [Portlama kılavuzu](_PortStudioMain/docs/INSTANT_PORT_PLAYBOOK.md) araştırma ve fizibiliteden cihaz testine kadar izlenecek sırayı verir. [AGENTS.md](AGENTS.md) aynı iş akışını kodlama ajanlarına aktarır.
- [Launcher standardı](_PortStudioMain/docs/PORT_LAUNCHER_STANDARD.md) hedefe özel ayarlar, dock/handheld geçişleri, gamepad, dokunmatik, klavye/fare ve kontrolcü yeniden atamaları için kabul ölçütlerini tanımlar.
- [Yayın akışı](_PortStudioMain/docs/RELEASE_WORKFLOW.md) kişisel ve mağaza paketlerini, sürüm geçmişini, bilinen sorunları ve gerçek ekran görüntülerini açıklar.
- [Port Market](_PortStudioMain/docs/PORT_MARKET.md) SD kitaplığını ve seçtiğin Internet Archive öğelerini Nexvyn OS üzerinde gösterir. Paket ve kişisel katalog çıktıları Git dışında tutulur.
- [SDK güncellemeleri](_PortStudioMain/docs/SDK_UPDATES.md) yerel tanı, aday sürüm ve port bazında SDK sabitlemesini açıklar.

[Red Alert 2 / Yuri’s Revenge](GamePorts/RedAlert2/ILERLEME.md) mevcut referans uygulama. Counter-Strike 1.6, Diablo 1 ve Blender için başlangıç araştırmaları kendi klasörlerinde bulunur.
