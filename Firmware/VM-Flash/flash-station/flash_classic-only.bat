@ECHO OFF
REM Flashea la variante: classic-only
REM Solo MIFARE Classic (maximo margen, sin deteccion)
CD /D "%~dp0"
COPY /Y "fw\classic-only.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-only.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: classic-only
ECHO  Solo MIFARE Classic (maximo margen, sin deteccion)
ECHO ============================================================
CALL _retry.bat
