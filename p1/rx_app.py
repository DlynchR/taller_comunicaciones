# rx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import threading
import time
import pyaudio
import scipy.signal as signal

from ssb_isb_simulator import ssb_demodulate, save_audio, load_audio, play_audio
from digital_passband_modulator import (
    record_audio_with_tone_trigger,
    receive_and_demodulate_passband_signal,
    bpsk_demodulate,
    bits_to_file,
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

        self.create_widgets()

        # 🔊 Parámetros de tonos (puedes cambiarlos aquí)
        self.start_tone_freq = 1000.0
        self.stop_tone_freq = 2000.0

    def create_widgets(self):
        frame_ssb = ttk.LabelFrame(self.root, text="Recepción SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Frecuencia portadora SSB (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de fase (deg):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.phase_err, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de frecuencia (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.freq_err, width=12).grid(row=2, column=1, sticky="w")
        

        ttk.Button(frame_ssb, text="Escuchar y Demodular SSB", command=self.rx_ssb).grid(row=3, column=0, columnspan=2, pady=6)

        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital Pasobanda (como audio)")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Frecuencia portadora digital (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.carrier_dig, width=12).grid(row=0, column=1, sticky="w")

        ttk.Button(frame_dig, text="Escuchar y Demodular Digital", command=self.rx_digital).grid(row=1, column=0, columnspan=2, pady=6)

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

            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, recovered, FS)
                if messagebox.askyesno("Reproducir", "¿Reproducir audio?"):
                    play_audio(recovered, FS)

        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))

    def rx_digital(self):
        """Ahora funciona como rx_ssb: NO espera preámbulos ni postámbulos."""
        try:
            carrier = float(self.carrier_dig.get())

            rec = record_audio_with_tone_trigger(
                fs=FS,
                start_tone_freq=self.start_tone_freq,
                stop_tone_freq=self.stop_tone_freq
            )
            if rec is None:
                messagebox.showerror("Error", "No se detectó tono de inicio/fin.")
                return

            # Demodulación exactamente igual que antes
            est_num_symbols = max(1, int(len(rec) / SAMPLES_PER_SYMBOL))

            sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(
                rec, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols
            )

            # Señal recuperada = banda base filtrada
            recovered = filtered_baseband / (np.max(np.abs(filtered_baseband)) + 1e-12)

            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, recovered, FS)
                if messagebox.askyesno("Reproducir", "¿Reproducir señal recuperada?"):
                    play_audio(recovered, FS)

        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
