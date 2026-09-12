@ECHO OFF
REM Flash variant: classic-detection-brute
REM Classic + detection + key brute force
CD /D "%~dp0"
COPY /Y "fw\classic-detection-brute.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection-brute.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: classic-detection-brute
ECHO  Classic + detection + key brute force
ECHO ============================================================
CALL _retry.bat
