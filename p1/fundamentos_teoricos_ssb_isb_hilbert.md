# Fundamentos Teóricos de Modulación SSB/ISB y Transformada de Hilbert

## 1. Modulación de Banda Lateral Única (SSB - Single Sideband)

La modulación SSB es una forma de modulación de amplitud que transmite solo una de las bandas laterales generadas por la modulación de una señal portadora con una señal de mensaje. Esto permite un uso más eficiente del espectro de frecuencia y de la potencia de transmisión en comparación con la modulación de amplitud (AM) de doble banda lateral (DSB).

Existen dos tipos principales de SSB:

*   **SSB con Portadora Suprimida (SSB-SC - Single Sideband-Suppressed Carrier):** En este tipo, la portadora se suprime completamente, lo que maximiza la eficiencia de potencia al transmitir solo la información de la banda lateral. Requiere una demodulación síncrona precisa.
*   **SSB con Portadora Completa (SSB-FC - Single Sideband-Full Carrier):** Aunque el enunciado menciona SSB-FC, es más común referirse a SSB con portadora reducida o vestigial para facilitar la demodulación. La SSB-FC como tal no es una práctica común, ya que contradice el principio de eficiencia espectral y de potencia de la SSB. Asumo que se refiere a una modulación AM estándar o a una SSB con una portadora residual para facilitar la sincronización.

La elección de la banda lateral a transmitir puede ser:

*   **Banda Lateral Superior (USB - Upper Sideband):** Contiene las frecuencias sumadas de la portadora y el mensaje.
*   **Banda Lateral Inferior (LSB - Lower Sideband):** Contiene las frecuencias restadas de la portadora y el mensaje.

## 2. Modulación de Banda Lateral Independiente (ISB - Independent Sideband)

La modulación ISB es una extensión de la SSB donde se transmiten dos señales de mensaje independientes, una en la banda lateral superior y otra en la banda lateral inferior, utilizando la misma portadora (generalmente suprimida). Esto duplica la capacidad de información dentro de un ancho de banda similar al de una señal DSB.

## 3. La Transformada de Hilbert en la Generación de SSB

La transformada de Hilbert es una herramienta matemática fundamental para la generación de señales SSB. La transformada de Hilbert de una señal real $x(t)$, denotada como $\hat{x}(t)$, es una señal que tiene la misma amplitud espectral que $x(t)$ pero con un desfase de $-90^{\circ}$ (o $-\pi/2$ radianes) para todas las componentes de frecuencia positivas y $+90^{\circ}$ (o $+\pi/2$ radianes) para las componentes de frecuencia negativas.

Matemáticamente, la transformada de Hilbert de $x(t)$ se define como:

$\hat{x}(t) = x(t) * \frac{1}{\pi t} = \frac{1}{\pi} \int_{-\infty}^{\infty} \frac{x(\tau)}{t-\tau} d\tau$

La señal analítica $z(t)$ de una señal real $x(t)$ se define como:

$z(t) = x(t) + j\hat{x}(t)$

Esta señal analítica es clave para la generación de SSB. Para generar una señal SSB-SC (USB o LSB) a partir de una señal de mensaje $m(t)$ y una portadora $cos(\omega_c t)$:

*   **SSB-SC (USB):** $s_{USB}(t) = m(t) \cos(\omega_c t) - \hat{m}(t) \sin(\omega_c t)$
*   **SSB-SC (LSB):** $s_{LSB}(t) = m(t) \cos(\omega_c t) + \hat{m}(t) \sin(\omega_c t)$

Donde $\hat{m}(t)$ es la transformada de Hilbert de la señal de mensaje $m(t)$.

Para la generación de ISB, se aplicarían estas fórmulas a dos señales de mensaje independientes, $m_1(t)$ y $m_2(t)$, una para la USB y otra para la LSB.

## 4. Demodulación Síncrona y Efectos de Errores de Fase y Frecuencia

La demodulación síncrona es esencial para recuperar la señal de mensaje de una señal SSB-SC. Implica multiplicar la señal SSB recibida por una portadora local que está perfectamente sincronizada en fase y frecuencia con la portadora original utilizada en la modulación.

Si la portadora local tiene un error de fase $\phi$ y/o un error de frecuencia $\Delta\omega$, la señal demodulada se verá afectada:

*   **Error de Fase ($\phi$):** Si la portadora local es $2 \cos((\omega_c + \Delta\omega)t + \phi)$, un error de fase $\phi$ causará una atenuación de la señal recuperada por un factor de $\cos(\phi)$ y la aparición de una componente en cuadratura (distorsión). Si $\phi = 90^{\circ}$, la señal se anula.

*   **Error de Frecuencia ($\Delta\omega$):** Un error de frecuencia $\Delta\omega$ resultará en un desplazamiento de frecuencia en la señal demodulada, haciendo que la señal de mensaje suene distorsionada o ininteligible. La señal recuperada contendrá componentes de frecuencia que son la suma y diferencia de las frecuencias del mensaje y el error de frecuencia.

La combinación de ambos errores puede degradar severamente la calidad de la señal recuperada, introduciendo distorsión y ruido. La robustez del sistema de demodulación frente a estos errores es un aspecto crítico a evaluar.
