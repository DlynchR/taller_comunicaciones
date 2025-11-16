# test_protocol.py
from digital_passband_modulator_fsk import encode_data_simple, decode_data_simple, PREAMBLE_BITS, POSTAMBLE_BITS
from digital_passband_modulator_fsk import bytes_to_bits, bits_to_bytes

mensaje = "Hola mundo digital BPSK!"
bits = []
for c in mensaje.encode("utf-8"):
    for i in range(8):
        bits.append((c >> (7 - i)) & 1)

encoded = encode_data_simple(bits, len(mensaje.encode('utf-8')), "txt")

print(f"Mensaje original: {mensaje}")
print(f"Bits del mensaje: {len(bits)}")
print(f"Bits totales codificados: {len(encoded)}")

# Chequear preámbulo y postámbulo
print("Comienza con preámbulo?:", encoded[:len(PREAMBLE_BITS)] == PREAMBLE_BITS)
print("Termina con postámbulo?:", encoded[-len(POSTAMBLE_BITS):] == POSTAMBLE_BITS)

# --- Decodificar ---
decoded_bits, original_size, ext = decode_data_simple(encoded)
if decoded_bits is None:
    print("\n❌ Error: no se pudo decodificar.")
else:
    data_bytes = bits_to_bytes(decoded_bits)
    print(f"\n✅ Decodificación exitosa: extensión .{ext}, tamaño {original_size} bytes")
    print("Contenido recuperado:", data_bytes.decode("utf-8"))
