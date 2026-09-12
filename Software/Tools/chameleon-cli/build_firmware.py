#!/usr/bin/env python3
"""
build_firmware.py - Compila las variantes viables del firmware ChameleonMini
RevE rebooted y prepara la 'flash-station' para grabarlas desde la VM Windows.

Cada variante debe caber en 28672 B (0x7000): el limite de BOOT_LOADER_EXE.exe,
que no acepta --suppress-bootloader-mem.

Uso:
    build_firmware.py [--fw-dir DIR] [--station DIR] [--only NOMBRE ...]

Genera, por cada variante que compila y cabe:
    <station>/fw/<nombre>.hex , <nombre>.eep
    <station>/flash_<nombre>.bat

CHANGELOG
  1.0.0 - Version inicial.
"""

import argparse
import os
import shutil
import subprocess
import sys

CURRENT_VERSION = "1.0.0"

FLASH_CEILING = 28672  # 0x7000

# Ajustes comunes a todas las variantes (equivalentes al Makefile del repo).
BASE_SETTINGS = [
    "-DSUPPORT_MF_CLASSIC_MAGIC_MODE",
    "-DSUPPORT_FIRMWARE_UPGRADE",
    "-DDEFAULT_CONFIGURATION=CONFIG_NONE",
    "-DDEFAULT_BUTTON_ACTION=BUTTON_ACTION_CYCLE_SETTINGS",
    "-DDEFAULT_BUTTON_LONG_ACTION=BUTTON_ACTION_NONE",
    "-DBUTTON_SETTING_GLOBAL",
    "-DDEFAULT_SETTING=SETTINGS_FIRST",
    "-DDEFAULT_PENDING_TASK_TIMEOUT=50",
]

# nombre -> (descripcion, [flags de configuracion])
VARIANTS = {
    "classic-detection": (
        "MIFARE Classic (Mini/1K/4K, UID 4/7B) + captura de claves",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT"],
    ),
    "classic-detection-brute": (
        "Classic + deteccion + fuerza bruta de claves",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT",
         "-DCONFIG_MF_CLASSIC_BRUTE_SUPPORT"],
    ),
    "classic-detection-log": (
        "Classic + deteccion + registro de interacciones",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT",
         "-DCONFIG_MF_CLASSIC_LOG_SUPPORT"],
    ),
    "classic-only": (
        "Solo MIFARE Classic (maximo margen, sin deteccion)",
        ["-DCONFIG_MF_CLASSIC_SUPPORT"],
    ),
    "classic-ntag": (
        "Classic + NTAG 213/215/216 (sin deteccion)",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_NTAG213_SUPPORT",
         "-DCONFIG_NTAG215_SUPPORT", "-DCONFIG_NTAG216_SUPPORT"],
    ),
    "ultralight-ntag": (
        "MIFARE Ultralight + NTAG 213/215/216 (sin Classic)",
        ["-DCONFIG_MF_ULTRALIGHT_SUPPORT", "-DCONFIG_NTAG213_SUPPORT",
         "-DCONFIG_NTAG215_SUPPORT", "-DCONFIG_NTAG216_SUPPORT"],
    ),
}

FLASH_BAT_TEMPLATE = """@ECHO OFF
REM Flashea la variante: {name}
REM {desc}
CD /D "%~dp0"
COPY /Y "fw\\{name}.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\\{name}.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: {name}
ECHO  {desc}
ECHO ============================================================
CALL _retry.bat
"""

