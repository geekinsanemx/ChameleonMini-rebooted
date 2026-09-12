# chameleon-cli

Tools for the ChameleonMini **RevE rebooted** (Chinese clone, ATxmega32A4U).
They auto-detect whether the firmware uses the `MY` command suffix (factory,
`Chameleon-new-1.0`) or not (iceman's rebooted), so they work with both.

## Requirements

```
pip install -r requirements.txt        # pyserial (+ pycryptodome for createbin)
```
For the physical-reader features (ACR122U): `libnfc-bin`, `mfoc`, `mfcuk` and
`mfkey32` (from proxmark3) on the host. The port is autodetected (`/dev/ttyACM*`);
use `--port` to force it. If a VM has the USB captured, release it first.

## chameleon.py - action-flag CLI

Pick ONE action (a flag) and add modifiers.

### Actions

| Flag | What it does | Requires |
|---|---|---|
| `--info` | version + overview of the 8 slots | |
| `--slots` | list slots (config/uid/memsize) | |
| `--dump` | dump slot(s) to file | `--slot N` \| `--all`, opt. `-o DIR` |
| `--upload` | upload a dump to a slot | `--file F --slot N`, opt. `--type CONF` |
| `--backup` | back up FULL state (config+uid+atqa+sak+data) | `--slot N` \| `--all`, opt. `-o DIR` |
| `--restore` | restore from a backup | `--dir D` (`--slot N` \| `--all`) |
| `--create` | create a tag from scratch | `--slot N`, opt. `--type --uid --atqa --sak --file` |
| `--set-config CONF` | set a slot's configuration | `--slot N` |
| `--set-uid HEX` | set the UID | `--slot N` |
| `--set-atqa HEX` | set the ATQA | `--slot N` |
| `--set-sak HEX` | set the SAK | `--slot N` |
| `--detection` | read detection data and point to mfkey32 | `--slot N`, opt. `-o FILE` |
| `--clone` | read/crack a physical card (ACR122U) and upload | `--slot N`, opt. `--type` |
| `--read-card` | read a physical card (ACR122U) | opt. `-o FILE --keyfile K` |
| `--crack` | recover keys (mfoc, or mfcuk with `--darkside`) | opt. `-o FILE` |
| `--reset` / `--dfu` | reset / enter bootloader mode | |

### Modifiers

`--slot N` `--all` `--file F` `-o/--out PATH` `--dir D` `--type CONF`
`--uid HEX` `--atqa HEX` `--sak HEX` `--darkside` `--keyfile K` `-p/--port P`

### Examples

```
python3 chameleon.py --info
python3 chameleon.py --dump --all -o backup-today
python3 chameleon.py --upload --file ~/card.bin --slot 4
python3 chameleon.py --backup --all -o bk
python3 chameleon.py --restore --all --dir bk
python3 chameleon.py --restore --slot 2 --dir bk
python3 chameleon.py --create --slot 5 --type MF_CLASSIC_1K_7B --uid 04112233445566 --sak 20 --atqa 0044
python3 chameleon.py --set-uid AABBCCDD --slot 0
python3 chameleon.py --clone --slot 6
```

A backup is a directory with `manifest.json` + `slotN.bin`. `--restore` accepts
`--all` (every slot in the backup) or `--slot N` (just one).

## build_firmware.py - compile variants and build the flash-station

```
python3 build_firmware.py                 # all viable variants
python3 build_firmware.py --only classic-detection
```
Only builds those that fit in 28672 B (the BOOT_LOADER_EXE.exe limit). Output in
`Firmware/VM-Flash/flash-station/`.

## chameleon_createbin.py - encrypt firmware for the bootloader

Python 3 port of `crypt_operations.py createbin`. Used by build_firmware.

## Notes

The rebooted firmware has **no reader mode**: `read-card`, `crack` and `clone`
use the host **ACR122U**, not the board. **Detection** mode captures the keys a
REAL reader uses against the board (it does not work with the ACR122U as the
attacker; it needs the target reader).
