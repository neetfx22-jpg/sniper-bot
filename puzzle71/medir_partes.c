/* medir_partes.c -- mede quanto cada parte do engine pesa por chave, numa thread.
 * Compilar no Termux (mesmas flags do build_onda.sh):
 *   clang -O3 -march=armv8-a+crypto -flto -funroll-loops -pthread -DSHA_INTERCALADO medir_partes.c -o medir_partes -lm
 * Rodar com o engine PARADO: ./medir_partes
 */
#define main engine_main
#include "engine_salto_onda.c"
#undef main

static double agora(void) { struct timespec s; clock_gettime(CLOCK_MONOTONIC, &s); return s.tv_sec + s.tv_nsec * 1e-9; }

int main(void) {
    init_tables();
    memset(target, 0xff, 20);                       /* alvo impossivel: varre tudo sem parar */
    const int LOTES = 3000;
    const double nk = (double)LOTES * BATCH;
    u128 k; double t0;

    t0 = agora(); scan_range((u128)1 << 69, LOTES, &k, 0); double total = agora() - t0;

    uint8_t pub[4][33]; uint32_t sh[4][8]; uint8_t h[4][20];
    memset(pub, 2, sizeof pub);
    t0 = agora();
    for (long i = 0; i < (long)nk; i += 4) {
        pub[0][5] = (uint8_t)i;
#if defined(SHA_INTERCALADO) && defined(__aarch64__)
        sha256_33_x2(pub[0], pub[1], sh[0], sh[1]); sha256_33_x2(pub[2], pub[3], sh[2], sh[3]);
#else
        for (int l = 0; l < 4; l++) sha256_33(pub[l], sh[l]);
#endif
    }
    double tsha = agora() - t0;

    t0 = agora();
    for (long i = 0; i < (long)nk; i += 4) { sh[0][0] = (uint32_t)i; ripemd160_32_x4((const uint32_t (*)[8])sh, h); }
    double trip = agora() - t0;
    volatile uint8_t sink = h[0][0]; (void)sink;

    double resto = total - tsha - trip;
    printf("sha256: %s%s | 1 thread\n", SHA_IMPL, SHA_MODO);
    printf("por chave: total %.0f ns (%.2f M chaves/s por nucleo)\n", total / nk * 1e9, nk / total / 1e6);
    printf("  SHA-256        %6.0f ns  (%4.1f%%)\n", tsha / nk * 1e9, 100 * tsha / total);
    printf("  RIPEMD-160 x4  %6.0f ns  (%4.1f%%)\n", trip / nk * 1e9, 100 * trip / total);
    printf("  curva + resto  %6.0f ns  (%4.1f%%)\n", resto / nk * 1e9, 100 * resto / total);
    return 0;
}
