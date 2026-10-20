// engine_salto_onda.c -- engine_salto_final + modo "onda" (franjas de interferencia da dupla fenda)
// Base: engine.c -- varredura sequencial secp256k1 -> hash160 (projeto p71b, independente)
// Soma de pontos com INVERSAO EM LOTE (truque de Montgomery), SHA-256/RIPEMD-160 proprios.
// Sem dependencias externas. Compilar: clang -O3 -pthread engine.c -o engine
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <math.h>

typedef unsigned __int128 u128;
typedef struct { uint64_t d[4]; } fe;           // inteiro mod p, little-endian
typedef struct { fe x, y; } pt;                 // ponto afim
static const uint64_t CC = 0x1000003D1ULL;      // 2^256 mod p

/* ---------------- campo F_p ---------------- */
static inline uint64_t add_c(uint64_t t[4]) {
    u128 a = (u128)t[0] + CC; t[0] = (uint64_t)a; a >>= 64;
    for (int i = 1; i < 4; i++) { a += t[i]; t[i] = (uint64_t)a; a >>= 64; }
    return (uint64_t)a;
}
static inline uint64_t sub_c(uint64_t t[4]) {
    uint64_t x = t[0]; t[0] = x - CC; uint64_t b = x < CC;
    for (int i = 1; i < 4; i++) { x = t[i]; t[i] = x - b; b = x < b; }
    return b;
}
static inline void fe_add(fe *r, const fe *a, const fe *b) {
    u128 acc = 0; uint64_t t[4];
    for (int i = 0; i < 4; i++) { acc += (u128)a->d[i] + b->d[i]; t[i] = (uint64_t)acc; acc >>= 64; }
    uint64_t c = (uint64_t)acc;
    while (c) c = add_c(t);
    memcpy(r->d, t, 32);
}
static inline void fe_sub(fe *r, const fe *a, const fe *b) {
    uint64_t t[4]; uint64_t br = 0;
    for (int i = 0; i < 4; i++) {
        uint64_t x = a->d[i], y = b->d[i];
        uint64_t s = x - y; uint64_t b1 = x < y;
        uint64_t s2 = s - br; uint64_t b2 = s < br;
        t[i] = s2; br = b1 | b2;
    }
    while (br) br = sub_c(t);
    memcpy(r->d, t, 32);
}
static inline void fe_mul(fe *r, const fe *a, const fe *b) {
    uint64_t t[8]; u128 acc;
    for (int i = 0; i < 8; i++) t[i] = 0;
    for (int i = 0; i < 4; i++) {
        uint64_t carry = 0;
        for (int j = 0; j < 4; j++) {
            acc = (u128)a->d[i] * b->d[j] + t[i + j] + carry;
            t[i + j] = (uint64_t)acc; carry = (uint64_t)(acc >> 64);
        }
        t[i + 4] = carry;
    }
    uint64_t s[5]; acc = 0;
    for (int i = 0; i < 4; i++) { acc += (u128)t[4 + i] * CC + t[i]; s[i] = (uint64_t)acc; acc >>= 64; }
    s[4] = (uint64_t)acc;
    acc = (u128)s[4] * CC + s[0]; s[0] = (uint64_t)acc; acc >>= 64;
    for (int i = 1; i < 4; i++) { acc += s[i]; s[i] = (uint64_t)acc; acc >>= 64; }
    if (acc) add_c(s);
    memcpy(r->d, s, 32);
}
static inline void fe_sqr(fe *r, const fe *a) { fe_mul(r, a, a); }
static inline void fe_norm(fe *a) {
    uint64_t t[4]; memcpy(t, a->d, 32);
    if (add_c(t)) memcpy(a->d, t, 32);
}
static int fe_eq(const fe *a, const fe *b) {
    fe x = *a, y = *b; fe_norm(&x); fe_norm(&y);
    return memcmp(x.d, y.d, 32) == 0;
}
static void fe_inv(fe *r, const fe *a) {        // a^(p-2)
    static const uint64_t e[4] = {0xFFFFFFFEFFFFFC2DULL, ~0ULL, ~0ULL, ~0ULL};
    fe res = {{1, 0, 0, 0}}, base = *a;
    for (int i = 255; i >= 0; i--) {
        fe_sqr(&res, &res);
        if ((e[i >> 6] >> (i & 63)) & 1) fe_mul(&res, &res, &base);
    }
    *r = res;
}

