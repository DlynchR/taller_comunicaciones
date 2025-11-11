import numpy as np
from digital_passband_modulator import (
    record_audio_with_tone_trigger, receive_and_demodulate_passband_signal, 
    bpsk_demodulate, decode_data_simple, bits_to_file, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL
)

def bpsk_receive(carrier=CARRIER_FREQ):
    rec = record_audio_with_tone_trigger(fs=FS, start_tone_freq=1000.0, stop_tone_freq=2000.0)
    if rec is None:
        print("❌ No se detectaron tonos de inicio/fin.")
        return

    num_symbols = max(1, int(len(rec) / SAMPLES_PER_SYMBOL))
    sampled, _, _ = receive_and_demodulate_passband_signal(rec, carrier, FS, SAMPLES_PER_SYMBOL, num_symbols)
    bits = bpsk_demodulate(sampled)

    recovered_bits, size, ext = decode_data_simple(bits)
    if recovered_bits is None:
        print("❌ Error al decodificar protocolo.")
        return

    output = f"archivo_recibido.{ext}"
    bits_to_file(recovered_bits, output)
    print(f"✅ Archivo recibido y guardado como: {output}")

if __name__ == "__main__":
    bpsk_receive()
