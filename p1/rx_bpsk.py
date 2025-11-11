import numpy as np
import sounddevice as sd
import scipy.signal as signal
import argparse
from hashlib import crc32

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

def bits_to_bytes(bits):
    pad = (-len(bits))%8
    if pad: bits = np.concatenate([bits, np.zeros(pad)])
    return np.packbits(bits.astype(np.uint8)).tobytes()

def parse_frame(bits):
    pre = np.tile([1,0],32)
    # Buscar preámbulo por correlación
    corr = np.correlate(bits, pre, mode='valid')
    start = np.argmax(corr)
    bits = bits[start+64:]
    header = bits[:64]
    header_bytes = bits_to_bytes(header)
    length = int.from_bytes(header_bytes[:4],'big')
    crc_rx = int.from_bytes(header_bytes[4:8],'big')
    data_bits = bits[64:64+length*8]
    payload = bits_to_bytes(data_bits)
    ok = (crc32(payload)&0xffffffff)==crc_rx
    return payload, ok

parser = argparse.ArgumentParser()
parser.add_argument("outfile")
parser.add_argument("--fc", type=float, default=2000.0)
parser.add_argument("--fs", type=int, default=44100)
parser.add_argument("--baud", type=float, default=100.0)
parser.add_argument("--duration", type=float, default=6.0)
args = parser.parse_args()

print("Grabando...")
rec = sd.rec(int(args.duration*args.fs), samplerate=args.fs, channels=1)
sd.wait()
rec = rec.flatten()

sps = int(args.fs//args.baud)
filt = rrc(0.35, sps)
t = np.arange(len(rec))/args.fs
i = rec * np.cos(2*np.pi*args.fc*t)

mf = np.convolve(i, filt[::-1], mode='same')
samples = mf[sps//2::sps]
bits = (samples>0).astype(np.uint8)

payload, ok = parse_frame(bits)

if ok:
    with open(args.outfile,"wb") as f:
        f.write(payload)
    print("Archivo recibido correctamente:", args.outfile)
else:
    print("Error: CRC no coincide (datos corruptos o SNR bajo)")