/* ---------------- pontos (so usados na inicializacao e no passo de centro) ---------------- */
static const pt GEN = {
    {{0x59F2815B16F81798ULL, 0x029BFCDB2DCE28D9ULL, 0x55A06295CE870B07ULL, 0x79BE667EF9DCBBACULL}},
    {{0x9C47D08FFB10D4B8ULL, 0xFD17B448A6855419ULL, 0x5DA4FBFC0E1108A8ULL, 0x483ADA7726A3C465ULL}}};

static void pt_add(pt *r, const pt *a, const pt *b) {
    fe l, t1, t2, x3, y3;
    if (fe_eq(&a->x, &b->x)) {
        fe_sqr(&t1, &a->x); fe_add(&t2, &t1, &t1); fe_add(&t1, &t2, &t1);
        fe_add(&t2, &a->y, &a->y); fe_inv(&t2, &t2); fe_mul(&l, &t1, &t2);
    } else {
        fe_sub(&t1, &b->y, &a->y); fe_sub(&t2, &b->x, &a->x);
        fe_inv(&t2, &t2); fe_mul(&l, &t1, &t2);
    }
    fe_sqr(&x3, &l); fe_sub(&x3, &x3, &a->x); fe_sub(&x3, &x3, &b->x);
    fe_sub(&t1, &a->x, &x3); fe_mul(&y3, &l, &t1); fe_sub(&y3, &y3, &a->y);
    r->x = x3; r->y = y3;
}
static void pt_mul(pt *r, u128 k) {             // k >= 1
    pt acc = GEN, base = GEN; int have = 0;
    while (k) {
        if (k & 1) { if (!have) { acc = base; have = 1; } else pt_add(&acc, &acc, &base); }
        k >>= 1;
        if (k) pt_add(&base, &base, &base);
    }
    *r = acc;
}

