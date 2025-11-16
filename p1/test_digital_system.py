#!/usr/bin/env python3
"""
Script de prueba para el sistema de comunicación digital simple
Prueba la codificación/decodificación sin transmisión real de audio
"""

from digital_protocol import encode_text_file, decode_to_text_file, encode_protocol, decode_protocol
from digital_simple import bpsk_modulate, bpsk_demodulate
import os

def test_protocol():
    """Prueba el protocolo completo"""
    print("="*60)
    print("PRUEBA DEL SISTEMA DE COMUNICACIÓN DIGITAL")
    print("="*60)
    
    # Crear archivo de prueba
    test_file = "test_message.txt"
    if not os.path.exists(test_file):
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("¡Hola! Este es un mensaje de prueba. 123 ABC.")
    
    print(f"\n1️⃣ Archivo original: {test_file}")
    print(f"   Tamaño: {os.path.getsize(test_file)} bytes")
    
    # Leer contenido original
    with open(test_file, 'r', encoding='utf-8') as f:
        original_text = f.read()
    print(f"   Contenido: '{original_text}'")
    
    # Probar SIN FEC
    print("\n" + "="*60)
    print("PRUEBA SIN FEC")
    print("="*60)
    test_transmission(test_file, use_fec=False)
    
    # Probar CON FEC
    print("\n" + "="*60)
    print("PRUEBA CON FEC")
    print("="*60)
    test_transmission(test_file, use_fec=True)

def test_transmission(input_file, use_fec):
    """Simula una transmisión completa"""
    
    # 1. Codificar
    print("\n📤 Codificando archivo...")
    encoded_bits, file_size = encode_text_file(input_file, use_fec)
    print(f"   Bits totales: {len(encoded_bits)}")
    
    # 2. Modular BPSK
    print("\n🔊 Modulando en BPSK...")
    symbols = bpsk_modulate(encoded_bits)
    print(f"   Símbolos: {len(symbols)}")
    
    # 3. Simular canal (en este caso, perfecto - sin ruido)
    print("\n📡 Simulando canal perfecto...")
    received_symbols = symbols.copy()
    
    # 4. Demodular BPSK
    print("\n📥 Demodulando BPSK...")
    demod_bits = bpsk_demodulate(received_symbols)
    print(f"   Bits demodulados: {len(demod_bits)}")
    
    # 5. Decodificar
    print("\n🔓 Decodificando protocolo...")
    output_file = f"test_output_{'fec' if use_fec else 'nofec'}.txt"
    success, stats = decode_to_text_file(demod_bits, output_file)
    
    if success:
        print(f"\n✅ ÉXITO: Archivo guardado como {output_file}")
        
        # Verificar contenido
        with open(input_file, 'r', encoding='utf-8') as f:
            original = f.read()
        with open(output_file, 'r', encoding='utf-8') as f:
            recovered = f.read()
        
        if original == recovered:
            print("   ✅ Contenido idéntico al original")
        else:
            print("   ❌ Contenido difiere del original")
            print(f"      Original : '{original}'")
            print(f"      Recuperado: '{recovered}'")
        
        # Mostrar estadísticas
        print(f"\n📊 Estadísticas:")
        print(f"   Tamaño archivo: {stats['file_size']} bytes")
        print(f"   Bits de datos: {stats['data_bits']}")
        print(f"   Bits totales: {stats['received_bits']}")
        if use_fec:
            overhead = (stats['received_bits'] - 32) / stats['data_bits']
            print(f"   Overhead FEC: {overhead:.2f}x")
    else:
        print("\n❌ ERROR: No se pudo decodificar")

def test_fec_correction():
    """Prueba la capacidad de corrección del FEC"""
    print("\n" + "="*60)
    print("PRUEBA DE CORRECCIÓN FEC")
    print("="*60)
    
    # Crear bits de prueba
    test_bits = [1, 0, 1, 1, 0, 0, 1, 0]
    print(f"\nBits originales: {test_bits}")
    
    # Codificar con FEC
    from digital_protocol import apply_fec, decode_fec
    fec_bits = apply_fec(test_bits)
    print(f"Bits con FEC: {fec_bits}")
    print(f"Longitud: {len(test_bits)} → {len(fec_bits)}")
    
    # Introducir errores
    fec_with_errors = fec_bits.copy()
    # Corromper 1 bit por cada 3 (dentro de la capacidad de corrección)
    fec_with_errors[0] = 1 - fec_with_errors[0]  # Error en primer triplete
    fec_with_errors[5] = 1 - fec_with_errors[5]  # Error en segundo triplete
    
    print(f"\nBits con errores: {fec_with_errors}")
    
    # Decodificar
    recovered = decode_fec(fec_with_errors)
    print(f"Bits recuperados: {recovered}")
    
    if recovered == test_bits:
        print("✅ FEC corrigió los errores exitosamente")
    else:
        print("❌ FEC no pudo corregir todos los errores")

if __name__ == "__main__":
    try:
        test_protocol()
        test_fec_correction()
        
        print("\n" + "="*60)
        print("✅ TODAS LAS PRUEBAS COMPLETADAS")
        print("="*60)
        print("\nAhora puedes probar con las aplicaciones GUI:")
        print("  TX: python tx_app_clean.py")
        print("  RX: python rx_app_clean.py")
        
    except Exception as e:
        print(f"\n❌ ERROR EN PRUEBAS: {e}")
        import traceback
        traceback.print_exc()
