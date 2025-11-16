# rx_app_clean.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt

# SSB/ISB imports (unchanged)
from ssb_isb_simulator import ssb_demodulate, save_audio, load_audio, play_audio, plot_spectrum, plot_time_domain

# Digital imports (new simple system)
from digital_simple import receive_text_file, FS, CARRIER_FREQ, record_with_tone_trigger, demodulate_passband_signal, bpsk_demodulate, SAMPLES_PER_SYMBOL, START_TONE_FREQ, STOP_TONE_FREQ

class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX - Receptor (SSB/ISB + Digital)")

        # Parámetros SSB (UNCHANGED)
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.phase_err = tk.DoubleVar(value=0.0)
        self.freq_err = tk.DoubleVar(value=0.0)

        # Parámetros digitales (simplified)
        self.carrier_dig = tk.DoubleVar(value=CARRIER_FREQ)

        # Variables para graficación SSB
        self.last_received_ssb = None
        self.last_demodulated_ssb = None
        self.last_fs_ssb = None

        self.create_widgets()

    def create_widgets(self):
        # ==================== SSB/ISB SECTION (UNCHANGED) ====================
        frame_ssb = ttk.LabelFrame(self.root, text="Recepción SSB / ISB (Audio)")
        frame_ssb.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_ssb, text="Frecuencia portadora SSB (Hz):").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.fc_ssb, width=12).grid(row=0, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de fase (deg):").grid(row=1, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.phase_err, width=12).grid(row=1, column=1, sticky="w")

        ttk.Label(frame_ssb, text="Error de frecuencia (Hz):").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame_ssb, textvariable=self.freq_err, width=12).grid(row=2, column=1, sticky="w")
        
        btn_frame_ssb = ttk.Frame(frame_ssb)
        btn_frame_ssb.grid(row=3, column=0, columnspan=2, pady=6)
        ttk.Button(btn_frame_ssb, text="Escuchar y Demodular SSB", command=self.rx_ssb).pack(side="left", padx=6)
        ttk.Button(btn_frame_ssb, text="Mostrar Gráficas", command=self.show_rx_plots_ssb).pack(side="left", padx=6)

        # ==================== DIGITAL SECTION (NEW SIMPLE) ====================
        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital (Solo Texto)")
        frame_dig.pack(fill="x", padx=8, pady=6)

        ttk.Label(frame_dig, text="Portadora digital (Hz):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(frame_dig, textvariable=self.carrier_dig, width=12).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Button(frame_dig, text="📡 Escuchar y Demodular", 
                   command=self.rx_digital).grid(row=1, column=0, columnspan=2, pady=10)
        
        # Status label
        self.status_label = ttk.Label(frame_dig, text="Esperando transmisión...", foreground="gray")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=5)

    # ==================== SSB/ISB METHODS (UNCHANGED) ====================

    def rx_ssb(self):
        try:
            rec = record_with_tone_trigger(FS, START_TONE_FREQ, STOP_TONE_FREQ)
            
            if rec is None:
                messagebox.showerror("Error", "No se detectaron tonos")
                return

            fc = float(self.fc_ssb.get())
            recovered = ssb_demodulate(rec, FS, fc,
                                       phase_error_deg=float(self.phase_err.get()),
                                       freq_error_hz=float(self.freq_err.get()))
            recovered = recovered / (np.max(np.abs(recovered)) + 1e-12)

            self.last_received_ssb = rec
            self.last_demodulated_ssb = recovered
            self.last_fs_ssb = FS

            fname = filedialog.asksaveasfilename(defaultextension=".wav", filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, recovered, FS)
                if messagebox.askyesno("Reproducir", "¿Reproducir audio?"):
                    play_audio(recovered, FS)

        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))

    def show_rx_plots_ssb(self):
        try:
            if self.last_received_ssb is None or self.last_demodulated_ssb is None:
                messagebox.showwarning("Aviso", "No hay datos para graficar")
                return

            rec = self.last_received_ssb
            demod = self.last_demodulated_ssb
            fs = self.last_fs_ssb

            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Señal SSB/ISB - Receptor', fontsize=14, fontweight='bold')

            plot_time_domain(rec, fs, "Señal Recibida Modulada (Tiempo)", ax=axs[0, 0])
            plot_spectrum(rec, fs, "Señal Recibida Modulada (Frecuencia)", ax=axs[0, 1])
            plot_time_domain(demod, fs, "Señal Demodulada (Tiempo)", ax=axs[1, 0])
            plot_spectrum(demod, fs, "Señal Demodulada (Frecuencia)", ax=axs[1, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))

    # ==================== DIGITAL METHODS (NEW SIMPLE) ====================

    def rx_digital(self):
        """Recepción digital simple: Escucha tonos 1kHz/2kHz, demodula BPSK, decodifica"""
        try:
            self.status_label.config(text="🎙️ Esperando tono de inicio (1 kHz)...", foreground="blue")
            self.root.update()
            
            carrier = float(self.carrier_dig.get())
            
            print(f"\n{'='*50}")
            print("MODO RECEPCIÓN")
            print(f"Portadora: {carrier} Hz")
            print(f"{'='*50}\n")
            
            # Seleccionar archivo de salida
            output_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Archivos de texto", "*.txt")],
                title="Guardar archivo recibido como..."
            )
            
            if not output_path:
                self.status_label.config(text="Cancelado por usuario", foreground="gray")
                return
            
            self.status_label.config(text="📡 Grabando...", foreground="orange")
            self.root.update()
            
            # Recibir y demodular
            success, stats = receive_text_file(output_path, carrier, FS)
            
            if success:
                self.status_label.config(text="✅ Archivo recibido correctamente", foreground="green")
                
                # Mostrar estadísticas
                file_size = stats.get('file_size', 0)
                trans_time = stats.get('transmission_time', 0)
                data_rate = stats.get('data_rate', 0)
                
                msg = f"✅ Archivo recibido y guardado:\n{output_path}\n\n"
                msg += f"📊 Estadísticas:\n"
                msg += f"  • Tamaño: {file_size} bytes\n"
                msg += f"  • Tiempo: {trans_time:.2f} segundos\n"
                msg += f"  • Tasa: {data_rate:.0f} bps\n"
                
                messagebox.showinfo("Recepción exitosa", msg)
            else:
                self.status_label.config(text="❌ Error en recepción", foreground="red")
                messagebox.showerror("Error", "No se pudo decodificar el archivo correctamente")
        
        except Exception as e:
            self.status_label.config(text="❌ Error", foreground="red")
            messagebox.showerror("Error RX Digital", str(e))
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()
