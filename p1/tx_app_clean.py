# tx_app_clean.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import matplotlib.pyplot as plt

# SSB/ISB imports (unchanged)
from ssb_isb_simulator import load_audio, ssb_modulate, isb_modulate, save_audio, play_audio, plot_spectrum, plot_time_domain

# Digital imports (new simple system)
from digital_simple import transmit_text_file, FS, CARRIER_FREQ
from digital_protocol import is_text_file

class TXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TX - Transmisor (SSB/ISB + Digital)")

        # Variables SSB/ISB (UNCHANGED)
        self.wav_path = tk.StringVar()
        self.wav_path2 = tk.StringVar()
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.mod_type = tk.StringVar(value="SSB-SC")
        self.band_type = tk.StringVar(value="USB")

        # Variables digitales (simplified)
        self.digital_path = tk.StringVar()
        self.digital_use_fec = tk.BooleanVar(value=False)
        self.carrier_digital = tk.DoubleVar(value=CARRIER_FREQ)
        self.fs = FS

        # Variables para graficación SSB
        self.last_msg_signal = None
        self.last_msg_fs = None
        self.last_modulated_signal = None

        self.create_widgets()

    def _load_beacon(self, filename, tone_freq, target_fs, duration_fallback=0.5):
        """Carga beacon o lo genera si no existe"""
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
        # ==================== SSB/ISB SECTION (UNCHANGED) ====================
        frame_ssb = ttk.LabelFrame(self.root, text="SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Archivo WAV 1:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.wav_path, width=50).grid(row=0, column=1)
        ttk.Button(frame_ssb, text="Seleccionar", 
                   command=lambda: self.select_file(self.wav_path, [('WAV files','*.wav')])).grid(row=0, column=2)

        ttk.Label(frame_ssb, text="Archivo WAV 2 (para ISB):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.wav_path2, width=50).grid(row=1, column=1)
        ttk.Button(frame_ssb, text="Seleccionar", 
                   command=lambda: self.select_file(self.wav_path2, [('WAV files','*.wav')])).grid(row=1, column=2)

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

        # ==================== DIGITAL SECTION (NEW SIMPLE) ====================
        frame_dig = ttk.LabelFrame(self.root, text="Transmisión Digital (Solo Texto)")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Archivo de texto (.txt):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(frame_dig, textvariable=self.digital_path, width=50).grid(row=0, column=1, padx=5)
        ttk.Button(frame_dig, text="Seleccionar", 
                   command=lambda: self.select_file(self.digital_path, [('Archivos de texto','*.txt')])).grid(row=0, column=2, padx=5)

        ttk.Checkbutton(frame_dig, text="Usar FEC (Repetición x3)", 
                       variable=self.digital_use_fec).grid(row=1, column=0, columnspan=2, sticky="w", padx=5, pady=5)

        ttk.Label(frame_dig, text="Portadora digital (Hz):").grid(row=2, column=0, sticky="w", padx=5)
        ttk.Entry(frame_dig, textvariable=self.carrier_digital, width=12).grid(row=2, column=1, sticky="w", padx=5)

        ttk.Button(frame_dig, text="📡 Transmitir Archivo", 
                   command=self.tx_digital).grid(row=3, column=0, columnspan=3, pady=10)

    def select_file(self, var, types=[("All files","*.*")]):
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            var.set(path)

    # ==================== SSB/ISB METHODS (UNCHANGED) ====================

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
            
            messagebox.showinfo("Éxito", "Señal SSB/ISB transmitida")
        except Exception as e:
            messagebox.showerror("Error TX SSB", str(e))

    def save_modulated_ssb(self):
        try:
            if not hasattr(self, "last_modulated"):
                messagebox.showwarning("Aviso", "No hay señal modulada")
                return
            mod, fs = self.last_modulated
            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, mod, fs)
                messagebox.showinfo("Guardado", f"Señal guardada en: {fname}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_tx_plots_ssb(self):
        try:
            if self.last_msg_signal is None or self.last_modulated_signal is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar")
                return

            msg = self.last_msg_signal
            mod = self.last_modulated_signal
            fs = self.last_msg_fs

            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Señal SSB/ISB - Transmisor', fontsize=14, fontweight='bold')

            plot_time_domain(msg, fs, "Mensaje Original (Tiempo)", ax=axs[0, 0])
            plot_spectrum(msg, fs, "Mensaje Original (Frecuencia)", ax=axs[0, 1])
            plot_time_domain(mod, fs, "Señal Modulada (Tiempo)", ax=axs[1, 0])
            plot_spectrum(mod, fs, "Señal Modulada (Frecuencia)", ax=axs[1, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))

    # ==================== DIGITAL METHODS (NEW SIMPLE) ====================

    def tx_digital(self):
        try:
            file_path = self.digital_path.get()
            
            if not file_path:
                messagebox.showerror("Error", "Selecciona un archivo de texto")
                return
            
            if not file_path.lower().endswith('.txt'):
                messagebox.showerror("Error", "Solo se permiten archivos .txt")
                return
            
            if not is_text_file(file_path):
                messagebox.showerror("Error", "El archivo no es un archivo de texto válido UTF-8")
                return
            
            use_fec = self.digital_use_fec.get()
            carrier = float(self.carrier_digital.get())
            
            file_size = os.path.getsize(file_path)
            fec_msg = "con FEC (x3)" if use_fec else "sin FEC"
            
            print(f"\n{'='*50}")
            print(f"TRANSMITIENDO: {os.path.basename(file_path)}")
            print(f"Tamaño: {file_size} bytes")
            print(f"FEC: {fec_msg}")
            print(f"Portadora: {carrier} Hz")
            print(f"{'='*50}\n")
            
            # Transmitir
            transmit_text_file(file_path, carrier, self.fs, use_fec)
            
            messagebox.showinfo("Transmisión exitosa", 
                              f"✅ Archivo transmitido {fec_msg}\n"
                              f"Tamaño: {file_size} bytes\n"
                              f"Tonos: 1kHz (inicio) / 2kHz (fin)")
        
        except Exception as e:
            messagebox.showerror("Error TX Digital", str(e))
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    root = tk.Tk()
    app = TXApp(root)
    root.mainloop()
