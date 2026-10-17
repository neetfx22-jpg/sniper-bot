#!/usr/bin/env python3
# Teste cego de viés nas chaves resolvidas do Bitcoin Puzzle.
# Hipóteses fixadas antes de olhar os dados; alpha global 0,05, Bonferroni (4 testes).
#  H1: u = (k - 2^(n-1)) / 2^(n-1) uniforme em [0,1)       KS exato, n >= 16
#  H2: total de bits 1 nos n-1 bits livres ~ Binomial(p=0,5) binomial exato bilateral, n >= 2
#  H3: autocorrelação lag-1 de u entre puzzles consecutivos  Pearson, pares (n, n+1) com n >= 16
#  H4: proporção de chaves ímpares = 0,5                     binomial exato bilateral, n >= 2
# Conjunto principal: puzzles 1-70. O conjunto estendido (+75..125) é só sensibilidade.
# Cada chave é validada pelo intervalo e por k*G -> HASH160 -> endereço Base58Check.
# Fonte das chaves: btcpuzzle.info (lista de puzzles), conferidas aqui pelo endereço.
# Não depende de scipy (Termux); se scipy existir, compara os p-values.
import hashlib, math, sys

DATA = [
    (1, 0x1, "1BgGZ9tcN4rm9KBzDn7KprQz87SZ26SAMH"),
    (2, 0x3, "1CUNEBjYrCn2y1SdiUMohaKUi4wpP326Lb"),
    (3, 0x7, "19ZewH8Kk1PDbSNdJ97FP4EiCjTRaZMZQA"),
    (4, 0x8, "1EhqbyUMvvs7BfL8goY6qcPbD6YKfPqb7e"),
    (5, 0x15, "1E6NuFjCi27W5zoXg8TRdcSRq84zJeBW3k"),
    (6, 0x31, "1PitScNLyp2HCygzadCh7FveTnfmpPbfp8"),
    (7, 0x4c, "1McVt1vMtCC7yn5b9wgX1833yCcLXzueeC"),
    (8, 0xe0, "1M92tSqNmQLYw33fuBvjmeadirh1ysMBxK"),
    (9, 0x1d3, "1CQFwcjw1dwhtkVWBttNLDtqL7ivBonGPV"),
    (10, 0x202, "1LeBZP5QCwwgXRtmVUvTVrraqPUokyLHqe"),
    (11, 0x483, "1PgQVLmst3Z314JrQn5TNiys8Hc38TcXJu"),
    (12, 0xa7b, "1DBaumZxUkM4qMQRt2LVWyFJq5kDtSZQot"),
    (13, 0x1460, "1Pie8JkxBT6MGPz9Nvi3fsPkr2D8q3GBc1"),
    (14, 0x2930, "1ErZWg5cFCe4Vw5BzgfzB74VNLaXEiEkhk"),
    (15, 0x68f3, "1QCbW9HWnwQWiQqVo5exhAnmfqKRrCRsvW"),
    (16, 0xc936, "1BDyrQ6WoF8VN3g9SAS1iKZcPzFfnDVieY"),
    (17, 0x1764f, "1HduPEXZRdG26SUT5Yk83mLkPyjnZuJ7Bm"),
    (18, 0x3080d, "1GnNTmTVLZiqQfLbAdp9DVdicEnB5GoERE"),
    (19, 0x5749f, "1NWmZRpHH4XSPwsW6dsS3nrNWfL1yrJj4w"),
    (20, 0xd2c55, "1HsMJxNiV7TLxmoF6uJNkydxPFDog4NQum"),
    (21, 0x1ba534, "14oFNXucftsHiUMY8uctg6N487riuyXs4h"),
    (22, 0x2de40f, "1CfZWK1QTQE3eS9qn61dQjV89KDjZzfNcv"),
    (23, 0x556e52, "1L2GM8eE7mJWLdo3HZS6su1832NX2txaac"),
    (24, 0xdc2a04, "1rSnXMr63jdCuegJFuidJqWxUPV7AtUf7"),
    (25, 0x1fa5ee5, "15JhYXn6Mx3oF4Y7PcTAv2wVVAuCFFQNiP"),
    (26, 0x340326e, "1JVnST957hGztonaWK6FougdtjxzHzRMMg"),
    (27, 0x6ac3875, "128z5d7nN7PkCuX5qoA4Ys6pmxUYnEy86k"),
    (28, 0xd916ce8, "12jbtzBb54r97TCwW3G1gCFoumpckRAPdY"),
    (29, 0x17e2551e, "19EEC52krRUK1RkUAEZmQdjTyHT7Gp1TYT"),
    (30, 0x3d94cd64, "1LHtnpd8nU5VHEMkG2TMYYNUjjLc992bps"),
    (31, 0x7d4fe747, "1LhE6sCTuGae42Axu1L1ZB7L96yi9irEBE"),
    (32, 0xb862a62e, "1FRoHA9xewq7DjrZ1psWJVeTer8gHRqEvR"),
    (33, 0x1a96ca8d8, "187swFMjz1G54ycVU56B7jZFHFTNVQFDiu"),
    (34, 0x34a65911d, "1PWABE7oUahG2AFFQhhvViQovnCr4rEv7Q"),
    (35, 0x4aed21170, "1PWCx5fovoEaoBowAvF5k91m2Xat9bMgwb"),
    (36, 0x9de820a7c, "1Be2UF9NLfyLFbtm3TCbmuocc9N1Kduci1"),
    (37, 0x1757756a93, "14iXhn8bGajVWegZHJ18vJLHhntcpL4dex"),
    (38, 0x22382facd0, "1HBtApAFA9B2YZw3G2YKSMCtb3dVnjuNe2"),
    (39, 0x4b5f8303e9, "122AJhKLEfkFBaGAd84pLp1kfE7xK3GdT8"),
    (40, 0xe9ae4933d6, "1EeAxcprB2PpCnr34VfZdFrkUWuxyiNEFv"),
    (41, 0x153869acc5b, "1L5sU9qvJeuwQUdt4y1eiLmquFxKjtHr3E"),
    (42, 0x2a221c58d8f, "1E32GPWgDyeyQac4aJxm9HVoLrrEYPnM4N"),
    (43, 0x6bd3b27c591, "1PiFuqGpG8yGM5v6rNHWS3TjsG6awgEGA1"),
    (44, 0xe02b35a358f, "1CkR2uS7LmFwc3T2jV8C1BhWb5mQaoxedF"),
    (45, 0x122fca143c05, "1NtiLNGegHWE3Mp9g2JPkgx6wUg4TW7bbk"),
    (46, 0x2ec18388d544, "1F3JRMWudBaj48EhwcHDdpeuy2jwACNxjP"),
    (47, 0x6cd610b53cba, "1Pd8VvT49sHKsmqrQiP61RsVwmXCZ6ay7Z"),
    (48, 0xade6d7ce3b9b, "1DFYhaB2J9q1LLZJWKTnscPWos9VBqDHzv"),
    (49, 0x174176b015f4d, "12CiUhYVTTH33w3SPUBqcpMoqnApAV4WCF"),
    (50, 0x22bd43c2e9354, "1MEzite4ReNuWaL5Ds17ePKt2dCxWEofwk"),
    (51, 0x75070a1a009d4, "1NpnQyZ7x24ud82b7WiRNvPm6N8bqGQnaS"),
    (52, 0xefae164cb9e3c, "15z9c9sVpu6fwNiK7dMAFgMYSK4GqsGZim"),
    (53, 0x180788e47e326c, "15K1YKJMiJ4fpesTVUcByoz334rHmknxmT"),
    (54, 0x236fb6d5ad1f43, "1KYUv7nSvXx4642TKeuC2SNdTk326uUpFy"),
    (55, 0x6abe1f9b67e114, "1LzhS3k3e9Ub8i2W1V8xQFdB8n2MYCHPCa"),
    (56, 0x9d18b63ac4ffdf, "17aPYR1m6pVAacXg1PTDDU7XafvK1dxvhi"),
    (57, 0x1eb25c90795d61c, "15c9mPGLku1HuW9LRtBf4jcHVpBUt8txKz"),
    (58, 0x2c675b852189a21, "1Dn8NF8qDyyfHMktmuoQLGyjWmZXgvosXf"),
    (59, 0x7496cbb87cab44f, "1HAX2n9Uruu9YDt4cqRgYcvtGvZj1rbUyt"),
    (60, 0xfc07a1825367bbe, "1Kn5h2qpgw9mWE5jKpk8PP4qvvJ1QVy8su"),
    (61, 0x13c96a3742f64906, "1AVJKwzs9AskraJLGHAZPiaZcrpDr1U6AB"),
    (62, 0x363d541eb611abee, "1Me6EfpwZK5kQziBwBfvLiHjaPGxCKLoJi"),
    (63, 0x7cce5efdaccf6808, "1NpYjtLira16LfGbGwZJ5JbDPh3ai9bjf4"),
    (64, 0xf7051f27b09112d4, "16jY7qLJnxb7CHZyqBP8qca9d51gAjyXQN"),
    (65, 0x1a838b13505b26867, "18ZMbwUFLMHoZBbfpCjUJQTCMCbktshgpe"),
    (66, 0x2832ed74f2b5e35ee, "13zb1hQbWVsc2S7ZTZnP2G4undNNpdh5so"),
    (67, 0x730fc235c1942c1ae, "1BY8GQbnueYofwSuFAT3USAhGjPrkxDdW9"),
    (68, 0xbebb3940cd0fc1491, "1MVDYgVaSN6iKKEsbzRUAYFrYJadLYZvvZ"),
    (69, 0x101d83275fb2bc7e0c, "19vkiEajfhuZ8bs8Zu2jgmC6oqZbWqhxhG"),
    (70, 0x349b84b6431a6c4ef1, "19YZECXj3SxEZMoUeJ1yiPsw8xANe7M7QR"),
    (75, 0x4c5ce114686a1336e07, "1J36UjUByGroXcCvmj13U6uwaVv9caEeAt"),
    (80, 0xea1a5c66dcc11b5ad180, "1BCf6rHUW6m3iH2ptsvnjgLruAiPQQepLe"),
    (85, 0x11720c4f018d51b8cebba8, "1Kh22PvXERd2xpTQk3ur6pPEqFeckCJfAr"),
    (90, 0x2ce00bb2136a445c71e85bf, "1L12FHH2FHjvTviyanuiFVfmzCy46RRATU"),
    (95, 0x527a792b183c7f64a0e8b1f4, "19eVSDuizydXxhohGh8Ki9WY9KsHdSwoQC"),
    (100, 0xaf55fc59c335c8ec67ed24826, "1KCgMv8fo2TPBpddVi9jqmMmcne9uSNJ5F"),
    (105, 0x16f14fc2054cd87ee6396b33df3, "1CMjscKB3QW7SDyQ4c3C3DEUHiHRhiZVib"),
    (110, 0x35c0d7234df7deb0f20cf7062444, "12JzYkkN76xkwvcPT6AWKZtGX6w2LAgsJg"),
    (115, 0x60f4d11574f5deee49961d9609ac6, "1NLbHuJebVwUZ1XqDjsAyfTRUPwDQbemfv"),
    (120, 0xb10f22572c497a836ea187f2e1fc23, "17s2b9ksz5y7abUm92cHwG8jEPCzK3dLnT"),
    (125, 0x1c533b6bb7f0804e09960225e44877ac, "1PXAyUB8ZoH3WD8n5zoAthYjN15yN5CVq5"),
]

