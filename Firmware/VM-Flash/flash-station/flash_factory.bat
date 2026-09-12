@ECHO OFF
REM Restaura el firmware de FABRICA (Chameleon-new-1.0)
CD /D "%~dp0"
COPY /Y "fw\factory.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\factory.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Restaurando firmware de FABRICA
ECHO ============================================================
CALL _retry.bat
