# rx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np

from ssb_isb_simulator import ssb_demodulate, save_audio, load_audio, play_audio
from digital_passband_modulator import record_audio, receive_and_demodulate_passband_signal, bpsk_demodulate, decode_data_with_protocol, bits_to_file, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL
from digital_passband_modulator import (
    record_audio, receive_and_demodulate_passband_signal, bpsk_demodulate,
    decode_data_with_protocol, bits_to_file, detect_preamble_postamble,
    FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL, PREAMBLE_BITS, POSTAMBLE_BITS
    )
class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX - Receptor (SSB/ISB + Pasobanda Digital)")

        # Parámetros SSB
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.phase_err = tk.DoubleVar(value=0.0)
        self.freq_err = tk.DoubleVar(value=0.0)
        self.record_duration = tk.DoubleVar(value=5.0)

        # Parámetros digitales
        self.carrier_dig = tk.DoubleVar(value=CARRIER_FREQ)
        self.expected_symbols = tk.IntVar(value=0)  # opcional: número de símbolos esperado

        self.create_widgets()

    def create_widgets(self):
        frame_ssb = ttk.LabelFrame(self.root, text="Recepción SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Frecuencia portadora esperada (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de fase a aplicar (simulación, deg):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.phase_err, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de frecuencia a aplicar (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.freq_err, width=12).grid(row=2, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Duración de grabación (s):").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.record_duration, width=12).grid(row=3, column=1, sticky="w")

        ttk.Button(frame_ssb, text="Grabar y Demodular SSB", command=self.rx_ssb).grid(row=4, column=0, columnspan=2, pady=6)

        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital Pasobanda")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Frecuencia portadora esperada (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.carrier_dig, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_dig, text="Duración de grabación (s):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.record_duration, width=12).grid(row=1, column=1, sticky="w")

        ttk.Button(frame_dig, text="Grabar y Demodular Digital", command=self.rx_digital).grid(row=2, column=0, columnspan=2, pady=6)

    def rx_ssb(self):
        try:
            duration = float(self.record_duration.get())
            if duration <= 0:
                messagebox.showerror("Error", "Duración inválida")
                return
            # grabar
            rec = record_audio(duration=duration, fs=FS)
            # demodular con parámetros
            fc = float(self.fc_ssb.get())
            phase_err = float(self.phase_err.get())
            freq_err = float(self.freq_err.get())
            recovered = ssb_demodulate(rec, FS, fc, phase_error_deg=phase_err, freq_error_hz=freq_err)
            # normalizar
            recovered = recovered / (np.max(np.abs(recovered)) + 1e-12)
            # guardar
            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")], title="Guardar audio recuperado")
            if fname:
                save_audio(fname, recovered, FS)
                messagebox.showinfo("Guardado", f"Audio recuperado guardado en: {fname}")
                # opcional: reproducir
                if messagebox.askyesno("Reproducir", "¿Reproducir audio recuperado ahora?"):
                    play_audio(recovered, FS)
        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))



    def rx_digital(self):
        try:
            duration = float(self.record_duration.get())
            carrier = float(self.carrier_dig.get())
            if duration <= 0:
                messagebox.showerror("Error", "Duración inválida")
                return

            rec = record_audio(duration=duration, fs=FS)

            # --- Detección de tonos de inicio y fin ---
            start_idx, end_idx = detect_preamble_postamble(
                rec, FS, carrier, SAMPLES_PER_SYMBOL, PREAMBLE_BITS, POSTAMBLE_BITS
            )

            if end_idx <= start_idx:
                messagebox.showerror("Error", "No se detectaron los tonos de inicio/fin correctamente.")
                return

            rec_segment = rec[start_idx:end_idx]

            # --- Demodulación ---
            est_num_symbols = int((len(rec_segment) / FS) * (FS / SAMPLES_PER_SYMBOL))
            sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(
                rec_segment, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols
            )
            demod_bits = bpsk_demodulate(sampled_symbols)

            # --- Decodificación de protocolo ---
            recovered_bits, original_size = decode_data_with_protocol(demod_bits, use_fec=False)
            if recovered_bits is None:
                messagebox.showerror("Error", "No se pudo decodificar protocolo (verifica el SNR o sincronización).")
                return

            # --- Guardar el archivo original con extensión flexible ---
            outname = filedialog.asksaveasfilename(
                title="Guardar archivo recuperado",
                defaultextension="",
                filetypes=[("Todos los archivos", "*.*")]
            )
            if outname:
                bits_to_file(recovered_bits, outname)
                messagebox.showinfo("Guardado", f"Archivo recuperado guardado en: {outname}")

        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
