#!/usr/bin/env python3
"""Common utilities for simple acoustic BPSK file transfer.

Design goals:
- Self‑contained (only numpy, pyaudio, soundfile, scipy.signal, zlib).
- Robust framing: PREAMBLE | HEADER | PAYLOAD | CRC32
  * PREAMBLE: 32 bits: 0xA5A55A5A (alternating pattern for clock + energy)
  * HEADER:
      - 16 bits: payload length in bytes (unsigned)
      - 8 bits: file extension length (n)
      - n*8 bits: ASCII lower-case file extension (e.g. 'txt','jpg','png')
  * PAYLOAD: raw file bytes
  * CRC32: 32 bits little endian of PAYLOAD bytes
- BPSK parameters configurable.

Signal chain TX:
  bytes -> bits -> map {0,1} -> symbols {-1,+1} -> rectangular pulse shaping -> carrier cos -> float32 audio

RX:
  audio -> carrier mix -> integrate & dump -> symbol decisions -> bits -> parse frame -> file.

Edge cases considered:
- Short recordings (abort early)
- Missing preamble (return None)
- CRC mismatch (report error)
- Extension length sanity limit (<=8)
- Payload length sanity (<= MAX_PAYLOAD_BYTES)

"""
from __future__ import annotations
import numpy as np
import scipy.signal as signal
import soundfile as sf
import pyaudio
import zlib
import time
from dataclasses import dataclass

# -------- Parameters ---------
FS = 44100                 # sample rate (Hz)
CARRIER_FREQ = 6000        # acoustic carrier (Hz) – keep well below Nyquist
SYMBOL_RATE = 100          # symbols per second (keep low for reliability)
SAMPLES_PER_SYMBOL = FS // SYMBOL_RATE
PREAMBLE = 0xA5A55A5A
PREAMBLE_BITS = 32
MAX_EXTENSION_LEN = 8
MAX_PAYLOAD_BYTES = 65535  # matches 16-bit length field
ENERGY_THRESHOLD = 0.02

@dataclass
class BPSKConfig:
    fs: int = FS
    carrier: float = CARRIER_FREQ
    symbol_rate: int = SYMBOL_RATE
    samples_per_symbol: int = SAMPLES_PER_SYMBOL

# -------- Bit & framing helpers ---------

def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))

def bits_to_bytes(bits: np.ndarray) -> bytes:
    # pad to multiple of 8
    if len(bits) % 8:
        bits = np.concatenate([bits, np.zeros(8 - len(bits)%8, dtype=np.uint8)])
    return np.packbits(bits).tobytes()

def build_frame(payload: bytes, extension: str) -> np.ndarray:
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError("Payload too large")
    ext = extension.lower().strip('.')
    if len(ext) == 0:
        ext = 'bin'
    if len(ext) > MAX_EXTENSION_LEN:
        raise ValueError("Extension too long")
    # header
    length_field = len(payload).to_bytes(2, 'little')
    ext_len_field = len(ext).to_bytes(1, 'little')
    header = length_field + ext_len_field + ext.encode('ascii')
    crc32 = zlib.crc32(payload) & 0xFFFFFFFF
    frame_bytes = PREAMBLE.to_bytes(4, 'big') + header + payload + crc32.to_bytes(4, 'little')
    bits = bytes_to_bits(frame_bytes)
    return bits.astype(np.uint8)

def parse_frame(bits: np.ndarray):
    # search preamble (convert bits to bytes gradually)
    if len(bits) < (PREAMBLE_BITS + 16 + 8 + 32):
        return None, "Too few bits"
    # sliding window to find preamble pattern 0xA5A55A5A
    preamble_bytes = PREAMBLE.to_bytes(4, 'big')
    # convert bits to bytes for scanning
    raw_bytes = bits_to_bytes(bits)
    idx = raw_bytes.find(preamble_bytes)
    if idx == -1:
        return None, "Preamble not found"
    pos_bits = idx * 8 + PREAMBLE_BITS  # position after preamble bits
    # Need at least header
    if len(bits) < pos_bits + (16 + 8):
        return None, "Incomplete header"
    # Re-extract from byte offset for simplicity
    frame_after = raw_bytes[idx+4:]  # skip preamble bytes
    if len(frame_after) < 3:
        return None, "Incomplete header 2"
    payload_len = int.from_bytes(frame_after[0:2], 'little')
    ext_len = frame_after[2]
    if ext_len == 0 or ext_len > MAX_EXTENSION_LEN:
        return None, "Bad extension length"
    needed = 2 + 1 + ext_len + payload_len + 4
    if len(frame_after) < needed:
        return None, "Incomplete payload"
    ext = frame_after[3:3+ext_len].decode('ascii', errors='ignore')
    payload = frame_after[3+ext_len:3+ext_len+payload_len]
    crc_recv = int.from_bytes(frame_after[3+ext_len+payload_len:3+ext_len+payload_len+4], 'little')
    crc_calc = zlib.crc32(payload) & 0xFFFFFFFF
    if crc_calc != crc_recv:
        return None, f"CRC mismatch calc={crc_calc:08X} recv={crc_recv:08X}"
    return {"extension": ext, "payload": payload}, None