RETRY_BAT = """@ECHO OFF
REM Bucle de flasheo con reset del MCU entre intentos.
REM Espera ChameleonMini.hex / ChameleonMini.eep en el directorio actual.
CD /D "%~dp0"
SETLOCAL
SET MAX=6
FOR /L %%i IN (1,1,%MAX%) DO (
    ECHO.
    ECHO --- intento %%i de %MAX% ---
    CALL flash.bat > _salida.txt 2>&1
    TYPE _salida.txt
    FINDSTR /C:"load_success!" _salida.txt >NUL
    IF NOT ERRORLEVEL 1 (
        ECHO.
        ECHO ############ load_success!  FIRMWARE GRABADO ############
        ECHO Desconecta y reconecta la placa en modo normal.
        DEL _salida.txt 2>NUL
        PAUSE
        EXIT /B 0
    )
    ECHO --- sin load_success: reseteo del MCU y reintento ---
    dfu-programmer.exe atxmega32a4u launch >NUL 2>&1
    PING -n 4 127.0.0.1 >NUL
)
ECHO.
ECHO ############ %MAX% INTENTOS SIN EXITO ############
ECHO La flash quedo BORRADA. Ciclo fisico: desconecta, boton negro, reconecta,
ECHO y vuelve a ejecutar este .bat
DEL _salida.txt 2>NUL
PAUSE
EXIT /B 1
"""


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", ".."))


def firmware_dir():
    return os.path.join(repo_root(), "Firmware", "ChameleonMini")


def build_one(flags):
    fw = firmware_dir()
    settings = " ".join(BASE_SETTINGS + flags)
    subprocess.run(["make", "clean"], cwd=fw, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL, check=False)
    r = subprocess.run(["make", f"SETTINGS={settings}"], cwd=fw,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    elf = os.path.join(fw, "ChameleonMini.elf")
    if r.returncode != 0 or not os.path.exists(elf):
        return None, None, None, r.stderr.decode("utf-8", "replace")[-500:]
    size = subprocess.run(["avr-size", elf], capture_output=True, text=True).stdout
    nums = size.splitlines()[1].split()
    total = int(nums[0]) + int(nums[1])   # text + data
    return (os.path.join(fw, "ChameleonMini.hex"),
            os.path.join(fw, "ChameleonMini.eep"), total, None)


def main():
    ap = argparse.ArgumentParser(description="Compila variantes de firmware y arma la flash-station")
    default_station = os.path.join(repo_root(), "Firmware", "VM-Flash", "flash-station")
    ap.add_argument("--station", default=default_station)
    ap.add_argument("--only", nargs="*", help="compilar solo estas variantes")
    ap.add_argument("-V", "--version", action="version", version=CURRENT_VERSION)
    args = ap.parse_args()

    fwdir = os.path.join(args.station, "fw")
    os.makedirs(fwdir, exist_ok=True)

    with open(os.path.join(args.station, "_retry.bat"), "w", newline="\r\n") as fh:
        fh.write(RETRY_BAT)

    names = args.only or list(VARIANTS)
    built, skipped = [], []
    for name in names:
        desc, flags = VARIANTS[name]
        print(f"[build] {name} ...", end=" ", flush=True)
        hexf, eepf, size, err = build_one(flags)
        if hexf is None:
            print(f"FALLO\n{err}")
            skipped.append((name, "error de compilacion"))
            continue
        if size > FLASH_CEILING:
            print(f"NO CABE ({size} B > {FLASH_CEILING})")
            skipped.append((name, f"{size} B > {FLASH_CEILING}"))
            continue
        shutil.copyfile(hexf, os.path.join(fwdir, f"{name}.hex"))
        shutil.copyfile(eepf, os.path.join(fwdir, f"{name}.eep"))
        with open(os.path.join(args.station, f"flash_{name}.bat"), "w", newline="\r\n") as fh:
            fh.write(FLASH_BAT_TEMPLATE.format(name=name, desc=desc))
        print(f"OK  {size} B (margen {FLASH_CEILING - size} B)")
        built.append((name, size, desc))

    subprocess.run(["make", "clean"], cwd=firmware_dir(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    print("\n=== variantes disponibles en la flash-station ===")
    for name, size, desc in built:
        print(f"  flash_{name}.bat   {size} B   {desc}")
    if skipped:
        print("\n=== descartadas ===")
        for name, why in skipped:
            print(f"  {name}: {why}")


if __name__ == "__main__":
    main()
