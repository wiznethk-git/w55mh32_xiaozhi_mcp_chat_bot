import random
def uuid4():
    # Generate 16 random bytes
    b = bytearray(random.getrandbits(8) for _ in range(16))
    # Set version (4) and variant bits according to RFC 4122
    b[6] = (b[6] & 0x0f) | 0x40
    b[8] = (b[8] & 0x3f) | 0x80
    return '{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}'.format(*b)