# -------- Modulation / Demodulation ---------

def bits_to_symbols(bits: np.ndarray) -> np.ndarray:
    return 2*bits.astype(np.float32) - 1.0  # 0->-1, 1->+1 (or inverse, choose consistent)

def symbols_to_bits(symbols: np.ndarray) -> np.ndarray:
    return (symbols > 0).astype(np.uint8)

def pulse_shape(symbols: np.ndarray, samples_per_symbol: int) -> np.ndarray:
    return np.repeat(symbols, samples_per_symbol)

def modulate(bits: np.ndarray, cfg: BPSKConfig) -> np.ndarray:
    symbols = bits_to_symbols(bits)
    baseband = pulse_shape(symbols, cfg.samples_per_symbol)
    t = np.arange(len(baseband)) / cfg.fs
    carrier = np.cos(2*np.pi*cfg.carrier*t)
    tx = baseband * carrier
    # simple amplitude normalization
    tx = 0.8 * tx / (np.max(np.abs(tx)) + 1e-12)
    return tx.astype(np.float32)

def demodulate(rx: np.ndarray, cfg: BPSKConfig) -> np.ndarray:
    """Demodulate BPSK and perform simple timing/polarity search using preamble bytes.

    Tries all symbol offsets in [0..SPS-1], and both polarities, returning the bit
    sequence for the best candidate (first preamble hit; otherwise the one with
    maximal correlation to preamble bytes).
    """
    # Mix down
    t = np.arange(len(rx)) / cfg.fs
    carrier = np.cos(2*np.pi*cfg.carrier*t)
    mixed = rx * carrier * 2.0
    # Low-pass: rectangular matched filter
    sps = cfg.samples_per_symbol
    kernel = np.ones(sps)
    filtered = np.convolve(mixed, kernel, mode='same') / sps

    # Prepare reference preamble bytes
    preamble_bytes = PREAMBLE.to_bytes(4, 'big')

    best_bits = None
    best_score = -1

    # Try each symbol offset
    for off in range(sps):
        # sample symbol stream
        n_symbols = (len(filtered) - off) // sps
        if n_symbols <= 64:
            continue
        sample_points = off + (np.arange(n_symbols) * sps) + sps//2
        sample_points = sample_points[(sample_points >= 0) & (sample_points < len(filtered))]
        sym_vals = filtered[sample_points]

        for polarity in (1.0, -1.0):
            bits = symbols_to_bits(polarity * sym_vals)
            raw = bits_to_bytes(bits)
            idx = raw.find(preamble_bytes)
            score = (len(raw) - idx) if idx >= 0 else 0
            # keep if found or better score
            if idx >= 0:
                return bits  # early return on success
            if score > best_score:
                best_score = score
                best_bits = bits

    return best_bits if best_bits is not None else np.array([], dtype=np.uint8)

# -------- Audio I/O helpers ---------

def play_audio(sig: np.ndarray, fs: int):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
    stream.write(sig.astype(np.float32).tobytes())
    stream.stop_stream(); stream.close(); p.terminate()


def record_audio(duration: float, fs: int) -> np.ndarray:
    p = pyaudio.PyAudio()
    frames = []
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=1024)
    total = int(duration * fs)
    collected = 0
    while collected < total:
        data = stream.read(min(1024, total-collected), exception_on_overflow=False)
        chunk = np.frombuffer(data, dtype=np.float32)
        frames.append(chunk)
        collected += len(chunk)
    stream.stop_stream(); stream.close(); p.terminate()
    return np.concatenate(frames)


def save_wav(path: str, sig: np.ndarray, fs: int):
    sf.write(path, sig, fs)


def load_wav(path: str, target_fs: int | None = None):
    data, fs = sf.read(path)
    if data.ndim > 1:
        data = data.mean(axis=1)
    if target_fs and target_fs != fs:
        num = int(len(data) * target_fs / fs)
        data = signal.resample(data, num)
        fs = target_fs
    return data.astype(np.float32), fs

# -------- Convenience high-level ---------

def build_signal_from_file(path: str, cfg: BPSKConfig) -> tuple[np.ndarray, dict]:
    with open(path, 'rb') as f:
        payload = f.read()
    ext = path.split('.')[-1] if '.' in path else 'bin'
    bits = build_frame(payload, ext)
    sig = modulate(bits, cfg)
    meta = {"bits": len(bits), "payload_bytes": len(payload)}
    return sig, meta


def recover_file_from_signal(rx_sig: np.ndarray, cfg: BPSKConfig):
    bits = demodulate(rx_sig, cfg)
    frame, err = parse_frame(bits)
    if frame is None:
        return None, err
    return frame, None

if __name__ == "__main__":
    cfg = BPSKConfig()
    print("Self-test: building signal for dummy bytes...")
    dummy = b"Hello BPSK";
    bits = build_frame(dummy, 'txt')
    sig = modulate(bits, cfg)
    # add noise
    noisy = sig + 0.02*np.random.randn(len(sig)).astype(np.float32)
    rec_bits = demodulate(noisy, cfg)
    frame, err = parse_frame(rec_bits)
    if frame:
        print("Recovered payload:", frame['payload'])
    else:
        print("Error:", err)
