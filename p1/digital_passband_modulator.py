
import numpy as np
import scipy.signal as signal
import soundfile as sf
import matplotlib.pyplot as plt
import pyaudio
import os
import struct

# --- Parámetros Generales (Ajustables) ---
FS = 44100  # Frecuencia de muestreo (Hz)
CARRIER_FREQ = 8000 # Frecuencia de portadora para modulación digital (Hz)
BAUD_RATE = 1000 # Tasa de símbolos (símbolos/segundo)
SAMPLES_PER_SYMBOL = FS // BAUD_RATE # Muestras por símbolo

# --- Funciones Auxiliares ---

def bits_to_bytes(bits):
    """Convierte una lista de bits a un array de bytes."""
    byte_array = bytearray()
    # No añadir padding si ya es un múltiplo de 8
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

def bits_to_file(bits, file_path):
    """Convierte una secuencia de bits a un archivo."""
    data_bytes = bits_to_bytes(bits)
    with open(file_path, 'wb') as f:
        f.write(data_bytes)

def plot_spectrum(signal_data, samplerate, title="Espectro", ax=None):
    """Calcula y grafica el espectro de una señal."""
    N = len(signal_data)
    yf = np.fft.fft(signal_data)
    xf = np.fft.fftfreq(N, 1 / samplerate)
    if ax is None:
        plt.figure()
        plt.plot(xf, np.abs(yf))
        plt.title(title)
        plt.xlabel('Frecuencia (Hz)')
        plt.ylabel('Amplitud')
        plt.grid()
        plt.show()
    else:
        ax.plot(xf, np.abs(yf))
        ax.set_title(title)
        ax.set_xlabel('Frecuencia (Hz)')
        ax.set_ylabel('Amplitud')
        ax.grid()

def plot_time_domain(signal_data, samplerate, title="Dominio del Tiempo", ax=None):
    """Grafica la señal en el dominio del tiempo."""
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

def plot_constellation(symbols, title="Diagrama de Constelación", ax=None):
    """Grafica el diagrama de constelación."""
    if ax is None:
        plt.figure()
        plt.plot(np.real(symbols), np.imag(symbols), 'o')
        plt.title(title)
        plt.xlabel('Parte Real')
        plt.ylabel('Parte Imaginaria')
        plt.grid()
        plt.axhline(0, color='black',linewidth=0.5)
        plt.axvline(0, color='black',linewidth=0.5)
        plt.show()
    else:
        ax.plot(np.real(symbols), np.imag(symbols), 'o')
        ax.set_title(title)
        ax.set_xlabel('Parte Real')
        ax.set_ylabel('Parte Imaginaria')
        ax.grid()
        ax.axhline(0, color='black',linewidth=0.5)
        ax.axvline(0, color='black',linewidth=0.5)

