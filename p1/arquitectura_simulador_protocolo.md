# Arquitectura del Simulador y Protocolo de Transmisión Digital

## 1. Arquitectura General del Simulador

El simulador se dividirá en dos módulos principales: **Modulación/Demodulación SSB/ISB** y **Transmisión Digital Pasobanda**. Ambos módulos compartirán una interfaz gráfica de usuario (GUI) común para la interacción con el usuario y la visualización de resultados.

```mermaid
graph TD
    A[Interfaz de Usuario (GUI)] --> B{Módulo SSB/ISB}
    A --> C{Módulo Transmisión Digital}
    B --> D[Procesamiento de Audio (WAV)]
    B --> E[Generación/Demodulación SSB/ISB]
    B --> F[Análisis Espectral y Temporal]
    B --> G[Reproducción de Audio]
    C --> H[Procesamiento de Archivo Digital]
    C --> I[Modulación/Demodulación Pasobanda]
    C --> J[Análisis de Rendimiento (BER, Diagrama de Ojo)]
    C --> K[Transmisión/Recepción por Audio (Parlante/Micrófono)]
    D --> E
    E --> F
    E --> G
    H --> I
    I --> J
    I --> K
```

## 2. Módulo de Modulación/Demodulación SSB/ISB

Este módulo se encargará de procesar archivos de audio WAV para modularlos y demodularlos utilizando técnicas SSB e ISB basadas en la transformada de Hilbert. Permitirá la introducción de errores de fase y frecuencia para evaluar su impacto.

### 2.1. Componentes Clave:

*   **Carga de Audio:** Lectura de archivos WAV. Soporte para uno o dos archivos (para ISB).
*   **Transformada de Hilbert:** Implementación de la transformada de Hilbert para generar la señal en cuadratura ($\hat{m}(t)$).
*   **Modulador SSB/ISB:** Generación de señales SSB-SC (USB/LSB) e ISB utilizando la señal de mensaje y su transformada de Hilbert, junto con la portadora.
    *   **SSB-SC (USB):** $s_{USB}(t) = m(t) \cos(\omega_c t) - \hat{m}(t) \sin(\omega_c t)$
    *   **SSB-SC (LSB):** $s_{LSB}(t) = m(t) \cos(\omega_c t) + \hat{m}(t) \sin(\omega_c t)$
    *   **ISB:** Combinación de dos señales SSB-SC (una USB y otra LSB) con mensajes independientes.
*   **Demodulador Síncrono:** Multiplicación de la señal recibida por una portadora local. Se incluirán parámetros para simular errores de fase y frecuencia en esta portadora local.
    *   Portadora local: $2 \cos((\omega_c + \Delta\omega)t + \phi)$
*   **Filtro Pasa-Bajos:** Para extraer la señal de mensaje demodulada.
*   **Análisis y Visualización:** Cálculo y graficación de espectros (FFT) y formas de onda en el dominio del tiempo para la señal de mensaje original, DSB (para comparación), SSB/ISB modulada y mensaje recuperado.
*   **Reproducción:** Guardar y reproducir el audio recuperado.

### 2.2. Flujo de Datos (SSB/ISB):

1.  **Entrada del Usuario:** Archivo WAV (1 o 2), Frecuencia de Portadora, Tipo de Modulación (SSB-SC, ISB), Banda Lateral (USB/LSB), Error de Fase, Error de Frecuencia.
2.  **Pre-procesamiento:** Lectura del archivo WAV, normalización de la señal de audio.
3.  **Generación de Transformada de Hilbert:** Aplicación de la transformada de Hilbert a la señal(es) de mensaje.
4.  **Modulación:** Generación de la señal SSB o ISB según los parámetros seleccionados.
5.  **Simulación de Canal (Opcional/Implícito):** Para la demodulación, la señal modulada se pasa directamente al demodulador, donde se aplican los errores de fase y frecuencia.
6.  **Demodulación:** Recuperación de la señal de mensaje utilizando la portadora local con errores.
7.  **Post-procesamiento:** Filtrado pasa-bajos, normalización.
8.  **Salida:** Gráficas (tiempo y frecuencia), archivo WAV del audio recuperado, reproducción de audio.

## 3. Módulo de Transmisión Digital Pasobanda

Este módulo permitirá el envío de cualquier archivo digital a través de un canal de audio (parlante/micrófono) utilizando una modulación pasobanda y un protocolo de comunicación diseñado para este fin.

### 3.1. Componentes Clave:

