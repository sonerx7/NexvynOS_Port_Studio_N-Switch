#include <windows.h>
#include <d3d11.h>
#include <xinput.h>
// Synthetic fixture: Direct3D 11 game with a HUD.
int WINAPI WinMain(HINSTANCE h, HINSTANCE p, LPSTR c, int n) {
    HWND hwnd = CreateWindowExW(0, L"c", L"t", 0, 0, 0, 1, 1, 0, 0, h, 0);
    ID3D11Device *dev; D3D11CreateDevice(0, 0, 0, 0, 0, 0, 7, &dev, 0, 0);
    XINPUT_STATE s; XInputGetState(0, &s);
    draw_hud();
    return 0;
}
