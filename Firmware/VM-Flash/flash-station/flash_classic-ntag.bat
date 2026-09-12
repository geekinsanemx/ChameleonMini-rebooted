@ECHO OFF
REM Flash variant: classic-ntag
REM Classic + NTAG 213/215/216 (no detection)
CD /D "%~dp0"
COPY /Y "fw\classic-ntag.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-ntag.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: classic-ntag
ECHO  Classic + NTAG 213/215/216 (no detection)
ECHO ============================================================
CALL _retry.bat
