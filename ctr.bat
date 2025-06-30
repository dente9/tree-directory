@echo off
rem Get the directory of this batch file
set "script_dir=%~dp0"

rem Call the Python script in the same directory
python "%script_dir%tree.py" %*