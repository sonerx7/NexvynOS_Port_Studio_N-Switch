# Gelecek Yazılım Portu Şablonu (SoftwarePorts/XX)

Bu klasör, Nexvyn Port Studio bünyesine eklenecek yeni PC yazılımları, üretkenlik araçları veya emülatörler için standart şablon alanıdır.

---

## 🚀 Yeni Bir Yazılım Portu Başlatırken İzlenecek Adımlar:

1. Bu klasörü çoğaltın ve hedef yazılımın adını verin (örn. `SoftwarePorts/DosBox-X`).
2. `docs/ARCHITECTURE.md` oluşturarak bellek, ekran, mimari kısıtlarını tanımlayın.
3. `_PortStudioMain/sdk/include/nexvyn_port_core.h` kütüphanesini dahil ederek sanal fare ve ekran ölçekleyiciyi bağlayın.
4. Yazılımın bağımsız kaynak kodlarını `src/` altına yerleştirin.
5. Varsa başlatıcı veya yapılandırma dosyalarını `config/` altına ekleyin.
