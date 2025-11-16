
# digital_passband_modulator.py
# Módulo para transmisión y recepción digital pasobanda usando BPSK.
# Mejoras añadidas: protocolo de trama con preámbulo/postámbulo, CRC32,
# detección de preámbulo por correlación, matched filter, y funciones de Tx/Rx.
import numpy as np
import scipy.signal as signal
import soundfile as sf
import matplotlib.pyplot as plt
import pyaudio
import os
import struct
import binascii
from typing import Tuple, List

# --- Parámetros Generales (Ajustables) ---
FS = 44100  # Frecuencia de muestreo (Hz)
CARRIER_FREQ = 8000  # Frecuencia de portadora para modulación digital (Hz)
BAUD_RATE = 500  # Símbolos por segundo (ajustable a la capacidad del parlante/micro)
SAMPLES_PER_SYMBOL = FS // BAUD_RATE  # Muestras por símbolo
TX_AMPLITUDE = 0.8  # Amplitud para evitar clipping

# --- Protocolo ---
# Preambulo y postámbulo (bits). 32 bits con buena autocorrelación.
PREAMBLE_BITS = [1,0,1,0,1,0,1,0, 1,1,1,0,0,0,1,1, 1,0,0,1,1,0,1,0, 0,1,1,0,1,0,0,1]
POSTAMBLE_BITS = PREAMBLE_BITS[::-1]  # Inverso simple para distinguir

# Tono de handshake (inicio/fin)
START_TONE_FREQ = 1100.0
STOP_TONE_FREQ = 2200.0
HANDSHAKE_DURATION = 0.5  # segundos (tono de inicio/fin)

# --- Utilidades de bits/bytes ---
def bytes_to_bits(data_bytes: bytes) -> List[int]:
    bits = []
    for byte in data_bytes:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits

def bits_to_bytes(bits: List[int]) -> bytes:
    # Pad bits para completar bytes
    padding_needed = (8 - (len(bits) % 8)) % 8
    bits = bits + [0] * padding_needed
    ba = bytearray()
    for i in range(0, len(bits), 8):
        b = 0
        for j in range(8):
            b = (b << 1) | (bits[i + j] & 1)
        ba.append(b)
    return bytes(ba)

def file_to_bits(file_path: str) -> List[int]:
    with open(file_path, 'rb') as f:
        data_bytes = f.read()
    return bytes_to_bits(data_bytes)

def bits_to_file(bits: List[int], file_path: str):
    data_bytes = bits_to_bytes(bits)
    with open(file_path, 'wb') as f:
        f.write(data_bytes)

# --- CRC32 ---
def crc32_bits(bits: List[int]) -> List[int]:
    b = bits_to_bytes(bits)
    crc = binascii.crc32(b) & 0xffffffff
    return bytes_to_bits(struct.pack(">I", crc))

def check_crc32(bits: List[int], crc_bits: List[int]) -> bool:
    return crc32_bits(bits)[:32] == crc_bits[:32]

# --- Codificación del protocolo (frame builder) ---
def encode_data_with_protocol(payload_bits: List[int], original_file_size: int, use_fec: bool=False) -> List[int]:
    """
    Construye la trama: PREAMBULO | SIZE(32b) | CRC32(32b) | PAYLOAD | POSTAMBULO
    Retorna lista de bits para modular.
    """
    size_bytes = struct.pack(">I", original_file_size)
    size_bits = bytes_to_bits(size_bytes)
    crc_bits = crc32_bits(payload_bits)
    frame = PREAMBLE_BITS + size_bits + crc_bits + payload_bits + POSTAMBLE_BITS
    return frame

