"""Calcula o hash160 (endereco comprimido) de cada chave em chaves_resolvidas.txt."""
import hashlib
import sys

P = 2**256 - 2**32 - 977
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)


def add(a, b):
    if a is None:
        return b
    if b is None:
        return a
    if a[0] == b[0]:
        if (a[1] + b[1]) % P == 0:
            return None
        l = 3 * a[0] * a[0] * pow(2 * a[1], -1, P) % P
    else:
        l = (b[1] - a[1]) * pow(b[0] - a[0], -1, P) % P
    x = (l * l - a[0] - b[0]) % P
    return x, (l * (a[0] - x) - a[1]) % P


def mul(k):
    r, q = None, G
    while k:
        if k & 1:
            r = add(r, q)
        q = add(q, q)
        k >>= 1
    return r


def ripemd160(data):
    try:
        return hashlib.new("ripemd160", data).digest()
    except ValueError:
        return _ripemd160(data)


def _ripemd160(msg):
    # implementacao de referencia (para Pythons sem ripemd160 no OpenSSL)
    r1 = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,7,4,13,1,10,6,15,3,12,0,9,5,2,14,11,8,3,10,14,4,9,15,8,1,2,7,0,6,13,11,5,12,1,9,11,10,0,8,12,4,13,3,7,15,14,5,6,2,4,0,5,9,7,12,2,10,14,1,3,8,11,6,15,13]
    r2 = [5,14,7,0,9,2,11,4,13,6,15,8,1,10,3,12,6,11,3,7,0,13,5,10,14,15,8,12,4,9,1,2,15,5,1,3,7,14,6,9,11,8,12,2,10,0,4,13,8,6,4,1,3,11,15,0,5,12,2,13,9,7,10,14,12,15,10,4,1,5,8,7,6,2,13,14,0,3,9,11]
    s1 = [11,14,15,12,5,8,7,9,11,13,14,15,6,7,9,8,7,6,8,13,11,9,7,15,7,12,15,9,11,7,13,12,11,13,6,7,14,9,13,15,14,8,13,6,5,12,7,5,11,12,14,15,14,15,9,8,9,14,5,6,8,6,5,12,9,15,5,11,6,8,13,12,5,12,13,14,11,8,5,6]
    s2 = [8,9,9,11,13,15,15,5,7,7,8,11,14,14,12,6,9,13,15,7,12,8,9,11,7,7,12,7,6,15,13,11,9,7,15,11,8,6,6,14,12,13,5,14,13,13,7,5,15,5,8,11,14,14,6,14,6,9,12,9,12,5,15,8,8,5,12,9,12,5,14,6,8,13,6,5,15,13,11,11]
    ka = [0, 0x5A827999, 0x6ED9EBA1, 0x8F1BBCDC, 0xA953FD4E]
    kb = [0x50A28BE6, 0x5C4DD124, 0x6D703EF3, 0x7A6D76E9, 0]
    M = 0xFFFFFFFF
    rol = lambda x, n: ((x << n) | (x >> (32 - n))) & M

    def f(j, x, y, z):
        if j < 16: return x ^ y ^ z
        if j < 32: return (x & y) | (~x & z)
        if j < 48: return (x | ~y & M) ^ z
        if j < 64: return (x & z) | (y & ~z)
        return x ^ (y | ~z & M)

    ml = len(msg) * 8
    msg += b"\x80" + b"\x00" * ((55 - len(msg)) % 64) + ml.to_bytes(8, "little")
    h = [0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476, 0xC3D2E1F0]
    for i in range(0, len(msg), 64):
        X = [int.from_bytes(msg[i + 4 * j:i + 4 * j + 4], "little") for j in range(16)]
        a, b, c, d, e = h
        a2, b2, c2, d2, e2 = h
        for j in range(80):
            t = (rol((a + (f(j, b, c, d) & M) + X[r1[j]] + ka[j // 16]) & M, s1[j]) + e) & M
            a, e, d, c, b = e, d, rol(c, 10), b, t
            t = (rol((a2 + (f(79 - j, b2, c2, d2) & M) + X[r2[j]] + kb[j // 16]) & M, s2[j]) + e2) & M
            a2, e2, d2, c2, b2 = e2, d2, rol(c2, 10), b2, t
        t = (h[1] + c + d2) & M
        h[1] = (h[2] + d + e2) & M
        h[2] = (h[3] + e + a2) & M
        h[3] = (h[4] + a + b2) & M
        h[4] = (h[0] + b + c2) & M
        h[0] = t
    return b"".join(x.to_bytes(4, "little") for x in h)


def hash160(k):
    x, y = mul(k)
    pub = bytes([2 + (y & 1)]) + x.to_bytes(32, "big")
    return ripemd160(hashlib.sha256(pub).digest()).hex()


if __name__ == "__main__":
    arq = sys.argv[1] if len(sys.argv) > 1 else "chaves_resolvidas.txt"
    for linha in open(arq):
        n, k = linha.split()[:2]
        print(n, k, hash160(int(k, 16)))