# chaves do selftest do engine_salto (conferem com seus hash160)
SELFTEST = {20: 0xd2c55, 25: 0x1fa5ee5, 30: 0x3d94cd64, 40: 0xe9ae4933d6, 70: 0x349b84b6431a6c4ef1}

ALPHA = 0.05
NTESTS = 4
ALPHA_ADJ = ALPHA / NTESTS

# ---------- secp256k1 / endereço ----------
P = 2**256 - 2**32 - 977
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

def ec_add(a, b):
    if a is None: return b
    if b is None: return a
    if a[0] == b[0]:
        if (a[1] + b[1]) % P == 0: return None
        l = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        l = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (l * l - a[0] - b[0]) % P
    return (x, (l * (a[0] - x) - a[1]) % P)

def ec_mul(k):
    r, q = None, (GX, GY)
    while k:
        if k & 1: r = ec_add(r, q)
        q = ec_add(q, q)
        k >>= 1
    return r

def _rmd160_py(m):
    # RIPEMD-160 puro (fallback para OpenSSL sem ripemd160)
    f = [lambda x, y, z: x ^ y ^ z, lambda x, y, z: (x & y) | (~x & z),
         lambda x, y, z: (x | ~y) ^ z, lambda x, y, z: (x & z) | (y & ~z),
         lambda x, y, z: x ^ (y | ~z)]
    K1 = [0, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
    K2 = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0]
    R1 = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,
          3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,
          4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
    R2 = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,
          15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,
          12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
    S1 = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,
          11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,
          9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
    S2 = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,
          9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,
          8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
    M = 0xFFFFFFFF
    rol = lambda x, s: ((x << s) | (x >> (32 - s))) & M
    m = m + b"\x80" + b"\x00" * ((55 - len(m)) % 64) + (8 * len(m)).to_bytes(8, "little")
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    for o in range(0, len(m), 64):
        X = [int.from_bytes(m[o + 4*i:o + 4*i + 4], "little") for i in range(16)]
        a1, b1, c1, d1, e1 = h
        a2, b2, c2, d2, e2 = h
        for j in range(80):
            r = j // 16
            t = (rol((a1 + (f[r](b1, c1, d1) & M) + X[R1[j]] + K1[r]) & M, S1[j]) + e1) & M
            a1, b1, c1, d1, e1 = e1, t, b1, rol(c1, 10), d1
            t = (rol((a2 + (f[4 - r](b2, c2, d2) & M) + X[R2[j]] + K2[r]) & M, S2[j]) + e2) & M
            a2, b2, c2, d2, e2 = e2, t, b2, rol(c2, 10), d2
        t = (h[1] + c1 + d2) & M
        h[1] = (h[2] + d1 + e2) & M
        h[2] = (h[3] + e1 + a2) & M
        h[3] = (h[4] + a1 + b2) & M
        h[4] = (h[0] + b1 + c2) & M
        h[0] = t
    return b"".join(x.to_bytes(4, "little") for x in h)

