@ECHO OFF
CD /D "%~dp0"
ECHO === Write ONLY the application ===
ECHO Use only if flash.bat stopped after "Reading 0x400 bytes..."
ECHO.
dfu-programmer.exe atxmega32a4u flash --force --suppress-validation app_stock.hex
ECHO.
dfu-programmer.exe atxmega32a4u launch
ECHO.
ECHO Now run flash.bat again
PAUSE
