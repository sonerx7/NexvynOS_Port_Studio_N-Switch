# Port Market 0.2.1 beta

Port Market, seçtiğin Internet Archive öğelerini açılışta ve açıkken beş dakikada bir kontrol eder. Öğenin ayrıntı adresini veya kimliğini **Arşiv öğesi ekle** düğmesiyle bir kez kaydet. Yeni `.nxvapp` dosyaları en yeni yükleme önce sıralanır. **İndir** düğmesi SDK üzerinden ilerlemeyi gösterir ve doğru boyutta tamamlanan dosyayı uygulamanın özel alanına alır. **Kurulum ekranını aç**, Nexvyn OS paket incelemesine geçer. Takip listesi ve indirmeler cihazdaki kullanıcı profiline aittir.

**Yerel** sekmesi ayrıca SD karttaki kişisel stüdyo kataloğunu (`game/<port>/` ve `software/<port>/` alt klasörleriyle birlikte) açabilir:

```powershell
python _PortStudioMain/tools/port_market.py catalog
```

Üretilen `_RealesedBuilds/port-market.tsv` ve yanındaki `game/`, `software/` klasörlerini aynı dizin yapısıyla SD karta kopyala. Uygulamadan üst klasörü seç. Beta paketi herhangi bir kişisel katalog, oyun dosyası veya hesap bilgisi taşımaz. Game ve software paketlerinin yanı sıra arşiv hazırlığı da `_RealesedBuilds/` altında Git dışında tutulur.

## Internet Archive hazırlığı

Dağıtım hakkı kayıtlı bir portun paketini oluştur, sonra sürümün arşiv dosyalarını hazırla. Portu ve beraberindeki bütün veriyi dağıtabilme hakkı kayda geçtiyse `port.json` içinde `archiveFullData: true` kullan ve `--full-package` ekle. Bu çağrı ilgili kişisel sürüm paketini alır.

```powershell
python _PortStudioMain/tools/port_market.py prepare-archive "GamePorts/ornek" --item "ornek-nexvyn-port" --license MIT --output "_RealesedBuilds/archive/ornek"
```

Hazırlık komutu paket içeriğini onaylı `source/` ve varsa yerel veri eşlemesiyle karşılaştırır. Arşiv dizinine sürüm etiketli paketi, yükleme metadatasını ve dağıtım kaydını üretir. Aynı Internet Archive öğesine sonraki sürümü yeni dosya adıyla yüklediğinde Port Market bunu kendiliğinden görür. Arşiv öğesine erişim Internet Archive ayrıntı sayfasındaki erişim koşullarına bağlıdır.

SDK tek `.nxvapp` için açılmış içerikte 1 GiB (`1.073.741.824` byte) sınırı uygular. Red Alert 2’nin kişisel kurulumu için `port.json` içindeki `localData` listesi, motorun çalıştığı temel `.mix` arşivlerini, `gamemd.exe` ve `RA2.CSF` dosyalarını (~833 MiB veri + ~160 MiB modül = ~947 MiB açılmış boyut < 1 GiB) seçerek `_RealesedBuilds/game/redalert2/` altında geçerli tek dosya `.nxvapp` (~503,5 MiB) üretir.

## Yerel beta paketi

```powershell
python _PortStudioMain/tools/build_port_market_beta.py --checkout "../Nexvyn-OS-NX" --checker-checkout "../SnxOS-NX" --install-local
```

Resmî mağaza aracı Port Market kaydını üretir. `--install-local` yerel Nexvyn OS checkout’undaki beta girdisini günceller. Oluşan paket ayrıca uygulamanın `build/beta-0.2.1/` klasöründe bulunur.
