#!/usr/bin/env python3
import argparse
import sys
import time
import pyaudio
import numpy as np
import wave

# Valores por defecto
DEFAULT_CHUNK = 1024
DEFAULT_RATE = 44100
DEFAULT_THRESHOLD = 1500
DEFAULT_SECONDS = 5
DEFAULT_CHANNELS = 1
DEFAULT_OUTPUT = "grabacion.wav"
DEFAULT_TONE_FREQ = 0.0      # Hz, 0 = desactivado (usa umbral de amplitud)
DEFAULT_TONE_BW = 50.0       # Hz, semiancho de banda alrededor de la frecuencia
DEFAULT_TONE_RATIO = 0.5     # Proporción de energía en la banda [0-1] para disparo
DEFAULT_STOP_TONE_FREQ = 2000.0   # Hz, tono para detener grabación (0 = desactivado)
DEFAULT_STOP_TONE_BW = 30.0       # Hz
DEFAULT_STOP_TONE_RATIO = 0.5     # proporción de energía para detener

def list_input_devices(p: pyaudio.PyAudio):
    print("Dispositivos de entrada disponibles:")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if int(info.get("maxInputChannels", 0)) > 0:
            name = info.get("name", "desconocido")
            chans = int(info.get("maxInputChannels", 0))
            rate = int(info.get("defaultSampleRate", 0))
            print(f"  {i}: {name} (canales: {chans}, rate por defecto: {rate})")

