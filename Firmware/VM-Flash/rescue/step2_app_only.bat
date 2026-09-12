@ECHO OFF
CD /D "%~dp0"
ECHO === STEP 2: write only the application ===
ECHO Use ONLY if flash.bat stopped after "Reading 0x400 bytes..."
ECHO.
dfu-programmer.exe atxmega32a4u flash --force --suppress-validation app_stock.hex
ECHO.
dfu-programmer.exe atxmega32a4u launch
ECHO.
ECHO Now run flash.bat again
PAUSE
