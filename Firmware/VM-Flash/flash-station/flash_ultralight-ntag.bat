@ECHO OFF
REM Flash variant: ultralight-ntag
REM MIFARE Ultralight + NTAG 213/215/216 (no Classic)
CD /D "%~dp0"
COPY /Y "fw\ultralight-ntag.hex" "ChameleonMini.hex" >NUL
COPY /Y "fw\ultralight-ntag.eep" "ChameleonMini.eep" >NUL
ECHO ============================================================
ECHO  Variant: ultralight-ntag
ECHO  MIFARE Ultralight + NTAG 213/215/216 (no Classic)
ECHO ============================================================
CALL _retry.bat
