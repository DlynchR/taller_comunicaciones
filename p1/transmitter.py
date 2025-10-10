#!/usr/bin/env python3
"""
Script Transmisor - Convierte archivos a señales de audio y los transmite
"""

import numpy as np
import scipy.signal as signal
import soundfile as sf
import pyaudio
import os
import struct
import argparse
import sys

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

def file_to_bits(file_path):
    """Lee un archivo y lo convierte a una secuencia de bits."""
    with open(file_path, 'rb') as f:
        data_bytes = f.read()
    return bytes_to_bits(data_bytes)

def load_wav_file(file_path):
    """Carga un archivo WAV y devuelve los datos y metadatos."""
    try:
        import soundfile as sf
        audio_data, sample_rate = sf.read(file_path)
        
        # Convertir a mono si es estéreo
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)
            
        # Normalizar a rango [-1, 1]
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
            
        print(f"Audio cargado: {len(audio_data)} muestras, {sample_rate} Hz")
        print(f"Duración: {len(audio_data)/sample_rate:.2f} segundos")
        
        return audio_data, sample_rate
    except Exception as e:
        print(f"Error cargando archivo WAV: {e}")
        return None, None

# --- Modulación BPSK ---

def bpsk_modulate(bits):
    """Modula una secuencia de bits usando BPSK."""
    symbols = np.array([1.0 if bit == 1 else -1.0 for bit in bits])
    return symbols

def generate_passband_signal(symbols, carrier_freq, fs, samples_per_symbol):
    """Genera una señal pasobanda a partir de símbolos (BPSK)."""
    t_symbol = np.linspace(0, 1/BAUD_RATE, samples_per_symbol, endpoint=False)
    full_signal = np.array([])
    for symbol in symbols:
        modulated_waveform = symbol * np.cos(2 * np.pi * carrier_freq * t_symbol)
        full_signal = np.concatenate((full_signal, modulated_waveform))
    return full_signal

# --- Protocolo de Transmisión ---

def encode_data_with_protocol(bits, original_file_size):
    """Codifica los bits con un preámbulo y metadatos (tamaño del archivo)."""
    if original_file_size > 2**32 - 1:
        raise ValueError("El tamaño del archivo excede el límite de 4GB para el protocolo.")
    
    size_bytes = struct.pack(">I", original_file_size)
    size_bits = bytes_to_bits(size_bytes)
    
    encoded_bits = PREAMBLE_BITS + size_bits + bits
    return encoded_bits

# --- Transmisión de Audio ---

def transmit_audio(signal_data, fs):
    """Transmite una señal de audio a través del parlante."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=fs,
                    output=True)
    print("Transmitiendo audio...")
    stream.write(signal_data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()
    print("Transmisión finalizada.")

def save_signal_as_wav(signal_data, fs, filename):
    """Guarda la señal como archivo WAV."""
    sf.write(filename, signal_data, fs)
    print(f"Señal guardada como: {filename}")

# --- Función Principal ---

def transmit_wav_file(input_wav_file, output_modulated_wav=None, transmit_audio_flag=True):
    """Transmite un archivo WAV como señal de audio modulada."""
    if not os.path.exists(input_wav_file):
        print(f"Error: El archivo {input_wav_file} no existe.")
        return False
    
    # Verificar que sea un archivo WAV
    if not input_wav_file.lower().endswith('.wav'):
        print(f"Error: El archivo debe ser un archivo WAV (.wav)")
        return False
    
    # Cargar el archivo WAV
    audio_data, original_sample_rate = load_wav_file(input_wav_file)
    if audio_data is None:
        return False
    
    # Convertir los datos de audio a bits para transmisión
    # Primero convertimos a bytes manteniendo la información del sample rate
    import struct
    
    # Guardar metadatos del audio original
    metadata = struct.pack('>I', original_sample_rate)  # Sample rate como 4 bytes
    metadata += struct.pack('>I', len(audio_data))      # Número de muestras como 4 bytes
    
    # Convertir audio float32 a bytes
    audio_bytes = audio_data.tobytes()
    
    # Combinar metadatos + datos de audio
    full_data = metadata + audio_bytes
    
    # Convertir todo a bits
    original_bits = bytes_to_bits(full_data)
    original_file_size = len(full_data)
    
    print(f"Archivo WAV a transmitir: {input_wav_file}")
    print(f"Sample rate original: {original_sample_rate} Hz")
    print(f"Datos totales: {original_file_size} bytes ({len(original_bits)} bits)")
    
    # 1. Codificación con protocolo
    encoded_bits = encode_data_with_protocol(original_bits, original_file_size)
    print(f"Bits codificados: {len(encoded_bits)} bits")
    
    # 2. Modulación BPSK
    bpsk_symbols = bpsk_modulate(encoded_bits)
    print(f"Símbolos BPSK: {len(bpsk_symbols)}")
    
    # 3. Generar señal pasobanda
    passband_signal = generate_passband_signal(bpsk_symbols, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL)
    print(f"Señal pasobanda: {len(passband_signal)} muestras")
    
    # Normalizar la señal
    passband_signal = 0.8 * passband_signal / np.max(np.abs(passband_signal))
    
    # Calcular duración y tasa de transferencia
    duration = len(passband_signal) / FS
    data_rate = (original_file_size * 8) / duration
    print(f"Duración de transmisión: {duration:.2f} segundos")
    print(f"Tasa de transferencia: {data_rate:.2f} bps")
    
    # 4. Guardar como WAV si se especifica
    if output_modulated_wav:
        save_signal_as_wav(passband_signal, FS, output_modulated_wav)
    
    # 5. Transmitir por audio si se solicita
    if transmit_audio_flag:
        print("\nPreparándose para transmitir...")
        input("Presiona Enter para comenzar la transmisión...")
        transmit_audio(passband_signal, FS)
    
    return True

# --- Script Principal ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Transmisor de archivos WAV por audio modulado')
    parser.add_argument('input_wav', help='Archivo WAV a transmitir')
    parser.add_argument('-o', '--output', help='Guardar señal modulada como archivo WAV')
    parser.add_argument('--no-audio', action='store_true', help='No transmitir por audio, solo generar WAV modulado')
    
    args = parser.parse_args()
    
    success = transmit_wav_file(
        input_wav_file=args.input_wav,
        output_modulated_wav=args.output,
        transmit_audio_flag=not args.no_audio
    )
    
    if not success:
        sys.exit(1)
    
    print("\nTransmisión completada.")