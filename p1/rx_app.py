
# rx_app.py (corregido)
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
import os

# Importar funciones del módulo digital actualizado
from digital_passband_modulator import (
    FS, CARRIER_FREQ, SAMPLES_PER_SYMBOL,
    record_audio_with_tone_trigger,
    receive_and_demodulate_passband_signal,
    bpsk_demodulate,
    decode_data_with_protocol,
    bits_to_file,
    plot_time_domain,
    plot_spectrum,
    calculate_ber
)

class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX - Receptor Digital Pasobanda (BPSK)")

        self.save_folder = tk.StringVar(value=os.getcwd())
        self.original_file_for_ber = tk.StringVar()  # para comparar BER si se desea
        self.last_received = None  # tupla: (recorded_signal, fs)
        self.last_sampled_symbols = None
        self.last_filtered = None
        self.last_demod = None
        self.last_bits = None
        self.last_payload_bits = None
        self.last_original_size = None

        self.create_widgets()

    def create_widgets(self):
        frame_controls = ttk.LabelFrame(self.root, text="Controles RX")
        frame_controls.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_controls, text="Carpeta para guardar:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_controls, textvariable=self.save_folder, width=50).grid(row=0, column=1)
        ttk.Button(frame_controls, text="Seleccionar carpeta", command=self.select_folder).grid(row=0, column=2)

        ttk.Label(frame_controls, text="Archivo original (opcional, para BER):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_controls, textvariable=self.original_file_for_ber, width=50).grid(row=1, column=1)
        ttk.Button(frame_controls, text="Seleccionar archivo", command=self.select_original_for_ber).grid(row=1, column=2)

        btn_frame = ttk.Frame(frame_controls)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=6)
        ttk.Button(btn_frame, text="Escuchar y Demodular Digital", command=self.listen_and_demod).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Guardar archivo recuperado", command=self.save_recovered_file).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Mostrar gráficas RX", command=self.show_rx_plots).pack(side="left", padx=6)

    def select_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.save_folder.set(d)

    def select_original_for_ber(self):
        p = filedialog.askopenfilename()
        if p:
            self.original_file_for_ber.set(p)

    def listen_and_demod(self):
        try:
            # Grabar usando el trigger de tono (espera tono de inicio y stop tone para terminar)
            print("Iniciando grabación (esperando tono de inicio)...")
            recorded = record_audio_with_tone_trigger(FS)
            if recorded is None or len(recorded) == 0:
                messagebox.showwarning("Grabación", "No se registró señal o no se detectó el tono de inicio.")
                return
            self.last_received = (recorded, FS)
            # Demodulación pasobanda -> baseband -> símbolos muestreados
            # Estimar máximo de símbolos en la grabación
            est_symbols = max(1, int(len(recorded) / SAMPLES_PER_SYMBOL))
            sampled_symbols, filtered_bb, demodulated_bb = receive_and_demodulate_passband_signal(
                recorded, CARRIER_FREQ, FS, SAMPLES_PER_SYMBOL, est_symbols
            )
            self.last_sampled_symbols = sampled_symbols
            self.last_filtered = filtered_bb
            self.last_demod = demodulated_bb
            # Decidir bits
            bits = bpsk_demodulate(sampled_symbols)
            self.last_bits = bits
            # Intentar decodificar protocolo/frame
            payload_bits, original_size = decode_data_with_protocol(bits)
            if payload_bits is None:
                messagebox.showwarning("Decodificación", "No se pudo recuperar una trama válida (CRC/preambulo). Aún se muestran las gráficas de señal para diagnóstico.")
                self.last_payload_bits = None
                self.last_original_size = None
            else:
                self.last_payload_bits = payload_bits
                self.last_original_size = original_size
                messagebox.showinfo("Decodificación", f"Trama recuperada. Tamaño original aproximado: {original_size} bytes.")
            return
        except Exception as e:
            messagebox.showerror("Error RX", str(e))

    def save_recovered_file(self):
        try:
            if self.last_payload_bits is None:
                messagebox.showwarning("Guardar", "No hay un archivo recuperado válido para guardar.")
                return
            # Preguntar nombre
            suggested = os.path.join(self.save_folder.get(), "recovered.bin")
            fname = filedialog.asksaveasfilename(defaultextension=".bin", initialfile=suggested, filetypes=[("BIN files","*.bin"),("All files","*.*")])
            if not fname:
                return
            bits_to_save = self.last_payload_bits
            bits_to_file(bits_to_save, fname)
            messagebox.showinfo("Guardado", f"Archivo recuperado guardado en: {fname}")
        except Exception as e:
            messagebox.showerror("Error guardar", str(e))

    def show_rx_plots(self):
        try:
            if self.last_received is None:
                messagebox.showwarning("Graficar", "No hay señal grabada. Ejecuta 'Escuchar y Demodular Digital' primero.")
                return
            recorded, fs = self.last_received
            sampled = self.last_sampled_symbols if self.last_sampled_symbols is not None else np.array([])
            filtered = self.last_filtered if self.last_filtered is not None else np.array([])
            demod = self.last_demod if self.last_demod is not None else np.array([])

            fig, axs = plt.subplots(3, 2, figsize=(14, 10))
            fig.suptitle("Análisis RX - Señal grabada y baseband", fontsize=14, fontweight='bold')

            # 1: Señal grabada (tiempo)
            plot_time_domain(recorded, fs, "Señal grabada (Tiempo)", ax=axs[0,0])
            # 2: Espectro señal grabada
            plot_spectrum(recorded, fs, "Señal grabada (Espectro)", ax=axs[0,1])

            # 3: Baseband demodulado (tiempo)
            if len(demod)>0:
                plot_time_domain(demod, fs, "Baseband demodulado (Producto con cos)", ax=axs[1,0])
                plot_spectrum(demod, fs, "Baseband demodulado (Espectro)", ax=axs[1,1])
            else:
                axs[1,0].text(0.5,0.5,"No hay baseband demodulado", ha='center')
                axs[1,1].text(0.5,0.5,"No hay baseband demodulado", ha='center')

            # 5: Filtered baseband and sampled symbols (zoom)
            if len(filtered)>0:
                # mostrar primera parte
                plot_time_domain(filtered[:min(len(filtered), fs//2)], fs, "Filtered baseband (Zoom 0.5s)", ax=axs[2,0])
                # Diagrama de ojo aproximado: tomar una porción y plegarla por símbolo
                if len(sampled)>5:
                    # construir eye by slicing filtered into symbol intervals
                    sym = SAMPLES_PER_SYMBOL
                    n_syms = min(200, len(filtered)//sym - 2)
                    if n_syms>2:
                        eye_matrix = np.array([filtered[i*sym:(i+1)*sym] for i in range(2, 2+n_syms)])
                        eye = eye_matrix.T
                        axs[2,1].plot(eye)
                        axs[2,1].set_title("Diagrama de ojo (apilado por símbolo)")
                        axs[2,1].set_xlabel("Muestras dentro de símbolo")
                    else:
                        axs[2,1].text(0.5,0.5,"No hay suficientes símbolos para eye diagram", ha='center')
                else:
                    axs[2,1].text(0.5,0.5,"No hay suficientes símbolos para eye diagram", ha='center')
            else:
                axs[2,0].text(0.5,0.5,"No hay señal filtrada", ha='center')
                axs[2,1].text(0.5,0.5,"No hay eye diagram", ha='center')

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

            # Mostrar BER si el usuario proveyó archivo original para comparar
            if self.original_file_for_ber.get() and self.last_payload_bits is not None:
                orig_bits = None
                try:
                    with open(self.original_file_for_ber.get(), 'rb') as f:
                        orig_bytes = f.read()
                    # convertir a bits
                    orig_bits = []
                    for b in orig_bytes:
                        for i in range(8):
                            orig_bits.append((b >> (7-i)) & 1)
                except Exception as e:
                    orig_bits = None
                if orig_bits is not None:
                    ber = calculate_ber(orig_bits, self.last_payload_bits)
                    messagebox.showinfo("BER", f"BER aproximado (comparando con archivo original seleccionado): {ber:.6f}")
            return
        except Exception as e:
            messagebox.showerror("Error graficar", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()