
import numpy as np
import scipy.signal as signal
import soundfile as sf
import matplotlib.pyplot as plt
import pyaudio

# --- Funciones Auxiliares ---

def load_audio(file_path, target_samplerate=None):
    """Carga un archivo de audio WAV y lo remuestrea si es necesario."""
    data, samplerate = sf.read(file_path)
    if data.ndim > 1:  # Convertir a mono si es estéreo
        data = data.mean(axis=1)
    if target_samplerate and samplerate != target_samplerate:
        num = int(len(data) * target_samplerate / samplerate)
        data = signal.resample(data, num)
        samplerate = target_samplerate
    return data, samplerate

def save_audio(file_path, data, samplerate):
    """Guarda un archivo de audio WAV."""
    sf.write(file_path, data, samplerate)

def play_audio(data, samplerate):
    """Reproduce una señal de audio."""
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paFloat32, # Asumiendo que los datos son float32
                    channels=1,
                    rate=samplerate,
                    output=True)
    stream.write(data.astype(np.float32).tobytes())
    stream.stop_stream()
    stream.close()
    p.terminate()

def plot_spectrum(signal_data, samplerate, title="Espectro", ax=None):
    """Calcula y grafica el espectro de una señal."""
    N = len(signal_data)
    yf = np.fft.fft(signal_data)
    xf = np.fft.fftfreq(N, 1 / samplerate)
    if ax is None:
        plt.figure()
        plt.plot(xf, np.abs(yf))
        plt.title(title)
        plt.xlabel("Frecuencia (Hz)")
        plt.ylabel("Amplitud")
        plt.grid()
        plt.show()
    else:
        ax.plot(xf, np.abs(yf))
        ax.set_title(title)
        ax.set_xlabel("Frecuencia (Hz)")
        ax.set_ylabel("Amplitud")
        ax.grid()

def plot_time_domain(signal_data, samplerate, title="Dominio del Tiempo", ax=None):
    """Grafica la señal en el dominio del tiempo."""
    t = np.arange(0, len(signal_data)) / samplerate
    if ax is None:
        plt.figure()
        plt.plot(t, signal_data)
        plt.title(title)
        plt.xlabel("Tiempo (s)")
        plt.ylabel("Amplitud")
        plt.grid()
        plt.show()
    else:
        ax.plot(t, signal_data)
        ax.set_title(title)
        ax.set_xlabel("Tiempo (s)")
        ax.set_ylabel("Amplitud")
        ax.grid()

# --- Funciones de Modulación SSB/ISB ---

def hilbert_transform(s):
    """Calcula la transformada de Hilbert de una señal real."""
    return signal.hilbert(s).imag

def ssb_modulate(m_t, samplerate, fc, band_type="USB"):
    """Modula una señal de mensaje a SSB-SC (USB o LSB)."""
    t = np.arange(0, len(m_t)) / samplerate
    m_hilbert_t = hilbert_transform(m_t)

    carrier_cos = np.cos(2 * np.pi * fc * t)
    carrier_sin = np.sin(2 * np.pi * fc * t)

    if band_type == "USB":
        # s_USB(t) = m(t)cos(w_c t) - m_hilbert(t)sin(w_c t)
        s_ssb_t = m_t * carrier_cos - m_hilbert_t * carrier_sin
    elif band_type == "LSB":
        # s_LSB(t) = m(t)cos(w_c t) + m_hilbert(t)sin(w_c t)
        s_ssb_t = m_t * carrier_cos + m_hilbert_t * carrier_sin
    else:
        raise ValueError("band_type debe ser 'USB' o 'LSB'")
    return s_ssb_t

def isb_modulate(m1_t, m2_t, samplerate, fc):
    """Modula dos señales de mensaje a ISB (m1 en USB, m2 en LSB)."""
    t = np.arange(0, len(m1_t)) / samplerate
    m1_hilbert_t = hilbert_transform(m1_t)
    m2_hilbert_t = hilbert_transform(m2_t)

    carrier_cos = np.cos(2 * np.pi * fc * t)
    carrier_sin = np.sin(2 * np.pi * fc * t)

    # USB para m1
    s_usb_t = m1_t * carrier_cos - m1_hilbert_t * carrier_sin
    # LSB para m2
    s_lsb_t = m2_t * carrier_cos + m2_hilbert_t * carrier_sin

    s_isb_t = s_usb_t + s_lsb_t
    return s_isb_t

def ssb_demodulate(s_ssb_t, samplerate, fc, phase_error_deg=0, freq_error_hz=0):
    """Demodula una señal SSB-SC con posibles errores de fase y frecuencia."""
    t = np.arange(0, len(s_ssb_t)) / samplerate

    # Portadora local con errores
    local_carrier = 2 * np.cos(2 * np.pi * (fc + freq_error_hz) * t + np.deg2rad(phase_error_deg))

    # Multiplicación por la portadora local
    demodulated_signal = s_ssb_t * local_carrier

    # Filtro pasa-bajos para recuperar la señal de mensaje
    nyquist = 0.5 * samplerate
    cutoff_freq = fc / 2 # Asumiendo que el mensaje tiene un ancho de banda menor que fc/2
    if cutoff_freq >= nyquist:
        cutoff_freq = nyquist * 0.9 # Asegurarse de que la frecuencia de corte sea menor que Nyquist

    b, a = signal.butter(5, cutoff_freq / nyquist, btype="low")
    m_recovered_t = signal.lfilter(b, a, demodulated_signal)

    return m_recovered_t


