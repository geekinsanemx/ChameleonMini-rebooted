@ECHO OFF
REM Flash variant: classic-detection
REM MIFARE Classic (Mini/1K/4K, UID 4/7B) + key detection
CD /D "%~dp0"
COPY /Y "fw\classic-detection.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: classic-detection
ECHO  MIFARE Classic (Mini/1K/4K, UID 4/7B) + key detection
ECHO ============================================================
CALL _retry.bat
