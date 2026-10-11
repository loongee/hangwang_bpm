"""SM3 摘要。密码登录与客户端一致：UTF-8 字节做 SM3，十六进制再转大写。"""

_IV = [
    0x7380166F,
    0x4914B2B9,
    0x172442D7,
    0xDA8A0600,
    0xA96F30BC,
    0x163138AA,
    0xE38DEE4D,
    0xB0FB0E4E,
]


def _rotl(value: int, bits: int) -> int:
    bits %= 32
    return ((value << bits) | (value >> (32 - bits))) & 0xFFFFFFFF


def _ff(x: int, y: int, z: int, j: int) -> int:
    if j < 16:
        return x ^ y ^ z
    return (x & y) | (x & z) | (y & z)


def _gg(x: int, y: int, z: int, j: int) -> int:
    if j < 16:
        return x ^ y ^ z
    return (x & y) | ((~x) & z)


def _p0(x: int) -> int:
    return x ^ _rotl(x, 9) ^ _rotl(x, 17)


def _p1(x: int) -> int:
    return x ^ _rotl(x, 15) ^ _rotl(x, 23)


def _tj(j: int) -> int:
    return 0x79CC4519 if j < 16 else 0x7A879D8A


def sm3(data: bytes) -> bytes:
    message = bytearray(data)
    bit_length = len(message) * 8
    message.append(0x80)
    while len(message) % 64 != 56:
        message.append(0)
    message += bit_length.to_bytes(8, "big")

    state = _IV[:]
    for offset in range(0, len(message), 64):
        block = message[offset : offset + 64]
        words = [int.from_bytes(block[i : i + 4], "big") for i in range(0, 64, 4)]
        for index in range(16, 68):
            words.append(
                _p1(words[index - 16] ^ words[index - 9] ^ _rotl(words[index - 3], 15))
                ^ _rotl(words[index - 13], 7)
                ^ words[index - 6]
            )
        words1 = [words[index] ^ words[index + 4] for index in range(64)]
        a, b, c, d, e, f, g, h = state
        for index in range(64):
            ss1 = _rotl((_rotl(a, 12) + e + _rotl(_tj(index), index)) & 0xFFFFFFFF, 7)
            ss2 = ss1 ^ _rotl(a, 12)
            tt1 = (_ff(a, b, c, index) + d + ss2 + words1[index]) & 0xFFFFFFFF
            tt2 = (_gg(e, f, g, index) + h + ss1 + words[index]) & 0xFFFFFFFF
            d = c
            c = _rotl(b, 9)
            b = a
            a = tt1
            h = g
            g = _rotl(f, 19)
            f = e
            e = _p0(tt2)
        compressed = (a, b, c, d, e, f, g, h)
        state = [left ^ right for left, right in zip(compressed, state, strict=True)]
    return b"".join(word.to_bytes(4, "big") for word in state)


def sm3_password(password: str) -> str:
    return sm3(password.encode("utf-8")).hex().upper()
