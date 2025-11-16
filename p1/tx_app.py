import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import matplotlib.pyplot as plt

# Importar funciones SSB/ISB
from ssb_isb_simulator import load_audio, ssb_modulate, isb_modulate, save_audio, play_audio, plot_spectrum, plot_time_domain

# Importar funciones 2FSK
from digital_fsk_modulator import (
    file_to_bits, encode_data_with_protocol, fsk_modulate, 
    generate_tone, transmit_audio, calculate_ber,
    FS, FREQ_0, FREQ_1, SAMPLES_PER_SYMBOL,
    START_TONE_FREQ, STOP_TONE_FREQ, SYNC_TONE_FREQ,
    plot_constellation
)

class TXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TX - Transmisor (SSB/ISB + 2FSK Digital)")

        # Variables SSB/ISB
        self.wav_path = tk.StringVar()
        self.wav_path2 = tk.StringVar()
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.mod_type = tk.StringVar(value="SSB-SC")
        self.band_type = tk.StringVar(value="USB")

        # Variables digitales
        self.digital_path = tk.StringVar()
        self.fs = FS

        # Variables para almacenar datos de graficación
        self.last_msg_signal = None
        self.last_msg_fs = None
        self.last_modulated_signal = None
        
        # Variables digitales para graficación
        self.last_digital_bits = None
        self.last_digital_modulated = None
        self.last_digital_encoded = None

        self.create_widgets()

    def _load_beacon(self, filename, tone_freq, target_fs, duration_fallback=0.5):
        """Carga filename y si no existe genera un tono tone_freq Hz."""
        beacon_path = os.path.join(os.path.dirname(__file__), filename)
        if not os.path.exists(beacon_path):
            t = np.linspace(0, duration_fallback, int(target_fs * duration_fallback), endpoint=False)
            beacon = 0.5 * np.sin(2 * np.pi * tone_freq * t).astype(np.float32)
            save_audio(beacon_path, beacon, target_fs)
            return beacon
        beacon, fs_b = load_audio(beacon_path, target_samplerate=target_fs)
        beacon = 0.8 * beacon / (np.max(np.abs(beacon)) + 1e-12)
        return beacon.astype(np.float32)

    def create_widgets(self):
        # SSB/ISB frame
        frame_ssb = ttk.LabelFrame(self.root, text="SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Archivo WAV 1:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.wav_path, width=50).grid(row=0, column=1)
        ttk.Button(frame_ssb, text="Seleccionar", command=lambda: self.select_file(self.wav_path, [('WAV files','*.wav')])).grid(row=0, column=2)

        ttk.Label(frame_ssb, text="Archivo WAV 2 (para ISB):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.wav_path2, width=50).grid(row=1, column=1)
        ttk.Button(frame_ssb, text="Seleccionar", command=lambda: self.select_file(self.wav_path2, [('WAV files','*.wav')])).grid(row=1, column=2)

        ttk.Label(frame_ssb, text="Tipo:").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(frame_ssb, text="SSB-SC", variable=self.mod_type, value="SSB-SC").grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(frame_ssb, text="ISB", variable=self.mod_type, value="ISB").grid(row=2, column=2, sticky="w")

        ttk.Label(frame_ssb, text="Banda (SSB):").grid(row=3, column=0, sticky="w")
        ttk.Radiobutton(frame_ssb, text="USB", variable=self.band_type, value="USB").grid(row=3, column=1, sticky="w")
        ttk.Radiobutton(frame_ssb, text="LSB", variable=self.band_type, value="LSB").grid(row=3, column=2, sticky="w")

        ttk.Label(frame_ssb, text="Frecuencia portadora (Hz, ≤25000):").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=4, column=1, sticky="w")

        btn_frame = ttk.Frame(frame_ssb)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=6)
        ttk.Button(btn_frame, text="Modular y Transmitir", command=self.tx_ssb).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Guardar WAV Modulado", command=self.save_modulated_ssb).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Mostrar Gráficas", command=self.show_tx_plots_ssb).pack(side="left", padx=6)

        # Digital 2FSK frame
        frame_dig = ttk.LabelFrame(self.root, text="Transmisión Digital 2FSK")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Archivo digital:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.digital_path, width=50).grid(row=0, column=1)
        ttk.Button(frame_dig, text="Seleccionar", command=lambda: self.select_file(self.digital_path)).grid(row=0, column=2)

        info_frame = ttk.Frame(frame_dig)
        info_frame.grid(row=1, column=0, columnspan=3, pady=4)
        ttk.Label(info_frame, text=f"Modulación: 2FSK | Bit 0: {FREQ_0} Hz | Bit 1: {FREQ_1} Hz", 
                 font=('Arial', 9, 'italic')).pack()
        ttk.Label(info_frame, text=f"Tasa de símbolos: {FS // SAMPLES_PER_SYMBOL} bauds/s | Fs: {FS} Hz",
                 font=('Arial', 9, 'italic')).pack()

        btn_frame2 = ttk.Frame(frame_dig)
        btn_frame2.grid(row=2, column=0, columnspan=3, pady=6)
        ttk.Button(btn_frame2, text="Transmitir Archivo (FSK)", command=self.tx_digital).pack(side="left", padx=6)
        ttk.Button(btn_frame2, text="Guardar WAV Modulado", command=self.save_modulated_digital).pack(side="left", padx=6)
        ttk.Button(btn_frame2, text="Mostrar Gráficas", command=self.show_tx_plots_digital).pack(side="left", padx=6)

    def select_file(self, var, types=[("All files","*.*")]):
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            var.set(path)

    def tx_ssb(self):
        try:
            if not self.wav_path.get():
                messagebox.showerror("Error", "Selecciona un WAV")
                return
            fc = float(self.fc_ssb.get())
            if fc <= 0 or fc > 25000:
                messagebox.showerror("Error", "fc debe estar en (0, 25000]")
                return

            msg, fs = load_audio(self.wav_path.get(), target_samplerate=None)
            msg = msg / (np.max(np.abs(msg)) + 1e-12)

            if self.mod_type.get() == "SSB-SC":
                mod = ssb_modulate(msg, fs, fc, band_type=self.band_type.get())
            else:
                if not self.wav_path2.get():
                    messagebox.showerror("Error", "Para ISB selecciona WAV2")
                    return
                msg2, fs2 = load_audio(self.wav_path2.get(), target_samplerate=fs)
                msg2 = msg2 / (np.max(np.abs(msg2))+1e-12)
                minlen = min(len(msg), len(msg2))
                mod = isb_modulate(msg[:minlen], msg2[:minlen], fs, fc)

            mod = mod / (np.max(np.abs(mod)) + 1e-12) * 0.8

            start_beacon = self._load_beacon("message_start.wav", 1000.0, fs)
            end_beacon = self._load_beacon("message_end.wav", 2000.0, fs)
            tx_signal = np.concatenate([start_beacon, mod.astype(np.float32), end_beacon])

            play_audio(tx_signal, fs)
            self.last_modulated = (tx_signal, fs)
            
            self.last_msg_signal = msg
            self.last_msg_fs = fs
            self.last_modulated_signal = mod
            
            messagebox.showinfo("Éxito", "Señal SSB/ISB transmitida con balizas 1 kHz / 2 kHz.")
        except Exception as e:
            messagebox.showerror("Error TX SSB", str(e))

    def save_modulated_ssb(self):
        try:
            if not hasattr(self, "last_modulated"):
                messagebox.showwarning("Aviso", "No hay señal modulada (ejecuta 'Modular y Transmitir' primero).")
                return
            mod, fs = self.last_modulated
            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, mod, fs)
                messagebox.showinfo("Guardado", f"Señal modulada guardada en: {fname}")
        except Exception as e:
            messagebox.showerror("Error guardar WAV", str(e))

    def tx_digital(self):
        """Transmisión digital con 2FSK y protocolo de handshake."""
        try:
            if not self.digital_path.get():
                messagebox.showerror("Error", "Selecciona un archivo digital para transmitir.")
                return

            print("\n" + "="*60)
            print("INICIANDO TRANSMISIÓN DIGITAL 2FSK")
            print("="*60)

            # 1. Leer archivo y convertir a bits
            bits = file_to_bits(self.digital_path.get())
            file_size = os.path.getsize(self.digital_path.get())
            
            print(f"📄 Archivo: {os.path.basename(self.digital_path.get())}")
            print(f"📊 Tamaño: {file_size} bytes ({len(bits)} bits)")

            # 2. Codificar con protocolo
            encoded_bits = encode_data_with_protocol(bits, file_size)
            print(f"📦 Bits codificados: {len(encoded_bits)} (con protocolo)")

            # Guardar para graficación
            self.last_digital_bits = bits
            self.last_digital_encoded = encoded_bits

            # 3. Modular con 2FSK
            fsk_signal = fsk_modulate(encoded_bits)
            fsk_signal = 0.7 * fsk_signal / (np.max(np.abs(fsk_signal)) + 1e-12)
            
            print(f"🔊 Señal FSK: {len(fsk_signal)} muestras ({len(fsk_signal)/self.fs:.2f} s)")

            # Guardar para graficación
            self.last_digital_modulated = fsk_signal

            # 4. Construir secuencia de handshake completa
            tone_duration = 0.5  # segundos
            
            # Tono de inicio (1 kHz)
            start_tone = generate_tone(START_TONE_FREQ, tone_duration, self.fs)
            
            # Tono de sincronización (3 kHz)
            sync_tone = generate_tone(SYNC_TONE_FREQ, tone_duration, self.fs)
            
            # Tono de fin (2 kHz)
            stop_tone = generate_tone(STOP_TONE_FREQ, tone_duration, self.fs)
            
            # Silencios cortos
            short_silence = np.zeros(int(0.2 * self.fs))
            
            # Secuencia completa: START → silence → SYNC → silence → DATA → silence → STOP
            tx_signal = np.concatenate([
                start_tone,
                short_silence,
                sync_tone,
                short_silence,
                fsk_signal.astype(np.float32),
                short_silence,
                stop_tone
            ])

            print(f"📡 Señal total: {len(tx_signal)} muestras ({len(tx_signal)/self.fs:.2f} s)")
            print("\nProtocolo de handshake:")
            print(f"  1️⃣  Tono de inicio: {START_TONE_FREQ} Hz ({tone_duration} s)")
            print(f"  2️⃣  Tono de sincronización: {SYNC_TONE_FREQ} Hz ({tone_duration} s)")
            print(f"  3️⃣  Datos FSK ({len(fsk_signal)/self.fs:.2f} s)")
            print(f"  4️⃣  Tono de fin: {STOP_TONE_FREQ} Hz ({tone_duration} s)")
            
            # Calcular tasa de transferencia
            data_time = len(fsk_signal) / self.fs
            data_rate_bps = (file_size * 8) / data_time
            print(f"\n📈 Tasa de transferencia: {data_rate_bps:.0f} bps ({data_rate_bps/8:.0f} Bps)")

            # 5. Transmitir
            self.last_modulated = (tx_signal, self.fs)
            transmit_audio(tx_signal, self.fs)
            
            print("="*60)
            print("✅ TRANSMISIÓN COMPLETADA")
            print("="*60 + "\n")

            messagebox.showinfo("Transmisión", 
                f"Archivo transmitido exitosamente\n\n"
                f"Tamaño: {file_size} bytes\n"
                f"Bits: {len(bits)}\n"
                f"Duración: {len(tx_signal)/self.fs:.2f} s\n"
                f"Tasa: {data_rate_bps:.0f} bps")

        except Exception as e:
            messagebox.showerror("Error TX Digital", str(e))
            import traceback
            traceback.print_exc()

    def save_modulated_digital(self):
        try:
            if not hasattr(self, "last_modulated"):
                messagebox.showwarning("Aviso", "No hay señal modulada (ejecuta 'Transmitir Archivo' primero).")
                return
            mod, fs = self.last_modulated
            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, mod, fs)
                messagebox.showinfo("Guardado", f"Señal modulada guardada en: {fname}")
        except Exception as e:
            messagebox.showerror("Error guardar WAV", str(e))

    def show_tx_plots_ssb(self):
        """Muestra gráficas de amplitud vs tiempo y espectro para SSB/ISB."""
        try:
            if self.last_msg_signal is None or self.last_modulated_signal is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar. Ejecuta 'Modular y Transmitir' primero.")
                return

            msg = self.last_msg_signal
            mod = self.last_modulated_signal
            fs = self.last_msg_fs

            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Señal SSB/ISB - Transmisor', fontsize=14, fontweight='bold')

            plot_time_domain(msg, fs, "Mensaje Original (Amplitud vs Tiempo)", ax=axs[0, 0])
            plot_spectrum(msg, fs, "Mensaje Original (Espectro)", ax=axs[0, 1])
            plot_time_domain(mod, fs, "Señal Modulada (Amplitud vs Tiempo)", ax=axs[1, 0])
            plot_spectrum(mod, fs, "Señal Modulada (Espectro)", ax=axs[1, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))

    def show_tx_plots_digital(self):
        """Muestra gráficas para transmisión digital 2FSK."""
        try:
            if self.last_digital_modulated is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar. Ejecuta 'Transmitir Archivo' primero.")
                return

            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Transmisión Digital 2FSK', fontsize=14, fontweight='bold')

            # Gráfica 1: Señal FSK en tiempo
            plot_time_domain(self.last_digital_modulated, self.fs, 
                           "Señal FSK Modulada (Tiempo)", ax=axs[0, 0])

            # Gráfica 2: Espectro FSK
            plot_spectrum(self.last_digital_modulated, self.fs,
                        "Señal FSK Modulada (Espectro)", ax=axs[0, 1])

            # Gráfica 3: Constelación (pseudo)
            if self.last_digital_bits is not None:
                plot_constellation(self.last_digital_bits[:200],  # Primeros 200 bits
                                 "Bits Originales (primeros 200)", ax=axs[1, 0])

            # Gráfica 4: Información del protocolo
            axs[1, 1].axis('off')
            if self.last_digital_bits is not None and self.last_digital_encoded is not None:
                info_text = f"""
INFORMACIÓN DE TRANSMISIÓN

Modulación: 2FSK
Frecuencia Bit 0: {FREQ_0} Hz
Frecuencia Bit 1: {FREQ_1} Hz

Tasa de símbolos: {self.fs // SAMPLES_PER_SYMBOL} bauds/s
Muestras/símbolo: {SAMPLES_PER_SYMBOL}

Bits de datos: {len(self.last_digital_bits)}
Bits con protocolo: {len(self.last_digital_encoded)}
Overhead: {len(self.last_digital_encoded) - len(self.last_digital_bits)} bits

Duración señal: {len(self.last_digital_modulated)/self.fs:.2f} s
Tasa transferencia: {len(self.last_digital_bits)/(len(self.last_digital_modulated)/self.fs):.0f} bps
                """
                axs[1, 1].text(0.1, 0.5, info_text, fontsize=10, family='monospace',
                             verticalalignment='center')

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    root = tk.Tk()
    app = TXApp(root)
    root.mainloop()