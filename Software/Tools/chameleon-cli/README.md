# chameleon-cli

Herramientas para ChameleonMini **RevE rebooted** (clon chino, ATxmega32A4U).
Detectan automaticamente si el firmware usa comandos con sufijo `MY` (fabrica,
`Chameleon-new-1.0`) o sin el (rebooted de iceman), asi que sirven con ambos.

## Requisitos

```
pip install -r requirements.txt        # pyserial (+ pycryptodome para createbin)
```
Para las funciones con lector fisico (ACR122U): `libnfc-bin`, `mfoc`, `mfcuk`
y `mfkey32` (de proxmark3) en el host.

El puerto se autodetecta (`/dev/ttyACM*`); usa `-p` para forzarlo. Si una VM
tiene el USB capturado, sueltala antes.

## chameleon.py - CLI todo-en-uno

| Comando | Que hace |
|---|---|
| `info` | version del firmware + resumen de los 8 slots |
| `slots` | lista slots (config/uid/memsize) |
| `config SLOT CONF` | fija la configuracion de un slot (p.ej. `MF_CLASSIC_1K_7B`) |
| `setuid SLOT HEX` | fija el UID |
| `atqa SLOT HEX` / `sak SLOT HEX` | fija ATQA / SAK (solo rebooted) |
| `create SLOT --config .. --uid .. --atqa .. --sak .. --data f.bin` | crea un tag desde cero |
| `dump --slot N \| --all [-o DIR]` | vuelca slot(s) a fichero |
| `upload FILE SLOT [-c CONF]` | sube un volcado a un slot |
| `read-card [-o f.mfd] [-k keys]` | lee una tarjeta fisica con el ACR122U |
| `crack [-o f.mfd] [--darkside]` | recupera claves (mfoc, o mfcuk con --darkside) |
| `clone SLOT` | lee/crackea una tarjeta fisica y la sube a un slot |
| `detection SLOT [-o f.bin]` | lee datos de deteccion y apunta a mfkey32 |
| `reset` / `dfu` | reinicia / entra en modo bootloader |

Ejemplos:
```
python3 chameleon.py info
python3 chameleon.py create 4 --config MF_CLASSIC_1K_7B --uid 04112233445566 --sak 20 --atqa 0044
python3 chameleon.py clone 5
python3 chameleon.py dump --all -o backup-hoy
```

## chameleon_backup.py - backup / restore de slots

Guarda el ESTADO COMPLETO (config, UID, ATQA, SAK, datos), no solo los bytes.
```
python3 chameleon_backup.py backup  --all      [-o DIR]
python3 chameleon_backup.py backup  --slot N   [-o DIR]
python3 chameleon_backup.py restore --all  DIR
python3 chameleon_backup.py restore --slot N DIR
```
El backup es un directorio con `manifest.json` + `slotN.bin`.

## build_firmware.py - compila variantes y arma la flash-station

```
python3 build_firmware.py            # compila todas las variantes viables
python3 build_firmware.py --only classic-detection
```
Solo compila variantes que caben en 28672 B (limite de BOOT_LOADER_EXE.exe).
Resultado en `Firmware/VM-Flash/flash-station/`.

## chameleon_createbin.py - cifra firmware para el bootloader

Portado a Python 3 del `crypt_operations.py createbin` del repo. Lo usa
build_firmware; rara vez se llama a mano.

## Nota sobre el clonado y la deteccion

El firmware rebooted **no tiene modo lector**: no lee tarjetas fisicas. Por eso
`read-card`, `crack` y `clone` usan el **ACR122U** del host, no la placa. El
modo **deteccion** captura las claves que usa un LECTOR REAL contra la placa
(no funciona con el ACR122U como atacante; necesita el lector objetivo).
