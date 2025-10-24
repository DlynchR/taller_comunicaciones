# rx_app.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import threading
import time
import os
from collections import deque

from ssb_isb_simulator import ssb_demodulate, save_audio, load_audio, play_audio
from digital_passband_modulator import (
    record_audio, receive_and_demodulate_passband_signal, bpsk_demodulate,
    decode_data_with_protocol, bits_to_file, FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL,
    PREAMBLE_BITS, POSTAMBLE_BITS
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

        # Estado de "modo escucha"
        self.listening = False
        self.listen_thread = None
        self.status_var = tk.StringVar(value="Detenido")

        # Parámetros de detección
        self.preroll_ms = 50
        self.postroll_ms = 50
        self.end_timeout_s = 25
        self._reset_detection_state()

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

        # Controles de modo escucha
        frame_listen = ttk.LabelFrame(self.root, text="Modo Escucha (detección por preámbulo/postámbulo)")
        frame_listen.pack(fill="x", padx=8, pady=6)
        ttk.Button(frame_listen, text="Iniciar escucha", command=self.start_listening).grid(row=0, column=0, padx=4, pady=4)
        ttk.Button(frame_listen, text="Detener escucha", command=self.stop_listening).grid(row=0, column=1, padx=4, pady=4)
        ttk.Label(frame_listen, textvariable=self.status_var).grid(row=0, column=2, padx=8)

    def _reset_detection_state(self):
        # Buffer circular grande para mantener hasta ~40s
        self.buffer_max_seconds = 40
        self.buffer = deque(maxlen=int(FS * self.buffer_max_seconds))
        self.samples_seen = 0  # contador total de muestras procesadas
        self.state = "IDLE"  # IDLE -> CAPTURING
        self.start_sample_abs = None
        self.capture_started_at_time = None
        self.detect_carrier_hz = None  # portadora con la que se detectó
        # Precomputar plantillas de preámbulo para ambas portadoras candidatas
        self._build_templates()

    def _build_templates(self):
        # Genera plantillas de preámbulo/postámbulo BPSK en pasobanda para dos portadoras posibles
        def bpsk_template(bits, fc):
            symbols = np.array([1.0 if b == 1 else -1.0 for b in bits], dtype=np.float64)
            t_sym = np.arange(SAMPLES_PER_SYMBOL) / FS  # duración de símbolo = SAMPLES_PER_SYMBOL/FS
            # Construimos la forma de onda concatenando cada símbolo
            wave = np.concatenate([
                s * np.cos(2*np.pi*fc*t_sym) for s in symbols
            ]).astype(np.float64)
            # También la versión en cuadratura para magnitud fase-invariante
            wave_sin = np.concatenate([
                s * np.sin(2*np.pi*fc*t_sym) for s in symbols
            ]).astype(np.float64)
            # Normalizar energía
            denom = np.sqrt(np.sum(wave**2) + np.sum(wave_sin**2) + 1e-12)
            return wave/denom, wave_sin/denom

        fc_ssb = float(getattr(self, 'fc_ssb', tk.DoubleVar(value=15000.0)).get()) if hasattr(self, 'fc_ssb') else 15000.0
        fc_dig = float(getattr(self, 'carrier_dig', tk.DoubleVar(value=CARRIER_FREQ)).get()) if hasattr(self, 'carrier_dig') else CARRIER_FREQ
        self.templates = {
            fc_ssb: bpsk_template(PREAMBLE_BITS, fc_ssb),
            fc_dig: bpsk_template(PREAMBLE_BITS, fc_dig)
        }
        self.post_templates = {
            fc_ssb: bpsk_template(POSTAMBLE_BITS, fc_ssb),
            fc_dig: bpsk_template(POSTAMBLE_BITS, fc_dig)
        }

    def start_listening(self):
        if self.listening:
            return
        self._reset_detection_state()
        self.listening = True
        self.status_var.set("Escuchando…")
        self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listen_thread.start()

    def stop_listening(self):
        self.listening = False
        self.status_var.set("Detenido")

    def _listen_loop(self):
        # Abrimos un stream de grabación continuo con bloques
        import pyaudio
        p = pyaudio.PyAudio()
        chunk = 1024
        stream = p.open(format=pyaudio.paFloat32, channels=1, rate=FS, input=True, frames_per_buffer=chunk)
        try:
            while self.listening:
                data = stream.read(chunk, exception_on_overflow=False)
                samples = np.frombuffer(data, dtype=np.float32).astype(np.float64)
                self._process_samples(samples)
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
            p.terminate()

    def _process_samples(self, samples: np.ndarray):
        # Añadir a buffer circular
        self.buffer.extend(samples.tolist())
        cur_abs_start = self.samples_seen
        self.samples_seen += len(samples)

        # Procesamiento por estados
        if self.state == "IDLE":
            # Intentar detectar preámbulo en la parte reciente del buffer
            self._try_detect_preamble()
        elif self.state == "CAPTURING":
            # Chequear fin por postámbulo o timeout
            done, reason = self._try_detect_end()
            if done:
                self._finalize_capture(reason)

    def _buffer_as_np(self):
        if len(self.buffer) == 0:
            return np.zeros(0, dtype=np.float64)
        return np.fromiter(self.buffer, dtype=np.float64, count=len(self.buffer))

    def _try_detect_preamble(self):
        buf = self._buffer_as_np()
        if buf.size == 0:
            return

        # Buscar con ambas portadoras; usar correlación magnitud fase-invariante
        threshold = 0.6  # umbral empírico
        best_score = 0.0
        best_idx = None
        best_fc = None
        for fc, (tpl_c, tpl_s) in self.templates.items():
            L = len(tpl_c)
            if buf.size < L:
                continue
            seg = buf[-(L + int(0.5*FS)):] if buf.size >= L + int(0.5*FS) else buf  # última ventana ampliada
            # Correlación "válida" (deslizante) usando convolución con reverso
            c1 = np.correlate(seg, tpl_c[::-1], mode='valid')
            c2 = np.correlate(seg, tpl_s[::-1], mode='valid')
            mag = np.sqrt(c1**2 + c2**2)
            idx_local = np.argmax(mag)
            score = mag[idx_local]
            if score > best_score:
                best_score = score
                best_idx = seg.size - len(mag) + idx_local  # índice dentro de buf
                best_fc = fc

        if best_score >= threshold and best_idx is not None:
            # Determinar inicio con preroll
            preroll_samples = int(self.preroll_ms * 1e-3 * FS)
            start_idx_buf = max(0, best_idx - preroll_samples)
            # Guardar estado con índice absoluto
            buf_start_abs = self.samples_seen - len(self.buffer)
            self.start_sample_abs = buf_start_abs + start_idx_buf
            self.detect_carrier_hz = best_fc
            self.capture_started_at_time = time.time()
            self.state = "CAPTURING"
            # Actualizar estado visual (opcional)
            self.status_var.set("Capturando…")

    def _try_detect_end(self):
        # Fin por postámbulo o por timeout
        if self.capture_started_at_time is None:
            return False, None
        if (time.time() - self.capture_started_at_time) >= self.end_timeout_s:
            return True, "timeout"

        buf = self._buffer_as_np()
        if buf.size == 0:
            return False, None
        fc = self.detect_carrier_hz if self.detect_carrier_hz is not None else float(self.carrier_dig.get())
        tpl = self.post_templates.get(fc)
        if tpl is None:
            return False, None
        tpl_c, tpl_s = tpl
        L = len(tpl_c)
        if buf.size < L:
            return False, None
        # Desde el último segundo para delante, buscar el postámbulo
        seg = buf[-(L + int(1.0*FS)):] if buf.size >= L + int(1.0*FS) else buf
        c1 = np.correlate(seg, tpl_c[::-1], mode='valid')
        c2 = np.correlate(seg, tpl_s[::-1], mode='valid')
        mag = np.sqrt(c1**2 + c2**2)
        idx_local = np.argmax(mag)
        score = mag[idx_local]
        threshold = 0.6
        if score >= threshold:
            # Índice relativo al buffer actual
            end_idx_buf = seg.size - len(mag) + idx_local + L  # final del postámbulo
            # Aplicar postroll
            postroll_samples = int(self.postroll_ms * 1e-3 * FS)
            end_idx_buf = min(len(self.buffer), end_idx_buf + postroll_samples)
            # Convertir a índice absoluto y almacenar
            buf_start_abs = self.samples_seen - len(self.buffer)
            self.end_sample_abs = buf_start_abs + end_idx_buf
            return True, "postamble"
        return False, None

    def _finalize_capture(self, reason: str):
        # Extraer desde start_sample_abs hasta end_sample_abs (o hasta ahora si timeout sin setear)
        buf = self._buffer_as_np()
        buf_start_abs = self.samples_seen - len(self.buffer)
        if reason == "timeout":
            self.end_sample_abs = self.samples_seen  # hasta el último sample
        start = max(0, int(self.start_sample_abs - buf_start_abs))
        end = max(start + 1, int(self.end_sample_abs - buf_start_abs))
        segment = buf[start:end].astype(np.float64)

        # Rearmar estado para continuar escuchando siguiente mensaje
        self.state = "IDLE"
        self.start_sample_abs = None
        self.capture_started_at_time = None
        self.detect_carrier_hz = None
        self.status_var.set("Escuchando…")

        # Procesar segmento: intentar digital primero, si falla, tratar como SSB/ISB
        try:
            self._process_captured_segment(segment, reason)
        except Exception as e:
            messagebox.showerror("Error procesando captura", str(e))

    def _process_captured_segment(self, segment: np.ndarray, reason: str):
        ts = time.strftime("%Y%m%d_%H%M%S")
        no_end_suffix = "_no_end" if reason == "timeout" else ""

        # Intento digital
        carrier = float(self.carrier_dig.get())
        # Estimar símbolos
        est_num_symbols = int((len(segment) / FS) * (FS / SAMPLES_PER_SYMBOL))
        if est_num_symbols <= 0:
            return
        sampled_symbols, filtered_baseband, demodulated_baseband = receive_and_demodulate_passband_signal(
            segment, carrier, FS, SAMPLES_PER_SYMBOL, est_num_symbols
        )
        demod_bits = bpsk_demodulate(sampled_symbols)
        recovered_bits, original_size = decode_data_with_protocol(demod_bits, use_fec=False)
        if recovered_bits is not None and original_size is not None and original_size > 0:
            # Guardar en carpeta datos/
            out_dir = os.path.join(os.path.dirname(__file__), 'datos')
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"rx_data_{ts}{no_end_suffix}.bin")
            bits_to_file(recovered_bits, out_path)
            messagebox.showinfo("Datos guardados", f"Archivo recuperado guardado en: {out_path}")
            return

        # Si no se pudo decodificar como digital, intentar SSB/ISB (audio)
        fc = float(self.fc_ssb.get())
        # Remover explícitamente los pre/post de BPSK si existieran al inicio/fin del segmento
        prepost_samples = len(PREAMBLE_BITS) * SAMPLES_PER_SYMBOL
        if segment.size > 2 * prepost_samples:
            segment_audio = segment[prepost_samples: -prepost_samples]
        else:
            segment_audio = segment
        recovered = ssb_demodulate(segment_audio, FS, fc,
                                   phase_error_deg=float(self.phase_err.get()),
                                   freq_error_hz=float(self.freq_err.get()))
        recovered = recovered / (np.max(np.abs(recovered)) + 1e-12)
        out_dir = os.path.join(os.path.dirname(__file__), 'audios')
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"rx_audio_{ts}{no_end_suffix}.wav")
        save_audio(out_path, recovered.astype(np.float32), FS)
        messagebox.showinfo("Audio guardado", f"Audio recuperado guardado en: {out_path}")

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
            out_dir = os.path.join(os.path.dirname(__file__), 'datos')
            os.makedirs(out_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            outname = os.path.join(out_dir, f"rx_data_{ts}.bin")
            bits_to_file(recovered_bits, outname)
            messagebox.showinfo("Guardado", f"Archivo recuperado guardado en: {outname}")
        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
