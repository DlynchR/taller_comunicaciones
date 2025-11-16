# rx_app_fsk.py - Versión final con BER, gráficas, espectrograma y Goertzel robusto
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import pyaudio
import matplotlib.pyplot as plt
import time
import os
from scipy.signal import spectrogram

# Importar FSK
from digital_passband_modulator_fsk import (
    FS, SAMPLES_PER_SYMBOL,
    FREQ_0, FREQ_1,
    START_TONE_FREQ, STOP_TONE_FREQ,
    demodulate_fsk_from_signal,
    decode_frame,
    bits_to_bytes,
    calculate_ber
)

# --------------------------------------------------------------------
# -----------------------  Detector Goertzel  -------------------------
# --------------------------------------------------------------------
def goertzel_power(x, fs, freq):
    N = len(x)
    if N == 0:
        return 0.0
    k = int(0.5 + (N * freq) / fs)
    w = (2.0 * np.pi / N) * k
    cosine = np.cos(w)
    coeff = 2.0 * cosine
    s_prev = 0.0
    s_prev2 = 0.0
    for n in x:
        s = n + coeff * s_prev - s_prev2
        s_prev2 = s_prev
        s_prev = s
    return s_prev2*s_prev2 + s_prev*s_prev - coeff*s_prev*s_prev2

def detect_tone_goertzel(chunk, fs, target_freq, tolerance=80, step=20, threshold_factor=6.0):
    if len(chunk) == 0:
        return False

    x = chunk
    if np.max(np.abs(x)) != 0:
        x = x / (np.max(np.abs(x)) + 1e-12)

    freqs = np.arange(target_freq - tolerance, target_freq + tolerance + 1, step)
    band_power = np.mean([goertzel_power(x, fs, f) for f in freqs])

    ref_freqs = [target_freq * 0.5, target_freq * 1.6]
    ref_pow = np.mean([goertzel_power(x, fs, f) for f in ref_freqs]) + 1e-12

    return band_power > threshold_factor * ref_pow and band_power > 1e-6

# --------------------------------------------------------------------
# -----------------------  Grabación Handshake  ----------------------
# --------------------------------------------------------------------
def record_with_handshake(fs=FS, chunk=1024, start_freq=START_TONE_FREQ, stop_freq=STOP_TONE_FREQ):
    import pyaudio
    p = pyaudio.PyAudio()

    stream = p.open(format=pyaudio.paFloat32,
                    channels=1,
                    rate=fs,
                    input=True,
                    frames_per_buffer=chunk)

    print("[RX] Esperando tono de inicio (START)...")

    while True:
        data = stream.read(chunk, exception_on_overflow=False)
        audio = np.frombuffer(data, dtype=np.float32)
        if detect_tone_goertzel(audio, fs, start_freq):
            print("[RX] START detectado, comenzando grabación...")
            break

    frames = []
    print("[RX] Grabando...")

    while True:
        data = stream.read(chunk, exception_on_overflow=False)
        audio = np.frombuffer(data, dtype=np.float32)
        frames.append(audio.copy())

        if detect_tone_goertzel(audio, fs, stop_freq):
            print("[RX] STOP detectado, terminando grabación.")
            break

    stream.stop_stream()
    stream.close()
    p.terminate()

    return np.concatenate(frames)

