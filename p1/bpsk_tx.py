import numpy as np
import os
from digital_passband_modulator import (
    file_to_bits, encode_data_simple, bpsk_modulate, 
    generate_passband_signal, transmit_audio, save_audio, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL
)

def bpsk_transmit(file_path, carrier=CARRIER_FREQ, fs=FS):
    bits = file_to_bits(file_path)
    size = os.path.getsize(file_path)
    extension = os.path.splitext(file_path)[1].replace('.', '')

    encoded = encode_data_simple(bits, size, extension)
    symbols = bpsk_modulate(encoded)
    passband = generate_passband_signal(symbols, carrier, fs, SAMPLES_PER_SYMBOL)

    passband = 0.8 * passband / (np.max(np.abs(passband)) + 1e-12)
    transmit_audio(passband, fs)
    save_audio("bpsk_modulated.wav", passband, fs)
    print(f"✅ Archivo '{file_path}' modulado y transmitido con BPSK.")

if __name__ == "__main__":
    archivo = input("Ruta del archivo a transmitir (.txt o .jpg): ")
    bpsk_transmit(archivo)