/* ---------------- SHA-256 (1 bloco, msg de 33 bytes) ---------------- */
static const uint32_t K256[64] = { 0x428a2f98u,0x71374491u,0xb5c0fbcfu,0xe9b5dba5u,0x3956c25bu,0x59f111f1u,0x923f82a4u,0xab1c5ed5u,0xd807aa98u,0x12835b01u,0x243185beu,0x550c7dc3u,0x72be5d74u,0x80deb1feu,0x9bdc06a7u,0xc19bf174u,0xe49b69c1u,0xefbe4786u,0x0fc19dc6u,0x240ca1ccu,0x2de92c6fu,0x4a7484aau,0x5cb0a9dcu,0x76f988dau,0x983e5152u,0xa831c66du,0xb00327c8u,0xbf597fc7u,0xc6e00bf3u,0xd5a79147u,0x06ca6351u,0x14292967u,0x27b70a85u,0x2e1b2138u,0x4d2c6dfcu,0x53380d13u,0x650a7354u,0x766a0abbu,0x81c2c92eu,0x92722c85u,0xa2bfe8a1u,0xa81a664bu,0xc24b8b70u,0xc76c51a3u,0xd192e819u,0xd6990624u,0xf40e3585u,0x106aa070u,0x19a4c116u,0x1e376c08u,0x2748774cu,0x34b0bcb5u,0x391c0cb3u,0x4ed8aa4au,0x5b9cca4fu,0x682e6ff3u,0x748f82eeu,0x78a5636fu,0x84c87814u,0x8cc70208u,0x90befffau,0xa4506cebu,0xbef9a3f7u,0xc67178f2u };
static const uint32_t H256[8] = { 0x6a09e667u,0xbb67ae85u,0x3c6ef372u,0xa54ff53au,0x510e527fu,0x9b05688cu,0x1f83d9abu,0x5be0cd19u };
static inline uint32_t ror(uint32_t x, int n) { return (x >> n) | (x << (32 - n)); }
static inline uint32_t rol(uint32_t x, int n) { return (x << n) | (x >> (32 - n)); }
#if defined(__aarch64__) && defined(__ARM_FEATURE_CRYPTO)
#include <arm_neon.h>
static void sha256_33(const uint8_t *m, uint32_t out[8]) {
    uint32_t w[16];
    for (int i = 0; i < 8; i++)
        w[i] = ((uint32_t)m[4*i] << 24) | ((uint32_t)m[4*i+1] << 16) | ((uint32_t)m[4*i+2] << 8) | m[4*i+3];
    w[8] = ((uint32_t)m[32] << 24) | 0x00800000u;
    for (int i = 9; i < 15; i++) w[i] = 0;
    w[15] = 264;

    uint32x4_t STATE0 = vld1q_u32(&H256[0]);
    uint32x4_t STATE1 = vld1q_u32(&H256[4]);
    uint32x4_t ABEF_SAVE = STATE0, CDGH_SAVE = STATE1;
    uint32x4_t MSG0 = vld1q_u32(&w[0]);
    uint32x4_t MSG1 = vld1q_u32(&w[4]);
    uint32x4_t MSG2 = vld1q_u32(&w[8]);
    uint32x4_t MSG3 = vld1q_u32(&w[12]);
    uint32x4_t TMP0, TMP1, TMP2;

    TMP0 = vaddq_u32(MSG0, vld1q_u32(&K256[0]));

    /* G0: rounds 0-3 */
    MSG0 = vsha256su0q_u32(MSG0, MSG1);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG1, vld1q_u32(&K256[4]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG0 = vsha256su1q_u32(MSG0, MSG2, MSG3);
    /* G1: rounds 4-7 */
    MSG1 = vsha256su0q_u32(MSG1, MSG2);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG2, vld1q_u32(&K256[8]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG1 = vsha256su1q_u32(MSG1, MSG3, MSG0);
    /* G2: rounds 8-11 */
    MSG2 = vsha256su0q_u32(MSG2, MSG3);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG3, vld1q_u32(&K256[12]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG2 = vsha256su1q_u32(MSG2, MSG0, MSG1);
    /* G3: rounds 12-15 */
    MSG3 = vsha256su0q_u32(MSG3, MSG0);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG0, vld1q_u32(&K256[16]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG3 = vsha256su1q_u32(MSG3, MSG1, MSG2);
    /* G4: rounds 16-19 */
    MSG0 = vsha256su0q_u32(MSG0, MSG1);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG1, vld1q_u32(&K256[20]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG0 = vsha256su1q_u32(MSG0, MSG2, MSG3);
    /* G5: rounds 20-23 */
    MSG1 = vsha256su0q_u32(MSG1, MSG2);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG2, vld1q_u32(&K256[24]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG1 = vsha256su1q_u32(MSG1, MSG3, MSG0);
    /* G6: rounds 24-27 */
    MSG2 = vsha256su0q_u32(MSG2, MSG3);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG3, vld1q_u32(&K256[28]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG2 = vsha256su1q_u32(MSG2, MSG0, MSG1);
    /* G7: rounds 28-31 */
    MSG3 = vsha256su0q_u32(MSG3, MSG0);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG0, vld1q_u32(&K256[32]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG3 = vsha256su1q_u32(MSG3, MSG1, MSG2);
    /* G8: rounds 32-35 */
    MSG0 = vsha256su0q_u32(MSG0, MSG1);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG1, vld1q_u32(&K256[36]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG0 = vsha256su1q_u32(MSG0, MSG2, MSG3);
    /* G9: rounds 36-39 */
    MSG1 = vsha256su0q_u32(MSG1, MSG2);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG2, vld1q_u32(&K256[40]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG1 = vsha256su1q_u32(MSG1, MSG3, MSG0);
    /* G10: rounds 40-43 */
    MSG2 = vsha256su0q_u32(MSG2, MSG3);
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG3, vld1q_u32(&K256[44]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    MSG2 = vsha256su1q_u32(MSG2, MSG0, MSG1);
    /* G11: rounds 44-47 */
    MSG3 = vsha256su0q_u32(MSG3, MSG0);
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG0, vld1q_u32(&K256[48]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    MSG3 = vsha256su1q_u32(MSG3, MSG1, MSG2);
    /* G12: rounds 48-51 (sem mais schedule update necessario) */
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG1, vld1q_u32(&K256[52]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    /* G13: rounds 52-55 */
    TMP2 = STATE0; TMP0 = vaddq_u32(MSG2, vld1q_u32(&K256[56]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    /* G14: rounds 56-59 */
    TMP2 = STATE0; TMP1 = vaddq_u32(MSG3, vld1q_u32(&K256[60]));
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP0); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP0);
    /* G15: rounds 60-63 */
    TMP2 = STATE0;
    STATE0 = vsha256hq_u32(STATE0, STATE1, TMP1); STATE1 = vsha256h2q_u32(STATE1, TMP2, TMP1);
    STATE0 = vaddq_u32(STATE0, ABEF_SAVE);
    STATE1 = vaddq_u32(STATE1, CDGH_SAVE);
    vst1q_u32(&out[0], STATE0);
    vst1q_u32(&out[4], STATE1);
}

#else
/* fallback portavel (x86 etc.) -- mesmo resultado, so mais lento; no celular usa o caminho NEON acima */
static void sha256_33(const uint8_t *m, uint32_t out[8]) {
    uint32_t w[64];
    for (int i = 0; i < 8; i++)
        w[i] = ((uint32_t)m[4*i] << 24) | ((uint32_t)m[4*i+1] << 16) | ((uint32_t)m[4*i+2] << 8) | m[4*i+3];
    w[8] = ((uint32_t)m[32] << 24) | 0x00800000u;
    for (int i = 9; i < 15; i++) w[i] = 0;
    w[15] = 264;
    for (int i = 16; i < 64; i++) {
        uint32_t s0 = ror(w[i-15], 7) ^ ror(w[i-15], 18) ^ (w[i-15] >> 3);
        uint32_t s1 = ror(w[i-2], 17) ^ ror(w[i-2], 19) ^ (w[i-2] >> 10);
        w[i] = w[i-16] + s0 + w[i-7] + s1;
    }
    uint32_t a=H256[0],b=H256[1],c=H256[2],d=H256[3],e=H256[4],f=H256[5],g=H256[6],h=H256[7];
    for (int i = 0; i < 64; i++) {
        uint32_t t1 = h + (ror(e,6) ^ ror(e,11) ^ ror(e,25)) + ((e & f) ^ (~e & g)) + K256[i] + w[i];
        uint32_t t2 = (ror(a,2) ^ ror(a,13) ^ ror(a,22)) + ((a & b) ^ (a & c) ^ (b & c));
        h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
    }
    out[0]=a+H256[0]; out[1]=b+H256[1]; out[2]=c+H256[2]; out[3]=d+H256[3];
    out[4]=e+H256[4]; out[5]=f+H256[5]; out[6]=g+H256[6]; out[7]=h+H256[7];
}
#endif

/* ---------------- RIPEMD-160 (1 bloco, msg de 32 bytes) ---------------- */
static const uint8_t R1[80] = { 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13 };
static const uint8_t R2[80] = { 5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11 };
static const uint8_t S1T[80] = { 11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6 };
static const uint8_t S2T[80] = { 8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11 };
static const uint32_t KA[5] = {0x00000000u,0x5A827999u,0x6ED9EBA1u,0x8F1BBCDCu,0xA953FD4Eu};
static const uint32_t KB[5] = {0x50A28BE6u,0x5C4DD124u,0x6D703EF3u,0x7A6D76E9u,0x00000000u};
static inline uint32_t rf(int j, uint32_t x, uint32_t y, uint32_t z) {
    if (j < 16) return x ^ y ^ z;
    if (j < 32) return (x & y) | (~x & z);
    if (j < 48) return (x | ~y) ^ z;
    if (j < 64) return (x & z) | (y & ~z);
    return x ^ (y | ~z);
}
static void ripemd160_32(const uint32_t sha[8], uint8_t out[20]) {
    uint32_t X[16];
    for (int i = 0; i < 8; i++) X[i] = __builtin_bswap32(sha[i]);
    X[8] = 0x80; for (int i = 9; i < 14; i++) X[i] = 0; X[14] = 256; X[15] = 0;
    uint32_t h0=0x67452301u,h1=0xEFCDAB89u,h2=0x98BADCFEu,h3=0x10325476u,h4=0xC3D2E1F0u;
    uint32_t a=h0,b=h1,c=h2,d=h3,e=h4, a2=h0,b2=h1,c2=h2,d2=h3,e2=h4, t;
    for (int j = 0; j < 80; j++) {
        t = rol(a + rf(j,b,c,d) + X[R1[j]] + KA[j/16], S1T[j]) + e;
        a = e; e = d; d = rol(c,10); c = b; b = t;
        t = rol(a2 + rf(79-j,b2,c2,d2) + X[R2[j]] + KB[j/16], S2T[j]) + e2;
        a2 = e2; e2 = d2; d2 = rol(c2,10); c2 = b2; b2 = t;
    }
    t = h1 + c + d2; h1 = h2 + d + e2; h2 = h3 + e + a2; h3 = h4 + a + b2; h4 = h0 + b + c2; h0 = t;
    uint32_t r[5] = {h0,h1,h2,h3,h4};
    for (int i = 0; i < 5; i++) { out[4*i]=r[i]; out[4*i+1]=r[i]>>8; out[4*i+2]=r[i]>>16; out[4*i+3]=r[i]>>24; }
}

/* ---------------- estado global ---------------- */
#define HALF 512
#define BATCH (2*HALF+1)
#define CHUNK_BATCHES 256ULL
static u128 CHUNK_KEYS = (u128)BATCH * CHUNK_BATCHES;
static fe GXt[HALF+1], GYt[HALF+1], NGYt[HALF+1];
static pt QSTEP;
static uint8_t target[20];
static volatile int found_flag = 0;
static u128 found_key;
static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static uint64_t next_chunk = 0;
static uint64_t active[256];
static u128 range_start, range_end;
static volatile uint64_t total_keys = 0;
static int stop_flag = 0;
static u128 TOTAL_CHUNKS = 0;
static u128 STRIDE = 1;
static int force_stride = 0;

/* modo onda: a faixa e dividida em NBINS faixas; cada faixa recebe a intensidade
 * do padrao de dupla fenda I(u) = cos^2(pi*F*u) * sinc^2(pi*L*u), u = posicao - 0.5.
 * As faixas sao visitadas da mais clara (encontro construtivo das ondas) para a
 * mais escura; dentro de cada faixa, salto aureo. Continua cobrindo 100% dos chunks. */
#define NBINS_MAX 4096
static int modo_onda = 0;
static double ONDA_F = 10.0, ONDA_L = 1.5;
static int NBINS = 0;
static int bin_order[NBINS_MAX];            /* rank -> bin */
static int bin_rank[NBINS_MAX];             /* bin -> rank */
static u128 bin_lo[NBINS_MAX + 1];          /* bin b cobre chunks [bin_lo[b], bin_lo[b+1]) */
static u128 rank_cum[NBINS_MAX + 1];        /* chunks antes do rank r */
static u128 bin_stride[NBINS_MAX];
static double bin_int[NBINS_MAX];

static u128 gcd_u128(u128 a, u128 b) {
    while (b) { u128 t = a % b; a = b; b = t; }
    return a;
}

/* varredura de salto: mapeia o indice logico sequencial (idx) pra um chunk
 * fisico espalhado por toda a faixa, via permutacao (idx*STRIDE) mod N.
 * Cobre 100% dos chunks sem sobreposicao, so que em ordem embaralhada —
 * assim o espaco inteiro e amostrado desde o inicio, nao so um pedaco. */
static u128 golden_stride(u128 n);
static void init_onda(void);
static void init_salto(void) {
    u128 total_range_keys = range_end - range_start + 1;
    TOTAL_CHUNKS = (total_range_keys + CHUNK_KEYS - 1) / CHUNK_KEYS;
    if (force_stride) {
        if (modo_onda) init_onda();
        /* usado so pra backtest/comparacao (ex: --stride 1 = ordem sequencial pura) */
        if (STRIDE != 1 && gcd_u128(STRIDE, TOTAL_CHUNKS) != 1) {
            fprintf(stderr, "aviso: passo forcado nao e coprimo com N, pode repetir/pular chunks\n");
        }
        return;
    }
    STRIDE = golden_stride(TOTAL_CHUNKS);
    if (modo_onda) init_onda();
}

static u128 golden_stride(u128 n) {
    long double phi = (long double)n * 0.6180339887498949L;
    u128 st = (u128)phi;
    if (st == 0) st = 1;
    st |= 1;
    while (gcd_u128(st, n) != 1) st += 2;
    return st;
}
static double onda_intensidade(double u) {
    double a = M_PI * ONDA_F * u, b = M_PI * ONDA_L * u;
    double c = cos(a), sn = (b == 0) ? 1.0 : sin(b) / b;
    return c * c * sn * sn;
}
static int cmp_bins(const void *pa, const void *pb) {
    int a = *(const int *)pa, b = *(const int *)pb;
    if (bin_int[a] > bin_int[b]) return -1;
    if (bin_int[a] < bin_int[b]) return 1;
    return a - b;
}
static void init_onda(void) {
    NBINS = TOTAL_CHUNKS < NBINS_MAX ? (int)TOTAL_CHUNKS : NBINS_MAX;
    for (int b = 0; b <= NBINS; b++) bin_lo[b] = TOTAL_CHUNKS * (u128)b / (u128)NBINS;
    for (int b = 0; b < NBINS; b++) {
        double u = ((double)b + 0.5) / NBINS - 0.5;
        bin_int[b] = onda_intensidade(u);
        bin_order[b] = b;
        u128 sz = bin_lo[b+1] - bin_lo[b];
        bin_stride[b] = sz > 1 ? golden_stride(sz) : 1;
    }
    qsort(bin_order, NBINS, sizeof(int), cmp_bins);
    rank_cum[0] = 0;
    for (int r = 0; r < NBINS; r++) {
        bin_rank[bin_order[r]] = r;
        int b = bin_order[r];
        rank_cum[r+1] = rank_cum[r] + (bin_lo[b+1] - bin_lo[b]);
    }
}
/* indice logico -> chunk fisico */
static u128 map_chunk(u128 idx) {
    if (!modo_onda) return (idx * STRIDE) % TOTAL_CHUNKS;
    int lo = 0, hi = NBINS - 1;                 /* maior r com rank_cum[r] <= idx */
    while (lo < hi) { int mid = (lo + hi + 1) / 2; if (rank_cum[mid] <= idx) lo = mid; else hi = mid - 1; }
    int b = bin_order[lo];
    u128 sz = bin_lo[b+1] - bin_lo[b], o = idx - rank_cum[lo];
    return bin_lo[b] + (o * bin_stride[b]) % sz;
}

static void init_tables(void) {
    pt g = GEN, cur = GEN;
    GXt[1] = g.x; GYt[1] = g.y;
    for (int j = 2; j <= HALF; j++) { pt_add(&cur, &cur, &g); GXt[j] = cur.x; GYt[j] = cur.y; }
    fe zero = {{0,0,0,0}};
    for (int j = 1; j <= HALF; j++) { fe_sub(&NGYt[j], &zero, &GYt[j]); fe_norm(&NGYt[j]); fe_norm(&GXt[j]); fe_norm(&GYt[j]); }
    pt_mul(&QSTEP, (u128)BATCH);
}

static inline int check_pt(const fe *x, const fe *y) {
    fe xn = *x, yn = *y; fe_norm(&xn); fe_norm(&yn);
    uint8_t pub[33]; pub[0] = 2 + (yn.d[0] & 1);
    for (int i = 0; i < 4; i++) {
        uint64_t v = xn.d[3 - i];
        for (int k = 0; k < 8; k++) pub[1 + 8*i + k] = (uint8_t)(v >> (56 - 8*k));
    }
    uint32_t sh[8]; uint8_t h160[20];
    sha256_33(pub, sh);
    ripemd160_32(sh, h160);
    return memcmp(h160, target, 20) == 0;
}

static int scan_range(u128 start, uint64_t nbatches, u128 *key_out, int count) {
    pt C; u128 c = start + HALF;
    pt_mul(&C, c);
    fe dx[HALF], pre[HALF], inv_all;
    for (uint64_t b = 0; b < nbatches; b++) {
        if (found_flag || stop_flag) return 0;
        if (check_pt(&C.x, &C.y)) { *key_out = c; return 1; }
        for (int j = 1; j <= HALF; j++) fe_sub(&dx[j-1], &GXt[j], &C.x);
        pre[0] = dx[0];
        for (int i = 1; i < HALF; i++) fe_mul(&pre[i], &pre[i-1], &dx[i]);
        fe_inv(&inv_all, &pre[HALF-1]);
        for (int i = HALF - 1; i >= 0; i--) {
            fe inv_i, l, x3, y3, t;
            if (i > 0) { fe_mul(&inv_i, &inv_all, &pre[i-1]); fe_mul(&inv_all, &inv_all, &dx[i]); }
            else inv_i = inv_all;
            int j = i + 1;
            fe_sub(&t, &GYt[j], &C.y); fe_mul(&l, &t, &inv_i);
            fe_sqr(&x3, &l); fe_sub(&x3, &x3, &C.x); fe_sub(&x3, &x3, &GXt[j]);
            fe_sub(&t, &C.x, &x3); fe_mul(&y3, &l, &t); fe_sub(&y3, &y3, &C.y);
            if (check_pt(&x3, &y3)) { *key_out = c + j; return 1; }
            fe_sub(&t, &NGYt[j], &C.y); fe_mul(&l, &t, &inv_i);
            fe_sqr(&x3, &l); fe_sub(&x3, &x3, &C.x); fe_sub(&x3, &x3, &GXt[j]);
            fe_sub(&t, &C.x, &x3); fe_mul(&y3, &l, &t); fe_sub(&y3, &y3, &C.y);
            if (check_pt(&x3, &y3)) { *key_out = c - j; return 1; }
        }
        pt_add(&C, &C, &QSTEP); c += BATCH;
        if (count) __sync_fetch_and_add(&total_keys, BATCH);
    }
    return 0;
}

static void *worker(void *arg) {
    int tid = (int)(intptr_t)arg;
    while (!found_flag && !stop_flag) {
        pthread_mutex_lock(&mtx);
        uint64_t idx = next_chunk;
        if ((u128)idx >= TOTAL_CHUNKS) { active[tid] = ~0ULL; pthread_mutex_unlock(&mtx); break; }
        next_chunk++; active[tid] = idx;
        pthread_mutex_unlock(&mtx);
        u128 phys = map_chunk((u128)idx);
        u128 start = range_start + phys * CHUNK_KEYS;
        if (start > range_end) continue;
        u128 k;
        if (scan_range(start, CHUNK_BATCHES, &k, 1)) {
            pthread_mutex_lock(&mtx); found_key = k; found_flag = 1; pthread_mutex_unlock(&mtx);
            break;
        }
        pthread_mutex_lock(&mtx);
        active[tid] = ~0ULL;
        pthread_mutex_unlock(&mtx);
    }
    return NULL;
}

/* ---------------- util ---------------- */
static u128 parse_hex(const char *s) {
    if (s[0]=='0' && (s[1]=='x'||s[1]=='X')) s += 2;
    u128 v = 0;
    for (; *s; s++) {
        int d = (*s>='0'&&*s<='9') ? *s-'0' : (*s>='a'&&*s<='f') ? *s-'a'+10 : (*s>='A'&&*s<='F') ? *s-'A'+10 : -1;
        if (d < 0) break;
        v = (v << 4) | d;
    }
    return v;
}
static void fmt_hex(u128 v, char *buf) { sprintf(buf, "%llx%016llx", (unsigned long long)(v >> 64), (unsigned long long)v); }
static int parse_h160(const char *s, uint8_t out[20]) {
    if (strlen(s) != 40) return 0;
    for (int i = 0; i < 20; i++) { unsigned v; if (sscanf(s + 2*i, "%2x", &v) != 1) return 0; out[i] = v; }
    return 1;
}
static double now(void) { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec + ts.tv_nsec * 1e-9; }

static uint64_t min_active_locked(void) {
    uint64_t m = next_chunk;
    for (int i = 0; i < 256; i++) if (active[i] < m) m = active[i];
    return m;
}
static void write_ckpt(const char *path) {
    pthread_mutex_lock(&mtx); uint64_t m = min_active_locked(); pthread_mutex_unlock(&mtx);
    char tmp[512], hs[64]; snprintf(tmp, sizeof tmp, "%s.tmp", path); fmt_hex(range_start, hs);
    FILE *f = fopen(tmp, "w");
    if (!f) return;
    fprintf(f, "%s %llu %llu\n", hs, (unsigned long long)CHUNK_KEYS, (unsigned long long)m);
    fclose(f); rename(tmp, path);
}
static int load_ckpt(const char *path, uint64_t *chunk) {
    FILE *f = fopen(path, "r"); if (!f) return 0;
    char hs[64]; unsigned long long ck, nc;
    int ok = fscanf(f, "%63s %llu %llu", hs, &ck, &nc) == 3; fclose(f);
    if (!ok) return 0;
    if (parse_hex(hs) != range_start || (u128)ck != CHUNK_KEYS) { fprintf(stderr, "checkpoint de outro range/config; ignorado\n"); return 0; }
    *chunk = nc; return 1;
}

typedef struct { int puz; const char *key; const char *h160; } tcase;
static int selftest(void) {
    static const tcase cases[] = {
        {20, "d2c55", "b907c3a2a3b27789dfb509b730dd47703c272868"},
        {25, "1fa5ee5", "2f396b29b27324300d0c59b17c3abc1835bd3dbb"},
        {30, "3d94cd64", "d39c4704664e1deb76c9331e637564c257d68a08"},
        {40, "e9ae4933d6", "95a156cd21b4a69de969eb6716864f4c8b82a82a"},
        {70, "349b84b6431a6c4ef1", "5db8cda53a6a002db10365967d7f85d19e171b10"}};
    static const int offs[] = {0, 1, 100, 511, 512, 513, 1024, 1025, 1026, 2000, 3074};
    int fails = 0, total = 0;
    for (unsigned c = 0; c < sizeof cases / sizeof *cases; c++) {
        parse_h160(cases[c].h160, target);
        u128 key = parse_hex(cases[c].key);
        for (unsigned o = 0; o < sizeof offs / sizeof *offs; o++) {
            u128 k = 0; total++;
            int r = scan_range(key - offs[o], 3, &k, 0);
            if (!(r && k == key)) { fails++; printf("FALHOU puzzle %d offset %d\n", cases[c].puz, offs[o]); }
        }
        printf("puzzle %d: ok\n", cases[c].puz);
    }
    printf("selftest: %d/%d casos ok\n", total - fails, total);
    return fails ? 1 : 0;
}

int main(int argc, char **argv) {
    const char *ckpt = "checkpoint.txt", *foundf = "FOUND.txt", *statusf = "status.txt";
    const char *start_s = "400000000000000000", *end_s = "7fffffffffffffffff";
    const char *tgt_s = "f6f5431d25bbf7b12e8add9af5e3475c44a0a5b8";
    int threads = 2, do_self = 0; double seconds = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--selftest")) do_self = 1;
        else if (!strcmp(argv[i], "--threads") && i+1 < argc) threads = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--ckpt") && i+1 < argc) ckpt = argv[++i];
        else if (!strcmp(argv[i], "--found") && i+1 < argc) foundf = argv[++i];
        else if (!strcmp(argv[i], "--status") && i+1 < argc) statusf = argv[++i];
        else if (!strcmp(argv[i], "--start") && i+1 < argc) start_s = argv[++i];
        else if (!strcmp(argv[i], "--end") && i+1 < argc) end_s = argv[++i];
        else if (!strcmp(argv[i], "--target") && i+1 < argc) tgt_s = argv[++i];
        else if (!strcmp(argv[i], "--seconds") && i+1 < argc) seconds = atof(argv[++i]);
        else if (!strcmp(argv[i], "--modo") && i+1 < argc) { i++; modo_onda = !strcmp(argv[i], "onda"); }
        else if (!strcmp(argv[i], "--franjas") && i+1 < argc) ONDA_F = atof(argv[++i]);
        else if (!strcmp(argv[i], "--envelope") && i+1 < argc) ONDA_L = atof(argv[++i]);
        else if (!strcmp(argv[i], "--stride") && i+1 < argc) { STRIDE = (u128)strtoull(argv[++i], NULL, 10); force_stride = 1; }
    }
    if (threads < 1) threads = 1; if (threads > 64) threads = 64;
    init_tables();
    if (do_self) return selftest();
    if (!parse_h160(tgt_s, target)) { fprintf(stderr, "hash160 invalido\n"); return 2; }
    range_start = parse_hex(start_s); range_end = parse_hex(end_s);
    init_salto();
    for (int i = 0; i < 256; i++) active[i] = ~0ULL;
    uint64_t resume = 0; int resumed = load_ckpt(ckpt, &resume); next_chunk = resumed ? resume : 0;
    if (modo_onda) printf("modo ONDA | franjas=%.2f envelope=%.2f faixas=%d\n", ONDA_F, ONDA_L, NBINS);
    printf("p71b engine SALTO | threads=%d | resume_chunk=%llu/%llu | chunk=%llu chaves | passo=%llu\n", threads,
           (unsigned long long)next_chunk, (unsigned long long)TOTAL_CHUNKS,
           (unsigned long long)CHUNK_KEYS, (unsigned long long)STRIDE);
    fflush(stdout);
    pthread_t th[64];
    for (int i = 0; i < threads; i++) pthread_create(&th[i], NULL, worker, (void *)(intptr_t)i);
    double t0 = now(), tlast = t0; uint64_t base_chunk = next_chunk;
    while (1) {
        usleep(200000);
        double t = now();
        pthread_mutex_lock(&mtx); int done = found_flag; pthread_mutex_unlock(&mtx);
        int alive = 0;
        pthread_mutex_lock(&mtx); for (int i = 0; i < threads; i++) if (active[i] != ~0ULL) alive = 1; uint64_t nc = next_chunk; pthread_mutex_unlock(&mtx);
        if (done) break;
        if (seconds > 0 && t - t0 >= seconds) { stop_flag = 1; break; }
        if (!alive && (u128)nc >= TOTAL_CHUNKS) break;
        if (t - tlast >= 10) {
            tlast = t; write_ckpt(ckpt);
            FILE *f = fopen(statusf, "w");
            if (f) {
                double el = t - t0; uint64_t tk = total_keys;
                fprintf(f, "chaves_nesta_execucao=%llu\nvelocidade_chaves_por_s=%.0f\nchunk_atual=%llu\nchunks_desde_inicio=%llu\ntempo_s=%.0f\n",
                        (unsigned long long)tk, tk / el, (unsigned long long)nc, (unsigned long long)(nc - base_chunk), el);
                fclose(f);
            }
        }
    }
    stop_flag = 1;
    for (int i = 0; i < threads; i++) pthread_join(th[i], NULL);
    if (found_flag) {
        char hs[64]; fmt_hex(found_key, hs);
        double el = now() - t0;
        FILE *f = fopen(foundf, "a");
        if (f) { fprintf(f, "CHAVE ENCONTRADA: 0x%s | chunks=%llu chaves=%llu tempo_s=%.2f passo=%llu\n",
                         hs, (unsigned long long)next_chunk, (unsigned long long)total_keys, el, (unsigned long long)STRIDE); fclose(f); }
        printf("\n!!! CHAVE ENCONTRADA: 0x%s !!! | chunks=%llu chaves=%llu tempo_s=%.2f\n",
               hs, (unsigned long long)next_chunk, (unsigned long long)total_keys, el);
        return 0;
    }
    double el = now() - t0;
    if (seconds > 0) printf("bench: %llu chaves em %.1fs = %.0f chaves/s\n", (unsigned long long)total_keys, el, total_keys / el);
    else write_ckpt(ckpt);
    return 0;
}
