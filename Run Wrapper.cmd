@echo off
call "%~dp0pythonenv\Scripts\activate.bat"

python wrapper.py %*
