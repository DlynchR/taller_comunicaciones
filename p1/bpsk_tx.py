
#!/usr/bin/env python3
"""bpsk_tx.py

Standalone acoustic BPSK transmitter script.
Usage (CLI):
  python bpsk_tx.py input_file [--carrier 6000] [--symbol_rate 100] [--play] [--save out.wav]

Steps:
  1. Read input file bytes.
  2. Build frame (preamble + header + payload + CRC32).
  3. Modulate using BPSK with rectangular pulses and cosine carrier.
  4. Optionally play through speakers and/or save WAV.

Supported payload types: any binary file (txt, jpg, ...). Extension stored in header.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np

from bpsk_common import (
	BPSKConfig,
	build_signal_from_file_raw,
	play_audio,
	save_wav,
)


def parse_args():
	p = argparse.ArgumentParser(description="Acoustic BPSK transmitter")
	p.add_argument("input_file", help="File to transmit (txt, jpg, etc.)")
	p.add_argument("--carrier", type=float, default=6000.0, help="Carrier frequency Hz")
	p.add_argument("--symbol_rate", type=int, default=100, help="Symbol rate (sym/s)")
	p.add_argument("--play", action="store_true", help="Play audio signal via default output")
	p.add_argument("--save", metavar="WAV_PATH", help="Save modulated waveform to WAV")
	return p.parse_args()


def main():
	args = parse_args()
	infile = Path(args.input_file)
	if not infile.exists():
		print("Input file not found", file=sys.stderr)
		return 1
	cfg = BPSKConfig(carrier=args.carrier, symbol_rate=args.symbol_rate,
					 samples_per_symbol=int(BPSKConfig.symbol_rate.__get__(cfg:=BPSKConfig()) or (cfg.fs // args.symbol_rate)) if False else int(BPSKConfig().fs // args.symbol_rate))
	# override samples_per_symbol properly:
	cfg.samples_per_symbol = cfg.fs // args.symbol_rate

	sig, meta = build_signal_from_file_raw(str(infile), cfg)
	print(f"Built signal: {meta['bits']} bits, payload {meta['payload_bytes']} bytes")
	duration = len(sig)/cfg.fs
	print(f"Signal duration: {duration:.2f} s at fs={cfg.fs} carrier={cfg.carrier}Hz")

	if args.play:
		print("Playing signal ...")
		play_audio(sig, cfg.fs)
		print("Playback finished.")
	if args.save:
		save_wav(args.save, sig, cfg.fs)
		print(f"Saved WAV: {args.save}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
