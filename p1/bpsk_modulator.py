# bpsk_modulator.py
import numpy as np
import scipy.signal as signal
import pyaudio

# --- Parámetros Generales ---
FS = 44100
CARRIER_FREQ = 8000
BAUD_RATE = 1000
SAMPLES_PER_SYMBOL = FS // BAUD_RATE


# ------------------------------------------------------------
# BPSK - Modulación / Demodulación
# ------------------------------------------------------------
def bpsk_modulate(bits):
    """Convierte bits (0/1) a símbolos BPSK (-1/+1)."""
    return np.array([1.0 if b else -1.0 for b in bits], dtype=np.float32)


def generate_passband_signal(symbols, carrier_freq=CARRIER_FREQ, fs=FS, samples_per_symbol=SAMPLES_PER_SYMBOL):
    """Genera una señal pasobanda (coseno modulada) a partir de símbolos BPSK."""
    t_symbol = np.linspace(0, 1/BAUD_RATE, samples_per_symbol, endpoint=False)
    waveform = []
    for sym in symbols:
        carrier = np.cos(2*np.pi*carrier_freq*t_symbol)
        waveform.append(sym * carrier)
    return np.concatenate(waveform).astype(np.float32)


def receive_and_demodulate_passband_signal(
    received_signal, carrier_freq=CARRIER_FREQ, fs=FS,
    samples_per_symbol=SAMPLES_PER_SYMBOL, num_symbols=None
):
    """Demodula una señal pasobanda BPSK y devuelve los símbolos muestreados."""
    if num_symbols is None:
        num_symbols = len(received_signal) // samples_per_symbol

    # Multiplicación coherente
    t = np.arange(len(received_signal)) / fs
    local_carrier = np.cos(2 * np.pi * carrier_freq * t)
    demodulated = received_signal * local_carrier

    # Filtro paso bajo (para obtener la banda base)
    nyq = fs / 2
    cutoff = min(BAUD_RATE * 1.2, nyq * 0.9)
    b, a = signal.butter(5, cutoff / nyq, btype='low')
    baseband = signal.lfilter(b, a, demodulated)

    # Muestreo en el centro de cada símbolo
    samples = []
    for i in range(num_symbols):
        idx = int(i * samples_per_symbol + samples_per_symbol / 2)
        if idx < len(baseband):
            samples.append(baseband[idx])
        else:
            samples.append(0)
    return np.array(samples), baseband, demodulated


def bpsk_demodulate(samples):
    """Convierte símbolos BPSK recibidos en bits 0/1."""
    return [1 if s > 0 else 0 for s in samples]


# ------------------------------------------------------------
# Audio TX/RX
# ------------------------------------------------------------
def transmit_audio(signal_data, fs=FS):
    """Transmite una señal de audio a través del parlante."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
    print("🔊 Transmitiendo señal...")
    stream.write(signal_data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("✅ Transmisión finalizada.")


def record_audio_with_tone_trigger(
    fs=FS,
    chunk=1024,
    start_tone_freq=1000.0,
    start_tone_bw=30.0,
    start_ratio=0.5,
    stop_tone_freq=2000.0,
    stop_tone_bw=30.0,
    stop_ratio=0.5,
):
    """Graba hasta detectar tono de inicio (1 kHz), luego hasta detectar tono de fin (2 kHz)."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=chunk)
    print("🎧 Esperando tono de INICIO...")

    recording = False
    frames = []

    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            x = np.frombuffer(data, dtype=np.float32)

            w = np.hanning(len(x))
            X = np.fft.rfft(x * w)
            P = np.abs(X)**2
            freqs = np.fft.rfftfreq(len(x), 1/fs)

            def detect_tone(f0, bw, ratio):
                mask = np.abs(freqs - f0) <= bw
                if np.any(mask):
                    band_power = P[mask].sum()
                    return (band_power / (P.sum() + 1e-12)) > ratio
                return False

            if not recording:
                if detect_tone(start_tone_freq, start_tone_bw, start_ratio):
                    print("🎙️ Tono de inicio detectado → grabando...")
                    recording = True
            else:
                frames.append(x.copy())
                if detect_tone(stop_tone_freq, stop_tone_bw, stop_ratio):
                    print("🛑 Tono de fin detectado → fin de grabación.")
                    break
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    if len(frames) == 0:
        return None

    return np.concatenate(frames)
