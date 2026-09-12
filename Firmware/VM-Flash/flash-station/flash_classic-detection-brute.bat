@ECHO OFF
REM Flashea la variante: classic-detection-brute
REM Classic + deteccion + fuerza bruta de claves
CD /D "%~dp0"
COPY /Y "fw\classic-detection-brute.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection-brute.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: classic-detection-brute
ECHO  Classic + deteccion + fuerza bruta de claves
ECHO ============================================================
CALL _retry.bat
