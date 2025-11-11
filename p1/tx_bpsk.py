import numpy as np
import sounddevice as sd
import scipy.signal as signal
import argparse
from binascii import crc32

def bytes_to_bits(b):
    return np.unpackbits(np.frombuffer(b, dtype=np.uint8)).astype(np.uint8)

def make_frame(payload):
    preamble = np.tile([1,0], 32).astype(np.uint8)
    length = len(payload)
    crc = crc32(payload) & 0xffffffff
    header = length.to_bytes(4,'big') + crc.to_bytes(4,'big')
    header_bits = np.unpackbits(np.frombuffer(header, dtype=np.uint8))
    data_bits = bytes_to_bits(payload)
    return np.concatenate([preamble, header_bits, data_bits]).astype(np.uint8)

def rrc(beta, sps, N=6):
    t = np.arange(-N*sps, N*sps+1) / sps
    eps = 1e-8
    h = np.zeros_like(t)
    for i, ti in enumerate(t):
        if abs(ti) < eps:
            h[i] = 1 - beta + 4*beta/np.pi
        else:
            h[i] = (np.sin(np.pi*ti*(1-beta)) + 4*beta*ti*np.cos(np.pi*ti*(1+beta))) / (np.pi*ti*(1-(4*beta*ti)**2))
    h /= np.sqrt(np.sum(h**2))
    return h

def bpsk_mod(bits, baud, fs, fc):
    sps = int(fs//baud)
    symbols = 2*bits - 1
    up = np.repeat(symbols, sps)
    filt = rrc(0.35, sps)
    bb = np.convolve(up, filt, mode='same')
    t = np.arange(len(bb))/fs
    passband = bb * np.cos(2*np.pi*fc*t)
    passband /= np.max(np.abs(passband)) + 1e-12
    return passband, sps, filt

parser = argparse.ArgumentParser()
parser.add_argument("file")
parser.add_argument("--fc", type=float, default=2000.0)
parser.add_argument("--fs", type=int, default=44100)
parser.add_argument("--baud", type=float, default=100.0)
args = parser.parse_args()

with open(args.file,'rb') as f:
    payload = f.read()

frame = make_frame(payload)
tx, sps, filt = bpsk_mod(frame, args.baud, args.fs, args.fc)
print("Transmitiendo...")

sd.play(tx*0.8, samplerate=args.fs)
sd.wait()
print("Listo.")
