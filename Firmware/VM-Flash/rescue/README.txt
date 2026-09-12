================================================================================
RECOVERY KIT - ChameleonMini RevE rebooted (clone, ATxmega32A4U)
Restores the factory firmware "Chameleon-new-1.0"
Procedure verified 2026-09-11
================================================================================

WHEN TO USE THIS
----------------
- The board only enumerates as 03eb:2fe4 (ATxmega32A4U DFU bootloader)
- No LED / does not show up as a serial port
- Enters DFU with and without holding the black button
- Flashing reports "no device present" or "Bootloader and code overlap"

YOUR DATA IS NOT LOST. The card memory of the 8 slots lives in a different
region: it survives flash erases and EEPROM rewrites. Verified by md5 before and
after a full erase.


REQUIREMENTS (on the Windows VM)
--------------------------------
1. Visual C++ 2013 Redistributable. On 64-bit Windows the x86 build is required.
2. DFU driver installed: Device Manager > unknown device > Update driver >
   the driver\ folder. It should show up as "Atmel USB Devices > ATxmega32A4U".
   If Windows rejects the .inf over the signature, use Zadig (zadig.akeo.ie) and
   assign libusb-win32 to device 03EB:2FE4.
3. USB passthrough to the VM: Devices > USB > ATxmega32A4U DFU bootloader.

NEVER place a libusb0.dll in this folder. The executable would load it before
the system one and enumeration fails with "no device present". It is absent on
purpose.


PROCEDURE
---------
1. Unplug the USB. Hold the black button and plug it back in.
2. Passthrough to the VM.
3. In an ADMINISTRATOR cmd:

     cd C:\rescue
     flash.bat

4. Read the output. ALL of this must appear:

     Programming 0x400 bytes...   Success     <- EEPROM
     Reading 0x400 bytes...
     Programming 0x5900 bytes...  Success     <- APPLICATION
     Reading 0x7000 bytes...
     load_success!                            <- the real confirmation

   The trailing "Enjoy!" is printed by the .bat ALWAYS, pass or fail.
   It means nothing. The only line that counts is load_success!

5. Unplug and replug in normal mode. The LED should light and it should appear
   as 03eb:2044 / a COM port (on Linux: /dev/ttyACM0).


IF THE OUTPUT STOPS BEFORE "load_success!"   <-- HAPPENS OFTEN, IT IS NORMAL
----------------------------------------------------------------------------
The bootloader enters the dfuERROR (10) state and stalls everything after it.
BOOT_LOADER_EXE.exe does not report it: it silently stops and returns control
to the .bat.

FIX: power cycle. Unplug the USB, hold the black button, replug, and run
flash.bat again. Repeat until you see load_success!
Replugging resets the bootloader state machine back to dfuIDLE.

It took 4 attempts on one occasion. That is expected, not a fault.
Each attempt usually gets one step further than the previous one.

CAREFUL: an interrupted run ALREADY DID THE ERASE. It leaves the flash blank and
without an application. If you stop there, the board will NOT boot. Do not stop
until load_success!

For convenience, flash_auto.bat runs this loop automatically (up to 6 attempts,
resetting the MCU between them). Requires a fixed USB filter 03EB:2FE4 in
VirtualBox so it re-attaches after each reset.

If it keeps stopping at the same point across cycles:

     flash_app_only.bat      <- writes the application with dfu-programmer
     flash.bat               <- then repeat the official procedure


AFTER RECOVERY
--------------
Slots come up CLOSED. To make them usable again, over the serial terminal
(115200, commands terminated with \r):

     SETTINGMY=0     CONFIGMY=MF_CLASSIC_1K
     SETTINGMY=1     CONFIGMY=MF_DETECTION

Check with VERSIONMY? -> it should answer "Chameleon-new-1.0".


WHAT NOT TO DO
--------------
- Do not use dfu-programmer on your own to "fix it": its writes leave the board
  unable to boot. Only flash_app_only.bat as documented above.
- Do not flash ChameleonMini.eep as if it were an application: its content goes
  to 0x8000, which is the bootloader region.
- From Linux you CANNOT flash this board. All writes fail with
  dfu_download / Broken pipe, with both dfu-programmer and avrdude. Documented
  in issues #46, #93 and #62 of the repo, none resolved.


CONTENTS
--------
flash.bat               official procedure (Createbin -> BOOT_LOADER_EXE)
flash_auto.bat          retry loop around flash.bat (resets MCU between tries)
ChameleonMini.hex       factory firmware      (was ITS_A_CARD.hex)
ChameleonMini.eep       EEPROM content        (was ChameleonMiniRDV2.0_ATxmega32A4U.hex)
BOOT_LOADER_EXE.exe     manufacturer flasher
Createbin.exe           encrypts the firmware (AES) as the bootloader expects
avr-objcopy.exe         ihex -> binary
msvcr120d.dll           runtime needed by Createbin.exe
dfu-programmer.exe      only for step 2
app_stock.hex           factory firmware for step 2
flash_app_only.bat      step 2
driver\                 DFU libusb-win32 driver (.inf + .sys)
CHECKSUMS.md5           integrity
