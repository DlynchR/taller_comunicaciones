import numpy as np
import scipy.signal as signal
import soundfile as sf
import matplotlib.pyplot as plt
import pyaudio
import os
import struct

# --- Parámetros Generales 2FSK ---
FS = 44100  # Frecuencia de muestreo (Hz)
BAUD_RATE = 100  # Tasa de símbolos (símbolos/segundo) - reducida para mayor robustez
SAMPLES_PER_SYMBOL = FS // BAUD_RATE

# Frecuencias para 2FSK (bien separadas para robustez)
FREQ_0 = 4000  # Hz para bit 0
FREQ_1 = 8000  # Hz para bit 1

# Tonos de handshake
START_TONE_FREQ = 1000.0
STOP_TONE_FREQ = 2000.0
SYNC_TONE_FREQ = 3000.0  # Tono de sincronización adicional

# --- Funciones Auxiliares ---

def bits_to_bytes(bits):
    """Convierte una lista de bits a un array de bytes."""
    byte_array = bytearray()
    padding_needed = (8 - (len(bits) % 8)) % 8
    if padding_needed != 0:
        bits = bits + [0] * padding_needed
    
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if bits[i + j]:
                byte |= (1 << (7 - j))
        byte_array.append(byte)
    return bytes(byte_array)

def bytes_to_bits(data_bytes):
    """Convierte un array de bytes a una lista de bits."""
    bits = []
    for byte in data_bytes:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits

def file_to_bits(file_path):
    """Lee un archivo y lo convierte a una secuencia de bits."""
    with open(file_path, 'rb') as f:
        data_bytes = f.read()
    return bytes_to_bits(data_bytes)

def bits_to_file(bits, file_path):
    """Convierte una secuencia de bits a un archivo."""
    data_bytes = bits_to_bytes(bits)
    with open(file_path, 'wb') as f:
        f.write(data_bytes)

def calculate_checksum(bits):
    """Calcula un checksum simple de 16 bits."""
    data_bytes = bits_to_bytes(bits)
    checksum = sum(data_bytes) & 0xFFFF
    return checksum

# --- Modulación 2FSK ---

def fsk_modulate(bits):
    """Modula una secuencia de bits usando 2FSK."""
    signal_out = np.array([])
    t_symbol = np.linspace(0, 1/BAUD_RATE, SAMPLES_PER_SYMBOL, endpoint=False)
    
    for bit in bits:
        freq = FREQ_1 if bit == 1 else FREQ_0
        symbol_wave = np.sin(2 * np.pi * freq * t_symbol)
        signal_out = np.concatenate((signal_out, symbol_wave))
    
    return signal_out

def fsk_demodulate(received_signal, num_symbols):
    """Demodula una señal 2FSK usando filtros y detección de energía."""
    demodulated_bits = []
    
    # Diseñar filtros pasa-banda para cada frecuencia
    nyquist = 0.5 * FS
    bw = BAUD_RATE * 2  # Ancho de banda del filtro
    
    # Filtro para FREQ_0
    low_0 = max((FREQ_0 - bw) / nyquist, 0.01)
    high_0 = min((FREQ_0 + bw) / nyquist, 0.99)
    b0, a0 = signal.butter(4, [low_0, high_0], btype='band')
    
    # Filtro para FREQ_1
    low_1 = max((FREQ_1 - bw) / nyquist, 0.01)
    high_1 = min((FREQ_1 + bw) / nyquist, 0.99)
    b1, a1 = signal.butter(4, [low_1, high_1], btype='band')
    
    # Filtrar la señal recibida
    filtered_0 = signal.lfilter(b0, a0, received_signal)
    filtered_1 = signal.lfilter(b1, a1, received_signal)
    
    # Detectar energía en cada símbolo
    for i in range(num_symbols):
        start_idx = int(i * SAMPLES_PER_SYMBOL)
        end_idx = int((i + 1) * SAMPLES_PER_SYMBOL)
        
        if end_idx > len(received_signal):
            break
        
        # Calcular energía en cada filtro
        energy_0 = np.sum(filtered_0[start_idx:end_idx] ** 2)
        energy_1 = np.sum(filtered_1[start_idx:end_idx] ** 2)
        
        # Decidir bit basado en mayor energía
        bit = 1 if energy_1 > energy_0 else 0
        demodulated_bits.append(bit)
    
    return demodulated_bits, filtered_0, filtered_1