def plot_eye_diagram(signal_data, samples_per_symbol, num_symbols_to_plot=3, title="Diagrama de Ojo", ax=None):
    """Genera y grafica un diagrama de ojo."""
    if ax is None:
        plt.figure()
        ax = plt.gca()

    # Asegurarse de que la señal sea lo suficientemente larga
    if len(signal_data) < samples_per_symbol * num_symbols_to_plot:
        print("Advertencia: Señal demasiado corta para generar un diagrama de ojo significativo.")
        return

    # Normalizar la señal para una mejor visualización
    signal_data = signal_data / np.max(np.abs(signal_data))

    for i in range(0, len(signal_data) - samples_per_symbol * num_symbols_to_plot, samples_per_symbol // 2):
        segment = signal_data[i : i + samples_per_symbol * num_symbols_to_plot]
        if len(segment) == samples_per_symbol * num_symbols_to_plot:
            ax.plot(np.linspace(0, num_symbols_to_plot, len(segment)), segment, 'b-', alpha=0.1)

    ax.set_title(title)
    ax.set_xlabel('Tiempo (símbolos)')
    ax.set_ylabel('Amplitud Normalizada')
    ax.grid(True)
    ax.set_xticks(np.arange(0, num_symbols_to_plot + 1))
    ax.set_xlim(0, num_symbols_to_plot)
    if ax is None:
        plt.show()

# --- Codificación de Canal (Placeholder) ---

def apply_fec(bits, use_fec=False):
    """Aplica un algoritmo de corrección de errores (placeholder)."""
    if use_fec:
        print("Aplicando FEC (placeholder: no se aplica FEC real).")
        # Aquí iría la lógica real de codificación FEC, por ejemplo, Hamming o Reed-Solomon
        # Por ahora, solo devolvemos los bits originales.
    return bits

def decode_fec(bits, use_fec=False):
    """Decodifica un algoritmo de corrección de errores (placeholder)."""
    if use_fec:
        print("Decodificando FEC (placeholder: no se decodifica FEC real).")
        # Aquí iría la lógica real de decodificación FEC
    return bits

# --- Modulación Digital (BPSK como ejemplo) ---

def bpsk_modulate(bits):
    """Modula una secuencia de bits usando BPSK."""
    # 0 -> -1, 1 -> +1
    symbols = np.array([1.0 if bit == 1 else -1.0 for bit in bits])
    return symbols

def bpsk_demodulate(received_symbols):
    """Demodula símbolos BPSK."""
    # Si la parte real es > 0 es 1, si es < 0 es 0
    demodulated_bits = [1 if np.real(symbol) > 0 else 0 for symbol in received_symbols]
    return demodulated_bits

def generate_passband_signal(symbols, carrier_freq, fs, samples_per_symbol):
    """Genera una señal pasobanda a partir de símbolos (BPSK)."""
    t_symbol = np.linspace(0, 1/BAUD_RATE, samples_per_symbol, endpoint=False)
    full_signal = np.array([])
    for symbol in symbols:
        # Multiplicar el símbolo por la portadora
        # Para BPSK, el símbolo es real (-1 o 1)
        modulated_waveform = symbol * np.cos(2 * np.pi * carrier_freq * t_symbol)


        full_signal = np.concatenate((full_signal, modulated_waveform))
    return full_signal

def receive_and_demodulate_passband_signal(received_signal, carrier_freq, fs, samples_per_symbol, num_symbols):
    """Demodula una señal pasobanda recibida (BPSK)."""
    # Sincronización (simplificada: asume sincronización perfecta)
    # En una implementación real, se necesitarían algoritmos de sincronización de tiempo y fase.

    # Multiplicar por la portadora local (coherente)
    t_full = np.arange(0, len(received_signal)) / fs
    local_carrier = np.cos(2 * np.pi * carrier_freq * t_full)
    demodulated_baseband = received_signal * local_carrier

    # Filtro pasa-bajos para extraer la señal de banda base
    nyquist = 0.5 * fs
    cutoff_freq = BAUD_RATE / 2 * 1.5 # Frecuencia de corte un poco mayor que la tasa de símbolos
    if cutoff_freq >= nyquist:
        cutoff_freq = nyquist * 0.9
    b, a = signal.butter(5, cutoff_freq / nyquist, btype='low')
    filtered_baseband = signal.lfilter(b, a, demodulated_baseband)

    # Muestreo en el instante óptimo (simplificado)
    # En una implementación real, se necesitaría un algoritmo de recuperación de reloj.
    sampled_symbols = []
    for i in range(num_symbols):
        sample_index = int(i * samples_per_symbol + samples_per_symbol / 2) # Muestrear a la mitad del símbolo
        if sample_index < len(filtered_baseband):
            sampled_symbols.append(filtered_baseband[sample_index])
        else:
            sampled_symbols.append(0) # Rellenar si la señal es más corta de lo esperado

    return np.array(sampled_symbols), filtered_baseband, demodulated_baseband

# --- Transmisión y Recepción de Audio (PyAudio) ---

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

# --- Protocolo de Transmisión (Simplificado) ---


# ============================================================
# PREÁMBULO Y POSTÁMBULO
# ============================================================

# Patrón de sincronización robusto (repetido y balanceado)
PREAMBLE_BITS = [1,0,1,0,1,1,0,0] * 4   # 32 bits con buena autocorrelación
POSTAMBLE_BITS = [0,1,0,1,0,0,1,1] * 4  # patrón invertido (también 32 bits)

# ============================================================
# CODIFICACIÓN DE DATOS
# ============================================================

def encode_data_simple(bits, original_file_size, file_extension):
    """
    Formato transmitido:
    [PREAMBLE] [size:4 bytes] [ext_len:1 byte] [ext ASCII] [payload bits] [POSTAMBLE]
    """
    # Tamaño del archivo en bytes → 4 bytes big-endian
    size_bytes = struct.pack(">I", original_file_size)
    size_bits = bytes_to_bits(size_bytes)

    # Extensión
    ext_bytes = file_extension.encode("ascii")
    ext_len = len(ext_bytes)
    if ext_len > 6:
        raise ValueError("Extensión demasiado larga (>6 caracteres)")
    ext_len_bits = bytes_to_bits(bytes([ext_len]))
    ext_bits = bytes_to_bits(ext_bytes)

    # Armar secuencia final
    encoded = PREAMBLE_BITS + size_bits + ext_len_bits + ext_bits + bits + POSTAMBLE_BITS
    return encoded


# ============================================================
# DECODIFICACIÓN ROBUSTA
# ============================================================

def find_sequence(haystack, needle, max_offset=2000):
    """Busca una secuencia binaria (needle) dentro de otra (haystack)."""
    nh = len(haystack)
    nn = len(needle)
    for i in range(min(nh - nn, max_offset)):
        if haystack[i:i+nn] == needle:
            return i
    return -1


def decode_data_simple(received_bits):
    """
    Detecta preámbulo y postámbulo, extrae tamaño, extensión y datos.
    """
    import struct

    # Buscar preámbulo
    start_idx = find_sequence(received_bits, PREAMBLE_BITS)
    if start_idx == -1:
        print("❌ No se encontró preámbulo.")
        return None, None, None

    # Buscar postámbulo (después del preámbulo)
    search_region = received_bits[start_idx + len(PREAMBLE_BITS):]
    end_rel = find_sequence(search_region, POSTAMBLE_BITS)
    if end_rel == -1:
        print("❌ No se encontró postámbulo.")
        return None, None, None

    end_idx = start_idx + len(PREAMBLE_BITS) + end_rel
    data_region = received_bits[start_idx + len(PREAMBLE_BITS): end_idx]

    # 1) Tamaño (32 bits)
    if len(data_region) < 32:
        print("❌ Paquete incompleto (sin tamaño).")
        return None, None, None

    size_bits = data_region[:32]
    original_file_size = struct.unpack(">I", bits_to_bytes(size_bits))[0]

    # 2) Longitud de extensión (8 bits)
    if len(data_region) < 40:
        print("❌ Paquete incompleto (sin longitud de extensión).")
        return None, None, None

    ext_len_bits = data_region[32:40]
    ext_len = bits_to_bytes(ext_len_bits)[0]

    if ext_len == 0 or ext_len > 6:
        print("⚠️ Extensión inválida, usando .bin")
        file_extension = "bin"
        data_start = 40
    else:
        # 3) Extraer extensión
        ext_bits = data_region[40:40 + ext_len * 8]
        raw_ext = bits_to_bytes(ext_bits)
        try:
            file_extension = raw_ext.decode("ascii")
        except:
            print("⚠️ Extensión corrupta, usando .bin")
            file_extension = "bin"
        data_start = 40 + ext_len * 8

    # 4) Datos binarios
    payload_bits = data_region[data_start:]
    expected_bits = original_file_size * 8

    # Relleno si faltan bits
    if len(payload_bits) < expected_bits:
        payload_bits += [0] * (expected_bits - len(payload_bits))
    elif len(payload_bits) > expected_bits:
        payload_bits = payload_bits[:expected_bits]

    return payload_bits, original_file_size, file_extension


def record_audio_with_tone_trigger(
        fs,
        chunk=1024,
        start_tone_freq=1000.0,
        start_tone_bw=30.0,
        start_ratio=0.5,
        stop_tone_freq=2000.0,
        stop_tone_bw=30.0,
        stop_ratio=0.5
    ):
        """Graba indefinidamente hasta detectar tono de inicio; luego graba hasta tono de fin."""

        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=chunk)

        print("📡 Esperando tono de INICIO...")
        recording = False
        frames = []

        try:
            while True:
                data = stream.read(chunk, exception_on_overflow=False)
                x = np.frombuffer(data, dtype=np.float32)

                # FFT
                w = np.hanning(len(x))
                X = np.fft.rfft(x * w)
                P = np.abs(X)**2
                freqs = np.fft.rfftfreq(len(x), 1/fs)

                def detect_tone(freq, bw, ratio):
                    mask = np.abs(freqs - freq) <= bw
                    band = P[mask].sum() if np.any(mask) else 0.0
                    total = P.sum() + 1e-12
                    return (band / total) >= ratio

                if not recording:
                    if detect_tone(start_tone_freq, start_tone_bw, start_ratio):
                        print("🎙️ Tono de inicio detectado → Comenzando grabación...")
                        recording = True
                else:
                    frames.append(x.copy())

                    if detect_tone(stop_tone_freq, stop_tone_bw, stop_ratio):
                        print("🛑 Tono de fin detectado → Finalizando grabación.")
                        break

        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

        if len(frames) == 0:
            return None

        return np.concatenate(frames)

