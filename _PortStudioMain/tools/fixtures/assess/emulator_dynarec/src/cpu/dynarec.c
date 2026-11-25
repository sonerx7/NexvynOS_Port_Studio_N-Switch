#include <sys/mman.h>
/* Synthetic fixture: dynarec block cache that executes generated code. */
void *alloc_block(unsigned long size) { return mmap(0, size, PROT_READ | PROT_WRITE | PROT_EXEC, 0, -1, 0); }
int cpu_step(unsigned char opcode) { return opcode; }
