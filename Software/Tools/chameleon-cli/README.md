# chameleon-cli

Herramientas para ChameleonMini **RevE rebooted** (clon chino, ATxmega32A4U).
Detectan automaticamente si el firmware usa comandos con sufijo `MY` (fabrica,
`Chameleon-new-1.0`) o sin el (rebooted de iceman), asi que sirven con ambos.

## Requisitos

```
pip install -r requirements.txt        # pyserial (+ pycryptodome para createbin)
```
Para funciones con lector fisico (ACR122U): `libnfc-bin`, `mfoc`, `mfcuk` y
`mfkey32` (de proxmark3) en el host. El puerto se autodetecta (`/dev/ttyACM*`);
usa `--port` para forzarlo. Si una VM tiene el USB capturado, sueltala.

## chameleon.py - CLI por flags de accion

Se elige UNA accion (flag) y se acompana de modificadores.

### Acciones

| Flag | Que hace | Requiere |
|---|---|---|
| `--info` | version + resumen de los 8 slots | |
| `--slots` | lista slots (config/uid/memsize) | |
| `--dump` | vuelca slot(s) a fichero | `--slot N` \| `--all`, opc. `-o DIR` |
| `--upload` | sube un volcado a un slot | `--file F --slot N`, opc. `--type CONF` |
| `--backup` | respalda estado COMPLETO (config+uid+atqa+sak+datos) | `--slot N` \| `--all`, opc. `-o DIR` |
| `--restore` | restaura desde un backup | `--dir D` (`--slot N` \| `--all`) |
| `--create` | crea un tag desde cero | `--slot N`, opc. `--type --uid --atqa --sak --file` |
| `--set-config CONF` | fija la config de un slot | `--slot N` |
| `--set-uid HEX` | fija el UID | `--slot N` |
| `--set-atqa HEX` | fija el ATQA | `--slot N` |
| `--set-sak HEX` | fija el SAK | `--slot N` |
| `--detection` | lee datos de deteccion y apunta a mfkey32 | `--slot N`, opc. `-o FILE` |
| `--clone` | lee/crackea una tarjeta fisica (ACR122U) y la sube | `--slot N`, opc. `--type` |
| `--read-card` | lee una tarjeta fisica (ACR122U) | opc. `-o FILE --keyfile K` |
| `--crack` | recupera claves (mfoc, o mfcuk con `--darkside`) | opc. `-o FILE` |
| `--reset` / `--dfu` | reinicia / entra en modo bootloader | |

### Modificadores

`--slot N` `--all` `--file F` `-o/--out PATH` `--dir D` `--type CONF`
`--uid HEX` `--atqa HEX` `--sak HEX` `--darkside` `--keyfile K` `-p/--port P`

### Ejemplos

```
python3 chameleon.py --info
python3 chameleon.py --dump --all -o backup-hoy
python3 chameleon.py --upload --file ~/Documents/tarjeta.bin --slot 4
python3 chameleon.py --backup --all -o bk
python3 chameleon.py --restore --all --dir bk
python3 chameleon.py --restore --slot 2 --dir bk
python3 chameleon.py --create --slot 5 --type MF_CLASSIC_1K_7B --uid 04112233445566 --sak 20 --atqa 0044
python3 chameleon.py --set-uid AABBCCDD --slot 0
python3 chameleon.py --clone --slot 6
```

Un backup es un directorio con `manifest.json` + `slotN.bin`. `--restore` acepta
`--all` (todos los slots del backup) o `--slot N` (solo uno).

## build_firmware.py - compila variantes y arma la flash-station

```
python3 build_firmware.py                 # todas las variantes viables
python3 build_firmware.py --only classic-detection
```
Solo compila las que caben en 28672 B (limite de BOOT_LOADER_EXE.exe). Resultado
en `Firmware/VM-Flash/flash-station/`.

## chameleon_createbin.py - cifra firmware para el bootloader

Port a Python 3 del `crypt_operations.py createbin`. Lo usa build_firmware.

## Notas

El firmware rebooted **no tiene modo lector**: `read-card`, `crack` y `clone`
usan el **ACR122U** del host, no la placa. El modo **deteccion** captura las
claves que usa un LECTOR REAL contra la placa (no funciona con el ACR122U como
atacante; necesita el lector objetivo).
