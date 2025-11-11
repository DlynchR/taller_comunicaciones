# python3 bpsk_rx.py --record 10 --out /tmp/recibidos
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
	recover_file_from_signal,
)


def parse_args():
	p = argparse.ArgumentParser(description="Acoustic BPSK receiver")
	src = p.add_mutually_exclusive_group(required=True)
	src.add_argument("--record", type=float, metavar="SECS", help="Record microphone for SECS seconds")
	src.add_argument("--wav", help="Decode from existing WAV file path")
	p.add_argument("--carrier", type=float, default=6000.0, help="Carrier frequency Hz")
	p.add_argument("--symbol_rate", type=int, default=100, help="Symbol rate (sym/s)")
	p.add_argument("--out", required=True, help="Output directory for recovered file")
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

	print("Demodulating...")
	frame, err = recover_file_from_signal(rx_sig, cfg)
	if frame is None:
		print(f"Decoding error: {err}", file=sys.stderr)
		return 2
	outdir = Path(args.out)
	outdir.mkdir(parents=True, exist_ok=True)
	outname = outdir / f"received.{frame['extension']}"
	with open(outname, 'wb') as f:
		f.write(frame['payload'])
	print(f"Recovered file saved: {outname} ({len(frame['payload'])} bytes)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
