from PIL import Image

MAGIC = b"GUY"
BITS_PER_CHANNEL = 3

def _bytes_to_bits(data):
    bits = []
    for byte in data:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    return bits

def _bits_to_bytes(bits):
    out = []
    for i in range(0, len(bits) - 7, 8):
        byte = 0
        for b in bits[i:i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)

def embed(cover_path, payload: bytes, out_path):
    img = Image.open(cover_path).convert("RGB")
    pixels = list(img.getdata())
    stream = MAGIC + len(payload).to_bytes(4, "big") + payload
    bits = _bytes_to_bits(stream)

    capacity = len(pixels) * 3 * BITS_PER_CHANNEL
    if len(bits) > capacity:
        raise ValueError(f"too small: need {len(bits)} bits, have {capacity}")

    new_pixels = []
    bit_index = 0
    for (r, g, b) in pixels:
        chans = [r, g, b]
        for i in range(3):
            chunk = 0
            for _ in range(BITS_PER_CHANNEL):
                bit = bits[bit_index] if bit_index < len(bits) else 0
                chunk = (chunk << 1) | bit
                bit_index += 1
            chans[i] = ((chans[i] >> BITS_PER_CHANNEL) << BITS_PER_CHANNEL) | chunk
        new_pixels.append(tuple(chans))
    img.putdata(new_pixels)
    img.save(out_path, "PNG")
    return out_path

def extract(stego_path):
    img = Image.open(stego_path).convert("RGB")
    bits = []
    for px in img.getdata():
        for c in px:
            for shift in range(BITS_PER_CHANNEL - 1, -1, -1):
                bits.append((c >> shift) & 1)

    magic_len = len(MAGIC)
    header_bits = (magic_len + 4) * 8
    head = _bits_to_bytes(bits[:header_bits])
    if head[:magic_len] != MAGIC:
        return None
    length = int.from_bytes(head[magic_len:magic_len + 4], "big")
    return _bits_to_bytes(bits[header_bits:header_bits + length * 8])

def append_after_marker(cover_path, payload, out_path, marker):
    with open(cover_path, "rb") as f:
        cover_data = f.read()
    idx = cover_data.find(marker)
    if idx == -1:
        raise ValueError("cover file has no recognizable end marker")
    idx += len(marker)
    with open(out_path, "wb") as f:
        f.write(cover_data[:idx] + payload)
    return out_path

def extract_after_marker(stego_path, marker):
    with open(stego_path, "rb") as f:
        data = f.read()
    idx = data.find(marker)
    if idx == -1:
        return None
    payload = data[idx + len(marker):]
    return payload if payload else None