def listen_and_record(
    output=DEFAULT_OUTPUT,
    rate=DEFAULT_RATE,
    chunk=DEFAULT_CHUNK,
    threshold=DEFAULT_THRESHOLD,
    seconds=DEFAULT_SECONDS,
    channels=DEFAULT_CHANNELS,
    device_index=None,
    timeout=0,
    tone_freq=DEFAULT_TONE_FREQ,
    tone_bw=DEFAULT_TONE_BW,
    tone_ratio=DEFAULT_TONE_RATIO,
    stop_tone_freq=DEFAULT_STOP_TONE_FREQ,
    stop_tone_bw=DEFAULT_STOP_TONE_BW,
    stop_tone_ratio=DEFAULT_STOP_TONE_RATIO
):
    p = pyaudio.PyAudio()
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            frames_per_buffer=chunk,
            input_device_index=device_index
        )
    except Exception as e:
        print(f"No se pudo abrir el dispositivo de audio: {e}", file=sys.stderr)
        p.terminate()
        return 2

    print("Escuchando... (esperando sonido por encima del umbral)")
    frames = []
    t0 = time.monotonic()

    try:
        while True:
            data = stream.read(chunk, exception_on_overflow=False)
            arr = np.frombuffer(data, dtype=np.int16)
            amplitude = float(np.abs(arr).mean())

            trigger = False
            if tone_freq and tone_freq > 0:
                # Detección de tono por energía espectral en una banda alrededor de tone_freq
                x = arr.astype(np.float32)
                w = np.hanning(len(x))
                X = np.fft.rfft(x * w)
                P = np.abs(X) ** 2
                freqs = np.fft.rfftfreq(len(x), d=1.0 / rate)
                mask = np.abs(freqs - tone_freq) <= tone_bw
                band_power = float(P[mask].sum()) if np.any(mask) else 0.0
                total_power = float(P.sum()) + 1e-12
                ratio = band_power / total_power
                trigger = ratio >= tone_ratio
            else:
                # Modo original: umbral de amplitud
                trigger = amplitude > threshold

            if trigger:
                print("¡Sonido/tono detectado! Grabando...")
                max_frames = int(rate / chunk * seconds)
                recorded = 0
                while recorded < max_frames:
                    buf = stream.read(chunk, exception_on_overflow=False)
                    frames.append(buf)
                    recorded += 1

                    # Parada por tono específico (p. ej., ~2 kHz)
                    if stop_tone_freq and stop_tone_freq > 0:
                        arr2 = np.frombuffer(buf, dtype=np.int16).astype(np.float32)
                        w2 = np.hanning(len(arr2))
                        X2 = np.fft.rfft(arr2 * w2)
                        P2 = np.abs(X2) ** 2
                        freqs2 = np.fft.rfftfreq(len(arr2), d=1.0 / rate)
                        mask2 = np.abs(freqs2 - stop_tone_freq) <= stop_tone_bw
                        band_power2 = float(P2[mask2].sum()) if np.any(mask2) else 0.0
                        total_power2 = float(P2.sum()) + 1e-12
                        ratio2 = band_power2 / total_power2
                        if ratio2 >= stop_tone_ratio:
                            print(f"Frecuencia de parada detectada (~{stop_tone_freq} Hz). Deteniendo grabación.")
                            break
                break

            if timeout and (time.monotonic() - t0) >= timeout:
                print("Tiempo de espera agotado sin detectar sonido.")
                break
    except KeyboardInterrupt:
        print("Terminando escucha por interrupción (Ctrl+C).")
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

    if not frames:
        return 3

    try:
        wf = wave.open(output, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))
        wf.close()
    except Exception as e:
        print(f"No se pudo escribir el archivo WAV: {e}", file=sys.stderr)
        return 4

    print(f"Grabación guardada como '{output}'")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Escucha el micrófono y graba cuando el nivel supere un umbral o se detecte un tono.")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help=f"Archivo de salida WAV (por defecto: {DEFAULT_OUTPUT})")
    parser.add_argument("-r", "--rate", type=int, default=DEFAULT_RATE, help=f"Tasa de muestreo (Hz) (por defecto: {DEFAULT_RATE})")
    parser.add_argument("-k", "--chunk", type=int, default=DEFAULT_CHUNK, help=f"Tamaño de bloque (por defecto: {DEFAULT_CHUNK})")
    parser.add_argument("-t", "--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"Umbral de activación (por defecto: {DEFAULT_THRESHOLD})")
    parser.add_argument("-s", "--seconds", type=float, default=DEFAULT_SECONDS, help=f"Segundos a grabar tras detectar sonido (por defecto: {DEFAULT_SECONDS})")
    parser.add_argument("-c", "--channels", type=int, default=DEFAULT_CHANNELS, help=f"Número de canales (por defecto: {DEFAULT_CHANNELS})")
    parser.add_argument("-d", "--device-index", type=int, help="Índice del dispositivo de entrada")
    parser.add_argument("--timeout", type=float, default=0, help="Tiempo máximo de espera en segundos (0 = sin límite)")
    parser.add_argument("--list-devices", action="store_true", help="Listar dispositivos de entrada y salir")
    parser.add_argument("--tone-freq", type=float, default=DEFAULT_TONE_FREQ, help="Frecuencia del tono (Hz) para activar (0 = desactivado)")
    parser.add_argument("--tone-bw", type=float, default=DEFAULT_TONE_BW, help="Semiancho de banda (Hz) alrededor de la frecuencia del tono")
    parser.add_argument("--tone-ratio", type=float, default=DEFAULT_TONE_RATIO, help="Proporción de energía en la banda del tono respecto al total [0-1]")
    parser.add_argument("--stop-tone-freq", type=float, default=DEFAULT_STOP_TONE_FREQ, help="Frecuencia del tono (Hz) que detiene la grabación (0 = desactivado)")
    parser.add_argument("--stop-tone-bw", type=float, default=DEFAULT_STOP_TONE_BW, help="Semiancho de banda (Hz) del tono de parada")
    parser.add_argument("--stop-tone-ratio", type=float, default=DEFAULT_STOP_TONE_RATIO, help="Proporción de energía para detener [0-1]")

    args = parser.parse_args()

    if args.list_devices:
        p = pyaudio.PyAudio()
        try:
            list_input_devices(p)
        finally:
            p.terminate()
        sys.exit(0)

    code = listen_and_record(
        output=args.output,
        rate=args.rate,
        chunk=args.chunk,
        threshold=args.threshold,
        seconds=args.seconds,
        channels=args.channels,
        device_index=args.device_index,
        timeout=args.timeout,
        tone_freq=args.tone_freq,
        tone_bw=args.tone_bw,
        tone_ratio=args.tone_ratio,
        stop_tone_freq=args.stop_tone_freq,
        stop_tone_bw=args.stop_tone_bw,
        stop_tone_ratio=args.stop_tone_ratio
    )
    sys.exit(code)