def rmd160(m):
    try:
        return hashlib.new("ripemd160", m).digest()
    except ValueError:
        return _rmd160_py(m)

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def b58check(payload):
    raw = payload + hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    n, s = int.from_bytes(raw, "big"), ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + s

def address(k):
    x, y = ec_mul(k)
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return b58check(b"\0" + rmd160(hashlib.sha256(pub).digest()))

def validate(data):
    assert _rmd160_py(b"abc").hex() == "8eb208f7e05d987a9b044a8e98c6b087f15a0bfc"
    seen = set()
    for n, k, addr in data:
        assert n not in seen, f"puzzle {n} repetido"
        seen.add(n)
        assert 2**(n - 1) <= k <= 2**n - 1, f"puzzle {n}: chave fora do intervalo"
        a = address(k)
        assert a == addr, f"puzzle {n}: endereço {a} != {addr}"
    for n, k in SELFTEST.items():
        got = [kk for nn, kk, _ in data if nn == n]
        assert got == [k], f"puzzle {n}: difere do selftest do engine"

# ---------- estatística (sem scipy) ----------
def binom_two_sided(k, n):
    # p = 0,5: distribuição simétrica, p = 2*cauda menor (limitado a 1)
    lo = min(k, n - k)
    tail = sum(math.comb(n, i) for i in range(lo + 1))
    return min(1.0, 2 * tail / 2**n)

