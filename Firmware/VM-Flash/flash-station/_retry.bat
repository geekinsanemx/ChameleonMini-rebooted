@ECHO OFF
REM Bucle de flasheo con reset del MCU entre intentos.
REM Espera ChameleonMini.hex / ChameleonMini.eep en el directorio actual.
CD /D "%~dp0"
SETLOCAL
SET MAX=6
FOR /L %%i IN (1,1,%MAX%) DO (
    ECHO.
    ECHO --- intento %%i de %MAX% ---
    CALL flash.bat > _salida.txt 2>&1
    TYPE _salida.txt
    FINDSTR /C:"load_success!" _salida.txt >NUL
    IF NOT ERRORLEVEL 1 (
        ECHO.
        ECHO ############ load_success!  FIRMWARE GRABADO ############
        ECHO Desconecta y reconecta la placa en modo normal.
        DEL _salida.txt 2>NUL
        PAUSE
        EXIT /B 0
    )
    ECHO --- sin load_success: reseteo del MCU y reintento ---
    dfu-programmer.exe atxmega32a4u launch >NUL 2>&1
    PING -n 4 127.0.0.1 >NUL
)
ECHO.
ECHO ############ %MAX% INTENTOS SIN EXITO ############
ECHO La flash quedo BORRADA. Ciclo fisico: desconecta, boton negro, reconecta,
ECHO y vuelve a ejecutar este .bat
DEL _salida.txt 2>NUL
PAUSE
EXIT /B 1
