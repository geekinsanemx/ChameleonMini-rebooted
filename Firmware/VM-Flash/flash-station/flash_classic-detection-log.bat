@ECHO OFF
REM Flash variant: classic-detection-log
REM Classic + detection + reader interaction log
CD /D "%~dp0"
COPY /Y "fw\classic-detection-log.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\classic-detection-log.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: classic-detection-log
ECHO  Classic + detection + reader interaction log
ECHO ============================================================
CALL _retry.bat