def decode_data_with_protocol(received_bits: List[int], use_fec: bool=False) -> Tuple[List[int], int]:
    """
    Busca PREAMBULO en received_bits por correlación y extrae SIZE, CRC y PAYLOAD.
    Retorna (payload_bits, original_file_size) o (None, None) si falla.
    """
    rb = np.array(received_bits, dtype=int)
    pre = np.array(PREAMBLE_BITS, dtype=int)
    # Correlación: conv of bits mapped to +1/-1
    rb_map = 2*rb - 1
    pre_map = 2*pre - 1
    corr = np.abs(np.convolve(rb_map, pre_map[::-1], mode='valid'))
    # Umbral relativo al máximo de correlación
    if len(corr) == 0:
        return None, None
    peak_idx = int(np.argmax(corr))
    peak_val = corr[peak_idx]
    # Detec threshold (80% del máximo posible = len(pre))
    if peak_val < 0.8 * len(pre):
        # No se detectó preámbulo robusto
        return None, None
    start_bit = peak_idx + len(pre)  # índice del bit siguiente al preámbulo
    # Extraer size y crc (asegurarse de que alcance)
    if start_bit + 64 > len(rb):
        return None, None
    size_bits = rb[start_bit : start_bit + 32].tolist()
    crc_bits = rb[start_bit + 32 : start_bit + 64].tolist()
    try:
        size_bytes = bits_to_bytes(size_bits)
        original_size = struct.unpack(">I", size_bytes)[0]
    except Exception:
        return None, None
    expected_payload_bits = original_size * 8
    payload_start = start_bit + 64
    payload_end = payload_start + expected_payload_bits
    if payload_end > len(rb):
        # No alcanzó toda la carga útil
        # Intentar hasta lo que hay
        payload_bits = rb[payload_start:].tolist()
    else:
        payload_bits = rb[payload_start:payload_end].tolist()
    # Verificar CRC solo si tenemos suficientes bits
    if len(payload_bits) * 8 >= 0:
        # compute crc of payload and compare first 32 bits
        if not check_crc32(payload_bits, crc_bits):
            # CRC falla -> posible corrupción
            return None, None
    return payload_bits, original_size

# --- Modulador BPSK (rectangular pulse, matched filter en Rx) ---
def bpsk_modulate(bits: List[int]) -> np.ndarray:
    # Map: 0 -> -1, 1 -> +1
    symbols = np.array([1.0 if b == 1 else -1.0 for b in bits], dtype=float)
    # Pulse shaping: rectangular (SAMPLES_PER_SYMBOL samples per symbol)
    pulse = np.ones(SAMPLES_PER_SYMBOL)
    tx = np.repeat(symbols, SAMPLES_PER_SYMBOL) * np.tile(pulse, len(symbols))
    return tx

def bpsk_demodulate_from_samples(samples: np.ndarray) -> List[int]:
    # Matched filter: rectangular integrate over symbol interval
    # Ensure length multiple of samples per symbol
    n = len(samples) // SAMPLES_PER_SYMBOL
    samples = samples[:n*SAMPLES_PER_SYMBOL]
    reshaped = samples.reshape((n, SAMPLES_PER_SYMBOL))
    metric = np.sum(reshaped, axis=1)
    bits = [1 if m > 0 else 0 for m in metric]
    return bits

# --- Pasar a pasobanda y viceversa ---
def generate_passband_signal(baseband_samples: np.ndarray, carrier_freq: float, fs: int) -> np.ndarray:
    t = np.arange(0, len(baseband_samples)) / fs
    carrier = np.cos(2*np.pi*carrier_freq*t)
    return baseband_samples * carrier

def demodulate_to_baseband(received_signal: np.ndarray, carrier_freq: float, fs: int) -> np.ndarray:
    t = np.arange(0, len(received_signal)) / fs
    local = np.cos(2*np.pi*carrier_freq*t)
    return received_signal * local

# --- Transmisión / Recepción de audio ---
def save_wav(filename: str, signal_data: np.ndarray, fs: int):
    sf.write(filename, signal_data.astype(np.float32), fs)
    print(f"Guardado WAV: {filename}")

