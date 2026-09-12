# VM-Flash

Flasheo del ChameleonMini **RevE rebooted** (clon, ATxmega32A4U) desde una VM
Windows con USB passthrough. Desde Linux NO se puede flashear esta placa
(dfu-programmer/avrdude dan Broken pipe; wine ejecuta el .exe pero no ve el USB;
dosbox no aplica). La VM es imprescindible.

## flash-station/ - estacion de flasheo (copiar una vez a la VM)

Contiene los binarios compartidos, las variantes compiladas en `fw/`, y un
`flash_<variante>.bat` por cada una. Para flashear:

1. Entra en DFU: desconecta el USB, manten el boton negro, reconecta.
   (o `python3 ../../Software/Tools/chameleon-cli/chameleon.py dfu` antes)
2. Passthrough del `03eb:2fe4` a la VM.
3. Ejecuta el .bat de la variante que quieras, p.ej.:
   ```
   flash_classic-detection.bat
   ```
4. Reintenta hasta ver `load_success!` (el bucle resetea el MCU solo entre
   intentos). Desconecta y reconecta en modo normal.

Variantes (todas caben en 28672 B):

| .bat | contenido |
|---|---|
| flash_classic-detection      | Classic (Mini/1K/4K, UID 4/7B) + deteccion |
| flash_classic-detection-brute| + fuerza bruta |
| flash_classic-detection-log  | + registro |
| flash_classic-only           | solo Classic (maximo margen) |
| flash_classic-ntag           | Classic + NTAG 213/215/216 |
| flash_ultralight-ntag        | Ultralight + NTAG 213/215/216 |
| flash_factory                | firmware de FABRICA (Chameleon-new-1.0) |

`load_success!` es la unica confirmacion real; el "Enjoy!" se imprime siempre.

## rescue/ - salvavidas a fabrica (autonomo)

Copia independiente y probada para volver a fabrica si todo lo demas falla.
Ver `rescue/LEEME.txt`. Mismo resultado que `flash-station/flash_factory.bat`,
pero autocontenido por si prefieres una carpeta minima.

## Regenerar

Las variantes se recompilan con:
```
python3 ../../Software/Tools/chameleon-cli/build_firmware.py
```
