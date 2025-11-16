# digital_passband_modulator_fsk.py
# 2-FSK passband transmitter & receiver for audio channel
import numpy as np
import scipy.signal as signal
import soundfile as sf
import pyaudio
import struct, binascii, os
from typing import List, Tuple
import matplotlib.pyplot as plt

# Parámetros
FS = 44100
BAUD_RATE = 500
SAMPLES_PER_SYMBOL = FS // BAUD_RATE
FREQ_0 = 7000.0   # FSK freq for bit 0
FREQ_1 = 10000.0  # FSK freq for bit 1
START_TONE_FREQ = 1100.0
STOP_TONE_FREQ = 2200.0
HANDSHAKE_DURATION = 0.5
TX_AMPLITUDE = 0.8

# Protocolo
PREAMBLE_BITS = [1,0]*16
POSTAMBLE_BITS = PREAMBLE_BITS[::-1]

# Utils bits/bytes
def bytes_to_bits(data: bytes) -> List[int]:
    bits = []
    for b in data:
        for i in range(8):
            bits.append((b >> (7-i)) & 1)
    return bits

def bits_to_bytes(bits: List[int]) -> bytes:
    padding = (8 - (len(bits) % 8)) % 8
    bits = bits + [0]*padding
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            byte = (byte<<1) | (bits[i+j] & 1)
        out.append(byte)
    return bytes(out)

def file_to_bits(path: str) -> List[int]:
    with open(path, 'rb') as f:
        return bytes_to_bits(f.read())

def bits_to_file(bits: List[int], path: str):
    with open(path, 'wb') as f:
        f.write(bits_to_bytes(bits))

# CRC32
def crc32_bits(bits: List[int]) -> List[int]:
    b = bits_to_bytes(bits)
    crc = binascii.crc32(b) & 0xffffffff
    return bytes_to_bits(struct.pack(">I", crc))

def check_crc32(bits: List[int], crc_bits: List[int]) -> bool:
    return crc32_bits(bits)[:32] == crc_bits[:32]

# Framing
def encode_frame(payload_bits: List[int], original_size: int) -> List[int]:
    size_bits = bytes_to_bits(struct.pack(">I", original_size))
    crc = crc32_bits(payload_bits)
    frame = PREAMBLE_BITS + size_bits + crc + payload_bits + POSTAMBLE_BITS
    return frame

def decode_frame(bits: List[int]) -> Tuple[List[int], int]:
    rb = np.array(bits, dtype=int)
    pre = np.array(PREAMBLE_BITS, dtype=int)
    # map to +-1
    rbm = 2*rb - 1
    prem = 2*pre - 1
    corr = np.abs(np.convolve(rbm, prem[::-1], mode='valid'))
    if len(corr)==0:
        return None, None
    idx = int(np.argmax(corr))
    if corr[idx] < 0.8*len(pre):
        return None, None
    start = idx + len(pre)
    if start+64 > len(rb):
        return None, None
    size_bits = rb[start:start+32].tolist()
    crc_bits = rb[start+32:start+64].tolist()
    try:
        original_size = struct.unpack(">I", bits_to_bytes(size_bits))[0]
    except Exception:
        return None, None
    payload_start = start+64
    payload_end = payload_start + original_size*8
    if payload_end > len(rb):
        payload_bits = rb[payload_start:].tolist()
    else:
        payload_bits = rb[payload_start:payload_end].tolist()
    if not check_crc32(payload_bits, crc_bits):
        return None, None
    return payload_bits, original_size

# FSK modulation (passband)
def fsk_modulate(bits: List[int], fs=FS, f0=FREQ_0, f1=FREQ_1) -> np.ndarray:
    samples = []
    for b in bits:
        f = f1 if b==1 else f0
        t = np.arange(SAMPLES_PER_SYMBOL) / fs
        sym = np.sin(2*np.pi*f*t)
        samples.append(sym)
    tx = np.concatenate(samples)
    if np.max(np.abs(tx))>0:
        tx = TX_AMPLITUDE * tx / np.max(np.abs(tx))
    return tx.astype(np.float32)

def generate_start_stop_tone(freq, duration=HANDSHAKE_DURATION, fs=FS):
    t = np.arange(int(duration*fs)) / fs
    return 0.9 * np.sin(2*np.pi*freq*t).astype(np.float32)

# Transmit (play or save wav)
def save_wav(path: str, sig: np.ndarray, fs=FS):
    sf.write(path, sig.astype(np.float32), fs)
    print("Saved WAV:", path)

def play_audio(signal: np.ndarray, fs=FS):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
    stream.write(signal.tobytes())
    stream.stop_stream(); stream.close(); p.terminate()