def transmit_audio(signal_data: np.ndarray, fs: int):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
    stream.write(signal_data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()

def play_tone(freq: float, duration: float, fs: int):
    t = np.linspace(0, duration, int(fs*duration), endpoint=False)
    tone = 0.9 * np.sin(2*np.pi*freq*t)
    transmit_audio(tone, fs)

# Record until stop tone as in the user's rx_ssb behavior.
def record_audio_with_tone_trigger(
        fs,
        chunk=1024,
        start_tone_freq=START_TONE_FREQ,
        start_tone_bw=30.0,
        start_ratio=0.4,
        stop_tone_freq=STOP_TONE_FREQ,
        stop_tone_bw=30.0,
        stop_ratio=0.4
    ) -> np.ndarray:
    """
    Espera un tono de inicio, luego graba hasta detectar tono de fin.
    Devuelve la señal grabada (numpy float32) o None.
    """
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=chunk)
    print("Esperando tono de inicio...")
    recording = False
    frames = []
    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            x = np.frombuffer(data, dtype=np.float32)
            # FFT para detección de tono
            w = np.hanning(len(x))
            X = np.fft.rfft(x * w)
            P = np.abs(X)**2 + 1e-20
            freqs = np.fft.rfftfreq(len(x), 1/fs)
            def detect_tone(freq, bw, ratio):
                mask = np.abs(freqs - freq) <= bw
                band = P[mask].sum() if np.any(mask) else 0.0
                total = P.sum()
                return (band / total) >= ratio
            if not recording:
                if detect_tone(start_tone_freq, start_tone_bw, start_ratio):
                    recording = True
                    print("Tono de inicio detectado -> comenzando grabación.")
            else:
                frames.append(x.copy())
                if detect_tone(stop_tone_freq, stop_tone_bw, stop_ratio):
                    print("Tono de fin detectado -> finalizando grabación.")
                    break
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
    if len(frames) == 0:
        return None
    return np.concatenate(frames)

def transmit_file(file_path: str, carrier_freq: float=CARRIER_FREQ, fs:int=FS, use_fec:bool=False, play:bool=True, out_wav: str=None):
    """
    Construye la trama, modula, genera tono de inicio/fin y transmite por parlante o guarda WAV.
    """
    original_size = os.path.getsize(file_path)
    payload_bits = file_to_bits(file_path)
    frame_bits = encode_data_with_protocol(payload_bits, original_size, use_fec=use_fec)
    # Baseband samples (BPSK with rectangular pulse)
    baseband = bpsk_modulate(frame_bits)
    # Normalizar
    if np.max(np.abs(baseband)) > 0:
        baseband = TX_AMPLITUDE * baseband / np.max(np.abs(baseband))
    # Pasobanda
    passband = generate_passband_signal(baseband, carrier_freq, fs)
    # Add small ramp to avoid clicks
    ramp_len = int(0.01 * fs)
    if ramp_len > 0 and ramp_len*2 < len(passband):
        ramp = np.linspace(0,1,ramp_len)
        passband[:ramp_len] *= ramp
        passband[-ramp_len:] *= ramp[::-1]
    # Prepend start tone and append stop tone (handshake)
    start_tone = 0.9 * np.sin(2*np.pi*START_TONE_FREQ*np.arange(int(HANDSHAKE_DURATION*fs))/fs)
    stop_tone = 0.9 * np.sin(2*np.pi*STOP_TONE_FREQ*np.arange(int(HANDSHAKE_DURATION*fs))/fs)
    full = np.concatenate((start_tone, np.zeros(int(0.05*fs)), passband, np.zeros(int(0.05*fs)), stop_tone))
    # Guardar WAV si solicita
    if out_wav:
        save_wav(out_wav, full, fs)
    if play:
        print("Transmitiendo: Tono inicio -> datos -> Tono fin")
        transmit_audio(full, fs)
    return full

