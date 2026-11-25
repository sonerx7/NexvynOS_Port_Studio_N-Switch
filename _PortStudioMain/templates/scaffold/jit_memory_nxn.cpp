// JIT code memory for a windowed Nexvyn OS module: the same JitMemory interface as the kit's emu-skeleton, built on
// nxn_jit (dual-mapped write/execute views). libnx jitCreate is not available to windowed modules.
// nxn_jit needs the user setting native.windowedJit; without it create() returns false and the core must use its
// interpreter (memory is still given, but it is NOT executable).
#include "jit_memory.h"
#include <cstdlib>
#include <nexvyn/nxn_jit.h>

static nxn_jit* g_jit = nullptr;

bool JitMemory::create(size_t bytes) {
    size = bytes;
    if (nxn_jit_create(bytes, &g_jit) == NXN_OK) {
        nxn_jit_info info = NXN_STRUCT_INIT(nxn_jit_info);
        if (nxn_jit_get(g_jit, &info) == NXN_OK) {
            rw = info.rw;
            rx = info.rx;
            size = static_cast<size_t>(info.bytes);
            real = true;
            return true;
        }
        nxn_jit_destroy(g_jit);
        g_jit = nullptr;
    }
    rw = rx = std::malloc(bytes);  // not executable: run the interpreter path
    real = false;
    return false;
}

void JitMemory::beginWrite() {
    if (real) nxn_jit_begin_write(g_jit);
}

void JitMemory::endWrite() {
    if (real) nxn_jit_end_write(g_jit, 0, size);
}

void JitMemory::destroy() {
    if (real) {
        nxn_jit_destroy(g_jit);
        g_jit = nullptr;
    } else {
        std::free(rw);
    }
    rw = rx = nullptr;
    real = false;
}
