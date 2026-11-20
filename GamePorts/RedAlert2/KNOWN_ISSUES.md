# Red Alert 2 bilinen sorunlar

## 1.2.1

- Launcher, statik yeniden derlemenin beklediği `gamemd.exe` PE damgasına göre desteklenen kurulumu kabul eder. Diğer çalıştırılabilir sürümler için ayrı motor doğrulaması gerekir.
- Eldeki ham oyun klasöründe yer alan CnCNet / Qt / Map Renderer masaüstü eklentileri ve çift dil yedekleri dahil edildiğinde 1 GiB (`1.073.741.824` byte) açılmış paket sınırı aşılır; bu nedenle kişisel tek dosya `.nxvapp` paketi (`port.json` içindeki `localData`) yalnızca motorun kullandığı temel `.mix` arşivlerini, `gamemd.exe` ve `RA2.CSF` dosyalarını (~833 MiB veri, toplam 993 MB açılmış paket) içerir. Mağaza paketinde ise kullanıcı kendi oyun klasörünü seçer.
- Gerçek donanımda dock geçişi ve yeni kontrol davranışları sürüm kabul testi bekliyor.
- Kontrol ekranı mevcut RTS eylem seçeneklerini koruyor. Her fiziksel tuşu serbestçe atamaya izin veren tam eylem tablosu bu sürümde yer almıyor.
