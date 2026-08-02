# Arquitectura y protocolo

## Capas

La aplicación obtiene o presenta el mensaje. Presentación transforma texto UTF-8
o una cadena binaria a bits y usa `original_bits` para retirar padding. Enlace
codifica/verifica CRC-32 o codifica/decodifica SECDED. Ruido actúa después de
enlace sobre todos los bits, incluida la redundancia. Transporte mueve una línea
JSON por archivo, entrada estándar o un flujo TCP con timeout y cierre ordenado.
Los módulos matemáticos no conocen sockets, JSON ni argumentos de consola.

## Trama JSONL versión 1

Cada transmisión es exactamente un objeto JSON terminado por salto de línea:

```json
{"version":1,"algorithm":"hamming","encoding":"text","original_bits":8,"block_data_bits":8,"encoded_bits":"...","noise":{"mode":"none","ber":0,"seed":1,"flipped_positions":[]},"metrics":{"encode_ns":1200}}
```

Campos obligatorios: `version`, `algorithm`, `encoding`, `original_bits` y
`encoded_bits`. `algorithm` es `hamming` o `crc32`; `encoding` es `text` o `bits`.
Los metadatos de ruido son evidencia, no participan en la decisión del receptor.
El receptor impone tipos, valores permitidos, longitudes coherentes y un límite
de 16 MiB. JSON se interpreta como datos; nunca se evalúa ni ejecuta contenido.

## Hamming SECDED

Se usan bloques deterministas de ocho bits (el último se rellena con ceros). Para
un bloque de `m` bits se elige el menor `r` tal que `2^r >= m+r+1`. Las posiciones
Hamming se numeran desde uno: potencias de dos son paridades y las restantes son
datos. Se calcula paridad par y se agrega una paridad global al final.

El síndrome es la suma binaria de las comprobaciones fallidas. Síndrome cero y
paridad global correcta significa ausencia de error; síndrome no cero y paridad
global incorrecta identifica y corrige un bit; síndrome cero y paridad global
incorrecta identifica el bit global; síndrome no cero y paridad global correcta
indica doble error y se rechaza. Tres o más errores están fuera de la garantía.

## CRC-32/ISO-HDLC

Se implementa el desplazamiento reflejado con polinomio `0xEDB88320` (normal
`0x04C11DB7`), `init=0xFFFFFFFF`, entrada/salida reflejada y
`xorout=0xFFFFFFFF`. Los 32 bits del residuo se anexan en orden más significativo
primero. El vector `123456789` produce `0xCBF43926`. CRC detecta alteraciones, no
las corrige; una trama con residuo discordante se descarta.
