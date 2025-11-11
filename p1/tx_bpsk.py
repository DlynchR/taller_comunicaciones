#!/usr/bin/env python3
import numpy as np
import sounddevice as sd
from binascii import crc32
import argparse

def rrc_filter(beta, sps, num_symbols):
    N = num_symbols * sps
    t = np.arange(-N/2, N/2 + 1) / sps
    h = np.zeros_like(t)

    for i in range(len(t)):
        ti = t[i]
        if abs(ti) < 1e-10:
            h[i] = 1 - beta + (4*beta/np.pi)
        elif abs(abs(4*beta*ti) - 1) < 1e-10:
            h[i] = (beta/np.sqrt(2)) * (
                ((1+2/np.pi)*np.sin(np.pi/(4*beta))) +
                ((1-2/np.pi)*np.cos(np.pi/(4*beta)))
            )
        else:
            h[i] = (np.sin(np.pi*ti*(1-beta)) + 4*beta*ti*np.cos(np.pi*ti*(1+beta))) / \
                   (np.pi*ti*(1-(4*beta*ti)**2))
    return h / np.sqrt(np.sum(h*h))

parser = argparse.ArgumentParser()
parser.add_argument("input_file")
parser.add_argument("--fc", type=float, default=2000)
parser.add_argument("--baud", type=float, default=100)
args = parser.parse_args()

fs = 44100
fc = args.fc
baud = args.baud
sps = int(fs / baud)

# Leer archivo binario
with open(args.input_file, "rb") as f:
    data = f.read()

# Agregar CRC32
crc = crc32(data) & 0xffffffff
crc_bytes = crc.to_bytes(4, 'big')
payload = crc_bytes + data

# Convertir a bits
bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))

# BPSK (0->-1, 1->+1)
symbols = 2*bits - 1

# Upsampling
upsampled = np.zeros(len(symbols)*sps)
upsampled[::sps] = symbols

# Filtrado RRC
filt = rrc_filter(0.35, sps, 8)
baseband = np.convolve(upsampled, filt, mode='same')

# Modulación pasobanda
t = np.arange(len(baseband)) / fs
tx = baseband * np.cos(2*np.pi*fc*t)

# Preambulo (tono de sincronía)
preamble = 0.3*np.sin(2*np.pi*fc*t[:int(fs*0.6)])

signal = np.concatenate([preamble, tx])
signal /= np.max(np.abs(signal)) * 0.9

print("Transmitiendo...")
sd.play(signal, fs)
sd.wait()
print("Listo.")
