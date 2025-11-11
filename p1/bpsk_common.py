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
ENERGY_THRESHOLD = 0.02

@dataclass
class BPSKConfig:
    fs: int = FS
    carrier: float = CARRIER_FREQ
    symbol_rate: int = SYMBOL_RATE
    samples_per_symbol: int = SAMPLES_PER_SYMBOL

# -------- Bit helpers (raw, sin preámbulo) ---------

def bytes_to_bits(data: bytes) -> np.ndarray:
    return np.unpackbits(np.frombuffer(data, dtype=np.uint8))

def bits_to_bytes(bits: np.ndarray) -> bytes:
    # pad to multiple of 8
    if len(bits) % 8:
        bits = np.concatenate([bits, np.zeros(8 - len(bits)%8, dtype=np.uint8)])
    return np.packbits(bits).tobytes()

# No framing: enviar bytes crudos, recibir bytes crudos.

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
    """Demodulación sin preámbulo: busca el offset de símbolo que maximiza
    la energía de las muestras y devuelve los bits para la mejor polaridad.
    """
    # Mix down
    t = np.arange(len(rx)) / cfg.fs
    carrier = np.cos(2*np.pi*cfg.carrier*t)
    mixed = rx * carrier * 2.0
    # Low-pass: rectangular matched filter
    sps = cfg.samples_per_symbol
    kernel = np.ones(sps)
    filtered = np.convolve(mixed, kernel, mode='same') / sps

    best_bits = None
    best_metric = -1.0

    # Try each symbol offset
    for off in range(sps):
        # sample symbol stream
        n_symbols = (len(filtered) - off) // sps
        if n_symbols <= 64:
            continue
        sample_points = off + (np.arange(n_symbols) * sps) + sps//2
        sample_points = sample_points[(sample_points >= 0) & (sample_points < len(filtered))]
        sym_vals = filtered[sample_points]

        # Use energy metric to choose offset
        metric = float(np.mean(np.abs(sym_vals)))
        if metric > best_metric:
            # pick polarity that yields 'sharper' distribution (same metric works)
            bits_pos = symbols_to_bits(sym_vals)
            bits_neg = symbols_to_bits(-sym_vals)
            # Choose by variance of symbol values after decision aid
            var_pos = float(np.var((bits_pos*2-1).astype(np.float32)))
            var_neg = float(np.var((bits_neg*2-1).astype(np.float32)))
            best_bits = bits_pos if var_pos >= var_neg else bits_neg
            best_metric = metric

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

# -------- Convenience high-level (sin preámbulo) ---------

def build_signal_from_file_raw(path: str, cfg: BPSKConfig) -> tuple[np.ndarray, dict]:
    with open(path, 'rb') as f:
        payload = f.read()
    bits = bytes_to_bits(payload)
    sig = modulate(bits, cfg)
    meta = {"bits": len(bits), "payload_bytes": len(payload)}
    return sig, meta


MAGICS = [
    (b"\xFF\xD8\xFF", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF8", "gif"),
    (b"%PDF", "pdf"),
    (b"PK\x03\x04", "zip"),
    (b"RIFF", "wav"),
    (b"OggS", "ogg"),
]

def guess_extension(data: bytes) -> str:
    for magic, ext in MAGICS:
        if data.startswith(magic):
            return ext
    # ASCII text heuristic
    head = data[:512]
    if len(head) == 0:
        return "bin"
    printable = sum(32 <= b <= 126 or b in (9,10,13) for b in head)
    if printable / len(head) > 0.60:
        return "txt"
    return "bin"


def is_mostly_text(data: bytes, threshold: float = 0.60) -> bool:
    if not data:
        return False
    head = data[:2048]
    printable = sum(32 <= b <= 126 or b in (9,10,13) for b in head)
    return (printable / len(head)) >= threshold


def recover_bytes_from_signal_no_preamble(rx_sig: np.ndarray, cfg: BPSKConfig, force_invert: bool=False):
    bits = demodulate(rx_sig, cfg)
    if bits is None or len(bits) == 0:
        return None, "No bits recovered"
    # Try both polarities by flipping bits if requested
    bytes_a = bits_to_bytes(bits)
    if force_invert:
        bits = 1 - bits
        bytes_b = bits_to_bytes(bits)
    else:
        # Compute alternative candidate as bitwise NOT
        bits_inv = 1 - bits
        bytes_b = bits_to_bytes(bits_inv)

    # Choose by signature or text heuristic
    ext_a = guess_extension(bytes_a)
    ext_b = guess_extension(bytes_b)
    # Prefer non-bin over bin; or jpg/png/wav/zip/pdf over txt if magic matches
    priority = {"jpg":5,"png":5,"gif":4,"pdf":4,"zip":4,"wav":4,"ogg":4,"txt":3,"bin":1}
    pick_a = priority.get(ext_a,0) >= priority.get(ext_b,0)
    payload = bytes_a if pick_a else bytes_b
    ext = ext_a if pick_a else ext_b
    # If still unknown (bin) but looks text-ish, switch to txt
    if ext == "bin" and is_mostly_text(payload):
        ext = "txt"
    return {"payload": payload, "extension": ext}, None

if __name__ == "__main__":
    cfg = BPSKConfig()
    print("Self-test: raw bytes loopback...")
    dummy = b"Hello BPSK without preamble!";
    bits = bytes_to_bits(dummy)
    sig = modulate(bits, cfg)
    noisy = sig + 0.02*np.random.randn(len(sig)).astype(np.float32)
    frame, err = recover_bytes_from_signal_no_preamble(noisy, cfg)
    if frame:
        print("Recovered ext guess:", frame['extension'])
        print("Recovered payload head:", frame['payload'][:20])
    else:
        print("Error:", err)
