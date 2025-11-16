# digital_simple.py
# Sistema simple de transmisión digital con BPSK
# Usa tonos 1kHz (inicio) y 2kHz (fin) para sincronización
# FEC opcional por repetición triple

import numpy as np
import pyaudio
import scipy.signal as signal
from digital_protocol import encode_text_file, decode_to_text_file

# --- Parámetros ---
FS = 44100
CARRIER_FREQ = 8000
BAUD_RATE = 1000
SAMPLES_PER_SYMBOL = FS // BAUD_RATE

START_TONE_FREQ = 1000.0
STOP_TONE_FREQ = 2000.0
TONE_DURATION = 0.5

# --- Modulación BPSK ---

def bpsk_modulate(bits):
    """Modula bits usando BPSK: 0 -> -1, 1 -> +1"""
    return np.array([1.0 if bit == 1 else -1.0 for bit in bits])

def bpsk_demodulate(symbols):
    """Demodula símbolos BPSK"""
    return [1 if np.real(s) > 0 else 0 for s in symbols]

# --- Generación de Señal Pasobanda ---

def generate_passband_signal(symbols, carrier_freq, fs, samples_per_symbol):
    """Genera señal pasobanda BPSK"""
    t_symbol = np.linspace(0, 1/BAUD_RATE, samples_per_symbol, endpoint=False)
    signal_out = np.array([])
    
    for symbol in symbols:
        # Modular símbolo con portadora
        waveform = symbol * np.cos(2 * np.pi * carrier_freq * t_symbol)
        signal_out = np.concatenate((signal_out, waveform))
    
    return signal_out

def demodulate_passband_signal(received, carrier_freq, fs, samples_per_symbol, num_symbols):
    """Demodula señal pasobanda BPSK con mejor sincronización"""
    # Mezcla con portadora local (ambas en fase e cuadratura)
    t = np.arange(len(received)) / fs
    local_carrier_i = np.cos(2 * np.pi * carrier_freq * t)
    local_carrier_q = -np.sin(2 * np.pi * carrier_freq * t)
    
    baseband_i = received * local_carrier_i
    baseband_q = received * local_carrier_q
    
    # Filtro pasa-bajos
    nyquist = 0.5 * fs
    cutoff = min(BAUD_RATE / 2 * 1.5, nyquist * 0.9)
    b, a = signal.butter(5, cutoff / nyquist, btype='low')
    filtered_i = signal.lfilter(b, a, baseband_i)
    filtered_q = signal.lfilter(b, a, baseband_q)
    
    # Combinar I y Q
    filtered = filtered_i + 1j * filtered_q
    
    # Muestreo de símbolos (ajustado para compensar delay del filtro)
    filter_delay = len(b) // 2
    symbols = []
    for i in range(num_symbols):
        idx = int(i * samples_per_symbol + samples_per_symbol / 2 + filter_delay)
        if idx < len(filtered):
            # Usar solo la componente real (I) para BPSK
            symbols.append(np.real(filtered[idx]))
        else:
            break
    
    return np.array(symbols)

# --- Tonos de Sincronización ---

def generate_tone(freq, duration, fs):
    """Genera un tono puro"""
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    return 0.8 * np.sin(2 * np.pi * freq * t)

def detect_tone(audio_chunk, fs, target_freq, bandwidth=30.0, threshold=0.5):
    """Detecta si un tono específico está presente"""
    # FFT
    w = np.hanning(len(audio_chunk))
    X = np.fft.rfft(audio_chunk * w)
    P = np.abs(X)**2
    freqs = np.fft.rfftfreq(len(audio_chunk), 1/fs)
    
    # Energía en la banda del tono
    mask = np.abs(freqs - target_freq) <= bandwidth
    band_energy = P[mask].sum() if np.any(mask) else 0.0
    total_energy = P.sum() + 1e-12
    
    ratio = band_energy / total_energy
    return ratio >= threshold