# --- Ejemplo de Uso (para pruebas internas) ---
if __name__ == "__main__":
    # Generar una señal de audio de prueba (tono puro)
    samplerate = 44100  # Hz
    duration = 5      # segundos
    f_message = 1000    # Hz (frecuencia del mensaje)
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    message_signal = 0.5 * np.sin(2 * np.pi * f_message * t)

    # Guardar señal de mensaje para prueba
    sf.write("message_test.wav", message_signal, samplerate)

    # Parámetros de modulación
    fc = 10000 # Frecuencia de portadora (Hz)

    print("--- Prueba de Modulación/Demodulación SSB (USB) ---")
    # Modulación SSB (USB)
    ssb_usb_signal = ssb_modulate(message_signal, samplerate, fc, band_type="USB")
    sf.write("ssb_usb_modulated.wav", ssb_usb_signal, samplerate)

    # Demodulación SSB (USB) sin errores
    recovered_usb_no_error = ssb_demodulate(ssb_usb_signal, samplerate, fc)
    sf.write("recovered_usb_no_error.wav", recovered_usb_no_error, samplerate)
    print("Reproduciendo audio recuperado (USB sin errores)...")
    play_audio(recovered_usb_no_error, samplerate)

    # Demodulación SSB (USB) con error de fase (90 grados)
    recovered_usb_phase_error = ssb_demodulate(ssb_usb_signal, samplerate, fc, phase_error_deg=90)
    sf.write("recovered_usb_phase_error.wav", recovered_usb_phase_error, samplerate)
    print("Reproduciendo audio recuperado (USB con error de fase de 90 grados)...")
    play_audio(recovered_usb_phase_error, samplerate)

    # Demodulación SSB (USB) con error de frecuencia (100 Hz)
    recovered_usb_freq_error = ssb_demodulate(ssb_usb_signal, samplerate, fc, freq_error_hz=100)
    sf.write("recovered_usb_freq_error.wav", recovered_usb_freq_error, samplerate)
    print("Reproduciendo audio recuperado (USB con error de frecuencia de 100 Hz)...")
    play_audio(recovered_usb_freq_error, samplerate)

    print("--- Prueba de Modulación/Demodulación SSB (LSB) ---")
    # Modulación SSB (LSB)
    ssb_lsb_signal = ssb_modulate(message_signal, samplerate, fc, band_type="LSB")
    sf.write("ssb_lsb_modulated.wav", ssb_lsb_signal, samplerate)

    # Demodulación SSB (LSB) sin errores
    recovered_lsb_no_error = ssb_demodulate(ssb_lsb_signal, samplerate, fc)
    sf.write("recovered_lsb_no_error.wav", recovered_lsb_no_error, samplerate)
    print("Reproduciendo audio recuperado (LSB sin errores)...")
    play_audio(recovered_lsb_no_error, samplerate)

    print("--- Prueba de Modulación/Demodulación ISB ---")
    # Generar segunda señal de mensaje para ISB
    f_message2 = 2000 # Hz
    message_signal2 = 0.5 * np.sin(2 * np.pi * f_message2 * t)
    sf.write("message_test2.wav", message_signal2, samplerate)

    # Modulación ISB (m1 en USB, m2 en LSB)
    isb_modulated_signal = isb_modulate(message_signal, message_signal2, samplerate, fc)
    sf.write("isb_modulated.wav", isb_modulated_signal, samplerate)

    # Demodulación ISB (requiere separar USB y LSB, lo cual es más complejo y no se implementará directamente aquí como una función simple)
    print("La demodulación ISB completa es más compleja y no se implementa directamente en este ejemplo simple.")

    # --- Graficación de ejemplo (SSB USB sin errores) ---
    fig, axs = plt.subplots(3, 2, figsize=(12, 10))
    fig.suptitle("Modulación y Demodulación SSB (USB) - Ejemplo")

    plot_time_domain(message_signal, samplerate, "Mensaje Original (Tiempo)" , ax=axs[0, 0])
    plot_spectrum(message_signal, samplerate, "Mensaje Original (Frecuencia)" , ax=axs[0, 1])

    plot_time_domain(ssb_usb_signal, samplerate, "SSB Modulada (Tiempo)" , ax=axs[1, 0])
    plot_spectrum(ssb_usb_signal, samplerate, "SSB Modulada (Frecuencia)" , ax=axs[1, 1])

    plot_time_domain(recovered_usb_no_error, samplerate, "Mensaje Recuperado (Tiempo)" , ax=axs[2, 0])
    plot_spectrum(recovered_usb_no_error, samplerate, "Mensaje Recuperado (Frecuencia)" , ax=axs[2, 1])

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig("ssb_usb_example_plots.png")
    # plt.show() # Descomentar para mostrar las gráficas interactivamente

    print("Ejemplo de uso completado. Archivos WAV y gráficas generadas.")

