# tx_app.py
# Transmisor digital pasobanda con visualización de señales

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
import os
from digital_passband_modulator import (
    transmit_file,  
    FS, 
    CARRIER_FREQ,
    SAMPLES_PER_SYMBOL,
    file_to_bits,
    encode_data_with_protocol,
    bpsk_modulate,
    generate_passband_signal,
    plot_time_domain,
    plot_spectrum
)

class SimpleTX:
    def __init__(self, root):
        self.root = root
        self.root.title("TX Digital Simple (BPSK Pasobanda)")

        self.file_path = tk.StringVar()
        self.use_fec = tk.BooleanVar(value=False)
        self.carrier = tk.DoubleVar(value=CARRIER_FREQ)
        
        # Variables para almacenar las señales generadas
        self.last_bits = None
        self.last_symbols = None
        self.last_baseband = None
        self.last_passband = None

        self.create_widgets()

    def create_widgets(self):
        frame = ttk.LabelFrame(self.root, text="Transmisión Digital")
        frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(frame, text="Archivo a transmitir:").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.file_path, width=50).grid(row=0, column=1)
        ttk.Button(frame, text="Seleccionar archivo",
                   command=self.select_file).grid(row=0, column=2)

        ttk.Checkbutton(frame, text="Usar FEC (placeholder)",
                        variable=self.use_fec).grid(row=1, column=0, sticky="w")

        ttk.Label(frame, text="Carrier (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.carrier, width=10).grid(row=2, column=1, sticky="w")

        ttk.Button(frame, text="Transmitir por parlante",
                   command=self.tx_digital).grid(row=3, column=0, columnspan=3, pady=10)

        ttk.Button(frame, text="Generar WAV modulado",
                   command=self.save_wav).grid(row=4, column=0, columnspan=3, pady=5)
        
        ttk.Button(frame, text="Mostrar gráficas TX",
                   command=self.show_tx_plots).grid(row=5, column=0, columnspan=3, pady=5)

    def select_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.file_path.set(path)

    def generate_signals(self):
        """Genera todas las señales para transmisión y las almacena"""
        try:
            # Obtener tamaño original del archivo
            original_size = os.path.getsize(self.file_path.get())
            
            # Leer archivo y convertir a bits
            bits = file_to_bits(self.file_path.get())
            
            # Codificar con protocolo (preámbulo, tamaño, CRC)
            encoded_bits = encode_data_with_protocol(bits, original_size, use_fec=self.use_fec.get())
            self.last_bits = encoded_bits
            
            # Modular BPSK (bits -> símbolos y señal baseband)
            baseband_signal = bpsk_modulate(encoded_bits)
            self.last_baseband = baseband_signal
            
            # Extraer símbolos (valores +1/-1)
            symbols = np.array([1.0 if b == 1 else -1.0 for b in encoded_bits])
            self.last_symbols = symbols
            
            # Modular a pasobanda
            passband_signal = generate_passband_signal(
                baseband_signal, 
                float(self.carrier.get()), 
                FS
            )
            self.last_passband = passband_signal
            
            return passband_signal
            
        except Exception as e:
            raise Exception(f"Error generando señales: {str(e)}")

    def tx_digital(self):
        if not self.file_path.get():
            messagebox.showerror("Error", "Selecciona un archivo primero.")
            return
        try:
            transmit_file(
                self.file_path.get(),
                carrier_freq=float(self.carrier.get()),
                fs=FS,
                use_fec=self.use_fec.get(),
                play=True,
                out_wav=None
            )
            # Generar señales para visualización
            self.generate_signals()
            messagebox.showinfo("TX", "Transmisión realizada.")
        except Exception as e:
            messagebox.showerror("Error TX", str(e))

    def save_wav(self):
        if not self.file_path.get():
            messagebox.showerror("Error", "Selecciona un archivo primero.")
            return

        fname = filedialog.asksaveasfilename(defaultextension=".wav",
                                             filetypes=[("WAV files", "*.wav")])
        if not fname:
            return

        try:
            transmit_file(
                self.file_path.get(),
                carrier_freq=float(self.carrier.get()),
                fs=FS,
                use_fec=self.use_fec.get(),
                play=False,
                out_wav=fname
            )
            # Generar señales para visualización
            self.generate_signals()
            messagebox.showinfo("TX", "WAV generado correctamente.")
        except Exception as e:
            messagebox.showerror("Error WAV", str(e))

    def show_tx_plots(self):
        try:
            if self.last_passband is None:
                # Si no hay señales generadas, intentar generarlas
                if not self.file_path.get():
                    messagebox.showwarning("Graficar", 
                        "No hay señales generadas. Primero transmite o genera un WAV.")
                    return
                self.generate_signals()
            
            # Crear figura con subplots
            fig, axs = plt.subplots(3, 2, figsize=(14, 10))
            fig.suptitle("Análisis TX - Señales Generadas", fontsize=14, fontweight='bold')

            # 1: Señal Baseband (tiempo)
            if self.last_baseband is not None:
                samples_to_show = min(len(self.last_baseband), FS)  # Mostrar 1 segundo
                plot_time_domain(
                    self.last_baseband[:samples_to_show], 
                    FS, 
                    "Señal Baseband (Tiempo - 1s)", 
                    ax=axs[0,0]
                )
                # 2: Espectro Baseband
                plot_spectrum(
                    self.last_baseband, 
                    FS, 
                    "Señal Baseband (Espectro)", 
                    ax=axs[0,1]
                )
            else:
                axs[0,0].text(0.5, 0.5, "No hay señal baseband", ha='center')
                axs[0,1].text(0.5, 0.5, "No hay señal baseband", ha='center')

            # 3: Señal Modulada Pasobanda (tiempo)
            if self.last_passband is not None:
                samples_to_show = min(len(self.last_passband), FS)  # Mostrar 1 segundo
                plot_time_domain(
                    self.last_passband[:samples_to_show], 
                    FS, 
                    "Señal Pasobanda Modulada (Tiempo - 1s)", 
                    ax=axs[1,0]
                )
                # 4: Espectro Pasobanda
                plot_spectrum(
                    self.last_passband, 
                    FS, 
                    "Señal Pasobanda (Espectro)", 
                    ax=axs[1,1]
                )
            else:
                axs[1,0].text(0.5, 0.5, "No hay señal pasobanda", ha='center')
                axs[1,1].text(0.5, 0.5, "No hay señal pasobanda", ha='center')

            # 5: Diagrama de constelación (símbolos BPSK)
            if self.last_symbols is not None:
                axs[2,0].scatter(
                    self.last_symbols[:min(500, len(self.last_symbols))], 
                    np.zeros(min(500, len(self.last_symbols))),
                    alpha=0.5
                )
                axs[2,0].set_title("Constelación BPSK (primeros 500 símbolos)")
                axs[2,0].set_xlabel("Amplitud")
                axs[2,0].set_ylabel("Fase (0)")
                axs[2,0].grid(True)
                axs[2,0].axhline(y=0, color='k', linestyle='-', linewidth=0.5)
                axs[2,0].axvline(x=0, color='k', linestyle='-', linewidth=0.5)
            else:
                axs[2,0].text(0.5, 0.5, "No hay símbolos", ha='center')

            # 6: Diagrama de ojo de la señal baseband
            if self.last_baseband is not None and len(self.last_baseband) > SAMPLES_PER_SYMBOL * 10:
                n_symbols = min(200, len(self.last_baseband) // SAMPLES_PER_SYMBOL - 2)
                if n_symbols > 2:
                    eye_matrix = np.array([
                        self.last_baseband[i*SAMPLES_PER_SYMBOL:(i+1)*SAMPLES_PER_SYMBOL] 
                        for i in range(2, 2 + n_symbols)
                    ])
                    eye = eye_matrix.T
                    axs[2,1].plot(eye, alpha=0.3)
                    axs[2,1].set_title("Diagrama de Ojo (Baseband)")
                    axs[2,1].set_xlabel("Muestras dentro de símbolo")
                    axs[2,1].set_ylabel("Amplitud")
                    axs[2,1].grid(True)
                else:
                    axs[2,1].text(0.5, 0.5, "No hay suficientes símbolos", ha='center')
            else:
                axs[2,1].text(0.5, 0.5, "No hay señal para eye diagram", ha='center')

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()
            
        except Exception as e:
            messagebox.showerror("Error graficar", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleTX(root)
    root.mainloop()