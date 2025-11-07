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
from digital_passband_modulator import record_audio, receive_and_demodulate_passband_signal, bpsk_demodulate, decode_data_with_protocol, bits_to_file, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL

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

        ttk.Button(frame_dig, text="Escuchar y Demodular (balizas)", command=self.rx_digital_listen_mode).grid(row=3, column=0, columnspan=2, pady=6)

    def _load_beacon(self, target_fs):
        """Carga 'message_test.wav' y lo remuestrea a target_fs."""
        beacon_path = os.path.join(os.path.dirname(__file__), "message_test.wav")
        if not os.path.exists(beacon_path):
            messagebox.showerror("Baliza no encontrada", f"No se encontró {beacon_path}. Asegúrate de tener la baliza en TX o genera una.")
            return None
        beacon, fs_b = load_audio(beacon_path, target_samplerate=target_fs)
        # Normalizar y centrar
        beacon = beacon.astype(np.float32)
        beacon = beacon / (np.max(np.abs(beacon)) + 1e-12)
        return beacon

    def _listen_for_segment_with_beacons(self, fs, start_threshold=0.6, stop_threshold=0.6, timeout_sec=120):
        """Escucha el micrófono hasta detectar la baliza de inicio y fin; devuelve el segmento entre ambas (sin incluir balizas)."""
        beacon = self._load_beacon(fs)
        if beacon is None:
            return None
        beacon = beacon - np.mean(beacon)
        beacon /= (np.linalg.norm(beacon) + 1e-12)
        blen = len(beacon)

        p = pyaudio.PyAudio()
        chunk = 1024
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, input=True, frames_per_buffer=chunk)

        buf = np.zeros(0, dtype=np.float32)
        recording = False
        recorded = []
        t0 = time.time()
        try:
            while True:
                data = stream.read(chunk)
                samples = np.frombuffer(data, dtype=np.float32)
                # Normalizar un poco para estabilidad
                if np.max(np.abs(samples)) > 1e-6:
                    samples = samples / np.max(np.abs(samples))
                if not recording:
                    buf = np.concatenate([buf, samples])
                    if len(buf) >= blen:
                        window = buf[-blen:]
                        w = window - np.mean(window)
                        w /= (np.linalg.norm(w) + 1e-12)
                        corr = float(np.dot(w, beacon))
                        if corr >= start_threshold:
                            # Empezar a grabar después de la baliza
                            buf = np.zeros(0, dtype=np.float32)
                            recording = True
                            # print("Baliza de inicio detectada")
                else:
                    recorded.append(samples)
                    # Revisar si al final aparece otra baliza (usar últimas blen muestras del acumulado)
                    rec_concat = np.concatenate(recorded[-max(1, blen // chunk + 1):])
                    if len(rec_concat) >= blen:
                        tail = rec_concat[-blen:]
                        t0v = tail - np.mean(tail)
                        t0v /= (np.linalg.norm(t0v) + 1e-12)
                        corr2 = float(np.dot(t0v, beacon))
                        if corr2 >= stop_threshold:
                            # Quitar la baliza final de los datos grabados
                            total = np.concatenate(recorded)
                            if len(total) >= blen:
                                payload = total[:-blen]
                            else:
                                payload = total
                            return payload.astype(np.float32)

                if time.time() - t0 > timeout_sec:
                    return None
        finally:
            stream.stop_stream()
            stream.close()
            p.terminate()

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
            # Necesitamos saber cuántos símbolos esperamos. Si no, estimamos desde duración.
            # Estimación simple:
            est_num_symbols = int((len(rec) / FS) * (FS / SAMPLES_PER_SYMBOL))
            # receive_and_demodulate_passband_signal en tu módulo devuelve (sampled_symbols, filtered_baseband, demodulated_baseband)
            sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(rec, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols)
            demod_bits = bpsk_demodulate(sampled_symbols)
            # intentar decodificar protocolo
            recovered_bits, original_size = decode_data_with_protocol(demod_bits, use_fec=False)
            if recovered_bits is None:
                messagebox.showerror("Error", "No se pudo decodificar protocolo (preambulo no encontrado). Revisa sincronización y SNR.")
                return
            # guardar archivo recuperado
            outname = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Bin files","*.bin"),("All files","*.*")], title="Guardar archivo recuperado")
            if outname:
                bits_to_file(recovered_bits, outname)
                messagebox.showinfo("Guardado", f"Archivo recuperado guardado en: {outname}")
        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))

    def rx_digital_listen_mode(self):
        """Modo bloqueante que espera baliza de inicio y fin para capturar y demodular automáticamente."""
        def worker():
            try:
                carrier = float(self.carrier_dig.get())
                messagebox.showinfo("Escucha", "Entrando en modo escucha. Transmite desde TX con balizas.")
                segment = self._listen_for_segment_with_beacons(FS, start_threshold=0.6, stop_threshold=0.6, timeout_sec=180)
                if segment is None or len(segment) < SAMPLES_PER_SYMBOL * 10:
                    messagebox.showerror("Escucha", "No se detectaron balizas o el segmento es demasiado corto.")
                    return
                # Demodular
                est_num_symbols = max(1, int(len(segment) / SAMPLES_PER_SYMBOL))
                sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(segment, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols)
                demod_bits = bpsk_demodulate(sampled_symbols)
                recovered_bits, original_size = decode_data_with_protocol(demod_bits, use_fec=False)
                if recovered_bits is None:
                    messagebox.showerror("Decodificación", "No se pudo decodificar el protocolo (preambulo no encontrado).")
                    return
                outname = filedialog.asksaveasfilename(defaultextension=".bin", filetypes=[("Bin files","*.bin"),("All files","*.*")], title="Guardar archivo recuperado")
                if outname:
                    bits_to_file(recovered_bits, outname)
                    messagebox.showinfo("Guardado", f"Archivo recuperado guardado en: {outname}")
            except Exception as e:
                messagebox.showerror("Error RX Digital (escucha)", str(e))

        # Ejecutar en hilo para no congelar la UI
        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
