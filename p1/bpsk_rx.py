# python3 bpsk_rx.py --record 12 --carrier 6500 --out .
#!/usr/bin/env python3
"""bpsk_rx.py

Standalone acoustic BPSK receiver script.
Usage:
  python bpsk_rx.py (--record DURATION | --wav in.wav) [--carrier 6000] [--symbol_rate 100] --out output_dir

Flow:
  1. Acquire audio (record microphone or load WAV).
  2. Demodulate BPSK baseband coherently.
  3. Extract bits at symbol centers.
  4. Parse frame (preamble, header, payload, CRC32).
  5. Write recovered file with original extension in output directory.

Notes:
  - Simple amplitude/noise resilience; no AGC or FEC.
  - Ensure quiet environment; speaker-mic path latency doesn't affect recovery.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np

from bpsk_common import (
	BPSKConfig,
	load_wav,
	record_audio,
	recover_bytes_from_signal_no_preamble,
)


def parse_args():
	p = argparse.ArgumentParser(description="Acoustic BPSK receiver")
	src = p.add_mutually_exclusive_group(required=True)
	src.add_argument("--record", type=float, metavar="SECS", help="Record microphone for SECS seconds")
	src.add_argument("--wav", help="Decode from existing WAV file path")
	p.add_argument("--carrier", type=float, default=6000.0, help="Carrier frequency Hz")
	p.add_argument("--symbol_rate", type=int, default=100, help="Symbol rate (sym/s)")
	p.add_argument("--out", required=True, help="Output directory for recovered file")
	p.add_argument("--ext", help="Force output extension (e.g., txt, jpg). If omitted, guessed.")
	p.add_argument("--invert", action="store_true", help="Force polarity inversion if needed.")
	return p.parse_args()


def main():
	args = parse_args()
	cfg = BPSKConfig(carrier=args.carrier, symbol_rate=args.symbol_rate,
					 samples_per_symbol=int(BPSKConfig().fs // args.symbol_rate))
	cfg.samples_per_symbol = cfg.fs // args.symbol_rate

	if args.record:
		print(f"Recording {args.record:.2f} s at fs={cfg.fs}...")
		rx_sig = record_audio(args.record, cfg.fs)
	else:
		wav_path = Path(args.wav)
		if not wav_path.exists():
			print("WAV file not found", file=sys.stderr)
			return 1
		rx_sig, _ = load_wav(str(wav_path), target_fs=cfg.fs)
	if len(rx_sig) < cfg.samples_per_symbol*10:
		print("Signal too short", file=sys.stderr)
		return 1

	print("Demodulating (no preamble)...")
	frame, err = recover_bytes_from_signal_no_preamble(rx_sig, cfg, force_invert=args.invert)
	if frame is None:
		print(f"Decoding error: {err}", file=sys.stderr)
		return 2
	outdir = Path(args.out)
	outdir.mkdir(parents=True, exist_ok=True)
	ext = args.ext if args.ext else frame['extension']
	outname = outdir / f"received.{ext}"
	payload = frame['payload']
	with open(outname, 'wb') as f:
		f.write(payload)
	print(f"Recovered file saved: {outname} ({len(payload)} bytes)")

	# If it's text (by ext or forced), print decoded message to console
	if (args.ext and args.ext.lower() == 'txt') or ext.lower() == 'txt':
		try:
			# Try utf-8 first, fallback to latin-1 to avoid decode errors
			try:
				text = payload.decode('utf-8')
			except UnicodeDecodeError:
				text = payload.decode('latin-1', errors='replace')
			print("\n===== Mensaje recibido (texto) =====\n")
			# Avoid flooding terminal if very large
			if len(text) <= 10000:
				print(text)
			else:
				print(text[:5000])
				print("\n... [truncado] ...\n")
				print(text[-5000:])
			print("\n===== Fin del mensaje =====\n")
		except Exception as e:
			print(f"Warning: no se pudo mostrar el texto: {e}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
