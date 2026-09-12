@ECHO OFF
CD /D "%~dp0"
ECHO === PASO 2: escribe solo la aplicacion ===
ECHO Usar SOLO si flash.bat se corto tras "Reading 0x400 bytes..."
ECHO.
dfu-programmer.exe atxmega32a4u flash --force --suppress-validation app_stock.hex
ECHO.
dfu-programmer.exe atxmega32a4u launch
ECHO.
ECHO Ahora vuelve a ejecutar flash.bat
PAUSE
