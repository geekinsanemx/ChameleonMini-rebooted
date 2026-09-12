@ECHO OFF
REM Flashea la variante: classic-detection
REM MIFARE Classic (Mini/1K/4K, UID 4/7B) + captura de claves
CD /D "%~dp0"
COPY /Y "fw\classic-detection.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: classic-detection
ECHO  MIFARE Classic (Mini/1K/4K, UID 4/7B) + captura de claves
ECHO ============================================================
CALL _retry.bat
