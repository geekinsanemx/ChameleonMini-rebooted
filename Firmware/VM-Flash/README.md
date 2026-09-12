# VM-Flash

Flashing the ChameleonMini **RevE rebooted** (clone, ATxmega32A4U) from a Windows
VM with USB passthrough. This board cannot be flashed from Linux
(dfu-programmer/avrdude give Broken pipe; wine runs the .exe but cannot see the
USB; dosbox does not apply). The VM is required.

## flash-station/ - flashing station (copy once to the VM)

Holds the shared binaries, the compiled variants under `fw/`, and one
`flash_<variant>.bat` per variant. To flash:

1. Enter DFU: unplug the USB, hold the black button, replug.
   (or `python3 ../../Software/Tools/chameleon-cli/chameleon.py --dfu` first)
2. Passthrough 03eb:2fe4 to the VM.
3. Run the .bat for the variant you want, e.g.:
   ```
   flash_classic-detection.bat
   ```
4. Retry until you see `load_success!` (the loop resets the MCU between attempts
   on its own). Unplug and replug in normal mode.

Variants (all fit in 28672 B):

| .bat | contents |
|---|---|
| flash_classic-detection       | Classic (Mini/1K/4K, UID 4/7B) + detection |
| flash_classic-detection-brute | + brute force |
| flash_classic-detection-log   | + logging |
| flash_classic-only            | Classic only (max headroom) |
| flash_classic-ntag            | Classic + NTAG 213/215/216 |
| flash_ultralight-ntag         | Ultralight + NTAG 213/215/216 |
| flash_factory                 | FACTORY firmware (Chameleon-new-1.0) |

`load_success!` is the only real confirmation; the "Enjoy!" line is always printed.

## rescue/ - factory lifeboat (standalone)

Independent, tested copy to get back to factory if everything else fails.
See `rescue/README.txt`. Same result as `flash-station/flash_factory.bat`, but
self-contained in case you prefer a minimal folder.

## Regenerate

Recompile the variants with:
```
python3 ../../Software/Tools/chameleon-cli/build_firmware.py
```
