# Tarea 1 — Conexión Serial ESP32 ↔ PC

**CC5328-1 Sistemas Embebidos y Sensores · Universidad de Chile · Semestre 2026-2**

Sistema de adquisición y control de datos en tiempo real: un ESP32 emula un acelerómetro
tri-axial y un sensor de temperatura/humedad, y los transmite por UART (USB-serial) a una
aplicación de escritorio en Python/PyQt que grafica las señales y reconfigura el
microcontrolador en vivo.

**Integrantes:** _(nombre 1)_, _(nombre 2)_, _(nombre 3)_

> Enunciado completo: [`docs/Tarea1_CC5328_v2.pdf`](docs/Tarea1_CC5328_v2.pdf).
> Estado del trabajo y decisiones pendientes: [`TODO.md`](TODO.md).

## Estructura del repositorio

```
esp32_firmware/          Firmware ESP-IDF (C)
  CMakeLists.txt         Proyecto idf.py
  sdkconfig.defaults     Configuración base (target esp32, log level, baud del monitor)
  main/
    main.c               app_main: inicializa módulos y arranca la simulación
    app_config.h         Constantes y valores por defecto del enunciado
    protocol.[ch]        Tramas "$payload*XX" + checksum XOR (espejo de gui_python/protocol.py)
    uart_link.[ch]       Driver UART0, envío de tramas, tarea de recepción por líneas
    commands.[ch]        Interpretación de comandos de la GUI (CFG / ENV / INIT)
    accel_sim.[ch]       Acelerómetro sintético: 3 ejes, función/amplitud/fs independientes
    env_sim.[ch]         Temperatura y humedad aleatorias cada 30 s o 60 s
gui_python/              Aplicación PyQt5
  main.py                Punto de entrada
  main_window.py         Ventana principal: conecta paneles, gráficos y puerto serie
  serial_worker.py       Hilo de lectura/escritura serial (pyserial + QThread)
  protocol.py            Tramas y checksum (espejo de protocol.c)
  widgets/               Un archivo por panel: conexión, configuración, gráficos, ambiental
  tests/                 Pruebas unitarias del protocolo (pytest)
  requirements.txt
docs/                    Enunciado y capturas de pantalla
```

## Requisitos

| Componente | Versión |
|---|---|
| Tarjeta | ESP32 (target `esp32`) |
| Framework firmware | ESP-IDF **v6.1** (probado) |
| Python | 3.8+ |
| Librerías GUI | PyQt5, pyserial, pyqtgraph, numpy (ver `gui_python/requirements.txt`) |

## Compilación y carga del firmware

```bash
# 1. Activar ESP-IDF (instalación con el ESP-IDF Installation Manager)
. ~/.espressif/tools/activate_idf_v6.1.sh        # o:  . $IDF_PATH/export.sh

# 2. Compilar
cd esp32_firmware
idf.py build

# 3. Cargar y abrir el monitor serial (Ctrl+] para salir)
idf.py -p /dev/ttyUSB0 flash monitor
```

Notas:

- En Linux el usuario debe pertenecer al grupo `dialout` para abrir `/dev/ttyUSB0`.
- El monitor de `idf.py` y la GUI **no pueden usar el puerto al mismo tiempo**: cerrar el
  monitor antes de conectar desde la aplicación.
- Los cambios permanentes de configuración van en `sdkconfig.defaults` (`sdkconfig` está
  ignorado por git). Para regenerarlo: `rm sdkconfig && idf.py reconfigure`.
- Si se cambia `LINK_BAUD` en `main/app_config.h`, usar `idf.py monitor -b <baud>`.

