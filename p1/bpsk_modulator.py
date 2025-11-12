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





def receive_and_demodulate_passband_signal(received_signal, carrier_freq, fs, samples_per_symbol, num_symbols):
    """
    Demodulación BPSK mejorada con sincronización de símbolo basada en energía.
    """
    # Multiplicar por portadora local coherente
    t_full = np.arange(0, len(received_signal)) / fs
    local_carrier = np.cos(2 * np.pi * carrier_freq * t_full)
    baseband = received_signal * local_carrier

    # Filtro pasa bajos para eliminar doble frecuencia
    nyquist = 0.5 * fs
    cutoff = min(BAUD_RATE * 0.75 / nyquist, 0.99)
    b, a = signal.butter(5, cutoff, btype="low")
    filtered = signal.lfilter(b, a, baseband)

    # Sincronización automática de símbolos
    # Analizamos la energía por desplazamiento dentro de un símbolo
    spb = samples_per_symbol
    offsets = np.arange(0, spb)
    energies = []

    for offset in offsets:
        # muestreo cada símbolo con ese offset
        samples = filtered[offset::spb][:num_symbols]
        energies.append(np.mean(np.abs(samples)))

    best_offset = int(np.argmax(energies))
    print(f"⚙️ Mejor offset de muestreo detectado: {best_offset} muestras")

    # Muestrear símbolos en el offset óptimo
    sampled_symbols = filtered[best_offset::spb][:num_symbols]

    return np.array(sampled_symbols), filtered, baseband



def bpsk_demodulate(received_symbols):
    """
    Demodula símbolos BPSK con corrección automática de fase.
    Si detecta que la mayoría de los símbolos están invertidos, invierte todo.
    """
    symbols = np.real(received_symbols)
    # Determinar si está invertido (por energía promedio negativa)
    if np.mean(symbols) < 0:
        print("🔁 Fase invertida detectada → Corrigiendo (180°)")
        symbols = -symbols

    demodulated_bits = [1 if s > 0 else 0 for s in symbols]
    return demodulated_bits
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