def ks_stat(u):
    u = sorted(u); n = len(u)
    return max(max((i + 1) / n - x, x - i / n) for i, x in enumerate(u))

def ks_pvalue_exact(d, n):
    # Marsaglia, Tsang & Wang (2003): P(D_n >= d) bilateral exato
    k = int(n * d) + 1
    m = 2 * k - 1
    h = k - n * d
    H = [[1.0 if i - j + 1 >= 0 else 0.0 for j in range(m)] for i in range(m)]
    for i in range(m):
        H[i][0] -= h ** (i + 1)
        H[m - 1][i] -= h ** (m - i)
    H[m - 1][0] += (2 * h - 1) ** m if 2 * h - 1 > 0 else 0.0
    for i in range(m):
        for j in range(m):
            if i - j + 1 > 0:
                H[i][j] /= math.factorial(i - j + 1)

    def mul(A, B):
        return [[sum(A[i][t] * B[t][j] for t in range(m)) for j in range(m)] for i in range(m)]

    def mpow(A, e):
        if e == 1: return A, 0
        B, eB = mpow(A, e // 2)
        B = mul(B, B); eB *= 2
        if e % 2: B = mul(A, B)
        if B[k - 1][k - 1] > 1e140:
            B = [[x * 1e-140 for x in r] for r in B]; eB += 140
        return B, eB

    T, eT = mpow(H, n)
    s = T[k - 1][k - 1]
    for i in range(1, n + 1):
        s = s * i / n
        if s < 1e-140:
            s *= 1e140; eT -= 140
    return max(0.0, min(1.0, 1.0 - s * 10.0 ** eT))

def betacf(a, b, x):
    qab, qap, qam = a + b, a + 1, a - 1
    c, d = 1.0, 1 - qab * x / qap
    d = 1 / (d if abs(d) > 1e-300 else 1e-300); h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1 + aa * d; d = 1 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1 + aa / c if abs(1 + aa / c) > 1e-300 else 1e-300
        de = d * c; h *= de
        if abs(de - 1) < 1e-15: break
    return h

def betai(a, b, x):
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1 - x))
    if x < (a + 1) / (a + b + 2): return bt * betacf(a, b, x) / a
    return 1 - bt * betacf(b, a, 1 - x) / b

