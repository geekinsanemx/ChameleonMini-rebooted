@ECHO OFF
REM Flash variant: classic-only
REM MIFARE Classic only (max headroom, no detection)
CD /D "%~dp0"
COPY /Y "fw\classic-only.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-only.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: classic-only
ECHO  MIFARE Classic only (max headroom, no detection)
ECHO ============================================================
CALL _retry.bat
