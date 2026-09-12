@ECHO OFF
REM Flashea la variante: ultralight-ntag
REM MIFARE Ultralight + NTAG 213/215/216 (sin Classic)
CD /D "%~dp0"
COPY /Y "fw\ultralight-ntag.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\ultralight-ntag.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variante: ultralight-ntag
ECHO  MIFARE Ultralight + NTAG 213/215/216 (sin Classic)
ECHO ============================================================
CALL _retry.bat
