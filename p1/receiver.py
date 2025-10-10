#!/usr/bin/env python3
"""
Script Receptor - Recibe señales de audio y recupera archivos
"""

import numpy as np
import scipy.signal as signal
import soundfile as sf
import pyaudio
import os
import struct
import argparse
import sys
import time

# --- Parámetros Generales ---
FS = 44100  # Frecuencia de muestreo (Hz)
CARRIER_FREQ = 8000  # Frecuencia de portadora para modulación digital (Hz)
BAUD_RATE = 1000  # Tasa de símbolos (símbolos/segundo)
SAMPLES_PER_SYMBOL = FS // BAUD_RATE  # Muestras por símbolo

# Secuencia de preámbulo
PREAMBLE_BITS = [1, 0, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1, 0, 0, 0]

# --- Funciones Auxiliares ---

def bits_to_bytes(bits):
    """Convierte una lista de bits a un array de bytes."""
    byte_array = bytearray()
    padding_needed = (8 - (len(bits) % 8)) % 8
    if padding_needed != 0:
        bits.extend([0] * padding_needed)

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

def bits_to_file(bits, file_path):
    """Convierte una secuencia de bits a un archivo."""
    data_bytes = bits_to_bytes(bits)
    with open(file_path, 'wb') as f:
        f.write(data_bytes)

def reconstruct_wav_file(bits, output_wav_path):
    """Reconstruye un archivo WAV desde bits recibidos."""
    try:
        import struct
        import soundfile as sf
        
        # Convertir bits a bytes
        data_bytes = bits_to_bytes(bits)
        
        # Extraer metadatos (8 bytes: 4 para sample_rate, 4 para num_samples)
        if len(data_bytes) < 8:
            print("Error: Datos insuficientes para metadatos de audio")
            return False
            
        sample_rate = struct.unpack('>I', data_bytes[0:4])[0]
        num_samples = struct.unpack('>I', data_bytes[4:8])[0]
        
        print(f"Metadatos de audio: {sample_rate} Hz, {num_samples} muestras")
        
        # Extraer datos de audio
        audio_bytes = data_bytes[8:]
        expected_audio_bytes = num_samples * 4  # 4 bytes por muestra float32
        
        if len(audio_bytes) < expected_audio_bytes:
            print(f"Advertencia: Datos de audio incompletos ({len(audio_bytes)} de {expected_audio_bytes} bytes)")
            # Rellenar con ceros
            audio_bytes += b'\x00' * (expected_audio_bytes - len(audio_bytes))
        elif len(audio_bytes) > expected_audio_bytes:
            # Truncar si hay datos extra
            audio_bytes = audio_bytes[:expected_audio_bytes]
        
        # Convertir bytes a array de float32
        audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
        
        # Redimensionar al número correcto de muestras
        if len(audio_data) != num_samples:
            audio_data = audio_data[:num_samples] if len(audio_data) > num_samples else np.pad(audio_data, (0, num_samples - len(audio_data)))
        
        # Guardar como archivo WAV
        sf.write(output_wav_path, audio_data, sample_rate)
        
        print(f"Archivo WAV reconstruido: {output_wav_path}")
        print(f"Duración: {len(audio_data)/sample_rate:.2f} segundos")
        
        return True
        
    except Exception as e:
        print(f"Error reconstruyendo archivo WAV: {e}")
        return False

# --- Demodulación BPSK ---

def bpsk_demodulate(received_symbols):
    """Demodula símbolos BPSK."""
    demodulated_bits = [1 if np.real(symbol) > 0 else 0 for symbol in received_symbols]
    return demodulated_bits

