# Nexvyn Port Studio çalışma talimatları

- Her zaman Türkçe konuş. Kullanıcı istemedikçe tarayıcı açıp test etme, commit veya push yapma. Bir commit istendiğinde mesajını Türkçe yaz.
- Native Nexvyn OS uygulama ve oyunları için `start.bat` oluşturma, değiştirme veya başlatıcı olarak önerme. Bu dosya yalnızca web/HTML işleri içindir.
- Anahtar ve SSH dosyalarını silme. Kimlik bilgilerini kod, belge, log veya pakete yazma.
- “Bunu portla” isteği için [portlama kılavuzunu](_PortStudioMain/docs/INSTANT_PORT_PLAYBOOK.md) baştan sona uygula. Hedef bir oyun ise `GamePorts`, bir uygulama ise `SoftwarePorts` altında çalış. Mevcut portu sürdürüyorsan önce onun karar ve sürüm kayıtlarını oku.
- İlk iş `python _PortStudioMain/tools/port_studio.py doctor --json` çalıştır. Yerel SDK sürümünü ve kaynak commit’ini kontrol et. Manifest, derleme ve paketleme için aynı SDK snapshot’ını kullan. Aday yükseltmeleri [SDK güncelleme akışına](_PortStudioMain/docs/SDK_UPDATES.md) göre doğrula.
- İlk teslim adayı için motor ve kaynak seçeneklerini, yeniden dağıtım haklarını, SDK/ABI ve Switch sınırlarını araştır. Kararını ve kanıtını `PORT.md` dosyasına yaz. Belirsiz bir yaklaşımı küçük native prototiple sınayabilirsin. Bir engel varsa somut kanıtla kaydet ve uygulanabilir kısımları tamamla.
- Portun launcher ve kontrol tasarımı için [launcher standardını](_PortStudioMain/docs/PORT_LAUNCHER_STANDARD.md) uygula. Başka portların launcher ekranlarını kopyalama. Ortak API ve teknik desenler için yerel public SDK temel referanstır.
- Son aşamada [paketleme akışını](_PortStudioMain/docs/RELEASE_WORKFLOW.md) uygula. Kişisel veri yalnızca kişisel pakete girer. Mağaza ekran görüntülerini çalışan sürümden al. Canlı kanıt elde edilemeyen testleri ve eksik veriyi açıkça kaydet. Mağaza yayını, commit ve push kullanıcının talimatına bağlıdır.
- Teslimde seçilen yaklaşımı, SDK ve upstream commit’lerini, paket yollarını, geçen testleri ve bilinen sorunları yaz. Cihaz gözlemi, emülatör ve masaüstü denetim sonuçlarını açıkça belirt.