# --- Transmisión ---

def transmit_audio(signal_data, fs):
    """Transmite audio por el parlante"""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
    print("🔊 Transmitiendo audio...")
    stream.write(signal_data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("✅ Transmisión finalizada")

def transmit_text_file(file_path, carrier_freq, fs, use_fec):
    """Transmite un archivo de texto completo"""
    # Codificar archivo
    encoded_bits, file_size = encode_text_file(file_path, use_fec)
    
    # Modular
    symbols = bpsk_modulate(encoded_bits)
    passband = generate_passband_signal(symbols, carrier_freq, fs, SAMPLES_PER_SYMBOL)
    passband = 0.8 * passband / (np.max(np.abs(passband)) + 1e-12)
    
    # Agregar tonos de inicio y fin
    start_tone = generate_tone(START_TONE_FREQ, TONE_DURATION, fs)
    stop_tone = generate_tone(STOP_TONE_FREQ, TONE_DURATION, fs)
    
    tx_signal = np.concatenate([start_tone, passband, stop_tone])
    
    # Transmitir
    transmit_audio(tx_signal, fs)
    
    return tx_signal

# --- Recepción ---

def record_with_tone_trigger(fs, start_freq, stop_freq, chunk=1024):
    """Graba audio entre tonos de inicio y fin"""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, 
                    input=True, frames_per_buffer=chunk)
    
    print("📡 Esperando tono de inicio (1 kHz)...")
    recording = False
    frames = []
    
    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            audio_chunk = np.frombuffer(data, dtype=np.float32)
            
            if not recording:
                # Buscar tono de inicio
                if detect_tone(audio_chunk, fs, start_freq):
                    print("🎙️ Tono de inicio detectado. Grabando...")
                    recording = True
            else:
                # Grabar y buscar tono de fin
                frames.append(audio_chunk.copy())
                
                if detect_tone(audio_chunk, fs, stop_freq):
                    print("🛑 Tono de fin detectado. Finalizando grabación.")
                    break
    
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()
    
    if len(frames) == 0:
        return None
    
    return np.concatenate(frames)

def receive_text_file(output_path, carrier_freq, fs):
    """Recibe y demodula un archivo de texto"""
    # Grabar
    received = record_with_tone_trigger(fs, START_TONE_FREQ, STOP_TONE_FREQ)
    
    if received is None or len(received) < SAMPLES_PER_SYMBOL * 20:
        print("❌ Error: Grabación muy corta o sin tonos detectados")
        return False, {}
    
    print(f"✅ Grabación completa: {len(received)} muestras ({len(received)/fs:.2f}s)")
    
    # Normalizar señal recibida
    received = received / (np.max(np.abs(received)) + 1e-12)
    
    # Demodular
    est_symbols = max(1, int(len(received) / SAMPLES_PER_SYMBOL))
    print(f"📊 Estimando {est_symbols} símbolos...")
    symbols = demodulate_passband_signal(received, carrier_freq, fs, SAMPLES_PER_SYMBOL, est_symbols)
    
    print(f"✅ Símbolos demodulados: {len(symbols)}")
    print(f"   Rango de amplitudes: [{np.min(symbols):.3f}, {np.max(symbols):.3f}]")
    
    # BPSK -> Bits
    bits = bpsk_demodulate(symbols)
    print(f"✅ Bits demodulados: {len(bits)}")
    
    # Mostrar los primeros bits del header para debugging
    if len(bits) >= 32:
        header_preview = ''.join(map(str, bits[:32]))
        print(f"   Header bits: {header_preview}")
    
    # Decodificar protocolo y guardar
    success, stats = decode_to_text_file(bits, output_path)
    
    if success:
        transmission_time = len(received) / fs
        stats['transmission_time'] = transmission_time
        stats['data_rate'] = (stats['file_size'] * 8) / transmission_time
    
    return success, stats