def receive_and_demodulate_passband_signal(received_signal, carrier_freq, fs, samples_per_symbol, num_symbols):
    """Demodula una señal pasobanda recibida (BPSK)."""
    # Multiplicar por la portadora local (coherente)
    t_full = np.arange(0, len(received_signal)) / fs
    local_carrier = np.cos(2 * np.pi * carrier_freq * t_full)
    demodulated_baseband = received_signal * local_carrier
    
    # Filtro pasa-bajos para extraer la señal de banda base
    nyquist = 0.5 * fs
    cutoff_freq = BAUD_RATE / 2 * 1.5
    if cutoff_freq >= nyquist:
        cutoff_freq = nyquist * 0.9
    b, a = signal.butter(5, cutoff_freq / nyquist, btype='low')
    filtered_baseband = signal.lfilter(b, a, demodulated_baseband)
    
    # Muestreo en el instante óptimo
    sampled_symbols = []
    for i in range(num_symbols):
        sample_index = int(i * samples_per_symbol + samples_per_symbol / 2)
        if sample_index < len(filtered_baseband):
            sampled_symbols.append(filtered_baseband[sample_index])
        else:
            sampled_symbols.append(0)
    
    return np.array(sampled_symbols), filtered_baseband, demodulated_baseband

# --- Protocolo de Recepción ---

def decode_data_with_protocol(received_bits):
    """Decodifica los bits recibidos, extrayendo metadatos y datos."""
    preamble_len = len(PREAMBLE_BITS)
    size_bits_len = 32  # Tamaño del campo de longitud del archivo en bits
    
    # Buscar el preámbulo en los bits recibidos
    preamble_found_at = -1
    
    for i in range(len(received_bits) - preamble_len + 1):
        if received_bits[i : i + preamble_len] == PREAMBLE_BITS:
            preamble_found_at = i
            break
    
    if preamble_found_at == -1:
        print("Error: Preámbulo no encontrado.")
        return None, None
    
    print(f"Preámbulo encontrado en posición: {preamble_found_at}")
    
    # Los bits de metadatos comienzan después del preámbulo
    metadata_start_index = preamble_found_at + preamble_len
    
    if len(received_bits) < metadata_start_index + size_bits_len:
        print("Error: No hay suficientes bits para el tamaño del archivo.")
        return None, None
    
    # Extraer los bits que representan el tamaño del archivo
    raw_size_bits = received_bits[metadata_start_index : metadata_start_index + size_bits_len]
    
    # Convertir a bytes y luego a entero
    try:
        original_file_size = struct.unpack(">I", bits_to_bytes(raw_size_bits))[0]
    except struct.error as e:
        print(f"Error al desempaquetar el tamaño del archivo: {e}")
        return None, None
    
    # Validar el tamaño del archivo
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # Límite de 10 MB
    if original_file_size <= 0 or original_file_size > MAX_FILE_SIZE_BYTES:
        print(f"Error: Tamaño de archivo inválido ({original_file_size} bytes)")
        return None, None
    
    print(f"Tamaño de archivo esperado: {original_file_size} bytes")
    
    # Los bits de datos reales comienzan después del preámbulo y el tamaño
    data_payload_start_index = metadata_start_index + size_bits_len
    data_payload_bits = received_bits[data_payload_start_index:]
    
    # Recortar los bits de datos al tamaño original del archivo
    expected_data_bits_len = original_file_size * 8
    
    if len(data_payload_bits) > expected_data_bits_len:
        data_bits = data_payload_bits[:expected_data_bits_len]
    elif len(data_payload_bits) < expected_data_bits_len:
        print(f"Advertencia: Menos bits recibidos ({len(data_payload_bits)}) de los esperados ({expected_data_bits_len})")
        data_bits = data_payload_bits + [0] * (expected_data_bits_len - len(data_payload_bits))
    else:
        data_bits = data_payload_bits
    
    return data_bits, original_file_size

# --- Recepción de Audio ---