*   **Carga de Archivo Digital:** Lectura de cualquier tipo de archivo (texto, imagen, binario, etc.).
*   **Codificación de Fuente:** Conversión del archivo binario a una secuencia de símbolos (bits o grupos de bits).
*   **Codificación de Canal (Corrección de Errores):** Implementación opcional de un algoritmo de corrección de errores (FEC) (ej. Hamming, Reed-Solomon, convolucional). Esto aumentará la robustez pero reducirá la tasa de datos efectiva.
*   **Mapeo de Símbolos:** Conversión de los símbolos codificados a puntos en una constelación (ej. BPSK, QPSK, 8-PSK, 16-QAM).
*   **Modulación Pasobanda:** Generación de la señal analógica modulada (ej. PSK, QAM) para su transmisión a través del parlante. Esto implica el uso de una portadora de audio y el filtrado de conformación de pulso (ej. Raised Cosine).
*   **Transmisión por Audio:** Utilización de bibliotecas de audio (ej. `PyAudio` en Python) para enviar la señal modulada al parlante.
*   **Recepción por Audio:** Captura de audio desde el micrófono.
*   **Sincronización:** Implementación de algoritmos de sincronización de tiempo y frecuencia para la señal recibida.
*   **Demodulación Pasobanda:** Recuperación de los símbolos a partir de la señal analógica recibida.
*   **Demapeo de Símbolos:** Conversión de los puntos de la constelación a símbolos binarios.
*   **Decodificación de Canal:** Aplicación del algoritmo de corrección de errores inverso (si se usó).
*   **Decodificación de Fuente:** Reconstrucción del archivo digital original.
*   **Análisis de Rendimiento:** Cálculo de la Tasa de Error de Bit (BER), generación de diagramas de ojo y visualización de la constelación recibida.

### 3.2. Protocolo de Transmisión Digital (Propuesta)

El protocolo debe asegurar la transmisión confiable de datos a través de un canal de audio ruidoso y con posibles variaciones. Se propone un protocolo basado en tramas (frames) con las siguientes características:

*   **Preámbulo:** Una secuencia conocida de símbolos para facilitar la sincronización de tiempo y frecuencia al inicio de cada transmisión. Podría ser una secuencia de Barker o una secuencia pseudoaleatoria (PN).
*   **Cabecera (Header):** Contendrá información sobre la transmisión:
    *   **Longitud del Archivo:** Número de bytes del archivo original.
    *   **Tipo de Archivo:** Extensión del archivo (ej. `.txt`, `.jpg`).
    *   **Algoritmo FEC:** Indicador de si se usó corrección de errores y cuál.
    *   **Tipo de Modulación:** Indicador de la modulación pasobanda utilizada.
    *   **Checksum/CRC:** Para verificar la integridad de la cabecera.
*   **Carga Útil (Payload):** Los datos del archivo codificados y modulados.
*   **Postámbulo/CRC de Datos:** Un CRC al final de la carga útil para verificar la integridad de los datos.

```mermaid
graph LR
    A[Archivo Digital] --> B[Codificación de Fuente]
    B --> C[Codificación de Canal (FEC)]
    C --> D[Mapeo de Símbolos]
    D --> E[Modulación Pasobanda]
    E --> F[Transmisión (Parlante)]
    F --> G[Canal Acústico]
    G --> H[Recepción (Micrófono)]
    H --> I[Sincronización]
    I --> J[Demodulación Pasobanda]
    J --> K[Demapeo de Símbolos]
    K --> L[Decodificación de Canal (FEC)]
    L --> M[Decodificación de Fuente]
    M --> N[Archivo Recuperado]

    subgraph Protocolo de Trama
        O[Preámbulo] --> P[Cabecera] --> Q[Carga Útil] --> R[CRC de Datos]
    end

    E --> O
    R --> H
```

### 3.3. Consideraciones para el Canal Acústico (Parlante/Micrófono):

*   **Rango de Frecuencias:** Las frecuencias de portadora para la modulación pasobanda deben estar dentro del rango audible y reproducible por los parlantes y micrófonos de PC (típicamente 20 Hz - 20 kHz). Se recomienda trabajar en el rango de 1 kHz a 10 kHz para evitar ruidos de baja frecuencia y atenuación de alta frecuencia.
*   **Nivel de Señal:** La señal transmitida debe tener un nivel adecuado para ser detectada por el micrófono sin saturarlo.
*   **Ruido:** El entorno acústico es propenso a ruido, lo que justifica el uso de FEC y un diseño robusto de sincronización.
*   **Eco/Reverberación:** El protocolo debe ser robusto a posibles ecos y reverberaciones en el entorno.

## 4. Interfaz Gráfica de Usuario (GUI)

La GUI se desarrollará utilizando una biblioteca como `Tkinter` o `PyQt` en Python. Deberá ser amigable y permitir al usuario:

*   Seleccionar archivos WAV y cualquier archivo digital.
*   Introducir parámetros para SSB/ISB (frecuencia de portadora, tipo, banda lateral, errores de fase/frecuencia).
*   Seleccionar opciones para la transmisión digital (FEC, tipo de modulación).
*   Iniciar los procesos de modulación/demodulación y transmisión/recepción.
*   Visualizar las gráficas generadas (tiempo, frecuencia, constelación, BER, diagrama de ojo).
*   Reproducir el audio recuperado.
*   Mostrar mensajes de estado y resultados.

## 5. Herramientas de Programación

*   **Lenguaje:** Python 3.x
*   **Bibliotecas:**
    *   `numpy`: Para operaciones numéricas y procesamiento de señales.
    *   `scipy`: Para funciones de procesamiento de señales (ej. transformada de Hilbert, filtros).
    *   `matplotlib`: Para graficación.
    *   `soundfile` o `scipy.io.wavfile`: Para lectura/escritura de archivos WAV.
    *   `PyAudio`: Para transmisión y recepción de audio en tiempo real.
    *   `Tkinter` o `PyQt`: Para la interfaz gráfica de usuario.
    *   `commpy` (opcional): Para funciones de comunicación digital (modulaciones, codificación).

Este diseño proporciona una base sólida para la implementación del simulador, abordando los requisitos principales del proyecto.