## Ejecución de la aplicación

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r gui_python/requirements.txt
python gui_python/main.py
```

Pruebas unitarias del protocolo: `pytest gui_python/tests`

## Uso

1. Conectar el ESP32 por USB, elegir el puerto (`/dev/ttyUSB0`, `COMx`) y el baud rate
   (115200 por defecto, debe coincidir con `LINK_BAUD` del firmware) y pulsar **Conectar**.
   Al abrir el puerto la tarjeta se reinicia (señal DTR); las primeras líneas del bootloader
   se descartan automáticamente.
2. Pulsar **Inicializar ESP32**: el firmware vuelve a los valores por defecto del enunciado
   (armónica simple, 4 g, 100 Hz, ambiental cada 30 s) y responde con `ACK`.
3. Cambiar función / amplitud / frecuencia de muestreo de cada eje: el cambio se envía de
   inmediato y se refleja en el gráfico correspondiente.
4. Elegir el periodo del sensor ambiental (30 s / 60 s).

La barra de estado muestra las respuestas del ESP32 y un contador de tramas válidas y
rechazadas (checksum incorrecto o líneas que no son tramas), útil para verificar la
estabilidad del enlace.

## Protocolo de comunicación

> **BORRADOR** — completar y mantener sincronizado con `protocol.c`, `commands.c` y
> `main_window.py` (ver `TODO.md`, ítem P1).

Protocolo de texto, una trama por línea:

```
$<payload>*<XX>\n
```

- `payload`: campos separados por coma; el primero es el tipo de mensaje.
- `XX`: checksum = XOR de todos los bytes del payload, en dos dígitos hexadecimales.
  Ejemplo: `INIT` → `'I'^'N'^'I'^'T'` = `0x1A` → `$INIT*1A`.
- Cualquier línea que no cumpla el formato o cuyo checksum no coincida se descarta y se
  cuenta (mensajes de arranque, `ESP_LOG`, bytes corruptos).

### PC → ESP32 (comandos)

| Comando | Trama | Respuesta |
|---|---|---|
| Configurar eje | `$CFG,<eje>,<func>,<amp>,<fs>*XX` — eje `X`/`Y`/`Z`, func `1..3`, amp `4`/`8`/`16`, fs `50`/`100`/`200`/`500`/`1000` | `$ACK,CFG*XX` o `$ERR,BADARG*XX` |
| Periodo ambiental | `$ENV,<segundos>*XX` — `30` o `60` | `$ACK,ENV*XX` o `$ERR,BADARG*XX` |
| Inicializar | `$INIT*XX` — valores por defecto y (re)inicio del streaming | `$ACK,INIT,<versión>*XX` |

Errores posibles: `BADFRAME` (formato/checksum), `EMPTY`, `UNKNOWN` (tipo desconocido),
`BADARG` (valor fuera de las opciones permitidas), `NOTIMPL` (comando aún no implementado).

### ESP32 → PC (datos)

| Mensaje | Trama | Notas |
|---|---|---|
| Acelerómetro | `$ACC,<eje>,<t0_ms>,<fs>,<v1>,<v2>,…,<vN>*XX` | N muestras consecutivas de un eje (en g), separadas `1/fs` s; `t0_ms` es el instante de `v1` desde el arranque |
| Ambiental | `$ENV,<temp_c>,<hum_pct>*XX` | ej. `$ENV,23.4,31*XX` |

Las muestras se agrupan en tramas de ~10–20 ms por eje para que 3 ejes a 1000 Hz quepan en
el enlace (ver *Decisiones de diseño*).

## Decisiones de diseño

_(completar a medida que se implementa — ver `TODO.md`)_

- **Ancho de banda / baud rate.** _Cuántas muestras por trama, baud elegido y por qué._
- **Muestreo por eje.** Un tick maestro de 1 kHz (`esp_timer`) del que cada eje toma una
  muestra cada `1000/fs` ticks; el tiempo global mantiene la fase continua al cambiar `fs`.
- **Frecuencias de las señales** (`f`, `f1`, `f2`, no fijadas por el enunciado): _valores y
  justificación (Nyquist a fs = 50 Hz)._
- **Fórmula a₃(t).** _Interpretación del factor `2A/2` impreso en el enunciado._
- **Consola compartida.** UART0 transporta datos y logs; los logs no empiezan con `$` y se
  descartan en la GUI.

## Capturas de pantalla

_(agregar en `docs/screenshots/` y enlazar aquí)_

## Solución de problemas

| Síntoma | Causa / solución |
|---|---|
| `Permission denied: /dev/ttyUSB0` | `sudo usermod -aG dialout $USER` y volver a iniciar sesión |
| `Device or resource busy` | Otro programa (p. ej. `idf.py monitor`) tiene el puerto abierto |
| Contador de tramas rechazadas sube al conectar | Normal: salida del bootloader tras el reinicio por DTR |
| Contador de rechazadas sube continuamente | Baud rate distinto entre GUI y firmware, o cable defectuoso |
