# rx_app_fsk.py - simple FSK receiver GUI
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
import matplotlib.pyplot as plt
from digital_passband_modulator_fsk import record_audio_with_tone_trigger, receive_and_demodulate_fsk, bits_to_bytes, bits_to_bytes as _b2b, bits_to_bytes, bits_to_file, calculate_ber, FS

# bits_to_file is not exported, create local helper
def bits_to_file_local(bits, path):
    from digital_passband_modulator_fsk import bits_to_bytes
    with open(path, "wb") as f:
        f.write(bits_to_bytes(bits))

class RXApp:
    def __init__(self, root):
        self.root = root; self.root.title("RX Simple FSK")
        self.save_folder = tk.StringVar()
        self.orig_file = tk.StringVar()
        self.last_bits = None
        self.create()

    def create(self):
        frame = ttk.Frame(self.root); frame.pack(padx=10, pady=10)
        ttk.Label(frame, text="Carpeta guardar:").grid(row=0, column=0)
        ttk.Entry(frame, textvariable=self.save_folder, width=40).grid(row=0, column=1)
        ttk.Button(frame, text="Seleccionar", command=self.sel_folder).grid(row=0, column=2)
        ttk.Label(frame, text="Archivo original (opcional para BER):").grid(row=1, column=0)
        ttk.Entry(frame, textvariable=self.orig_file, width=40).grid(row=1, column=1)
        ttk.Button(frame, text="Seleccionar", command=self.sel_orig).grid(row=1, column=2)
        ttk.Button(frame, text="Escuchar y recibir", command=self.listen).grid(row=2, column=0, columnspan=3, pady=6)
        ttk.Button(frame, text="Guardar recuperado", command=self.save_rec).grid(row=3, column=0, columnspan=3)
        ttk.Button(frame, text="Mostrar bits (primero 200)", command=self.show_bits).grid(row=4, column=0, columnspan=3)

    def sel_folder(self):
        p = filedialog.askdirectory()
        if p: self.save_folder.set(p)

    def sel_orig(self):
        p = filedialog.askopenfilename()
        if p: self.orig_file.set(p)

    def listen(self):
        rec = record_audio_with_tone_trigger(FS)
        if rec is None:
            messagebox.showwarning("RX", "No se grabó señal")
            return
        bits, raw = receive_and_demodulate_fsk(rec, fs=FS)
        self.last_bits = bits
        # try decode frame
        from digital_passband_modulator_fsk import decode_frame
        payload, size = decode_frame(bits)
        if payload is None:
            messagebox.showwarning("RX", "No se pudo decodificar la trama (CRC/preamble)")
        else:
            messagebox.showinfo("RX", f"Trama recuperada, tamaño {size} bytes. Guardala con 'Guardar recuperado'")

    def save_rec(self):
        if self.last_bits is None:
            messagebox.showwarning("Save", "No hay bits recibidos")
            return
        from digital_passband_modulator_fsk import decode_frame, bits_to_bytes
        payload, size = decode_frame(self.last_bits)
        if payload is None:
            messagebox.showwarning("Save", "No se pudo recuperar trama")
            return
        fname = filedialog.asksaveasfilename(defaultextension=".bin")
        if not fname: return
        with open(fname, "wb") as f:
            f.write(bits_to_bytes(payload))
        messagebox.showinfo("Saved", f"Guardado {fname}")
        # BER if orig provided
        if self.orig_file.get():
            with open(self.orig_file.get(),"rb") as fo:
                ob = fo.read()
            ob_bits = []
            for b in ob:
                for i in range(8):
                    ob_bits.append((b>>(7-i))&1)
            from digital_passband_modulator_fsk import calculate_ber
            ber = calculate_ber(ob_bits, payload)
            messagebox.showinfo("BER", f"BER approx: {ber:.6f}")

    def show_bits(self):
        if self.last_bits is None:
            messagebox.showwarning("Bits", "No hay bits")
            return
        print(self.last_bits[:200])
        messagebox.showinfo("Bits", "Mostré primeros 200 bits en consola")

if __name__ == "__main__":
    root = tk.Tk(); app = RXApp(root); root.mainloop()
