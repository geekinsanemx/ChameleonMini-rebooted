#!/usr/bin/env python3
"""
build_firmware.py - Compiles the viable ChameleonMini RevE rebooted firmware
variants and prepares the 'flash-station' to flash them from the Windows VM.

Every variant must fit in 28672 B (0x7000): the limit of BOOT_LOADER_EXE.exe,
which cannot pass --suppress-bootloader-mem.

Usage:
    build_firmware.py [--station DIR] [--only NAME ...]

For each variant that compiles and fits it produces:
    <station>/fw/<name>.hex , <name>.eep
    <station>/flash_<name>.bat

CHANGELOG
  1.0.0 - Initial version.
"""

import argparse
import os
import shutil
import subprocess

CURRENT_VERSION = "1.0.0"

FLASH_CEILING = 28672  # 0x7000

# Settings common to every variant (equivalent to the repo Makefile).
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

# name -> (description, [configuration flags])
VARIANTS = {
    "classic-detection": (
        "MIFARE Classic (Mini/1K/4K, UID 4/7B) + key detection",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT"],
    ),
    "classic-detection-brute": (
        "Classic + detection + key brute force",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT",
         "-DCONFIG_MF_CLASSIC_BRUTE_SUPPORT"],
    ),
    "classic-detection-log": (
        "Classic + detection + reader interaction log",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_MF_CLASSIC_DETECTION_SUPPORT",
         "-DCONFIG_MF_CLASSIC_LOG_SUPPORT"],
    ),
    "classic-only": (
        "MIFARE Classic only (max headroom, no detection)",
        ["-DCONFIG_MF_CLASSIC_SUPPORT"],
    ),
    "classic-ntag": (
        "Classic + NTAG 213/215/216 (no detection)",
        ["-DCONFIG_MF_CLASSIC_SUPPORT", "-DCONFIG_NTAG213_SUPPORT",
         "-DCONFIG_NTAG215_SUPPORT", "-DCONFIG_NTAG216_SUPPORT"],
    ),
    "ultralight-ntag": (
        "MIFARE Ultralight + NTAG 213/215/216 (no Classic)",
        ["-DCONFIG_MF_ULTRALIGHT_SUPPORT", "-DCONFIG_NTAG213_SUPPORT",
         "-DCONFIG_NTAG215_SUPPORT", "-DCONFIG_NTAG216_SUPPORT"],
    ),
}

FLASH_BAT_TEMPLATE = """@ECHO OFF
REM Flash variant: {name}
REM {desc}
CD /D "%~dp0"
COPY /Y "fw\\{name}.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\\{name}.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: {name}
ECHO  {desc}
ECHO ============================================================
CALL _retry.bat
"""

RETRY_BAT = """@ECHO OFF
REM Flash loop that resets the MCU between attempts.
REM Expects ChameleonMini.hex / ChameleonMini.eep in the current directory.
CD /D "%~dp0"
SETLOCAL
SET MAX=6
FOR /L %%i IN (1,1,%MAX%) DO (
    ECHO.
    ECHO --- attempt %%i of %MAX% ---
    CALL flash.bat > _out.txt 2>&1
    TYPE _out.txt
    FINDSTR /C:"load_success!" _out.txt >NUL
    IF NOT ERRORLEVEL 1 (
        ECHO.
        ECHO ############ load_success!  FIRMWARE FLASHED ############
        ECHO Unplug and replug the board in normal mode.
        DEL _out.txt 2>NUL
        PAUSE
        EXIT /B 0
    )
    ECHO --- no load_success: resetting the MCU and retrying ---
    dfu-programmer.exe atxmega32a4u launch >NUL 2>&1
    PING -n 4 127.0.0.1 >NUL
)
ECHO.
ECHO ############ %MAX% ATTEMPTS, NO SUCCESS ############
ECHO The flash was erased. Power cycle: unplug, hold the black button, replug,
ECHO and run this .bat again.
DEL _out.txt 2>NUL
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
    ap = argparse.ArgumentParser(description="Compile firmware variants and build the flash-station")
    default_station = os.path.join(repo_root(), "Firmware", "VM-Flash", "flash-station")
    ap.add_argument("--station", default=default_station)
    ap.add_argument("--only", nargs="*", help="build only these variants")
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
            print(f"FAILED\n{err}")
            skipped.append((name, "build error"))
            continue
        if size > FLASH_CEILING:
            print(f"DOES NOT FIT ({size} B > {FLASH_CEILING})")
            skipped.append((name, f"{size} B > {FLASH_CEILING}"))
            continue
        shutil.copyfile(hexf, os.path.join(fwdir, f"{name}.hex"))
        shutil.copyfile(eepf, os.path.join(fwdir, f"{name}.eep"))
        with open(os.path.join(args.station, f"flash_{name}.bat"), "w", newline="\r\n") as fh:
            fh.write(FLASH_BAT_TEMPLATE.format(name=name, desc=desc))
        print(f"OK  {size} B (margin {FLASH_CEILING - size} B)")
        built.append((name, size, desc))

    subprocess.run(["make", "clean"], cwd=firmware_dir(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

    print("\n=== variants available in the flash-station ===")
    for name, size, desc in built:
        print(f"  flash_{name}.bat   {size} B   {desc}")
    if skipped:
        print("\n=== skipped ===")
        for name, why in skipped:
            print(f"  {name}: {why}")


if __name__ == "__main__":
    main()