# --- Cálculo de BER ---

def calculate_ber(original_bits, received_bits):
    """Calcula la Tasa de Error de Bit (BER)."""
    min_len = min(len(original_bits), len(received_bits))
    errors = sum(1 for i in range(min_len) if original_bits[i] != received_bits[i])
    if min_len == 0:
        return 0.0
    return errors / min_len

# --- Ejemplo de Uso (para pruebas internas) ---
if __name__ == '__main__':
    # Crear un archivo de texto de prueba
    test_file_name = 'test_digital_data.txt'
    with open(test_file_name, 'w') as f:
        f.write("Hola mundo! Este es un mensaje de prueba para la transmisión digital.\n")
        f.write("El objetivo es enviar este archivo a través del canal de audio.\n")
        f.write("Se utilizará modulación BPSK y un protocolo simple.\n")

    original_file_size = os.path.getsize(test_file_name)
    original_bits = file_to_bits(test_file_name)

    print(f"Archivo original: {test_file_name} ({original_file_size} bytes, {len(original_bits)} bits)")

    # 1. Codificación con protocolo
    encoded_bits = encode_data_with_protocol(original_bits, original_file_size, use_fec=False)
    print(f"Bits codificados con protocolo: {len(encoded_bits)} bits")

    # 2. Modulación BPSK
    bpsk_symbols = bpsk_modulate(encoded_bits)
    print(f"Símbolos BPSK generados: {len(bpsk_symbols)}")

    # 3. Generar señal pasobanda
    passband_signal = generate_passband_signal(bpsk_symbols, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL)
    print(f"Señal pasobanda generada: {len(passband_signal)} muestras")

    # Normalizar la señal para evitar clipping en la tarjeta de sonido
    passband_signal = 0.8 * passband_signal / np.max(np.abs(passband_signal))

    # Guardar la señal modulada para inspección
    sf.write('digital_modulated_signal.wav', passband_signal, FS)

    # 4. Transmitir y Recibir (simulado o real)
    # Para una prueba real, descomentar las siguientes líneas:
    # transmit_audio(passband_signal, FS)
    # received_audio_signal = record_audio(duration=len(passband_signal)/FS + 1, fs=FS) # +1 segundo para asegurar captura completa

    # Para simulación, usamos los bits codificados directamente como recibidos (canal ideal para la lógica de protocolo)
    # Esto evita la complejidad de la demodulación analógica para probar el protocolo.
    demodulated_bits_with_protocol = encoded_bits

    # Inicializar variables para la graficación, ya que no se ejecutó la demodulación analógica
    received_audio_signal = passband_signal # Necesario para la longitud de la señal
    received_symbols = bpsk_symbols # Para la constelación
    # Crear placeholders para las señales de banda base si no se van a generar a través de la demodulación analógica
    filtered_baseband = np.zeros_like(passband_signal) # Placeholder
    demodulated_baseband = np.zeros_like(passband_signal) # Placeholder




    print(f"Bits demodulados con protocolo: {len(demodulated_bits_with_protocol)} bits")

    # 6. Decodificación de protocolo
    recovered_bits, recovered_file_size = decode_data_with_protocol(demodulated_bits_with_protocol, use_fec=False)

    if recovered_bits is not None and recovered_file_size is not None:

        # 7. Guardar archivo recuperado
        recovered_file_name = 'recovered_digital_data.txt'
        bits_to_file(recovered_bits, recovered_file_name)
        print(f"Archivo recuperado: {recovered_file_name} ({recovered_file_size} bytes)")

        # 8. Calcular BER
        ber = calculate_ber(original_bits, recovered_bits)
        print(f"Tasa de Error de Bit (BER): {ber:.6f}")

        # 9. Tasa de Transferencia (aproximada, sin considerar overhead de protocolo/FEC)
        transmission_time = len(passband_signal) / FS
        data_rate_bps = (original_file_size * 8) / transmission_time
        print(f"Tasa de transferencia (aproximada): {data_rate_bps:.2f} bps")

        # --- Graficación ---
        fig, axs = plt.subplots(4, 2, figsize=(14, 16))
        fig.suptitle('Modulación y Demodulación Digital Pasobanda (BPSK) - Ejemplo')

        # Modulador
        plot_time_domain(passband_signal[:FS], FS, 'Señal Modulada (Tiempo - 1s)' , ax=axs[0, 0])
        plot_spectrum(passband_signal, FS, 'Señal Modulada (Frecuencia)' , ax=axs[0, 1])

        # Recalcular la banda base filtrada para graficar
        t_full_received = np.arange(0, len(received_audio_signal)) / FS
        local_carrier_plot = np.cos(2 * np.pi * CARRIER_FREQ * t_full_received)
        demodulated_baseband_plot = received_audio_signal * local_carrier_plot
        nyquist_plot = 0.5 * FS
        cutoff_freq_plot = BAUD_RATE / 2 * 1.5
        if cutoff_freq_plot >= nyquist_plot:
            cutoff_freq_plot = nyquist_plot * 0.9
        b_plot, a_plot = signal.butter(5, cutoff_freq_plot / nyquist_plot, btype='low')
        filtered_baseband_for_plot = signal.lfilter(b_plot, a_plot, demodulated_baseband_plot)

        # Demodulador
        plot_time_domain(filtered_baseband_for_plot[:FS], FS, 'Banda Base Filtrada (Tiempo - 1s)' , ax=axs[1, 0])
        plot_spectrum(filtered_baseband_for_plot, FS, 'Banda Base Filtrada (Frecuencia)' , ax=axs[1, 1])

        # Constelación
        plot_constellation(bpsk_symbols, 'Constelación Transmitida (BPSK)' , ax=axs[2, 0])
        plot_constellation(received_symbols, 'Constelación Recibida (BPSK)' , ax=axs[2, 1])

        # Diagrama de Ojo
        plot_eye_diagram(filtered_baseband_for_plot, SAMPLES_PER_SYMBOL, title="Diagrama de Ojo (Banda Base Filtrada)" , ax=axs[3, 0])
        axs[3, 1].axis('off') # Ocultar el segundo subgráfico si no se usa
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.savefig('digital_modulation_example_plots.png')
        # plt.show() # Descomentar para mostrar las gráficas interactivamente

    else:
        print("Ejemplo de uso de modulación digital completado. Archivos y gráficas generadas.")