def transmit_file_fsk(path: str, fs=FS, f0=FREQ_0, f1=FREQ_1, play=True, out_wav=None):
    size = os.path.getsize(path)
    payload = file_to_bits(path)
    frame = encode_frame(payload, size)
    tx_bb = fsk_modulate(frame, fs=fs, f0=f0, f1=f1)
    start_tone = generate_start_stop_tone(START_TONE_FREQ, fs=fs)
    stop_tone = generate_start_stop_tone(STOP_TONE_FREQ, fs=fs)
    full = np.concatenate([start_tone, np.zeros(int(0.05*fs)), tx_bb, np.zeros(int(0.05*fs)), stop_tone])
    if out_wav:
        save_wav(out_wav, full, fs)
    if play:
        play_audio(full, fs)
    return full

# Goertzel detector for a single frequency on a window
def goertzel_power(x: np.ndarray, fs:int, freq: float) -> float:
    # compute power at freq using Goertzel
    k = int(0.5 + (len(x) * freq) / fs)
    w = (2*np.pi*k)/len(x)
    coeff = 2*np.cos(w)
    s0 = 0.0; s1 = 0.0; s2=0.0
    for n in range(len(x)):
        s0 = x[n] + coeff*s1 - s2
        s2 = s1; s1 = s0
    power = s1*s1 + s2*s2 - coeff*s1*s2
    return power

# Demodulate by sliding window per symbol (non-coherent)
def demodulate_fsk_from_signal(sig: np.ndarray, fs=FS, f0=FREQ_0, f1=FREQ_1, max_symbols=None) -> List[int]:
    # normalize
    x = sig.copy()
    if np.max(np.abs(x))>0:
        x = x / np.max(np.abs(x))
    n_sym = len(x)//SAMPLES_PER_SYMBOL if max_symbols is None else max_symbols
    bits = []
    for i in range(n_sym):
        window = x[i*SAMPLES_PER_SYMBOL:(i+1)*SAMPLES_PER_SYMBOL]
        if len(window)==0:
            break
        p0 = goertzel_power(window, fs, f0)
        p1 = goertzel_power(window, fs, f1)
        bits.append(1 if p1>p0 else 0)
    return bits

# Recording with tone trigger (same idea as before)
def record_audio_with_tone_trigger(fs=FS, chunk=1024, start_tone_freq=START_TONE_FREQ, stop_tone_freq=STOP_TONE_FREQ):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=chunk)
    print("Listening for start tone...")
    recording = False
    frames = []
    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            x = np.frombuffer(data, dtype=np.float32)
            # FFT
            X = np.fft.rfft(x * np.hanning(len(x)))
            P = np.abs(X)**2 + 1e-20
            freqs = np.fft.rfftfreq(len(x), 1/fs)
            def detect(freq):
                mask = np.abs(freqs - freq) < 30.0
                return P[mask].sum() / P.sum() > 0.3 if np.any(mask) else False
            if not recording:
                if detect(start_tone_freq):
                    recording = True
                    print("Start tone detected, recording...")
            else:
                frames.append(x.copy())
                if detect(stop_tone_freq):
                    print("Stop tone detected, stopping.")
                    break
    finally:
        stream.stop_stream(); stream.close(); p.terminate()
    if len(frames)==0:
        return None
    return np.concatenate(frames)

# Receive: demodulate recorded signal (expects recording that contains only the FSK block)
def receive_and_demodulate_fsk(recorded: np.ndarray, fs=FS, f0=FREQ_0, f1=FREQ_1) -> Tuple[List[int], np.ndarray]:
    # Attempt to find preamble by correlating energy envelope with preamble sequence
    # First demodulate entire recording into bits (may include extra samples)
    max_symbols = max(1, len(recorded)//SAMPLES_PER_SYMBOL)
    bits = demodulate_fsk_from_signal(recorded, fs=fs, f0=f0, f1=f1, max_symbols=max_symbols)
    return bits, recorded

# BER
def calculate_ber(original_bits: List[int], received_bits: List[int]) -> float:
    n = min(len(original_bits), len(received_bits))
    if n==0: return 0.0
    errors = sum(1 for i in range(n) if original_bits[i]!=received_bits[i])
    return errors / n

# Simple plotting helpers
def plot_time(sig, fs, title="Time"):
    t = np.arange(len(sig))/fs
    import matplotlib.pyplot as plt
    plt.figure(); plt.plot(t, sig); plt.title(title); plt.xlabel("s"); plt.grid(); plt.show()

def plot_spectrum(sig, fs, title="Spectrum"):
    N = len(sig)
    Y = np.fft.fft(sig)
    f = np.fft.fftfreq(N, 1/fs)
    import matplotlib.pyplot as plt
    plt.figure(); plt.plot(f[:N//2], np.abs(Y)[:N//2]); plt.title(title); plt.xlabel("Hz"); plt.grid(); plt.show()

if __name__ == "__main__":
    # Demo: modulate a short message and save WAV
    test = "fsk_test.bin"
    with open(test, "wb") as f:
        f.write(b"Hola FSK test")
    s = transmit_file_fsk(test, play=False, out_wav="tx_fsk_demo.wav")
    print("WAV generated: tx_fsk_demo.wav")
