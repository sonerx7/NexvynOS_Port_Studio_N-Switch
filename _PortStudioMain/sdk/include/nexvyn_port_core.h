/**
 * @file nexvyn_port_core.h
 * @brief Nexvyn Port Studio Core SDK - Ortak C/C++ Yardımcı Kütüphanesi
 * 
 * Klasik PC oyunları ve uygulamalarının konsola ve modern platformlara
 * taşınmasında ortak fare emülasyonu, dokunmatik kontroller, çözünürlük ölçekleme
 * ve gamepad eşleştirme arayüzünü sağlar.
 */

#ifndef NEXVYN_PORT_CORE_H
#define NEXVYN_PORT_CORE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* --- Sanal Fare Yapısı --- */
typedef struct {
    float x;
    float y;
    float speed;
    float deadzone;
    bool left_button;
    bool right_button;
    bool middle_button;
} NexvynVirtualMouse;

/* --- Ekran Ölçekleme Yapısı --- */
typedef struct {
    int native_width;
    int native_height;
    int target_width;
    int target_height;
    int viewport_x;
    int viewport_y;
    int viewport_w;
    int viewport_h;
    float scale_factor;
} NexvynScreenScaler;

/* --- Sanal Fare Güncelleme --- */
static inline void Nexvyn_UpdateVirtualMouse(NexvynVirtualMouse* mouse, float stick_x, float stick_y, float dt, int max_w, int max_h) {
    if (!mouse) return;
    if (stick_x > mouse->deadzone || stick_x < -mouse->deadzone) {
        mouse->x += stick_x * mouse->speed * dt;
    }
    if (stick_y > mouse->deadzone || stick_y < -mouse->deadzone) {
        mouse->y += stick_y * mouse->speed * dt;
    }
    if (mouse->x < 0) mouse->x = 0;
    if (mouse->y < 0) mouse->y = 0;
    if (mouse->x >= max_w) mouse->x = (float)(max_w - 1);
    if (mouse->y >= max_h) mouse->y = (float)(max_h - 1);
}

/* --- Aspect Ratio Koruyarak Viewport Hesaplama --- */
static inline void Nexvyn_CalculateAspectViewport(NexvynScreenScaler* scaler) {
    if (!scaler || scaler->native_width <= 0 || scaler->native_height <= 0) return;
    
    float ratio_x = (float)scaler->target_width / (float)scaler->native_width;
    float ratio_y = (float)scaler->target_height / (float)scaler->native_height;
    scaler->scale_factor = (ratio_x < ratio_y) ? ratio_x : ratio_y;

    scaler->viewport_w = (int)(scaler->native_width * scaler->scale_factor);
    scaler->viewport_h = (int)(scaler->native_height * scaler->scale_factor);
    scaler->viewport_x = (scaler->target_width - scaler->viewport_w) / 2;
    scaler->viewport_y = (scaler->target_height - scaler->viewport_h) / 2;
}

#ifdef __cplusplus
}
#endif

#endif /* NEXVYN_PORT_CORE_H */
