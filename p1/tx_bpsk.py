#!/usr/bin/env python3
"""
tx_bpsk.py
Transmisor BPSK por parlante para enviar archivos (txt/jpg/png...).
Uso: python tx_bpsk.py <ruta_al_archivo>
Requiere: numpy, scipy, sounddevice
"""

import sys
import numpy as np
import sounddevice as sd
from scipy import signal
import zlib
import os

# ==========================
# Parámetros (ajustables)
FS = 44100            # frecuencia de muestreo (Hz)
CARRIER = 2000.0      # frecuencia portadora (Hz)
BAUD = 100.0          # símbolos por segundo (baud)
SAMPLES_PER_SYMBOL = int(FS / BAUD)
PREAMBLE_BITS = np.tile([1,0], 64)  # preámbulo alternado para sincronía
HEADER_FMT = "{:016d}:{:08x}:"  # header = <num_bits(16)>:<crc32(8hex)>:
AMPLITUDE = 0.6       # amplitud máxima (0..1)
# ==========================

def file_to_bits(path):
    """Lee archivo binario y convierte a array de bits (0/1)."""
    with open(path, "rb") as f:
        data = f.read()
    bits = np.unpackbits(np.frombuffer(data, dtype=np.uint8))
    return bits, data

def bits_from_header(num_bits, crc):
    """Genera bits del header en ASCII para transmitir filename/long/etc si quieres."""
    hdr = HEADER_FMT.format(num_bits, crc)
    hdr_bytes = hdr.encode('ascii')
    hdr_bits = np.unpackbits(np.frombuffer(hdr_bytes, dtype=np.uint8))
    return hdr_bits

def pack_frame(bits, filename=None):
    """Crea la trama: preámbulo + header (n bits + crc) + bits + postamble (same pattern)"""
    crc = zlib.crc32(np.packbits(bits).tobytes()) & 0xFFFFFFFF
    header_bits = bits_from_header(len(bits), crc)
    frame = np.concatenate([PREAMBLE_BITS, header_bits, bits, PREAMBLE_BITS])
    return frame, crc

def bits_to_nrz_symbols(bits):
    """Convierte bits 0/1 a símbolos NRZ bipolar: 0 -> -1, 1 -> +1"""
    sym = np.zeros(len(bits), dtype=np.int8)
    current = 1
    for i, b in enumerate(bits):
        if b == 1:
            current = -current
        sym[i] = current
    return sym.astype(np.float32)

def pulse_shape(symbols, sps):
    """Upsample (hold) cada símbolo durante sps muestras (rectangular pulse)."""
    up = np.repeat(symbols, sps)
    # opcional: filtro raised-cosine o filtro lowpass para suavizar
    return up

def modulate_bpsk(baseband, carrier_freq, fs):
    t = np.arange(len(baseband)) / fs
    carrier = np.cos(2*np.pi*carrier_freq*t)
    return baseband * carrier

def normalize_and_play(signal_out, fs):
    # evita clipping y reproduce
    max_val = np.max(np.abs(signal_out))
    if max_val > 0:
        sig = signal_out * (AMPLITUDE / max_val)
    else:
        sig = signal_out
    sd.play(sig, fs)
    sd.wait()

def main():
    if len(sys.argv) < 2:
        print("Uso: python tx_bpsk.py <ruta_al_archivo>")
        sys.exit(1)

    path = sys.argv[1]
    bits, rawdata = file_to_bits(path)
    frame_bits, crc = pack_frame(bits, filename=os.path.basename(path))
    print(f"Transmitiendo {path} -> {len(bits)} bits, crc32=0x{crc:08x}")

    symbols = bits_to_nrz_symbols(frame_bits.astype(np.int8))
    baseband = pulse_shape(symbols, SAMPLES_PER_SYMBOL)

    # multiplicar por rampa de ventana para evitar clics al inicio/fin
    ramp_len = int(0.01 * FS)
    window = np.ones(len(baseband))
    if ramp_len*2 < len(window):
        window[:ramp_len] = np.linspace(0,1,ramp_len)
        window[-ramp_len:] = np.linspace(1,0,ramp_len)
    baseband = baseband * window

    tx = modulate_bpsk(baseband, CARRIER, FS)

    # opcional: filtrar fuera de banda
    # b,a = signal.butter(5, (CARRIER+1000)/(FS/2), btype='low')
    # tx = signal.lfilter(b,a,tx)

    normalize_and_play(tx, FS)
    print("Transmisión finalizada.")

if __name__ == "__main__":
    main()
