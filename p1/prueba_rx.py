import pyaudio
import numpy as np
import wave

CHUNK = 1024
RATE = 44100
THRESHOLD = 1500  # ajusta según tu micrófono
RECORD_SECONDS = 3

def listen_and_record():
    p = pyaudio.PyAudio()

    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("Escuchando... (esperando sonido fuerte)")

    frames = []

    try:
        while True:
            data = np.frombuffer(stream.read(CHUNK, exception_on_overflow=False), dtype=np.int16)
            amplitude = np.abs(data).mean()

            if amplitude > THRESHOLD:
                print("¡Sonido detectado! Grabando...")
                for _ in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                    frames.append(stream.read(CHUNK))
                break
    except KeyboardInterrupt:
        print("Terminando escucha...")

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open("grabacion.wav", 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    print("Grabación guardada como 'grabacion.wav'")

if _name_ == "_main_":
    listen_and_record()