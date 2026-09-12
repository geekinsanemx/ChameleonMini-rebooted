@ECHO OFF
REM Restore the FACTORY firmware (Chameleon-new-1.0)
CD /D "%~dp0"
COPY /Y "fw\factory.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\factory.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Restoring FACTORY firmware
ECHO ============================================================
CALL _retry.bat