# --- Protocolo de Transmisión ---

# Preámbulo robusto de 64 bits (patrón Barker extendido)
PREAMBLE_BITS = [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 1, 0, 1] * 5  # 65 bits
PREAMBLE_BITS = PREAMBLE_BITS[:64]  # Exactamente 64 bits

def encode_data_with_protocol(bits, original_file_size):
    """
    Codifica datos con protocolo:
    - Preámbulo (64 bits)
    - Tamaño del archivo (32 bits)
    - Checksum (16 bits)
    - Datos
    - Postámbulo (32 bits)
    """
    # Tamaño del archivo (32 bits)
    size_bytes = struct.pack(">I", original_file_size)
    size_bits = bytes_to_bits(size_bytes)
    
    # Calcular checksum
    checksum = calculate_checksum(bits)
    checksum_bytes = struct.pack(">H", checksum)
    checksum_bits = bytes_to_bits(checksum_bytes)
    
    # Postámbulo (patrón invertido del preámbulo)
    postamble_bits = [1 - bit for bit in PREAMBLE_BITS[:32]]
    
    # Ensamblar paquete
    packet = PREAMBLE_BITS + size_bits + checksum_bits + bits + postamble_bits
    
    return packet

def find_preamble(bits):
    """Encuentra el preámbulo en una secuencia de bits usando correlación."""
    preamble = np.array(PREAMBLE_BITS)
    bits_array = np.array(bits)
    
    if len(bits_array) < len(preamble):
        return -1
    
    # Convertir a valores -1, 1 para correlación
    preamble_signal = 2 * preamble - 1
    bits_signal = 2 * bits_array - 1
    
    # Calcular correlación
    correlation = np.correlate(bits_signal, preamble_signal, mode='valid')
    
    # Encontrar el pico máximo
    if len(correlation) == 0:
        return -1
    
    max_idx = np.argmax(np.abs(correlation))
    max_corr = correlation[max_idx]
    
    # Umbral de detección (80% del máximo teórico)
    threshold = len(preamble) * 0.8
    
    if abs(max_corr) >= threshold:
        return max_idx
    return -1

def decode_data_with_protocol(received_bits):
    """
    Decodifica datos del protocolo.
    Retorna: (data_bits, file_size, checksum_valid)
    """
    # Buscar preámbulo
    preamble_idx = find_preamble(received_bits)
    
    if preamble_idx < 0:
        print("⚠️ Preámbulo no encontrado")
        return None, None, False
    
    print(f"✓ Preámbulo encontrado en posición {preamble_idx}")
    
    # Extraer campos
    start = preamble_idx + len(PREAMBLE_BITS)
    
    # Tamaño (32 bits)
    size_bits = received_bits[start:start + 32]
    if len(size_bits) < 32:
        print("⚠️ Datos insuficientes para tamaño")
        return None, None, False
    
    file_size = struct.unpack(">I", bits_to_bytes(size_bits))[0]
    start += 32
    
    # Checksum (16 bits)
    checksum_bits = received_bits[start:start + 16]
    if len(checksum_bits) < 16:
        print("⚠️ Datos insuficientes para checksum")
        return None, None, False
    
    received_checksum = struct.unpack(">H", bits_to_bytes(checksum_bits))[0]
    start += 16
    
    # Datos
    expected_data_bits = file_size * 8
    data_bits = received_bits[start:start + expected_data_bits]
    
    if len(data_bits) < expected_data_bits:
        print(f"⚠️ Datos incompletos: {len(data_bits)}/{expected_data_bits} bits")
        # Rellenar con ceros
        data_bits = data_bits + [0] * (expected_data_bits - len(data_bits))
    
    # Verificar checksum
    calculated_checksum = calculate_checksum(data_bits)
    checksum_valid = (received_checksum == calculated_checksum)
    
    print(f"Tamaño archivo: {file_size} bytes")
    print(f"Checksum recibido: {received_checksum:04X}")
    print(f"Checksum calculado: {calculated_checksum:04X}")
    print(f"Checksum válido: {'✓' if checksum_valid else '✗'}")
    
    return data_bits, file_size, checksum_valid