def record_audio(duration, fs):
    """Graba audio desde el micrófono por una duración específica."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=fs,
                    input=True,
                    frames_per_buffer=1024)
    print(f"Grabando audio por {duration} segundos...")
    frames = []
    for _ in range(0, int(fs / 1024 * duration)):
        data = stream.read(1024)
        frames.append(np.frombuffer(data, dtype=np.float32))
    print("Grabación finalizada.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    return np.concatenate(frames)

def load_signal_from_wav(filename):
    """Carga una señal desde un archivo WAV."""
    signal_data, fs = sf.read(filename)
    print(f"Señal cargada desde: {filename}")
    print(f"Frecuencia de muestreo: {fs} Hz")
    print(f"Duración: {len(signal_data)/fs:.2f} segundos")
    return signal_data, fs

# --- Cálculo de BER ---

def calculate_ber(original_bits, received_bits):
    """Calcula la Tasa de Error de Bit (BER)."""
    min_len = min(len(original_bits), len(received_bits))
    errors = sum(1 for i in range(min_len) if original_bits[i] != received_bits[i])
    if min_len == 0:
        return 0.0
    return errors / min_len

# --- Función Principal ---

def receive_wav_file(output_wav_file, input_modulated_wav=None, duration=None, save_received_signal=None):
    """Recibe un archivo WAV desde una señal de audio modulada."""
    
    # Recibir señal de audio
    if input_modulated_wav:
        # Cargar desde archivo WAV
        received_signal, actual_fs = load_signal_from_wav(input_modulated_wav)
        if actual_fs != FS:
            print(f"Advertencia: Frecuencia de muestreo del archivo ({actual_fs}) diferente a la esperada ({FS})")
    else:
        # Grabar desde micrófono
        if duration is None:
            duration = float(input("Ingresa la duración de grabación en segundos: "))
        
        print("\nPreparándose para recibir...")
        input("Presiona Enter para comenzar la grabación...")
        received_signal = record_audio(duration, FS)
    
    # Guardar señal recibida si se solicita
    if save_received_signal:
        sf.write(save_received_signal, received_signal, FS)
        print(f"Señal recibida guardada como: {save_received_signal}")
    
    print(f"Señal recibida: {len(received_signal)} muestras")
    
    # Estimar número de símbolos
    num_symbols = len(received_signal) // SAMPLES_PER_SYMBOL
    print(f"Número estimado de símbolos: {num_symbols}")
    
    # Demodular la señal
    print("Demodulando señal...")
    received_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(
        received_signal, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL, num_symbols
    )
    
    # Demodular BPSK
    demodulated_bits = bpsk_demodulate(received_symbols)
    print(f"Bits demodulados: {len(demodulated_bits)}")
    
    # Decodificar protocolo
    print("Decodificando protocolo...")
    recovered_bits, recovered_file_size = decode_data_with_protocol(demodulated_bits)
    
    if recovered_bits is None or recovered_file_size is None:
        print("Error: No se pudo decodificar el archivo.")
        return False
    
    # Verificar que el nombre de salida sea WAV
    if not output_wav_file.lower().endswith('.wav'):
        print("Advertencia: El archivo de salida debería tener extensión .wav")
        output_wav_file += '.wav'
    
    # Reconstruir archivo WAV
    success = reconstruct_wav_file(recovered_bits, output_wav_file)
    
    if success:
        print(f"Archivo WAV recuperado exitosamente: {output_wav_file}")
        print(f"Tamaño de datos: {recovered_file_size} bytes")
        return True
    else:
        print("Error: No se pudo reconstruir el archivo WAV")
        return False

# --- Script Principal ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Receptor de archivos WAV desde audio modulado')
    parser.add_argument('output_wav', help='Nombre del archivo WAV recuperado')
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-i', '--input-wav', help='Cargar señal modulada desde archivo WAV')
    group.add_argument('-d', '--duration', type=float, help='Duración de grabación en segundos')
    
    parser.add_argument('--save-signal', help='Guardar señal recibida como archivo WAV')
    
    args = parser.parse_args()
    
    success = receive_wav_file(
        output_wav_file=args.output_wav,
        input_modulated_wav=args.input_wav,
        duration=args.duration,
        save_received_signal=args.save_signal
    )
    
    if not success:
        sys.exit(1)
    
    print("\nRecepción completada.")