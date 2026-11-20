# Blender Gömülü Port Planı

## Fazlar

### Faz 1: Minimal Headless Derleme
- Bağımlılıkların azaltılması (OpenColorIO, OpenImageIO, Boost kütüphanelerinin hafifletilmesi).
- devkitA64 ile ARM64 cross-compile ortamının kurulması.
- `WITH_HEADLESS=ON` seçeneği ile CLI model dönüştürücünün çalıştırılması.

### Faz 2: SDL2 & GLES2 Viewport
- GHOST (Blender'ın pencere yöneticisi) arayüzünün SDL2 backend'ine yönlendirilmesi.
- Sabit fonksiyon OpenGL çağrılarının GLES uyumlu hale getirilmesi.

### Faz 3: Giriş ve UI Uyarlaması
- `NexvynPortCore` sanal fare ve dokunmatik jestlerinin Blender arayüzüne entegrasyonu.
- Viewport navigasyonunun analog çubuklara atanması (Sol: Pan/Orbit, Sağ: Zoom).
