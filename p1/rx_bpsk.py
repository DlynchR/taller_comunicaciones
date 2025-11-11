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
parser.add_argument("output_file")
parser.add_argument("--fc", type=float, default=2000)
parser.add_argument("--baud", type=float, default=100)
parser.add_argument("--duration", type=float, default=6)
args = parser.parse_args()

fs = 44100
fc = args.fc
baud = args.baud
sps = int(fs / baud)

print("Grabando...")
rec = sd.rec(int(args.duration*fs), fs, channels=1)
sd.wait()
rx = rec[:,0]

# Detectar inicio por energía
energy = np.abs(rx)
th = np.max(energy)*0.25
start = np.argmax(energy > th)
rx = rx[start:]

# Demodulación
t = np.arange(len(rx))/fs
baseband = rx * np.cos(2*np.pi*fc*t)

filt = rrc_filter(0.35, sps, 8)
filtered = np.convolve(baseband, filt, 'same')

samples = filtered[::sps]
bits = (samples > 0).astype(np.uint8)

# Reconstruir bytes
data = np.packbits(bits)
crc_rx = int.from_bytes(data[:4], 'big')
payload = data[4:]

if (crc32(payload) & 0xffffffff) == crc_rx:
    print("Archivo recibido correctamente ✅")
    with open(args.output_file, "wb") as f:
        f.write(payload)
else:
    print("Advertencia: CRC inválido ❌ Archivo puede estar dañado.")
    with open(args.output_file, "wb") as f:
        f.write(payload)
