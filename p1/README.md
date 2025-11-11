## BPSK Acoustic File Transfer (Standalone Scripts)

This project now includes two self‑contained scripts for sending files wirelessly (speaker → microphone) using simple BPSK modulation:

Files:
* `bpsk_common.py` – shared utilities (framing, modulation/demodulation, audio I/O)
* `bpsk_tx.py` – transmitter CLI
* `bpsk_rx.py` – receiver CLI

### Frame Structure
```
PREAMBLE (32 bits = 0xA5A55A5A)
LENGTH   (16 bits, payload bytes, little‑endian)
EXT_LEN  (8 bits, ASCII extension length)
EXT      (EXT_LEN * 8 bits)
PAYLOAD  (LENGTH bytes)
CRC32    (32 bits little‑endian of PAYLOAD)
```

### Default Physical Parameters
* Sample rate: 44100 Hz
* Carrier: 6000 Hz (adjustable)
* Symbol rate: 100 sym/s (adjustable) → 441 samples/symbol (rectangular pulse)
* BPSK mapping: bit 0 → −1, bit 1 → +1

### Transmitter Usage
Play over speakers or save to WAV.
```
python bpsk_tx.py path/to/file.txt --play
python bpsk_tx.py image.jpg --carrier 5500 --symbol_rate 150 --save bpsk_image.wav
```

Options:
* `--carrier` – carrier frequency Hz (keep < 15 kHz for most speakers)
* `--symbol_rate` – lower for reliability, higher for speed
* `--play` – play immediately through system audio
* `--save` – save generated waveform

### Receiver Usage
Record live or decode from WAV.
```
python bpsk_rx.py --record 8 --out received_dir
python bpsk_rx.py --wav bpsk_image.wav --out received_dir
```

The recovered file will be saved as `received.<ext>` inside the output directory.

### Tips for Reliable Transfer
* Keep transmitter and receiver devices stationary ~20–40 cm apart.
* Reduce background noise and echoes.
* Avoid clipping: adjust system volume so waveform peak stays clean.
* If decoding fails (preamble not found), lower symbol rate or carrier.
* Try different carriers (5–9 kHz) depending on speaker/mic frequency response.

### Known Limitations / Future Ideas
* No forward error correction (consider simple parity or Reed–Solomon).
* No adaptive gain control.
* Single framing per transmission (no streaming of multiple frames).
* Simple rectangular pulse shaping (could use raised cosine to reduce bandwidth).

### Safety
Carrier and symbol rates chosen to stay in audible range but not uncomfortable. Avoid very high volumes.

### License
Internal educational use.

# Proyecto 1 - Taller de comunicacion 