# rx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import time
import pyaudio

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

        # Parámetros de escucha (basados en prueba_rx)
        self.chunk = 1024
        self.timeout = tk.DoubleVar(value=0.0)  # 0 = sin límite
        self.use_tone_activation = tk.BooleanVar(value=False)
        self.threshold = tk.DoubleVar(value=1500.0)  # para paInt16
        self.tone_freq = tk.DoubleVar(value=0.0)     # 0 = desactivado
        self.tone_bw = tk.DoubleVar(value=50.0)
        self.tone_ratio = tk.DoubleVar(value=0.5)
        self.stop_tone_freq = tk.DoubleVar(value=2000.0)
        self.stop_tone_bw = tk.DoubleVar(value=30.0)
        self.stop_tone_ratio = tk.DoubleVar(value=0.5)

        # Dispositivos de entrada
        self.device_display = tk.StringVar(value="")
        self.device_map = {}  # display_str -> index

        self.create_widgets()
        self.populate_input_devices()

    def create_widgets(self):
        # Parámetros de escucha y disparo
        frame_listen = ttk.LabelFrame(self.root, text="Escucha y Disparo (Start/Stop)")
        frame_listen.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_listen, text="Dispositivo de entrada:").grid(row=0, column=0, sticky="w")
        self.combo_devices = ttk.Combobox(frame_listen, textvariable=self.device_display, width=50, state="readonly")
        self.combo_devices.grid(row=0, column=1, columnspan=2, sticky="we", padx=(0, 6))
        ttk.Button(frame_listen, text="Actualizar", command=self.populate_input_devices).grid(row=0, column=3, sticky="e")

        ttk.Label(frame_listen, text="Timeout (s, 0 = sin límite):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.timeout, width=12).grid(row=1, column=1, sticky="w")

        # Modo de activación
        ttk.Label(frame_listen, text="Modo de activación:").grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(frame_listen, text="Umbral de amplitud", value=False, variable=self.use_tone_activation).grid(row=2, column=1, sticky="w")
        ttk.Radiobutton(frame_listen, text="Detección de tono", value=True, variable=self.use_tone_activation).grid(row=2, column=2, sticky="w")

        # Parámetros umbral
        ttk.Label(frame_listen, text="Umbral (paInt16):").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.threshold, width=12).grid(row=3, column=1, sticky="w")

        # Parámetros tono de activación
        ttk.Label(frame_listen, text="Tono activación (Hz):").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.tone_freq, width=12).grid(row=4, column=1, sticky="w")

        ttk.Label(frame_listen, text="BW (Hz):").grid(row=4, column=2, sticky="e")
        ttk.Entry(frame_listen, textvariable=self.tone_bw, width=12).grid(row=4, column=3, sticky="w")

        ttk.Label(frame_listen, text="Proporción de energía [0-1]:").grid(row=5, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.tone_ratio, width=12).grid(row=5, column=1, sticky="w")

        # Parámetros tono de parada
        ttk.Label(frame_listen, text="Tono de parada (Hz):").grid(row=6, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.stop_tone_freq, width=12).grid(row=6, column=1, sticky="w")

        ttk.Label(frame_listen, text="BW parada (Hz):").grid(row=6, column=2, sticky="e")
        ttk.Entry(frame_listen, textvariable=self.stop_tone_bw, width=12).grid(row=6, column=3, sticky="w")

        ttk.Label(frame_listen, text="Proporción parada [0-1]:").grid(row=7, column=0, sticky="w")
        ttk.Entry(frame_listen, textvariable=self.stop_tone_ratio, width=12).grid(row=7, column=1, sticky="w")

        # SSB
        frame_ssb = ttk.LabelFrame(self.root, text="Recepción SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Frecuencia portadora esperada (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de fase a aplicar (simulación, deg):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.phase_err, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de frecuencia a aplicar (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.freq_err, width=12).grid(row=2, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Segundos a grabar tras disparo:").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.record_duration, width=12).grid(row=3, column=1, sticky="w")

        ttk.Button(frame_ssb, text="Escuchar y Demodular SSB", command=self.rx_ssb).grid(row=4, column=0, columnspan=2, pady=6)

        # Digital
        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital Pasobanda")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Frecuencia portadora esperada (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.carrier_dig, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_dig, text="Segundos a grabar tras disparo:").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_dig, textvariable=self.record_duration, width=12).grid(row=1, column=1, sticky="w")

        ttk.Button(frame_dig, text="Escuchar y Demodular Digital", command=self.rx_digital).grid(row=2, column=0, columnspan=2, pady=6)

    def populate_input_devices(self):
        try:
            p = pyaudio.PyAudio()
            devices = []
            self.device_map.clear()
            default_idx = None
            try:
                default_info = p.get_default_input_device_info()
                default_idx = int(default_info.get("index", -1))
            except Exception:
                default_idx = None

            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                if int(info.get("maxInputChannels", 0)) > 0:
                    name = info.get("name", "desconocido")
                    rate = int(info.get("defaultSampleRate", 0))
                    display = f"{i}: {name} (rate {rate} Hz)"
                    devices.append(display)
                    self.device_map[display] = i
            self.combo_devices["values"] = devices
            # Selecciona por defecto
            if devices:
                if default_idx is not None:
                    for d in devices:
                        if self.device_map[d] == default_idx:
                            self.device_display.set(d)
                            break
                    else:
                        self.device_display.set(devices[0])
                else:
                    self.device_display.set(devices[0])
            else:
                self.device_display.set("")
        except Exception as e:
            messagebox.showerror("Audio", f"No se pudieron listar dispositivos: {e}")
        finally:
            try:
                p.terminate()
            except Exception:
                pass

    def get_selected_device_index(self):
        disp = self.device_display.get()
        return self.device_map.get(disp, None) if disp else None

    def listen_and_record(self, seconds, fs, chunk=1024):
        """
        Escucha hasta disparo por umbral o tono, graba 'seconds' segundos, 
        y detiene antes si detecta tono de parada. Devuelve float32 normalizado.
        """
        p = pyaudio.PyAudio()
        device_index = self.get_selected_device_index()
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=fs,
                            input=True,
                            frames_per_buffer=chunk,
                            input_device_index=device_index)
        except Exception as e:
            p.terminate()
            raise RuntimeError(f"No se pudo abrir el dispositivo de audio: {e}")

        frames = []
        t0 = time.monotonic()
        timeout_s = float(self.timeout.get())

        # Parámetros
        use_tone = bool(self.use_tone_activation.get())
        threshold = float(self.threshold.get())
        tone_freq = float(self.tone_freq.get())
        tone_bw = float(self.tone_bw.get())
        tone_ratio = float(self.tone_ratio.get())
        stop_tone_freq = float(self.stop_tone_freq.get())
        stop_tone_bw = float(self.stop_tone_bw.get())
        stop_tone_ratio = float(self.stop_tone_ratio.get())

        try:
            # Espera de disparo
            while True:
                data = stream.read(chunk, exception_on_overflow=False)
                arr16 = np.frombuffer(data, dtype=np.int16)
                trigger = False
                if use_tone and tone_freq > 0:
                    x = arr16.astype(np.float32)
                    if len(x) < 8:
                        continue
                    w = np.hanning(len(x)).astype(np.float32)
                    X = np.fft.rfft(x * w)
                    P = np.abs(X) ** 2
                    freqs = np.fft.rfftfreq(len(x), d=1.0 / fs)
                    mask = np.abs(freqs - tone_freq) <= tone_bw
                    band_power = float(P[mask].sum()) if np.any(mask) else 0.0
                    total_power = float(P.sum()) + 1e-12
                    ratio = band_power / total_power
                    trigger = ratio >= tone_ratio
                else:
                    amplitude = float(np.abs(arr16).mean())
                    trigger = amplitude > threshold

                if trigger:
                    # Grabación posterior al disparo
                    max_frames = int(fs / chunk * seconds)
                    recorded = 0
                    while recorded < max_frames:
                        buf = stream.read(chunk, exception_on_overflow=False)
                        frames.append(buf)
                        recorded += 1
                        # Parada anticipada por tono específico
                        if stop_tone_freq and stop_tone_freq > 0:
                            arr2 = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
                            w2 = np.hanning(len(arr2)).astype(np.float32)
                            X2 = np.fft.rfft(arr2 * w2)
                            P2 = np.abs(X2) ** 2
                            freqs2 = np.fft.rfftfreq(len(arr2), d=1.0 / fs)
                            mask2 = np.abs(freqs2 - stop_tone_freq) <= stop_tone_bw
                            band_power2 = float(P2[mask2].sum()) if np.any(mask2) else 0.0
                            total_power2 = float(P2.sum()) + 1e-12
                            ratio2 = band_power2 / total_power2
                            if ratio2 >= stop_tone_ratio:
                                break
                    break

                if timeout_s and (time.monotonic() - t0) >= timeout_s:
                    raise TimeoutError("Tiempo de espera agotado sin detectar disparo.")
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            p.terminate()

        if not frames:
            raise RuntimeError("No se capturó audio tras el disparo.")

        data_all = b"".join(frames)
        arr16_all = np.frombuffer(data_all, dtype=np.int16)
        # Normalizar a float32 [-1, 1]
        audio = (arr16_all.astype(np.float32) / 32768.0).copy()
        return audio

    def rx_ssb(self):
        try:
            duration = float(self.record_duration.get())
            if duration <= 0:
                messagebox.showerror("Error", "Duración inválida")
                return
            # escuchar con disparo y grabar
            rec = self.listen_and_record(seconds=duration, fs=FS, chunk=self.chunk)
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
        except TimeoutError as e:
            messagebox.showwarning("Tiempo agotado", str(e))
        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))

    def rx_digital(self):
        try:
            duration = float(self.record_duration.get())
            carrier = float(self.carrier_dig.get())
            if duration <= 0:
                messagebox.showerror("Error", "Duración inválida")
                return
            # escuchar con disparo y grabar
            rec = self.listen_and_record(seconds=duration, fs=FS, chunk=self.chunk)
            # Estimar símbolos
            est_num_symbols = int(len(rec) / SAMPLES_PER_SYMBOL)
            # Demodular
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
        except TimeoutError as e:
            messagebox.showwarning("Tiempo agotado", str(e))
        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