# --- Transmisión y Recepción de Audio ---

def generate_tone(freq, duration, fs, amplitude=0.8):
    """Genera un tono puro."""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)

def transmit_audio(signal_data, fs):
    """Transmite una señal de audio a través del parlante."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=fs,
                    output=True)
    print("🔊 Transmitiendo audio...")
    stream.write(signal_data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("✓ Transmisión finalizada.")

def detect_tone_in_chunk(chunk, fs, target_freq, bandwidth=50.0, threshold=0.3):
    """Detecta si un tono específico está presente en un chunk de audio."""
    # Aplicar ventana
    w = np.hanning(len(chunk))
    X = np.fft.rfft(chunk * w)
    P = np.abs(X) ** 2
    freqs = np.fft.rfftfreq(len(chunk), 1/fs)
    
    # Energía en la banda del tono
    mask = np.abs(freqs - target_freq) <= bandwidth
    band_energy = P[mask].sum() if np.any(mask) else 0.0
    total_energy = P.sum() + 1e-12
    
    ratio = band_energy / total_energy
    return ratio >= threshold

def record_audio_with_tone_trigger(
    fs,
    chunk=2048,
    start_tone_freq=START_TONE_FREQ,
    stop_tone_freq=STOP_TONE_FREQ,
    sync_tone_freq=SYNC_TONE_FREQ
):
    """
    Protocolo de handshake:
    1. Espera tono de inicio (1 kHz)
    2. Espera tono de sincronización (3 kHz)
    3. Graba datos
    4. Detecta tono de fin (2 kHz)
    """
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, 
                    channels=1, 
                    rate=fs, 
                    input=True, 
                    frames_per_buffer=chunk)
    
    print("📡 Esperando handshake...")
    print(f"   - Tono de inicio: {start_tone_freq} Hz")
    print(f"   - Tono de sincronización: {sync_tone_freq} Hz")
    print(f"   - Tono de fin: {stop_tone_freq} Hz")
    
    state = "WAITING_START"
    frames = []
    consecutive_start = 0
    consecutive_sync = 0
    consecutive_stop = 0
    
    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            x = np.frombuffer(data, dtype=np.float32)
            
            if state == "WAITING_START":
                if detect_tone_in_chunk(x, fs, start_tone_freq):
                    consecutive_start += 1
                    if consecutive_start >= 3:  # 3 chunks consecutivos
                        print("✓ Tono de inicio detectado")
                        state = "WAITING_SYNC"
                        consecutive_start = 0
                else:
                    consecutive_start = 0
            
            elif state == "WAITING_SYNC":
                if detect_tone_in_chunk(x, fs, sync_tone_freq):
                    consecutive_sync += 1
                    if consecutive_sync >= 3:
                        print("✓ Tono de sincronización detectado → Grabando datos...")
                        state = "RECORDING"
                        consecutive_sync = 0
                else:
                    consecutive_sync = 0
            
            elif state == "RECORDING":
                # Verificar si es tono de fin
                if detect_tone_in_chunk(x, fs, stop_tone_freq):
                    consecutive_stop += 1
                    if consecutive_stop >= 3:
                        print("✓ Tono de fin detectado → Finalizando grabación")
                        break
                else:
                    consecutive_stop = 0
                    frames.append(x.copy())
    
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
    
    if len(frames) == 0:
        print("⚠️ No se grabaron datos")
        return None
    
    print(f"✓ Grabación completa: {len(frames)} chunks")
    return np.concatenate(frames)

# --- Funciones de graficación ---

def plot_spectrum(signal_data, samplerate, title="Espectro", ax=None):
    """Calcula y grafica el espectro de una señal."""
    N = len(signal_data)
    yf = np.fft.fft(signal_data)
    xf = np.fft.fftfreq(N, 1 / samplerate)
    
    # Solo frecuencias positivas
    pos_mask = xf >= 0
    
    if ax is None:
        plt.figure(figsize=(10, 4))
        plt.plot(xf[pos_mask], np.abs(yf[pos_mask]))
        plt.title(title)
        plt.xlabel('Frecuencia (Hz)')
        plt.ylabel('Magnitud')
        plt.grid(True)
        plt.tight_layout()
    else:
        ax.plot(xf[pos_mask], np.abs(yf[pos_mask]))
        ax.set_title(title)
        ax.set_xlabel('Frecuencia (Hz)')
        ax.set_ylabel('Magnitud')
        ax.grid(True)

def plot_time_domain(signal_data, samplerate, title="Dominio del Tiempo", ax=None, max_samples=10000):
    """Grafica la señal en el dominio del tiempo."""
    # Limitar muestras para visualización
    if len(signal_data) > max_samples:
        signal_data = signal_data[:max_samples]
    
    t = np.arange(len(signal_data)) / samplerate
    
    if ax is None:
        plt.figure(figsize=(10, 4))
        plt.plot(t, signal_data)
        plt.title(title)
        plt.xlabel('Tiempo (s)')
        plt.ylabel('Amplitud')
        plt.grid(True)
        plt.tight_layout()
    else:
        ax.plot(t, signal_data)
        ax.set_title(title)
        ax.set_xlabel('Tiempo (s)')
        ax.set_ylabel('Amplitud')
        ax.grid(True)

def plot_constellation(bits, title="Constelación 2FSK", ax=None):
    """Grafica pseudo-constelación para 2FSK."""
    # Para 2FSK, mostramos los bits como puntos en un eje
    bits_array = np.array(bits)
    zeros = np.where(bits_array == 0)[0]
    ones = np.where(bits_array == 1)[0]
    
    if ax is None:
        plt.figure(figsize=(8, 6))
        plt.scatter(zeros, np.zeros_like(zeros), alpha=0.5, label='Bit 0')
        plt.scatter(ones, np.ones_like(ones), alpha=0.5, label='Bit 1')
        plt.title(title)
        plt.xlabel('Índice de bit')
        plt.ylabel('Valor de bit')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
    else:
        ax.scatter(zeros, np.zeros_like(zeros), alpha=0.5, label='Bit 0')
        ax.scatter(ones, np.ones_like(ones), alpha=0.5, label='Bit 1')
        ax.set_title(title)
        ax.set_xlabel('Índice de bit')
        ax.set_ylabel('Valor de bit')
        ax.legend()
        ax.grid(True)

def plot_eye_diagram(signal_data, samples_per_symbol, num_traces=100, title="Diagrama de Ojo", ax=None):
    """Genera diagrama de ojo."""
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 6))
    
    # Normalizar señal
    signal_norm = signal_data / (np.max(np.abs(signal_data)) + 1e-12)
    
    # Extraer trazas
    for i in range(min(num_traces, len(signal_norm) // samples_per_symbol - 2)):
        start = i * samples_per_symbol
        trace = signal_norm[start:start + 2 * samples_per_symbol]
        if len(trace) == 2 * samples_per_symbol:
            t = np.linspace(0, 2, len(trace))
            ax.plot(t, trace, 'b-', alpha=0.1)
    
    ax.set_title(title)
    ax.set_xlabel('Tiempo (símbolos)')
    ax.set_ylabel('Amplitud normalizada')
    ax.grid(True)
    ax.set_xlim(0, 2)

def calculate_ber(original_bits, received_bits):
    """Calcula la Tasa de Error de Bit (BER)."""
    min_len = min(len(original_bits), len(received_bits))
    if min_len == 0:
        return 1.0
    
    errors = sum(1 for i in range(min_len) if original_bits[i] != received_bits[i])
    return errors / min_len