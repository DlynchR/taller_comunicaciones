
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import soundfile as sf
import scipy.signal as signal
import os

# Importar las funciones de los módulos de simulación
from ssb_isb_simulator import load_audio, save_audio, play_audio, plot_spectrum, plot_time_domain, ssb_modulate, isb_modulate, ssb_demodulate, hilbert_transform
from digital_passband_modulator import file_to_bits, bits_to_file, encode_data_with_protocol, bpsk_modulate, generate_passband_signal, transmit_audio, record_audio, receive_and_demodulate_passband_signal, bpsk_demodulate, decode_data_with_protocol, calculate_ber, plot_constellation, plot_eye_diagram, FS, CARRIER_FREQ, BAUD_RATE, SAMPLES_PER_SYMBOL

class CommunicationsSimulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Simulador de Modulaciones de Comunicaciones")

        # Variables para SSB/ISB - Inicializar ANTES de crear las pestañas
        self.ssb_audio_file_path = tk.StringVar()
        self.ssb_audio_file_path2 = tk.StringVar() # Para ISB
        self.ssb_carrier_freq = tk.DoubleVar(value=15000) # Default 15 kHz
        self.ssb_modulation_type = tk.StringVar(value="SSB-SC")
        self.ssb_band_type = tk.StringVar(value="USB")
        self.ssb_phase_error = tk.DoubleVar(value=0)
        self.ssb_freq_error = tk.DoubleVar(value=0)

        self.message_signal = None
        self.message_signal2 = None
        self.samplerate = None
        self.modulated_ssb_signal = None
        self.recovered_ssb_signal = None

        # Variables para Digital Pasobanda
        self.digital_file_path = tk.StringVar()
        self.digital_use_fec = tk.BooleanVar(value=False)
        self.original_digital_bits = None
        self.modulated_digital_signal = None
        self.recovered_digital_bits = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Pestaña SSB/ISB ---
        self.ssb_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.ssb_frame, text="SSB/ISB")
        self.create_ssb_tab(self.ssb_frame)

        # --- Pestaña Digital Pasobanda ---
        self.digital_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.digital_frame, text="Digital Pasobanda")
        self.create_digital_tab(self.digital_frame)

    def create_ssb_tab(self, parent_frame):
        # Controles de entrada
        input_frame = ttk.LabelFrame(parent_frame, text="Parámetros de Entrada SSB/ISB")
        input_frame.pack(padx=10, pady=10, fill="x")

        # Archivo de audio 1
        ttk.Label(input_frame, text="Archivo de Audio (WAV): ").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.ssb_audio_file_path, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(input_frame, text="Seleccionar", command=lambda: self.select_audio_file(self.ssb_audio_file_path)).grid(row=0, column=2, padx=5, pady=2)

        # Archivo de audio 2 (para ISB)
        ttk.Label(input_frame, text="Archivo de Audio 2 (WAV, para ISB): ").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.ssb_audio_file_path2, width=50).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(input_frame, text="Seleccionar", command=lambda: self.select_audio_file(self.ssb_audio_file_path2)).grid(row=1, column=2, padx=5, pady=2)

        # Frecuencia de portadora
        ttk.Label(input_frame, text="Frecuencia de Portadora (Hz, max 25KHz): ").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.ssb_carrier_freq, width=10).grid(row=2, column=1, padx=5, pady=2, sticky="w")

        # Tipo de modulación
        ttk.Label(input_frame, text="Tipo de Modulación: ").grid(row=3, column=0, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(input_frame, text="SSB-SC", variable=self.ssb_modulation_type, value="SSB-SC").grid(row=3, column=1, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(input_frame, text="ISB", variable=self.ssb_modulation_type, value="ISB").grid(row=3, column=2, padx=5, pady=2, sticky="w")

        # Banda lateral (solo para SSB-SC)
        ttk.Label(input_frame, text="Banda Lateral (SSB-SC): ").grid(row=4, column=0, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(input_frame, text="USB", variable=self.ssb_band_type, value="USB").grid(row=4, column=1, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(input_frame, text="LSB", variable=self.ssb_band_type, value="LSB").grid(row=4, column=2, padx=5, pady=2, sticky="w")

        # Error de fase
        ttk.Label(input_frame, text="Error de Fase (grados, 0-180): ").grid(row=5, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.ssb_phase_error, width=10).grid(row=5, column=1, padx=5, pady=2, sticky="w")

        # Error de frecuencia
        ttk.Label(input_frame, text="Error de Frecuencia (Hz, +/-25% de fc): ").grid(row=6, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.ssb_freq_error, width=10).grid(row=6, column=1, padx=5, pady=2, sticky="w")

        # Botones de acción
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(padx=10, pady=5, fill="x")
        ttk.Button(button_frame, text="Modular y Demodular", command=self.run_ssb_simulation).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Reproducir Audio Recuperado", command=self.play_recovered_ssb_audio).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Reproducir señal Modulada", command=lambda: play_audio(self.modulated_ssb_signal, self.samplerate) if self.modulated_ssb_signal is not None else messagebox.showwarning("Advertencia", "No hay señal modulada para reproducir.")).pack(side="left", padx=5)

        # Área de gráficas
        self.ssb_fig, self.ssb_axs = plt.subplots(3, 2, figsize=(12, 10))
        self.ssb_canvas = FigureCanvasTkAgg(self.ssb_fig, master=parent_frame)
        self.ssb_canvas_widget = self.ssb_canvas.get_tk_widget()
        self.ssb_canvas_widget.pack(padx=10, pady=10, expand=True, fill="both")

    def create_digital_tab(self, parent_frame):
        # Controles de entrada
        input_frame = ttk.LabelFrame(parent_frame, text="Parámetros de Transmisión Digital Pasobanda")
        input_frame.pack(padx=10, pady=10, fill="x")

        # Archivo digital
        ttk.Label(input_frame, text="Archivo Digital a Enviar: ").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Entry(input_frame, textvariable=self.digital_file_path, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(input_frame, text="Seleccionar", command=lambda: self.select_digital_file(self.digital_file_path)).grid(row=0, column=2, padx=5, pady=2)

        # Corrección de errores
        ttk.Checkbutton(input_frame, text="Usar Corrección de Errores (FEC)", variable=self.digital_use_fec).grid(row=1, column=0, columnspan=3, padx=5, pady=2, sticky="w")

        # Botones de acción
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(padx=10, pady=5, fill="x")
        ttk.Button(button_frame, text="Transmitir Archivo", command=self.run_digital_transmission).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Recibir Archivo", command=self.run_digital_reception).pack(side="left", padx=5)

        # Área de resultados
        self.digital_results_text = tk.Text(parent_frame, height=5, width=80)
        self.digital_results_text.pack(padx=10, pady=5, fill="x")

        # Área de gráficas
        self.digital_fig, self.digital_axs = plt.subplots(4, 2, figsize=(12, 16))
        self.digital_canvas = FigureCanvasTkAgg(self.digital_fig, master=parent_frame)
        self.digital_canvas_widget = self.digital_canvas.get_tk_widget()
        self.digital_canvas_widget.pack(padx=10, pady=10, expand=True, fill="both")

    def select_audio_file(self, path_var):
        file_path = filedialog.askopenfilename(filetypes=[("Archivos WAV", "*.wav")])
        if file_path:
            path_var.set(file_path)

    def select_digital_file(self, path_var):
        file_path = filedialog.askopenfilename()
        if file_path:
            path_var.set(file_path)

    def run_ssb_simulation(self):
        try:
            audio_file = self.ssb_audio_file_path.get()
            if not audio_file:
                messagebox.showerror("Error", "Por favor, seleccione un archivo de audio WAV.")
                return

            fc = self.ssb_carrier_freq.get()
            if not (0 < fc <= 25000):
                messagebox.showerror("Error", "La frecuencia de portadora debe estar entre 0 y 25 KHz.")
                return

            phase_error = self.ssb_phase_error.get()
            if not (0 <= phase_error <= 180):
                messagebox.showerror("Error", "El error de fase debe estar entre 0 y 180 grados.")
                return

            freq_error = self.ssb_freq_error.get()
            # Validar error de frecuencia como +/- 25% de fc
            if not (-0.25 * fc <= freq_error <= 0.25 * fc):
                messagebox.showerror("Error", f"El error de frecuencia debe estar entre {-0.25*fc:.2f} Hz y {0.25*fc:.2f} Hz (±25% de la portadora).")
                return

            mod_type = self.ssb_modulation_type.get()
            band_type = self.ssb_band_type.get()

            self.message_signal, self.samplerate = load_audio(audio_file)
            self.message_signal = self.message_signal / np.max(np.abs(self.message_signal)) # Normalizar

            # Limpiar gráficas anteriores
            for ax_row in self.ssb_axs:
                for ax in ax_row:
                    ax.clear()

            # Graficar mensaje original
            plot_time_domain(self.message_signal, self.samplerate, "Mensaje Original (Tiempo)", ax=self.ssb_axs[0, 0])
            plot_spectrum(self.message_signal, self.samplerate, "Mensaje Original (Frecuencia)", ax=self.ssb_axs[0, 1])

            if mod_type == "SSB-SC":
                self.modulated_ssb_signal = ssb_modulate(self.message_signal, self.samplerate, fc, band_type=band_type)
                title_mod = f"SSB-SC {band_type} Modulada"
                # Demodulación
                self.recovered_ssb_signal = ssb_demodulate(self.modulated_ssb_signal, self.samplerate, fc, phase_error_deg=phase_error, freq_error_hz=freq_error)
                title_demod = "Mensaje Recuperado SSB-SC"

            elif mod_type == "ISB":
                audio_file2 = self.ssb_audio_file_path2.get()
                if not audio_file2:
                    messagebox.showerror("Error", "Para ISB, por favor seleccione un segundo archivo de audio WAV.")
                    return
                message_signal2, samplerate2 = load_audio(audio_file2)
                if samplerate2 != self.samplerate:
                    messagebox.showwarning("Advertencia", "El segundo archivo de audio tiene una frecuencia de muestreo diferente. Se remuestreará.")
                    message_signal2, _ = load_audio(audio_file2, target_samplerate=self.samplerate)
                self.message_signal2 = message_signal2 / np.max(np.abs(message_signal2)) # Normalizar

                # Asegurar que ambas señales tengan la misma longitud
                min_len = min(len(self.message_signal), len(self.message_signal2))
                self.message_signal = self.message_signal[:min_len]
                self.message_signal2 = self.message_signal2[:min_len]

                self.modulated_ssb_signal = isb_modulate(self.message_signal, self.message_signal2, self.samplerate, fc)
                title_mod = "ISB Modulada"
                # La demodulación ISB es más compleja y requiere filtros de banda para separar las señales.
                # Por simplicidad, aquí se demodulará la USB (m1) y se mostrará.
                # Para una implementación completa, se necesitarían dos demoduladores y filtros de banda.
                # Aquí, simulamos la demodulación de la USB (m1) asumiendo que es la señal principal.
                self.recovered_ssb_signal = ssb_demodulate(self.modulated_ssb_signal, self.samplerate, fc, phase_error_deg=phase_error, freq_error_hz=freq_error)
                title_demod = "Mensaje Recuperado (USB de ISB)"
                messagebox.showinfo("Nota ISB", "La demodulación ISB en este simulador recupera la banda lateral superior (USB) como ejemplo. La recuperación completa de ambas bandas laterales independientes requeriría un procesamiento adicional (filtrado de banda y dos demoduladores).")

            # Normalizar la señal modulada para visualización
            self.modulated_ssb_signal = self.modulated_ssb_signal / np.max(np.abs(self.modulated_ssb_signal)) if np.max(np.abs(self.modulated_ssb_signal)) > 0 else self.modulated_ssb_signal

            # Graficar señal modulada
            plot_time_domain(self.modulated_ssb_signal, self.samplerate, title_mod + " (Tiempo)", ax=self.ssb_axs[1, 0])
            plot_spectrum(self.modulated_ssb_signal, self.samplerate, title_mod + " (Frecuencia)", ax=self.ssb_axs[1, 1])

            # Normalizar la señal recuperada para visualización y reproducción
            self.recovered_ssb_signal = self.recovered_ssb_signal / np.max(np.abs(self.recovered_ssb_signal)) if np.max(np.abs(self.recovered_ssb_signal)) > 0 else self.recovered_ssb_signal

            # Graficar mensaje recuperado
            plot_time_domain(self.recovered_ssb_signal, self.samplerate, title_demod + " (Tiempo)", ax=self.ssb_axs[2, 0])
            plot_spectrum(self.recovered_ssb_signal, self.samplerate, title_demod + " (Frecuencia)", ax=self.ssb_axs[2, 1])

            self.ssb_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            self.ssb_canvas.draw()

            messagebox.showinfo("Éxito", "Simulación SSB/ISB completada. Gráficas generadas.")

        except Exception as e:
            messagebox.showerror("Error en Simulación SSB/ISB", str(e))

    def play_recovered_ssb_audio(self):
        if self.recovered_ssb_signal is not None and self.samplerate is not None:
            try:
                messagebox.showinfo("Reproduciendo", "Reproduciendo audio recuperado...")
                play_audio(self.recovered_ssb_signal, self.samplerate)
            except Exception as e:
                messagebox.showerror("Error de Reproducción", str(e))
        else:
            messagebox.showwarning("Advertencia", "No hay audio recuperado para reproducir. Ejecute la simulación primero.")

    def run_digital_transmission(self):
        try:
            digital_file = self.digital_file_path.get()
            if not digital_file:
                messagebox.showerror("Error", "Por favor, seleccione un archivo digital a enviar.")
                return

            use_fec = self.digital_use_fec.get()

            # 1. Leer archivo y convertir a bits
            original_file_size = os.path.getsize(digital_file)
            self.original_digital_bits = file_to_bits(digital_file)

            # 2. Codificación con protocolo
            encoded_bits = encode_data_with_protocol(self.original_digital_bits, original_file_size, use_fec=use_fec)

            # 3. Modulación BPSK
            bpsk_symbols = bpsk_modulate(encoded_bits)

            # 4. Generar señal pasobanda
            self.modulated_digital_signal = generate_passband_signal(bpsk_symbols, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL)

            # Normalizar la señal para evitar clipping en la tarjeta de sonido
            self.modulated_digital_signal = 0.8 * self.modulated_digital_signal / np.max(np.abs(self.modulated_digital_signal)) if np.max(np.abs(self.modulated_digital_signal)) > 0 else self.modulated_digital_signal

            # Limpiar gráficas anteriores
            for ax_row in self.digital_axs:
                for ax in ax_row:
                    ax.clear()

            # Graficar señal modulada
            plot_time_domain(self.modulated_digital_signal[:FS], FS, "Señal Modulada (Tiempo - 1s)", ax=self.digital_axs[0, 0])
            plot_spectrum(self.modulated_digital_signal, FS, "Señal Modulada (Frecuencia)", ax=self.digital_axs[0, 1])
            plot_constellation(bpsk_symbols, "Constelación Transmitida (BPSK)", ax=self.digital_axs[2, 0])

            self.digital_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
            self.digital_canvas.draw()

            # Transmitir audio (real)
            messagebox.showinfo("Transmisión Digital", "Iniciando transmisión de audio. Asegúrese de que el micrófono esté listo para grabar en la recepción.")
            transmit_audio(self.modulated_digital_signal, FS)
            messagebox.showinfo("Transmisión Digital", "Transmisión de audio finalizada.")

        except Exception as e:
            messagebox.showerror("Error en Transmisión Digital", str(e))

    def run_digital_reception(self):
        try:
            if self.original_digital_bits is None:
                messagebox.showerror("Error", "Primero debe transmitir un archivo digital para poder recibirlo.")
                return

            use_fec = self.digital_use_fec.get()

            # Calcular duración esperada de la señal
            expected_duration = len(self.modulated_digital_signal) / FS + 1 # +1 segundo para asegurar captura completa

            messagebox.showinfo("Recepción Digital", f"Iniciando grabación de audio por {expected_duration:.1f} segundos. Por favor, reproduzca la señal transmitida.")
            received_audio_signal = record_audio(duration=expected_duration, fs=FS)
            messagebox.showinfo("Recepción Digital", "Grabación de audio finalizada.")

            # Asegurarse de que la señal recibida tenga la longitud esperada para la demodulación
            expected_len = len(self.original_digital_bits) * SAMPLES_PER_SYMBOL # Esto no es correcto, debería ser len(encoded_bits) * SAMPLES_PER_SYMBOL
            # Corregir la longitud esperada de la señal recibida
            # Necesitamos recalcular encoded_bits para obtener su longitud correcta
            original_file_size = os.path.getsize(self.digital_file_path.get())
            temp_encoded_bits = encode_data_with_protocol(self.original_digital_bits, original_file_size, use_fec=use_fec)
            expected_len = len(temp_encoded_bits) * SAMPLES_PER_SYMBOL

            if len(received_audio_signal) > expected_len:
                received_audio_signal = received_audio_signal[:expected_len]
            elif len(received_audio_signal) < expected_len:
                messagebox.showwarning("Advertencia", f"Señal de audio recibida más corta de lo esperado ({len(received_audio_signal)} vs {expected_len}). Rellenando con ceros.")
                received_audio_signal = np.pad(received_audio_signal, (0, expected_len - len(received_audio_signal)))

            # 5. Demodulación
            received_symbols_baseband = receive_and_demodulate_passband_signal(received_audio_signal, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL, len(temp_encoded_bits))
            demodulated_bits_with_protocol = bpsk_demodulate(received_symbols_baseband)

            # 6. Decodificación de protocolo
            recovered_bits, recovered_file_size = decode_data_with_protocol(demodulated_bits_with_protocol, use_fec=use_fec)

            if recovered_bits is not None:
                # 7. Guardar archivo recuperado
                recovered_file_name = "recovered_digital_data.bin"
                bits_to_file(recovered_bits, recovered_file_name)
                messagebox.showinfo("Recepción Digital", f"Archivo recuperado guardado como: {recovered_file_name}")

                # 8. Calcular BER
                ber = calculate_ber(self.original_digital_bits, recovered_bits)
                self.digital_results_text.delete(1.0, tk.END)
                self.digital_results_text.insert(tk.END, f"Tasa de Error de Bit (BER): {ber:.6f}\n")

                # 9. Tasa de Transferencia (aproximada, sin considerar overhead de protocolo/FEC)
                transmission_time = len(self.modulated_digital_signal) / FS
                data_rate_bps = (original_file_size * 8) / transmission_time
                self.digital_results_text.insert(tk.END, f"Tasa de transferencia (aproximada): {data_rate_bps:.2f} bps\n")

                # Graficar resultados de demodulación
                # Limpiar gráficas anteriores (excepto las del modulador)
                for i in range(1, 4):
                    for j in range(2):
                        self.digital_axs[i, j].clear()

                # Para la gráfica de banda base filtrada, necesitamos la señal filtrada
                # La función receive_and_demodulate_passband_signal devuelve los símbolos muestreados, no la señal filtrada completa.
                # Para graficar la señal filtrada, necesitamos modificar la función o recalcularla aquí.
                # Por simplicidad, aquí solo graficaremos los símbolos recibidos y el diagrama de ojo.

                # Recalcular la banda base filtrada para graficar
                t_full = np.arange(0, len(received_audio_signal)) / FS
                local_carrier = np.cos(2 * np.pi * CARRIER_FREQ * t_full)
                demodulated_baseband = received_audio_signal * local_carrier
                nyquist = 0.5 * FS
                cutoff_freq = BAUD_RATE / 2 * 1.5
                if cutoff_freq >= nyquist:
                    cutoff_freq = nyquist * 0.9
                b, a = signal.butter(5, cutoff_freq / nyquist, btype='low')
                filtered_baseband_for_plot = signal.lfilter(b, a, demodulated_baseband)

                plot_time_domain(filtered_baseband_for_plot[:FS], FS, "Banda Base Filtrada (Tiempo - 1s)", ax=self.digital_axs[1, 0])
                plot_spectrum(filtered_baseband_for_plot, FS, "Banda Base Filtrada (Frecuencia)", ax=self.digital_axs[1, 1])
                plot_constellation(received_symbols_baseband, "Constelación Recibida (BPSK)", ax=self.digital_axs[2, 1])
                plot_eye_diagram(filtered_baseband_for_plot, SAMPLES_PER_SYMBOL, title="Diagrama de Ojo (Banda Base Demodulada)", ax=self.digital_axs[3, 0])

                self.digital_fig.tight_layout(rect=[0, 0.03, 1, 0.95])
                self.digital_canvas.draw()

            else:
                messagebox.showerror("Error en Recepción Digital", "No se pudieron recuperar los bits del archivo.")

        except Exception as e:
            messagebox.showerror("Error en Recepción Digital", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = CommunicationsSimulatorApp(root)
    root.mainloop()

