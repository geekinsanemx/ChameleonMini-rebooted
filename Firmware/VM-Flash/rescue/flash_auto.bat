@ECHO OFF
CD /D "%~dp0"
SETLOCAL
SET T=atxmega32a4u
SET MAX=6

FOR /L %%i IN (1,1,%MAX%) DO (
    ECHO.
    ECHO ============================================
    ECHO  INTENTO %%i de %MAX%
    ECHO ============================================
    CALL flash.bat > _salida.txt 2>&1
    TYPE _salida.txt
    FINDSTR /C:"load_success!" _salida.txt >NUL
    IF NOT ERRORLEVEL 1 (
        ECHO.
        ECHO ############################################
        ECHO  load_success!  FIRMWARE GRABADO
        ECHO ############################################
        ECHO Desconecta y reconecta la placa en modo normal.
        DEL _salida.txt
        PAUSE
        EXIT /B 0
    )
    ECHO.
    ECHO --- sin load_success: reseteando el MCU y reintentando ---
    dfu-programmer.exe %T% launch
    PING -n 4 127.0.0.1 >NUL
)

ECHO.
ECHO ############################################
ECHO  %MAX% INTENTOS SIN EXITO
ECHO ############################################
ECHO La flash quedo BORRADA. La placa no arrancara asi.
ECHO Haz un ciclo FISICO: desconecta el USB, manten el boton negro,
ECHO reconecta, y vuelve a lanzar este .bat
DEL _salida.txt
PAUSE
EXIT /B 1
