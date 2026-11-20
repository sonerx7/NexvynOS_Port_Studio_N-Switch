# Nintendo Switch üzerinde Nexvyn OS native derleme

Public SDK’nın [native kit rehberini](../nexvyn_sdk/Guides/NATIVE_KIT.md) ve [araç zinciri kurulumunu](../nexvyn_sdk/Languages/c/native-kit/README.md) izle. Entegre portun çıktısı AArch64 ELF `.nxvmod` modülü. Pencere veya fullscreen davranışı manifestte ve motorun yaşam döngüsünde tanımlanır.

Depo kökünden temel akış:

```powershell
$nativeKit = "_PortStudioMain/nexvyn_sdk/Languages/c/native-kit"
python "$nativeKit/tools/nxv_native" doctor
python "$nativeKit/tools/nxv_native" new motor-prototip --template port --dir "GamePorts/ornek-oyun"
python "$nativeKit/tools/nxv_native" build "GamePorts/ornek-oyun/motor-prototip"
python "$nativeKit/tools/nxv_native" check-win "<derlenen .nxvmod dosyası>"
```

Kendi CMake entegrasyonunda bu şablondaki Nexvyn toolchain ve modül hedefini kullan. Bahsedilen örnek şablon yeni port çekirdeği içindir. Mevcut port için kendi derleme sistemini ve bağımlılıklarını incele. Windows’ta devkitPro standart dışı bir dizindeyse `DEVKITPRO_WIN`, diğer sistemlerde `DEVKITPRO` kullan. Dış bağımlılık ve sysroot yollarını yapılandırılabilir tut. Portun yeniden üretilebilir build komutunu ve bağımlılık sürümlerini `PORT.md` içine yaz.

- Dosya sürümlerini ve büyük/küçük harf davranışını hedefte doğrula. Kullanıcı verisinin adını veya içeriğini değiştirmeden güvenli eşleştir.
- x86’dan gelen serileştirme kodunda hizalama, erişim ve endian varsayımlarını açıkça sınayıp düzelt. Grafik, ses ve sistem API’lerinin çalışma davranışını ilk prototipte doğrula.
- Native modül kimliği, relocation ve import kontrolleri geçince modülü [yayın çalışma akışındaki](RELEASE_WORKFLOW.md) `source/` klasörüne yerleştir.
