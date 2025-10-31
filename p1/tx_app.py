# tx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os

# Importar funciones proporcionadas por tus módulos
from ssb_isb_simulator import load_audio, ssb_modulate, isb_modulate, save_audio, play_audio
from digital_passband_modulator import file_to_bits, encode_data_with_protocol, bpsk_modulate, generate_passband_signal, transmit_audio, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL, PREAMBLE_BITS, POSTAMBLE_BITS

class TXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TX - Transmisor (SSB/ISB + Pasobanda Digital)")

        # Variables SSB/ISB
        self.wav_path = tk.StringVar()
        self.wav_path2 = tk.StringVar()  # para ISB
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.mod_type = tk.StringVar(value="SSB-SC")
        self.band_type = tk.StringVar(value="USB")

        # Variables digitales
        self.digital_path = tk.StringVar()
        self.digital_use_fec = tk.BooleanVar(value=False)
        self.carrier_digital = tk.DoubleVar(value=CARRIER_FREQ)
        self.fs = FS

        self.create_widgets()

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

        # Digital frame
        frame_dig = ttk.LabelFrame(self.root, text="Transmisión Digital Pasobanda")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Archivo digital:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.digital_path, width=50).grid(row=0, column=1)
        ttk.Button(frame_dig, text="Seleccionar", command=lambda: self.select_file(self.digital_path)).grid(row=0, column=2)

        ttk.Checkbutton(frame_dig, text="Usar FEC (placeholder)", variable=self.digital_use_fec).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(frame_dig, text="Frecuencia portadora (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.carrier_digital, width=12).grid(row=2, column=1, sticky="w")

        btn_frame2 = ttk.Frame(frame_dig)
        btn_frame2.grid(row=3, column=0, columnspan=3, pady=6)
        ttk.Button(btn_frame2, text="Transmitir Archivo (por parlante)", command=self.tx_digital).pack(side="left", padx=6)
        ttk.Button(btn_frame2, text="Generar WAV Modulado", command=self.save_modulated_digital).pack(side="left", padx=6)

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
                # ISB
                if not self.wav_path2.get():
                    messagebox.showerror("Error", "Para ISB selecciona WAV2")
                    return
                msg2, fs2 = load_audio(self.wav_path2.get(), target_samplerate=fs)
                msg2 = msg2 / (np.max(np.abs(msg2))+1e-12)
                minlen = min(len(msg), len(msg2))
                mod = isb_modulate(msg[:minlen], msg2[:minlen], fs, fc)

            # Anteponer preámbulo BPSK y agregar postámbulo BPSK a la señal SSB/ISB
            pre = generate_passband_signal(bpsk_modulate(PREAMBLE_BITS), fc, fs, SAMPLES_PER_SYMBOL)
            post = generate_passband_signal(bpsk_modulate(POSTAMBLE_BITS), fc, fs, SAMPLES_PER_SYMBOL)
            full_tx = np.concatenate([pre.astype(np.float64), mod.astype(np.float64), post.astype(np.float64)])

            # normalizar y transmitir
            full_tx = full_tx / (np.max(np.abs(full_tx)) + 1e-12) * 0.8
            play_audio(full_tx, fs)
            # store for saving
            self.last_modulated = (full_tx, fs)
            messagebox.showinfo("Éxito", "Se transmitió la señal modulada por parlante (TX).")

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
        try:
            if not self.digital_path.get():
                messagebox.showerror("Error", "Selecciona un archivo digital para transmitir.")
                return

            file_path = self.digital_path.get()
            bits = file_to_bits(file_path)
            size = os.path.getsize(file_path)
            encoded = encode_data_with_protocol(bits, size, use_fec=self.digital_use_fec.get())

            symbols = bpsk_modulate(encoded)
            carrier = float(self.carrier_digital.get())
            passband = generate_passband_signal(symbols, carrier, self.fs, SAMPLES_PER_SYMBOL)
            passband = 0.8 * passband / (np.max(np.abs(passband)) + 1e-12)

            transmit_audio(passband, self.fs)
            self.last_modulated = (passband, self.fs)

            fname = os.path.basename(file_path)
            messagebox.showinfo("Transmisión", f"Archivo '{fname}' transmitido correctamente por parlante (TX).")

        except Exception as e:
            messagebox.showerror("Error TX Digital", str(e))


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

if __name__ == "__main__":
    root = tk.Tk()
    app = TXApp(root)
    root.mainloop()
