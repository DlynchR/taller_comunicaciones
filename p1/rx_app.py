import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import os
import matplotlib.pyplot as plt

# Importar funciones SSB/ISB
from ssb_isb_simulator import (
    ssb_demodulate, save_audio, load_audio, play_audio, 
    plot_spectrum, plot_time_domain
)

# Importar funciones 2FSK
from digital_fsk_modulator import (
    record_audio_with_tone_trigger,
    fsk_demodulate,
    decode_data_with_protocol,
    bits_to_file,
    calculate_ber,
    file_to_bits,
    FS,
    SAMPLES_PER_SYMBOL,
    FREQ_0,
    FREQ_1,
    plot_constellation,
    plot_eye_diagram
)

class RXApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RX - Receptor (SSB/ISB + 2FSK Digital)")

        # Parámetros SSB
        self.fc_ssb = tk.DoubleVar(value=15000.0)
        self.phase_err = tk.DoubleVar(value=0.0)
        self.freq_err = tk.DoubleVar(value=0.0)

        self.create_widgets()

        # Parámetros de tonos
        self.start_tone_freq = 1000.0
        self.stop_tone_freq = 2000.0

        # Variables para almacenar datos de graficación SSB
        self.last_received_ssb = None
        self.last_demodulated_ssb = None
        self.last_fs_ssb = None

        # Variables para almacenar datos de graficación digital
        self.last_received_digital = None
        self.last_demodulated_bits = None
        self.last_filtered_0 = None
        self.last_filtered_1 = None
        self.last_ber = None
        self.last_original_file = None

    def create_widgets(self):
        # Frame SSB/ISB
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
        ttk.Button(btn_frame_ssb, text="Escuchar y Demodular SSB", 
                  command=self.rx_ssb).pack(side="left", padx=6)
        ttk.Button(btn_frame_ssb, text="Mostrar Gráficas", 
                  command=self.show_rx_plots_ssb).pack(side="left", padx=6)

        # Frame Digital 2FSK
        frame_dig = ttk.LabelFrame(self.root, text="Recepción Digital 2FSK")
        frame_dig.pack(fill="x", padx=8, pady=6)

        info_frame = ttk.Frame(frame_dig)
        info_frame.grid(row=0, column=0, columnspan=2, pady=4)
        ttk.Label(info_frame, text=f"Demodulación: 2FSK | Bit 0: {FREQ_0} Hz | Bit 1: {FREQ_1} Hz", 
                 font=('Arial', 9, 'italic')).pack()
        ttk.Label(info_frame, text="El receptor espera handshake automático", 
                 font=('Arial', 9, 'italic')).pack()

        btn_frame_dig = ttk.Frame(frame_dig)
        btn_frame_dig.grid(row=1, column=0, columnspan=2, pady=6)
        ttk.Button(btn_frame_dig, text="Recibir Archivo (FSK)", 
                  command=self.rx_digital).pack(side="left", padx=6)
        ttk.Button(btn_frame_dig, text="Mostrar Gráficas y BER", 
                  command=self.show_rx_plots_digital).pack(side="left", padx=6)

        # Frame para comparación opcional
        frame_compare = ttk.LabelFrame(self.root, text="Comparación con Original (Opcional)")
        frame_compare.pack(fill="x", padx=8, pady=6)
        
        ttk.Label(frame_compare, text="Archivo original para calcular BER:").grid(row=0, column=0, sticky="w")
        self.original_file_path = tk.StringVar()
        ttk.Entry(frame_compare, textvariable=self.original_file_path, width=50).grid(row=0, column=1)
        ttk.Button(frame_compare, text="Seleccionar", 
                  command=lambda: self.select_file(self.original_file_path)).grid(row=0, column=2)

    def select_file(self, var, types=[("All files","*.*")]):
        path = filedialog.askopenfilename(filetypes=types)
        if path:
            var.set(path)

    def rx_ssb(self):
        try:
            rec = record_audio_with_tone_trigger(fs=FS)
            if rec is None:
                messagebox.showerror("Error", "No se detectó handshake.")
                return

            fc = float(self.fc_ssb.get())
            recovered = ssb_demodulate(rec, FS, fc,
                                       phase_error_deg=float(self.phase_err.get()),
                                       freq_error_hz=float(self.freq_err.get()))
            recovered = recovered / (np.max(np.abs(recovered)) + 1e-12)

            # Guardar datos para graficación
            self.last_received_ssb = rec
            self.last_demodulated_ssb = recovered
            self.last_fs_ssb = FS

            fname = filedialog.asksaveasfilename(defaultextension=".wav", 
                                                filetypes=[("WAV files","*.wav")])
            if fname:
                save_audio(fname, recovered, FS)
                if messagebox.askyesno("Reproducir", "¿Reproducir audio?"):
                    play_audio(recovered, FS)

        except Exception as e:
            messagebox.showerror("Error RX SSB", str(e))
            import traceback
            traceback.print_exc()

    def rx_digital(self):
        """Recepción digital completa con 2FSK."""
        try:
            print("\n" + "="*60)
            print("INICIANDO RECEPCIÓN DIGITAL 2FSK")
            print("="*60)

            # 1. GRABAR CON HANDSHAKE
            print("📡 Esperando handshake del transmisor...")
            rec = record_audio_with_tone_trigger(fs=FS)
            
            if rec is None or len(rec) < SAMPLES_PER_SYMBOL * 20:
                messagebox.showerror("Error", "Grabación muy corta o handshake fallido.")
                return

            print(f"✓ Señal recibida: {len(rec)} muestras ({len(rec)/FS:.2f} s)")

            # Guardar señal recibida
            self.last_received_digital = rec

            # 2. DEMODULACIÓN 2FSK
            est_num_symbols = max(1, int(len(rec) / SAMPLES_PER_SYMBOL))
            print(f"📊 Estimando {est_num_symbols} símbolos...")

            demod_bits, filtered_0, filtered_1 = fsk_demodulate(rec, est_num_symbols)
            
            print(f"✓ Bits demodulados: {len(demod_bits)}")

            # Guardar para graficación
            self.last_demodulated_bits = demod_bits
            self.last_filtered_0 = filtered_0
            self.last_filtered_1 = filtered_1

            # 3. DECODIFICACIÓN DE PROTOCOLO
            print("📦 Decodificando protocolo...")
            data_bits, file_size, checksum_valid = decode_data_with_protocol(demod_bits)

            if data_bits is None:
                messagebox.showerror("Error", "No se pudo decodificar el protocolo.")
                return

            # 4. GUARDAR ARCHIVO RECUPERADO
            outname = filedialog.asksaveasfilename(
                defaultextension="",
                filetypes=[
                    ("Archivos binarios", "*.bin"),
                    ("Texto", "*.txt"),
                    ("Imagen PNG", "*.png"),
                    ("Imagen JPG", "*.jpg"),
                    ("Todos los archivos", "*.*")
                ],
                title="Guardar archivo recuperado"
            )
            
            if not outname:
                return

            bits_to_file(data_bits, outname)
            received_size = os.path.getsize(outname)

            # 5. CALCULAR BER SI HAY ARCHIVO ORIGINAL
            ber = None
            if self.original_file_path.get():
                try:
                    original_bits = file_to_bits(self.original_file_path.get())
                    ber = calculate_ber(original_bits, data_bits)
                    self.last_ber = ber
                    self.last_original_file = self.original_file_path.get()
                    print(f"📈 BER calculado: {ber:.6f} ({ber*100:.4f}%)")
                except Exception as e:
                    print(f"⚠️ No se pudo calcular BER: {e}")

            # 6. CALCULAR TASA DE TRANSFERENCIA
            data_time = len(rec) / FS
            data_rate_bps = (file_size * 8) / data_time

            print("="*60)
            print("✅ RECEPCIÓN COMPLETADA")
            print("="*60)
            print(f"📄 Archivo guardado: {outname}")
            print(f"📊 Tamaño esperado: {file_size} bytes")
            print(f"📊 Tamaño recibido: {received_size} bytes")
            print(f"🔐 Checksum: {'✓ Válido' if checksum_valid else '✗ Inválido'}")
            if ber is not None:
                print(f"📈 BER: {ber:.6f} ({ber*100:.4f}%)")
            print(f"📡 Tasa de transferencia: {data_rate_bps:.0f} bps")
            print("="*60 + "\n")

            # Mensaje final
            msg = f"✅ Archivo reconstruido y guardado:\n{outname}\n\n"
            msg += f"Tamaño: {received_size} bytes (esperado: {file_size})\n"
            msg += f"Checksum: {'✓ Válido' if checksum_valid else '✗ Inválido'}\n"
            if ber is not None:
                msg += f"BER: {ber:.6f} ({ber*100:.4f}%)\n"
            msg += f"Tasa: {data_rate_bps:.0f} bps"

            messagebox.showinfo("Recepción completada", msg)

        except Exception as e:
            messagebox.showerror("Error RX Digital", str(e))
            import traceback
            traceback.print_exc()

    def show_rx_plots_ssb(self):
        """Muestra gráficas de señal SSB/ISB recibida."""
        try:
            if self.last_received_ssb is None or self.last_demodulated_ssb is None:
                messagebox.showwarning("Aviso", "No hay datos. Ejecuta 'Escuchar y Demodular SSB' primero.")
                return

            rec = self.last_received_ssb
            demod = self.last_demodulated_ssb
            fs = self.last_fs_ssb

            fig, axs = plt.subplots(2, 2, figsize=(14, 10))
            fig.suptitle('Análisis de Señal SSB/ISB - Receptor', fontsize=14, fontweight='bold')

            plot_time_domain(rec, fs, "Señal Recibida Modulada", ax=axs[0, 0])
            plot_spectrum(rec, fs, "Señal Recibida (Espectro)", ax=axs[0, 1])
            plot_time_domain(demod, fs, "Señal Demodulada", ax=axs[1, 0])
            plot_spectrum(demod, fs, "Señal Demodulada (Espectro)", ax=axs[1, 1])

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))

    def show_rx_plots_digital(self):
        """Muestra gráficas completas de recepción digital 2FSK."""
        try:
            if self.last_received_digital is None:
                messagebox.showwarning("Aviso", "No hay datos. Ejecuta 'Recibir Archivo' primero.")
                return

            # Crear figura con 6 subplots
            fig = plt.figure(figsize=(16, 12))
            gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
            
            fig.suptitle('Análisis de Recepción Digital 2FSK', fontsize=14, fontweight='bold')

            # 1. Señal recibida en tiempo
            ax1 = fig.add_subplot(gs[0, 0])
            plot_time_domain(self.last_received_digital, FS, 
                           "Señal Recibida (Tiempo)", ax=ax1)

            # 2. Espectro de señal recibida
            ax2 = fig.add_subplot(gs[0, 1])
            plot_spectrum(self.last_received_digital, FS,
                        "Señal Recibida (Espectro)", ax=ax2)

            # 3. Señal filtrada para bit 0
            if self.last_filtered_0 is not None:
                ax3 = fig.add_subplot(gs[1, 0])
                plot_time_domain(self.last_filtered_0, FS,
                               f"Filtro {FREQ_0} Hz (Bit 0)", ax=ax3, max_samples=5000)

            # 4. Señal filtrada para bit 1
            if self.last_filtered_1 is not None:
                ax4 = fig.add_subplot(gs[1, 1])
                plot_time_domain(self.last_filtered_1, FS,
                               f"Filtro {FREQ_1} Hz (Bit 1)", ax=ax4, max_samples=5000)

            # 5. Diagrama de ojo
            ax5 = fig.add_subplot(gs[2, 0])
            if self.last_filtered_1 is not None:
                plot_eye_diagram(self.last_filtered_1, SAMPLES_PER_SYMBOL,
                               title="Diagrama de Ojo", ax=ax5)

            # 6. Información y BER
            ax6 = fig.add_subplot(gs[2, 1])
            ax6.axis('off')
            
            info_text = "RESULTADOS DE RECEPCIÓN\n" + "="*40 + "\n\n"
            info_text += f"Modulación: 2FSK\n"
            info_text += f"Frecuencia Bit 0: {FREQ_0} Hz\n"
            info_text += f"Frecuencia Bit 1: {FREQ_1} Hz\n\n"
            
            if self.last_demodulated_bits is not None:
                info_text += f"Bits demodulados: {len(self.last_demodulated_bits)}\n"
            
            info_text += f"Duración señal: {len(self.last_received_digital)/FS:.2f} s\n\n"
            
            if self.last_ber is not None:
                info_text += "="*40 + "\n"
                info_text += f"BER: {self.last_ber:.6f}\n"
                info_text += f"BER: {self.last_ber*100:.4f}%\n"
                info_text += f"Errores: {int(self.last_ber * len(self.last_demodulated_bits))}\n"
                info_text += "="*40 + "\n"
            else:
                info_text += "\n(Selecciona archivo original\npara calcular BER)"
            
            ax6.text(0.1, 0.5, info_text, fontsize=10, family='monospace',
                    verticalalignment='center', transform=ax6.transAxes)

            plt.tight_layout(rect=[0, 0.03, 1, 0.97])
            plt.show()

        except Exception as e:
            messagebox.showerror("Error al graficar", str(e))
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    root = tk.Tk()
    app = RXApp(root)
    root.mainloop()