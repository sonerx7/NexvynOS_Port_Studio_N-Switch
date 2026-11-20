# Blender Port - Nexvyn Port Studio

Bu proje, açık kaynaklı 3D modelleme ve animasyon yazılımı **Blender**'ın taşınabilir/gömülü platformlara (özellikle Nintendo Switch mimarisine) portlanması araştırması ve prototipidir.

---

## 🎯 Port Stratejisi

- **Hedef Sürüm:** **Blender 2.79b** (Hafif, düşük RAM tüketimli C/C++ mimarisi).
  - *Neden 2.79b?* Modern Blender 4.x sürümleri Vulkan/Modern OpenGL ve en az 8-16 GB RAM gerektirir. Switch'in 4 GB toplam paylaşımlı belleği (işletim sistemi sonrası ~3.2 GB kullanılabilir) ve GLES kısıtlamaları için 2.79b mimarisi en gerçekçi ve optimize edilebilir sürümdür.
- **Pencere & Girdi Katmanı:** SDL2 (ekran, gamepad, dokunmatik ekran, sanal klavye).
- **Grafik Arka Ucu:** GLES2 / OpenGL Legacy emülasyonu (glad/deko3d veya Mesa Gallium).
- **Python Motoru:** Gömülü Python 3.5/3.6 (minimal modüller).

---

## 🕹️ Hedef Kullanım Senaryosu

- Taşınabilir 3D Model İnceleyici (3D Model Viewer / Inspector).
- Basit düşük poligonlu (low-poly) model düzenleme ve vertex tweaking.
- Render testleri ve sahne incelemeleri.
- Dokunmatik ekran ve Joy-Con analoglarıyla 3D viewport navigasyonu (Orbit, Pan, Zoom).

---

## 📁 Dizin Yapısı

- `docs/`
  - `PORT_PLAN.md`: Derleme adımları, bağımlılıklar ve GLES haritası.
- `src/`: Yama (patch) ve portlama için gerekli wrapper kodları.
