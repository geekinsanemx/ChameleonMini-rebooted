@ECHO OFF
REM Flashea la variante: classic-detection-log
REM Classic + deteccion + registro de interacciones
CD /D "%~dp0"
COPY /Y "fw\classic-detection-log.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection-log.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: classic-detection-log
ECHO  Classic + deteccion + registro de interacciones
ECHO ============================================================
CALL _retry.bat
