/* Synthetic fixture: pure software renderer drawing sprites into a framebuffer. */
static unsigned int framebuffer[320 * 200];
static void put_pixel(int x, int y, unsigned int c) { framebuffer[y * 320 + x] = c; }
void draw_sprite(int x, int y) { put_pixel(x, y, 0xffffffu); }
int main(void) { int score = 0; draw_sprite(1, 1); return score; }
