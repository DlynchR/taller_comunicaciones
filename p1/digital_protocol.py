# digital_protocol.py
# Protocolo simple para transmisión digital de archivos de texto
# Usa tonos de 1kHz (inicio) y 2kHz (fin) para sincronización
# FEC opcional mediante repetición triple

import numpy as np
import struct
from typing import List, Tuple

# --- Codificación/Decodificación de Bits ---

def bytes_to_bits(data_bytes: bytes) -> List[int]:
    """Convierte bytes a lista de bits."""
    bits = []
    for byte in data_bytes:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits

def bits_to_bytes(bits: List[int]) -> bytes:
    """Convierte lista de bits a bytes."""
    # Pad to multiple of 8
    padding = (8 - (len(bits) % 8)) % 8
    if padding > 0:
        bits = bits + [0] * padding
    
    ba = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for j in range(8):
            if bits[i + j]:
                byte |= (1 << (7 - j))
        ba.append(byte)
    return bytes(ba)

# --- Manejo de Archivos de Texto ---

def text_file_to_bits(file_path: str) -> List[int]:
    """Lee archivo de texto UTF-8 y lo convierte a bits."""
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    data_bytes = text.encode('utf-8')
    return bytes_to_bits(data_bytes)

def bits_to_text_file(bits: List[int], file_path: str):
    """Convierte bits a archivo de texto UTF-8."""
    data_bytes = bits_to_bytes(bits)
    try:
        text = data_bytes.decode('utf-8', errors='ignore')
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
    except Exception as e:
        print(f"Warning: Error decoding as UTF-8: {e}")
        # Fallback to binary if needed
        with open(file_path, 'wb') as f:
            f.write(data_bytes)

def is_text_file(file_path: str) -> bool:
    """Verifica si un archivo es texto válido UTF-8."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            f.read()
        return True
    except (UnicodeDecodeError, IOError):
        return False

# --- FEC: Código de Repetición Triple ---

def apply_fec(bits: List[int]) -> List[int]:
    """Aplica FEC: cada bit se repite 3 veces."""
    fec_bits = []
    for bit in bits:
        fec_bits.extend([bit, bit, bit])
    return fec_bits

def decode_fec(bits: List[int]) -> List[int]:
    """Decodifica FEC: votación por mayoría de cada triplete."""
    decoded = []
    for i in range(0, len(bits) - 2, 3):
        trio = bits[i:i+3]
        # Mayoría: 2 o más de 3
        decoded.append(1 if sum(trio) >= 2 else 0)
    return decoded

# --- Protocolo Simple ---

def encode_protocol(data_bits: List[int], file_size: int, use_fec: bool) -> List[int]:
    """
    Codifica datos con protocolo simple:
    [32 bits header] [datos]
    
    Header (32 bits):
      - Bit 31: FEC flag (1=FEC enabled, 0=disabled)
      - Bits 30-0: File size in bytes (max 2GB)
    """
    # Aplicar FEC a los datos si está habilitado
    if use_fec:
        data_bits = apply_fec(data_bits)
        print(f"  FEC aplicado: {len(data_bits)//3} bits -> {len(data_bits)} bits")
    
    # Construir header
    fec_flag = 1 if use_fec else 0
    header_value = (fec_flag << 31) | (file_size & 0x7FFFFFFF)
    header_bytes = struct.pack(">I", header_value)
    header_bits = bytes_to_bits(header_bytes)
    
    # Retornar header + datos
    return header_bits + data_bits

def decode_protocol(received_bits: List[int]) -> Tuple[List[int], int, bool]:
    """
    Decodifica protocolo simple.
    Retorna: (data_bits, file_size, success)
    """
    if len(received_bits) < 32:
        print("Error: Bits insuficientes para header")
        return None, 0, False
    
    # Extraer header
    header_bits = received_bits[:32]
    header_bytes = bits_to_bytes(header_bits)
    header_value = struct.unpack(">I", header_bytes)[0]
    
    # Decodificar header
    fec_enabled = bool((header_value >> 31) & 1)
    file_size = header_value & 0x7FFFFFFF
    
    print(f"  Header decodificado: Size={file_size} bytes, FEC={'Sí' if fec_enabled else 'No'}")
    
    # Calcular bits esperados
    expected_data_bits = file_size * 8
    if fec_enabled:
        expected_received_bits = expected_data_bits * 3
    else:
        expected_received_bits = expected_data_bits
    
    # Extraer datos
    data_bits = received_bits[32:32 + expected_received_bits]
    
    # Rellenar con ceros si faltan bits
    if len(data_bits) < expected_received_bits:
        print(f"  Warning: Faltan {expected_received_bits - len(data_bits)} bits, rellenando con ceros")
        data_bits.extend([0] * (expected_received_bits - len(data_bits)))
    
    # Decodificar FEC si está habilitado
    if fec_enabled:
        data_bits = decode_fec(data_bits)
        print(f"  FEC decodificado: {len(data_bits)*3} bits -> {len(data_bits)} bits")
    
    # Asegurar longitud exacta
    if len(data_bits) > expected_data_bits:
        data_bits = data_bits[:expected_data_bits]
    elif len(data_bits) < expected_data_bits:
        data_bits.extend([0] * (expected_data_bits - len(data_bits)))
    
    return data_bits, file_size, True

# --- Funciones de Alto Nivel ---

def encode_text_file(file_path: str, use_fec: bool) -> Tuple[List[int], int]:
    """
    Codifica un archivo de texto completo.
    Retorna: (bits_to_transmit, original_file_size)
    """
    import os
    
    # Leer archivo
    file_size = os.path.getsize(file_path)
    data_bits = text_file_to_bits(file_path)
    
    print(f"Codificando archivo:")
    print(f"  Tamaño: {file_size} bytes")
    print(f"  Bits de datos: {len(data_bits)}")
    print(f"  FEC: {'Sí' if use_fec else 'No'}")
    
    # Aplicar protocolo
    encoded_bits = encode_protocol(data_bits, file_size, use_fec)
    
    print(f"  Bits totales a transmitir: {len(encoded_bits)}")
    
    return encoded_bits, file_size

def decode_to_text_file(received_bits: List[int], output_path: str) -> Tuple[bool, dict]:
    """
    Decodifica bits recibidos y guarda como archivo de texto.
    Retorna: (success, statistics_dict)
    """
    print(f"Decodificando señal recibida:")
    print(f"  Bits recibidos: {len(received_bits)}")
    
    # Decodificar protocolo
    data_bits, file_size, success = decode_protocol(received_bits)
    
    if not success or data_bits is None:
        return False, {}
    
    # Guardar archivo
    bits_to_text_file(data_bits, output_path)
    
    stats = {
        'file_size': file_size,
        'data_bits': len(data_bits),
        'received_bits': len(received_bits)
    }
    
    print(f"  Archivo guardado: {output_path}")
    
    return True, stats