def pearson(x, y):
    n = len(x); mx, my = sum(x) / n, sum(y) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x); syy = sum((b - my) ** 2 for b in y)
    r = sxy / math.sqrt(sxx * syy)
    df = n - 2
    if abs(r) >= 1:
        return r, 0.0
    t2 = df * r * r / (1 - r * r)
    return r, betai(df / 2, 0.5, df / (df + t2))

# ---------- testes ----------
def u_of(n, k):
    return (k - 2**(n - 1)) / 2**(n - 1)

def run(data, label):
    d = {n: k for n, k, _ in data}
    rows = []
    # H1
    s1 = sorted(n for n in d if n >= 16)
    u = [u_of(n, d[n]) for n in s1]
    D = ks_stat(u)
    rows.append(("H1 KS uniformidade de u (n>=16)", len(u), f"D={D:.4f}", ks_pvalue_exact(D, len(u)), u))
    # H2
    s2 = sorted(n for n in d if n >= 2)
    ones = sum(bin(d[n] - 2**(n - 1)).count("1") for n in s2)
    nbits = sum(n - 1 for n in s2)
    rows.append(("H2 bits 1 nos bits livres", len(s2), f"{ones}/{nbits}={ones/nbits:.4f}", binom_two_sided(ones, nbits), (ones, nbits)))
    # H3
    pairs = [(n, n + 1) for n in s1 if n + 1 in d]
    x = [u_of(a, d[a]) for a, _ in pairs]; y = [u_of(b, d[b]) for _, b in pairs]
    r, p = pearson(x, y)
    rows.append(("H3 Pearson lag-1 de u (pares n,n+1; n>=16)", len(pairs), f"r={r:+.4f}", p, (x, y)))
    # H4
    odd = sum(d[n] & 1 for n in s2)
    rows.append(("H4 paridade do LSB (n>=2)", len(s2), f"impares={odd}/{len(s2)}={odd/len(s2):.4f}", binom_two_sided(odd, len(s2)), (odd, len(s2))))

    print(f"\n== {label}: puzzles {min(d)}..{max(d)} ({len(d)} chaves) ==")
    print(f"alpha global {ALPHA}, Bonferroni {NTESTS} testes -> alpha_adj = {ALPHA_ADJ}")
    for name, N, stat, p, _ in rows:
        print(f"  {name:45s} N={N:3d}  {stat:28s} p={p:.4f}  {'REJEITA H0' if p < ALPHA_ADJ else 'nao rejeita'}")
    rej = [r for r in rows if r[3] < ALPHA_ADJ]
    print("  Conclusao:", "viés detectado em " + ", ".join(r[0][:2] for r in rej) if rej
          else "nenhum viés detectado; consistente com chaves uniformes.")
    return rows

def compare_scipy(rows):
    try:
        from scipy import stats
    except ImportError:
        print("\n(scipy ausente: p-values calculados pela implementação própria)")
        return
    ref = [stats.kstest(rows[0][4], "uniform", method="exact").pvalue,
           stats.binomtest(*rows[1][4], 0.5).pvalue,
           stats.pearsonr(*rows[2][4]).pvalue,
           stats.binomtest(*rows[3][4], 0.5).pvalue]
    print("\nconferencia com scipy:")
    for (name, _, _, p, _), q in zip(rows, ref):
        print(f"  {name[:2]}  proprio={p:.6f}  scipy={q:.6f}  {'ok' if abs(p - q) < 1e-6 else 'DIFERENTE'}")

if __name__ == "__main__":
    validate(DATA)
    print(f"{len(DATA)} chaves validadas (intervalo + endereço derivado + selftest do engine)")
    main = [r for r in DATA if r[0] <= 70]
    compare_scipy(run(main, "PRINCIPAL"))
    if "--estendido" in sys.argv:
        run(DATA, "SENSIBILIDADE (nao confirmatorio)")
