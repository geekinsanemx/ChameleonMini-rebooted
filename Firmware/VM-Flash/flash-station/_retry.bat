@ECHO OFF
REM Flash loop that resets the MCU between attempts.
REM Expects ChameleonMini.hex / ChameleonMini.eep in the current directory.
CD /D "%~dp0"
SETLOCAL
SET MAX=6
FOR /L %%i IN (1,1,%MAX%) DO (
    ECHO.
    ECHO --- attempt %%i of %MAX% ---
    CALL flash.bat > _out.txt 2>&1
    TYPE _out.txt
    FINDSTR /C:"load_success!" _out.txt >NUL
    IF NOT ERRORLEVEL 1 (
        ECHO.
        ECHO ############ load_success!  FIRMWARE FLASHED ############
        ECHO Unplug and replug the board in normal mode.
        DEL _out.txt 2>NUL
        PAUSE
        EXIT /B 0
    )
    ECHO --- no load_success: resetting the MCU and retrying ---
    dfu-programmer.exe atxmega32a4u launch >NUL 2>&1
    PING -n 4 127.0.0.1 >NUL
)
ECHO.
ECHO ############ %MAX% ATTEMPTS, NO SUCCESS ############
ECHO The flash was erased. Power cycle: unplug, hold the black button, replug,
ECHO and run this .bat again.
DEL _out.txt 2>NUL
PAUSE
EXIT /B 1
