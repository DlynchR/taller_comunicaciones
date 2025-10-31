#!/usr/bin/env python3
import argparse
import os
import sys
import wave
import pyaudio

def play_audio(filename, chunk=1024):
    with wave.open(filename, 'rb') as wf:
        p = pyaudio.PyAudio()
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        data = wf.readframes(chunk)
        while data:
            stream.write(data)
            data = wf.readframes(chunk)
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce un archivo WAV con PyAudio.")
    parser.add_argument("archivo", help="Ruta al archivo .wav")
    args = parser.parse_args()

    if not os.path.isfile(args.archivo):
        print(f"Archivo no encontrado: {args.archivo}", file=sys.stderr)
        sys.exit(1)

    try:
        play_audio(args.archivo)
    except Exception as e:
        print(f"Error reproduciendo audio: {e}", file=sys.stderr)
        sys.exit(2)