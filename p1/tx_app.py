# tx_simple_fsk.py - simple FSK transmitter GUI
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from digital_passband_modulator_fsk import transmit_file_fsk, FS, FREQ_0, FREQ_1

class SimpleTX:
    def __init__(self, root):
        self.root = root
        self.root.title("TX Simple FSK")
        self.path = tk.StringVar()
        self.f0 = tk.DoubleVar(value=FREQ_0)
        self.f1 = tk.DoubleVar(value=FREQ_1)
        self.fs = FS
        self.create()

    def create(self):
        frame = ttk.Frame(self.root); frame.pack(padx=10, pady=10)
        ttk.Label(frame, text="Archivo:").grid(row=0, column=0)
        ttk.Entry(frame, textvariable=self.path, width=50).grid(row=0, column=1)
        ttk.Button(frame, text="Seleccionar", command=self.select).grid(row=0, column=2)
        ttk.Label(frame, text="f0 (Hz):").grid(row=1, column=0)
        ttk.Entry(frame, textvariable=self.f0).grid(row=1, column=1, sticky="w")
        ttk.Label(frame, text="f1 (Hz):").grid(row=2, column=0)
        ttk.Entry(frame, textvariable=self.f1).grid(row=2, column=1, sticky="w")
        ttk.Button(frame, text="Transmitir", command=self.tx).grid(row=3, column=0, columnspan=3, pady=6)
        ttk.Button(frame, text="Guardar WAV", command=self.savewav).grid(row=4, column=0, columnspan=3)

    def select(self):
        p = filedialog.askopenfilename()
        if p: self.path.set(p)

    def tx(self):
        if not self.path.get():
            messagebox.showerror("Error", "Selecciona archivo")
            return
        try:
            transmit_file_fsk(self.path.get(), f0=float(self.f0.get()), f1=float(self.f1.get()), fs=self.fs, play=True)
            messagebox.showinfo("OK", "Transmitido")
        except Exception as e:
            messagebox.showerror("Error TX", str(e))

    def savewav(self):
        if not self.path.get(): return
        p = filedialog.asksaveasfilename(defaultextension=".wav")
        if not p: return
        transmit_file_fsk(self.path.get(), f0=float(self.f0.get()), f1=float(self.f1.get()), fs=self.fs, play=False, out_wav=p)
        messagebox.showinfo("Saved", "WAV saved")

if __name__ == "__main__":
    root = tk.Tk(); app = SimpleTX(root); root.mainloop()
