#!/usr/bin/env python3
"""
chameleon_createbin.py - Genera los .bin cifrados que espera BOOT_LOADER_EXE.exe
del bootloader bloqueado de ChameleonMini RevE rebooted.

Equivalente a Createbin.exe (Windows) y a la operacion 'createbin' de
Software/Tools/crypt_operations.py, que no funciona bajo Python 3.

Formato: relleno a multiplo de 16 con ceros, 16 bytes 0xCD al final, y por cada
bloque de 16 bytes un XOR incremental (0x2D + offset) seguido de descifrado AES.

CHANGELOG
  1.0.0 - Version inicial, portada a Python 3 / pycryptodome.
"""

import argparse
import subprocess
import sys

from Crypto.Cipher import AES

CURRENT_VERSION = "1.0.0"

AES_KEY = b"designed by dxls"
BLOCK = 16
SCRAMBLE_SEED = 0x2D
TRAILER_BYTE = 0xCD


def createbin(data):
    if len(data) % BLOCK != 0:
        data += b"\0" * (BLOCK - len(data) % BLOCK)
    data += bytes([TRAILER_BYTE]) * BLOCK

    out = bytearray()
    for offset in range(0, len(data), BLOCK):
        block = data[offset:offset + BLOCK]
        scrambled = bytes((block[j] ^ ((SCRAMBLE_SEED + offset + j) & 0xFF)) for j in range(BLOCK))
        cipher = AES.new(AES_KEY, AES.MODE_CBC, bytes(BLOCK))
        out += cipher.decrypt(scrambled)
    return bytes(out)


def ihex_to_bin(path):
    return subprocess.run(
        ["avr-objcopy", "-I", "ihex", path, "-O", "binary", "/dev/stdout"],
        check=True, stdout=subprocess.PIPE).stdout


def main():
    parser = argparse.ArgumentParser(description="Cifra firmware para el bootloader RevE rebooted")
    parser.add_argument("input", help="fichero .hex (ihex) o .bin (binario plano)")
    parser.add_argument("output", help="fichero .bin cifrado de salida")
    parser.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)
    args = parser.parse_args()

    raw = ihex_to_bin(args.input) if args.input.lower().endswith((".hex", ".eep")) else open(args.input, "rb").read()
    encoded = createbin(raw)
    with open(args.output, "wb") as handle:
        handle.write(encoded)
    print(f"{args.input}: {len(raw)} B -> {args.output}: {len(encoded)} B")


if __name__ == "__main__":
    main()