# --------------------------------------------------------------------
# -----------------------     GUI RX FSK      ------------------------
# --------------------------------------------------------------------
class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX FSK – Final con BER y gráficas")
        
        self.save_folder = tk.StringVar(value=os.getcwd())
        self.original_file = tk.StringVar(value="")
        
        self.last_recording = None
        self.last_bits = None
        self.last_payload = None
        self.last_size = None
        
        self.build_ui()

    # ---------------- GUI ------------------
    def build_ui(self):
        frm = ttk.Frame(self.root)
        frm.pack(padx=10, pady=10)

        ttk.Label(frm, text="Carpeta para guardar archivo:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.save_folder, width=50).grid(row=0, column=1)
        ttk.Button(frm, text="Seleccionar", command=self.choose_folder).grid(row=0, column=2)

        ttk.Label(frm, text="Archivo original (para BER):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.original_file, width=50).grid(row=1, column=1)
        ttk.Button(frm, text="Cargar", command=self.choose_original).grid(row=1, column=2)

        ttk.Button(frm, text="Escuchar y recibir archivo", command=self.listen).grid(row=2, column=0, columnspan=3, pady=10)
        ttk.Button(frm, text="Guardar archivo recuperado", command=self.save_file).grid(row=3, column=0, columnspan=3, pady=5)
        ttk.Button(frm, text="Ver gráficas", command=self.plot_all).grid(row=4, column=0, columnspan=3, pady=5)

    def choose_folder(self):
        p = filedialog.askdirectory()
        if p:
            self.save_folder.set(p)

    def choose_original(self):
        p = filedialog.askopenfilename()
        if p:
            self.original_file.set(p)

    # ---------------- RX principal ------------------
    def listen(self):
        try:
            rec = record_with_handshake(FS)
            self.last_recording = rec

            bits = demodulate_fsk_from_signal(rec, fs=FS, f0=FREQ_0, f1=FREQ_1)
            self.last_bits = bits

            payload, size = decode_frame(bits)
            if payload is None:
                messagebox.showerror("RX", "No se pudo decodificar el frame. Revise la señal o el SNR.")
                return

            self.last_payload = payload
            self.last_size = size

            messagebox.showinfo("RX", f"Archivo recuperado correctamente.\nTamaño: {size} bytes.")

        except Exception as e:
            messagebox.showerror("Error RX", str(e))

    # ---------------- Guardar archivo ------------------
    def save_file(self):
        if self.last_payload is None:
            messagebox.showwarning("Guardar", "No hay datos decodificados.")
            return

        fname = filedialog.asksaveasfilename(
            defaultextension=".bin",
            filetypes=[("Archivo", "*.*")]
        )
        if not fname:
            return

        with open(fname, "wb") as f:
            f.write(bits_to_bytes(self.last_payload))

        messagebox.showinfo("RX", f"Archivo guardado como:\n{fname}")

        if self.original_file.get():
            with open(self.original_file.get(), "rb") as fo:
                ob = fo.read()
            ob_bits = []
            for b in ob:
                for i in range(8):
                    ob_bits.append((b >> (7 - i)) & 1)

            ber = calculate_ber(ob_bits, self.last_payload)
            messagebox.showinfo("BER", f"BER aproximado: {ber:.6f}")

    # ---------------- Gráficas ------------------
    def plot_all(self):
        if self.last_recording is None:
            messagebox.showwarning("Plot", "No hay señal grabada.")
            return

        sig = self.last_recording
        t = np.arange(len(sig)) / FS

        # ----- Gráfica tiempo -----
        plt.figure(figsize=10)
        plt.plot(t, sig)
        plt.title("Grabación en el tiempo")
        plt.xlabel("Tiempo (s)")
        plt.grid()
        plt.tight_layout()
        plt.show()

        # ----- FFT -----
        N = len(sig)
        f = np.fft.fftfreq(N, 1/FS)
        Y = np.abs(np.fft.fft(sig))

        plt.figure(figsize=10)
        plt.plot(f[:N//2], Y[:N//2])
        plt.title("Espectro de la señal recibida")
        plt.xlabel("Frecuencia (Hz)")
        plt.grid()
        plt.tight_layout()
        plt.show()

        # ----- Espectrograma -----
        f2, t2, Sxx = spectrogram(sig, FS, nperseg=1024, noverlap=512)

        plt.figure(figsize=10)
        plt.pcolormesh(t2, f2, 10*np.log10(Sxx+1e-12), shading='gouraud')
        plt.colorbar(label="dB")
        plt.title("Espectrograma")
        plt.ylabel("Frecuencia (Hz)")
        plt.xlabel("Tiempo (s)")
        plt.tight_layout()
        plt.show()

        # ----- Energías por símbolo F0/F1 -----
        if self.last_bits is not None:
            energies = []
            for i in range(0, len(sig), SAMPLES_PER_SYMBOL):
                chunk = sig[i:i+SAMPLES_PER_SYMBOL]
                if len(chunk) < SAMPLES_PER_SYMBOL:
                    break
                e0 = goertzel_power(chunk, FS, FREQ_0)
                e1 = goertzel_power(chunk, FS, FREQ_1)
                energies.append((e0, e1))

            energies = np.array(energies)

            plt.figure(figsize=10)
            plt.plot(energies[:,0], label="Energía F0")
            plt.plot(energies[:,1], label="Energía F1")
            plt.title("Energías por símbolo (Goertzel)")
            plt.legend()
            plt.grid()
            plt.tight_layout()
            plt.show()


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
