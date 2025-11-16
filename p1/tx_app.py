# tx_simple.py
# Transmisor digital pasobanda simple (compatible con rx_app.py corregido)

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from digital_passband_modulator import (
    transmit_file,  
    FS, 
    CARRIER_FREQ
)

class SimpleTX:
    def __init__(self, root):
        self.root = root
        self.root.title("TX Digital Simple (BPSK Pasobanda)")

        self.file_path = tk.StringVar()
        self.use_fec = tk.BooleanVar(value=False)
        self.carrier = tk.DoubleVar(value=CARRIER_FREQ)

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

    def select_file(self):
        path = filedialog.askopenfilename()
        if path:
            self.file_path.set(path)

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
            messagebox.showinfo("TX", "WAV generado correctamente.")
        except Exception as e:
            messagebox.showerror("Error WAV", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleTX(root)
    root.mainloop()
