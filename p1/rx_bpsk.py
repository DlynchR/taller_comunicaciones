#!/usr/bin/env python3
"""
rx_bpsk.py
Receptor BPSK que graba por micrófono, demodula y reconstruye el archivo.
Uso: python rx_bpsk.py <duración_en_segundos> <archivo_salida.bin>
Ej: python rx_bpsk.py 10 recibido.bin
Requiere: numpy, scipy, sounddevice
"""

import sys
import numpy as np
import sounddevice as sd
from scipy import signal
import zlib

# ==========================
FS = 44100
CARRIER = 2000.0
BAUD = 200.0
SAMPLES_PER_SYMBOL = int(FS / BAUD)
PREAMBLE_BITS = np.tile([1,0], 64)
HEADER_FMT = "{:016d}:{:08x}:"
# ==========================

def record(duration_s, fs):
    print(f"Grabando {duration_s:.1f} s...")
    data = sd.rec(int(duration_s * fs), samplerate=fs, channels=1, dtype='float32')
    sd.wait()
    return data.flatten()

def bandpass(sig, fs, fc, bw=1200):
    nyq = fs/2
    low = max(0.1, (fc - bw/2)/nyq)
    high = min(0.999, (fc + bw/2)/nyq)
    b,a = signal.butter(4, [low, high], btype='band')
    return signal.lfilter(b,a,sig)

def demodulate_bpsk(rx, carrier_freq, fs):
    t = np.arange(len(rx)) / fs
    # multiplicar por referencia en fase 0 (cos)
    ref = np.cos(2*np.pi*carrier_freq*t)
    product = rx * ref
    # filtro pasa bajos para recuperar baseband
    b,a = signal.butter(6,  (carrier_freq/2) / (fs/2), btype='low')
    baseband = signal.lfilter(b,a,product)
    return baseband

def symbol_sampling(baseband, sps):
    # promediado por símbolo (matched filter rectangular)
    n_symbols = len(baseband) // sps
    baseband = baseband[:n_symbols*sps]
    reshaped = baseband.reshape((n_symbols, sps))
    # tomar suma/mean como estadístico
    sym = reshaped.mean(axis=1)
    return sym

def correlate_preamble(sym_samples, preamble_symbols):
    # preamble_symbols deben ser NRZ bipolar (+1/-1)
    # usar correlación cruzada para encontrar posición
    corr = np.correlate(sym_samples, preamble_symbols, mode='valid')
    peak_idx = np.argmax(np.abs(corr))
    peak_val = corr[peak_idx]
    return peak_idx, peak_val

def bits_from_symbols(sym):
    # signo: >=0 -> 1, <0 -> 0
    bits = (sym >= 0).astype(np.uint8)
    return bits

def parse_header_bits(bits_seq):
    # encontrar el primer ':' después de 16+8*? pero header fue ascii bits directo
    # convert bits to bytes and search for separator ':'
    b = np.packbits(bits_seq)
    try:
        s = b.tobytes().decode('ascii', errors='ignore')
    except:
        s = ""
    # intentar extraer pattern numbits:crc:
    # buscamos la primer ocurrencia de ':' y luego otra
    parts = s.split(':')
    if len(parts) >= 3:
        try:
            num_bits = int(parts[0])
            crc_hex = parts[1]
            crc = int(crc_hex, 16)
            header_len_bytes = len((parts[0]+":"+parts[1]+":").encode('ascii'))
            header_len_bits = header_len_bytes * 8
            return num_bits, crc, header_len_bits
        except:
            return None
    return None

def save_bits_to_file(bits, outpath):
    # recorta a múltiplos de 8
    nbytes = len(bits) // 8
    bits = bits[:nbytes*8]
    data = np.packbits(bits).tobytes()
    with open(outpath, "wb") as f:
        f.write(data)

def main():
    if len(sys.argv) < 3:
        print("Uso: python rx_bpsk.py <duracion_s> <archivo_salida.bin>")
        sys.exit(1)
    duration = float(sys.argv[1])
    outpath = sys.argv[2]

    rx = record(duration, FS)
    # opcional: filtrar banda cercana a la portadora
    rx_bp = bandpass(rx, FS, CARRIER, bw=2000)

    baseband = demodulate_bpsk(rx_bp, CARRIER, FS)

    # Downsample a símbolo
    sym = symbol_sampling(baseband, SAMPLES_PER_SYMBOL)

    # correlacion con preámbulo (NRZ bipolar)
    preamble_symbols = 2*PREAMBLE_BITS - 1
    idx, val = correlate_preamble(sym, preamble_symbols)
    print(f"Pico de correlación en símbolo {idx} (valor {val:.1f})")

    # tomar desde idx + len(preamble) => header luego payload
    start_sym = idx + len(preamble_symbols)
    remaining = sym[start_sym:]
    bits = bits_from_symbols(remaining)

    # intentar parsear header a partir del inicio de bits
    # convertimos a bytes y tratamos de encontrar header ascii
    # para robustez probamos varias offsets (0..7)
    parsed = None
    for off in range(8):
        seq = bits[off:]
        parsed = parse_header_bits(seq)
        if parsed:
            num_bits, crc, header_len_bits = parsed
            header_bits_consumed = header_len_bits
            data_bits = seq[header_bits_consumed: header_bits_consumed + num_bits]
            print(f"Header parseado: num_bits={num_bits}, crc=0x{crc:08x}, offset={off}")
            # calcular crc del payload
            payload_bytes = np.packbits(data_bits).tobytes()
            crc_calc = zlib.crc32(payload_bytes) & 0xFFFFFFFF
            if crc_calc == crc:
                print("CRC OK")
            else:
                print(f"CRC MISMATCH: calculado=0x{crc_calc:08x} (esperado 0x{crc:08x})")
            save_bits_to_file(data_bits, outpath)
            print(f"Datos guardados en {outpath}")
            return

    print("No se pudo parsear header correctamente. Intentando guardar todo lo decodificado.")
    # si no se pudo parsear, guardamos todo lo demodulado
    save_bits_to_file(bits, outpath)
    print(f"Guardado como {outpath} (sin header válido).")

if __name__ == "__main__":
    main()