# --- Demodulación completa (Rx side): """
def receive_and_demodulate_passband_signal(received_signal: np.ndarray, carrier_freq: float, fs:int, samples_per_symbol:int, max_symbols_estimate:int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Demodula pasobanda coherentemente (multiplica por cos) y aplica matched filter (integrador rectangular).
    Devuelve:
      - sampled_symbols: array con un valor por símbolo (float) para decidir 0/1
      - filtered_baseband: señal baseband filtrada (float array)
      - demodulated_baseband: señal producto con portadora (float array)
    NOTA: sincronización muy simple: se asume que la grabación incluye preámbulo y que el inicio
    del primer símbolo coincide aproximadamente con el inicio del bloque devuelto.
    """
    demod = demodulate_to_baseband(received_signal, carrier_freq, fs)
    # Lowpass para limpiar (muy suave)
    nyq = 0.5*fs
    cutoff = BAUD_RATE*1.5
    if cutoff >= nyq:
        cutoff = nyq*0.9
    b,a = signal.butter(4, cutoff/nyq)
    filtered = signal.lfilter(b,a,demod)
    # Matched filter: integrate over SAMPLES_PER_SYMBOL
    # To attempt synchronization, compute energy envelope and cross-correlate with preamble waveform
    # Build preamble baseband waveform for correlation
    pre_symbols = np.array([1.0 if b==1 else -1.0 for b in PREAMBLE_BITS])
    pre_bb = np.repeat(pre_symbols, samples_per_symbol)
    # Correlate filtered with preamble template
    corr = np.abs(np.correlate(filtered, pre_bb, mode='valid'))
    if len(corr) == 0:
        start_sample = 0
    else:
        start_sample = int(np.argmax(corr))
    # sample symbols from start_sample + half symbol offset
    samples = []
    for i in range(max_symbols_estimate):
        idx = start_sample + int(i*samples_per_symbol + samples_per_symbol/2)
        if idx < len(filtered):
            samples.append(filtered[idx])
        else:
            samples.append(0.0)
    return np.array(samples), filtered, demod

# --- Demodulación simple BPSK a bits (utilizada por rx_app) ---
def bpsk_demodulate(sampled_values: np.ndarray) -> List[int]:
    return [1 if v > 0 else 0 for v in sampled_values]

# --- Utilidades de graficación (compatibles con rx_app.py) ---
def plot_spectrum(signal_data, samplerate, title="Espectro", ax=None):
    N = len(signal_data)
    yf = np.fft.fft(signal_data)
    xf = np.fft.fftfreq(N, 1 / samplerate)
    if ax is None:
        plt.figure()
        plt.plot(xf[:N//2], np.abs(yf)[:N//2])
        plt.title(title)
        plt.xlabel('Frecuencia (Hz)')
        plt.ylabel('Amplitud')
        plt.grid()
        plt.show()
    else:
        ax.plot(xf[:N//2], np.abs(yf)[:N//2])
        ax.set_title(title)
        ax.set_xlabel('Frecuencia (Hz)')
        ax.set_ylabel('Amplitud')
        ax.grid()

def plot_time_domain(signal_data, samplerate, title="Dominio del Tiempo", ax=None):
    t = np.arange(0, len(signal_data)) / samplerate
    if ax is None:
        plt.figure()
        plt.plot(t, signal_data)
        plt.title(title)
        plt.xlabel('Tiempo (s)')
        plt.ylabel('Amplitud')
        plt.grid()
        plt.show()
    else:
        ax.plot(t, signal_data)
        ax.set_title(title)
        ax.set_xlabel('Tiempo (s)')
        ax.set_ylabel('Amplitud')
        ax.grid()

# --- BER ---
def calculate_ber(original_bits: List[int], received_bits: List[int]) -> float:
    min_len = min(len(original_bits), len(received_bits))
    if min_len == 0:
        return 0.0
    errors = sum(1 for i in range(min_len) if original_bits[i] != received_bits[i])
    return errors / min_len

# --- Main demo (si se ejecuta el módulo directamente) ---
if __name__ == '__main__':
    # Prueba local: crea archivo, modula, guarda WAV y simula recepción por lectura del WAV
    test_file = 'test_send.txt'
    with open(test_file, 'w') as f:
        f.write('Mensaje de prueba para transmisión digital por audio (BPSK).')
    full = transmit_file(test_file, out_wav='tx_example.wav', play=False)
    print('WAV transmitido (guardado): tx_example.wav')
    # Simular recepción leyendo el WAV
    rx, fs = sf.read('tx_example.wav')
    # recortar para simular que grabación incluye todo
    samples_per_symbol = SAMPLES_PER_SYMBOL
    est_symbols = max(1, int(len(rx) / samples_per_symbol))
    sampled, filtered, demod = receive_and_demodulate_passband_signal(rx, CARRIER_FREQ, fs, samples_per_symbol, est_symbols)
    bits = bpsk_demodulate(sampled)
    payload_bits, original_size = decode_data_with_protocol(bits)
    if payload_bits is not None:
        bits_to_file(payload_bits, 'recovered_from_wav.bin')
        print('Archivo recuperado: recovered_from_wav.bin')
    else:
        print('No se pudo recuperar la trama (CRC o preámbulo no detectado).')