# rx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import threading
import time
import pyaudio
import scipy.signal as signal
import matplotlib.pyplot as plt

from ssb_isb_simulator import ssb_demodulate, save_audio, load_audio, play_audio, plot_spectrum, plot_time_domain
from digital_passband_modulator import (
    record_audio_with_tone_trigger,
    receive_and_demodulate_passband_signal,
    decode_data_simple,   # ← usamos este
    bpsk_demodulate,
    bits_to_file,
    decode_fec,
    plot_eye_diagram,
    FS,
    CARRIER_FREQ,
    SAMPLES_PER_SYMBOL
)


class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX - Receptor (SSB/ISB + Pasobanda Digital)")

        # Parámetros SSB
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.phase_err = tk.DoubleVar(value=0.0)
        self.freq_err = tk.DoubleVar(value=0.0)

        # Parámetros digitales
        self.carrier_dig = tk.DoubleVar(value=CARRIER_FREQ)
        self.digital_use_fec = tk.BooleanVar(value=False)

        self.create_widgets()

        # 🔊 Parámetros de tonos (puedes cambiarlos aquí)
        self.start_tone_freq = 1000.0
        self.stop_tone_freq = 2000.0

        # Variables para almacenar datos de graficación SSB
        self.last_received_ssb = None
        self.last_demodulated_ssb = None
        self.last_fs_ssb = None

        # Variables para almacenar datos de graficación digital
        self.last_received_digital = None
        self.last_demodulated_baseband = None
        self.last_filtered_baseband = None

    def create_widgets(self):
        frame_ssb = ttk.LabelFrame(self.root, text="Recepción SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Frecuencia portadora SSB (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de fase (deg):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.phase_err, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de frecuencia (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.freq_err, width=12).grid(row=2, column=1, sticky="w")
        
        btn_frame_ssb = ttk.Frame(frame_ssb)
        btn_frame_ssb.grid(row=3, column=0, columnspan=2, pady=6)
        ttk.Button(btn_frame_ssb, text="Escuchar y Demodular SSB", command=self.rx_ssb).pack(side="left", padx=6)
        ttk.Button(btn_frame_ssb, text="Mostrar Gráficas", command=self.show_rx_plots_ssb).pack(side="left", padx=6)

        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital Pasobanda (como audio)")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Frecuencia portadora digital (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.carrier_dig, width=12).grid(row=0, column=1, sticky="w")

        ttk.Checkbutton(frame_dig, text="Usar FEC (Hamming 7,4)", variable=self.digital_use_fec).grid(row=1, column=0, columnspan=2, sticky="w")

        btn_frame_dig = ttk.Frame(frame_dig)
        btn_frame_dig.grid(row=2, column=0, columnspan=2, pady=6)
        ttk.Button(btn_frame_dig, text="Escuchar y Demodular Digital", command=self.rx_digital).pack(side="left", padx=6)
        ttk.Button(btn_frame_dig, text="Mostrar Gráficas", command=self.show_rx_plots_digital).pack(side="left", padx=6)

    def rx_ssb(self):
        try:
            rec = record_audio_with_tone_trigger(
                fs=FS,
                start_tone_freq=self.start_tone_freq,
                stop_tone_freq=self.stop_tone_freq
            )
            if rec is None:
                messagebox.showerror("Error", "No se detectó tono de inicio/fin.")
                return

            fc = float(self.fc_ssb.get())
            recovered = ssb_demodulate(rec, FS, fc,
                                       phase_error_deg=float(self.phase_err.get()),
                                       freq_error_hz=float(self.freq_err.get()))
            recovered = recovered / (np.max(np.abs(recovered)) + 1e-12)

            # Guardar datos para graficación
            self.last_received_ssb = rec
            self.last_demodulated_ssb = recovered
            self.last_fs_ssb = FS

            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, recovered, FS)
                if messagebox.askyesno("Reproducir", "¿Reproducir audio?"):
                    play_audio(recovered, FS)

        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))

    def rx_digital(self):
        """Recepción digital completa: tono inicio → grabar → tono fin → BPSK → protocolo → reconstrucción de archivo."""
        try:
            carrier = float(self.carrier_dig.get())

            # 1) GRABAR POR TONOS
            rec = record_audio_with_tone_trigger(
                fs=FS,
                start_tone_freq=self.start_tone_freq,
                stop_tone_freq=self.stop_tone_freq
            )
            if rec is None or len(rec) < SAMPLES_PER_SYMBOL * 20:
                messagebox.showerror("Error", "La grabación fue muy corta o no se detectaron tonos correctamente.")
                return

            # 2) DEMODULACIÓN COMPLETA PASOBANDA
            est_num_symbols = max(1, int(len(rec) / SAMPLES_PER_SYMBOL))
            sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(
                rec, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols
            )

            # Guardar datos para graficación
            self.last_received_digital = rec
            self.last_demodulated_baseband = demodulated_baseband
            self.last_filtered_baseband = filtered_baseband

            # 3) BPSK → Bits
            demod_bits = bpsk_demodulate(sampled_symbols)

            # 4) Decodificación de protocolo (encuentra preámbulo y tamaño automáticamente)
            recovered_bits, original_size = decode_data_simple(demod_bits)

            if recovered_bits is None:
                messagebox.showerror("Error en protocolo", "No se pudo detectar el preámbulo o el tamaño del archivo.")
                return

            # 5) Decodificar FEC si está habilitado
            use_fec = self.digital_use_fec.get()
            recovered_bits = decode_fec(recovered_bits, use_fec=use_fec)

            # 6) Guardar archivo recuperado
            outname = filedialog.asksaveasfilename(
                defaultextension="",
                filetypes=[
                    ("Archivos binarios", "*.bin"),
                    ("Texto", "*.txt"),
                    ("Imagen PNG", "*.png"),
                    ("Imagen JPG", "*.jpg"),
                    ("Todos los archivos", "*.*")
                ],
                title="Guardar archivo recuperado"
            )
            if not outname:
                return

            bits_to_file(recovered_bits, outname)

            messagebox.showinfo("Archivo guardado", f"✅ Archivo reconstruido y guardado:\n{outname}")

        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))

    def show_rx_plots_ssb(self):
        """Muestra gráficas de amplitud vs tiempo y espectro para señal SSB/ISB recibida."""
        try:
            if self.last_received_ssb is None or self.last_demodulated_ssb is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar. Ejecuta 'Escuchar y Demodular SSB' primero.")
                return

            rec = self.last_received_ssb
            demod = self.last_demodulated_ssb
            fs = self.last_fs_ssb

            # Crear figura con 4 subplots (2x2)
            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Señal SSB/ISB - Receptor', fontsize=14, fontweight='bold')

            # Gráfica 1: Señal recibida modulada en tiempo
            plot_time_domain(rec, fs, "Señal Recibida Modulada (Amplitud vs Tiempo)", ax=axs[0, 0])

            # Gráfica 2: Espectro de la señal recibida modulada
            plot_spectrum(rec, fs, "Señal Recibida Modulada (Espectro)", ax=axs[0, 1])

            # Gráfica 3: Señal demodulada en tiempo
            plot_time_domain(demod, fs, "Señal Demodulada (Amplitud vs Tiempo)", ax=axs[1, 0])

            # Gráfica 4: Espectro de la señal demodulada
            plot_spectrum(demod, fs, "Señal Demodulada (Espectro)", ax=axs[1, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))

    def show_rx_plots_digital(self):
        """Muestra gráficas para recepción digital: señal grabada, demodulada, zoom y diagrama de ojo."""
        try:
            if self.last_received_digital is None or self.last_filtered_baseband is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar. Ejecuta 'Escuchar y Demodular Digital' primero.")
                return

            rec = self.last_received_digital
            demod_baseband = self.last_demodulated_baseband
            filtered = self.last_filtered_baseband
            fs = FS

            # Crear figura con 6 subplots (3x2)
            fig, axs = plt.subplots(3, 2, figsize=(14, 12))
            fig.suptitle('Análisis RX - Señal grabada y baseband', fontsize=14, fontweight='bold')

            # Gráfica 1: Señal grabada en tiempo
            plot_time_domain(rec, fs, "Señal grabada (Tiempo)", ax=axs[0, 0])

            # Gráfica 2: Espectro de la señal grabada
            plot_spectrum(rec, fs, "Señal grabada (Espectro)", ax=axs[0, 1])

            # Gráfica 3: Baseband demodulado (producto con cos) en tiempo
            plot_time_domain(demod_baseband, fs, "Baseband demodulado (Producto con cos)", ax=axs[1, 0])

            # Gráfica 4: Espectro del baseband demodulado
            plot_spectrum(demod_baseband, fs, "Baseband demodulado (Espectro)", ax=axs[1, 1])

            # Gráfica 5: Filtered baseband con zoom (primeros 0.5s)
            zoom_samples = int(0.5 * fs)
            t_zoom = np.arange(0, min(zoom_samples, len(filtered))) / fs
            axs[2, 0].plot(t_zoom, filtered[:zoom_samples])
            axs[2, 0].set_title("Filtered baseband (Zoom 0.5s)")
            axs[2, 0].set_xlabel("Tiempo (s)")
            axs[2, 0].set_ylabel("Amplitud")
            axs[2, 0].grid()

            # Gráfica 6: Diagrama de ojo (aplicado por símbolo)
            plot_eye_diagram(filtered, SAMPLES_PER_SYMBOL, num_symbols_to_plot=3,
                           title="Diagrama de ojo (aplicado por símbolo)", ax=axs[2, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
