# Sistema de Comunicación Digital Simplificado

## Archivos Nuevos (Sistema Limpio)

### Módulos de Protocolo:
- **`digital_protocol.py`**: Protocolo simple con header de 32 bits y FEC opcional
- **`digital_simple.py`**: Modulación/demodulación BPSK y manejo de audio

### Aplicaciones GUI:
- **`tx_app_clean.py`**: Transmisor con SSB/ISB + Digital (texto)
- **`rx_app_clean.py`**: Receptor con SSB/ISB + Digital (texto)

## Características del Sistema Digital

### Protocolo Simple:
1. **Tono de inicio (1 kHz, 0.5s)** - Sincroniza el inicio de la transmisión
2. **Header (32 bits)**:
   - Bit 31: Flag FEC (1 = habilitado, 0 = deshabilitado)
   - Bits 30-0: Tamaño del archivo en bytes
3. **Datos modulados en BPSK**:
   - Sin FEC: bits directos
   - Con FEC: cada bit repetido 3 veces (votación por mayoría en RX)
4. **Tono de fin (2 kHz, 0.5s)** - Indica fin de transmisión

### Modulación:
- **BPSK** (Binary Phase Shift Keying)
- Portadora: 8000 Hz (configurable)
- Tasa de baudios: 1000 símbolos/segundo
- Frecuencia de muestreo: 44100 Hz

### FEC (Forward Error Correction):
- **Código de repetición triple**: Cada bit se transmite 3 veces
- **Decodificación**: Votación por mayoría (2 de 3)
- **Overhead**: 3x el tamaño original
- **Capacidad**: Corrige 1 error por cada 3 bits

## Uso

### Transmisor (`tx_app_clean.py`):

```bash
python tx_app_clean.py
```

1. **Sección SSB/ISB**: Sin cambios, funciona igual que antes
2. **Sección Digital**:
   - Seleccionar archivo `.txt` (UTF-8)
   - Marcar/desmarcar "Usar FEC (Repetición x3)"
   - Clic en "📡 Transmitir Archivo"
   - El sistema transmitirá por el parlante con tonos de sincronización

### Receptor (`rx_app_clean.py`):

```bash
python rx_app_clean.py
```

1. **Sección SSB/ISB**: Sin cambios, funciona igual que antes
2. **Sección Digital**:
   - Clic en "📡 Escuchar y Demodular"
   - Elegir dónde guardar el archivo recibido
   - El sistema esperará el tono de inicio (1 kHz)
   - Grabará hasta detectar el tono de fin (2 kHz)
   - Demodulará y decodificará automáticamente
   - Mostrará estadísticas de transmisión

## Ventajas del Nuevo Sistema

### ✅ Simplicidad:
- Sin preámbulos/postámbulos complejos
- Protocolo minimalista (solo 32 bits de header)
- Tonos de sincronización confiables

### ✅ FEC Opcional:
- Activar/desactivar según necesidad
- FEC simple pero efectivo (corrección de 1/3 errores)
- No interfiere cuando no se usa

### ✅ Solo Texto:
- Archivos UTF-8 únicamente
- Preprocesamiento simplificado
- Menor probabilidad de errores de decodificación

### ✅ Mantenimiento del Sistema SSB/ISB:
- Sección analógica completamente intacta
- Funcionalidad SSB/ISB preservada

## Ejemplo de Prueba

1. Ejecutar `rx_app_clean.py` en una computadora
2. Ejecutar `tx_app_clean.py` en otra computadora (o la misma)
3. En TX:
   - Seleccionar `test_message.txt`
   - Activar FEC si se desea
   - Transmitir
4. En RX:
   - Clic en "Escuchar y Demodular"
   - Guardar como `received_message.txt`
   - Verificar contenido

## Parámetros Configurables

En `digital_simple.py`:
```python
FS = 44100              # Frecuencia de muestreo
CARRIER_FREQ = 8000     # Portadora digital
BAUD_RATE = 1000        # Símbolos por segundo
START_TONE_FREQ = 1000  # Tono de inicio
STOP_TONE_FREQ = 2000   # Tono de fin
TONE_DURATION = 0.5     # Duración de tonos
```

## Archivos Obsoletos

Los siguientes archivos ya no son necesarios para el sistema digital nuevo:
- `tx_app.py` (reemplazado por `tx_app_clean.py`)
- `rx_app.py` (reemplazado por `rx_app_clean.py`)
- El sistema de preámbulos/postámbulos en `digital_passband_modulator.py`

**Nota**: Puedes seguir usando `tx_app.py` y `rx_app.py` si prefieres el sistema anterior, pero el nuevo sistema en `*_clean.py` es más simple y confiable.

## Troubleshooting

### "No se detectaron tonos":
- Verificar volumen del parlante/micrófono
- Ajustar umbrales de detección en `digital_simple.py` (función `detect_tone`)

### "Error de decodificación":
- Ruido ambiente excesivo → usar FEC
- Portadora incorrecta → verificar frecuencia en TX y RX
- Distancia excesiva → acercar dispositivos

### "Archivo corrupto":
- Activar FEC en el transmisor
- Reducir ruido ambiente
- Usar cable de audio en lugar de aire

## Próximas Mejoras Posibles

- Agregar CRC32 para verificación de integridad
- Implementar sincronización de símbolo más robusta
- Soporte para archivos binarios (imágenes, etc.)
- Interfaz de progreso durante transmisión
- Visualización de constelación BPSK en tiempo real
