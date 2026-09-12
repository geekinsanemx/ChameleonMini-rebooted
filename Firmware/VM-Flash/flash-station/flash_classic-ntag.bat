@ECHO OFF
REM Flashea la variante: classic-ntag
REM Classic + NTAG 213/215/216 (sin deteccion)
CD /D "%~dp0"
COPY /Y "fw\classic-ntag.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-ntag.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: classic-ntag
ECHO  Classic + NTAG 213/215/216 (sin deteccion)
ECHO ============================================================
CALL _retry.bat
