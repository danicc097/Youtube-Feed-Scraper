# PIPENV_IGNORE_VIRTUALENVS = 1
# .venv in current dir: virtualenv -p <python.exe path> .venv

$myDir = $PSScriptRoot
$venvPath = "$myDir\.venv\Scripts\Activate.ps1"
$specPath = "YouTube-Scraper-windows.spec"
if (Test-Path $specPath -PathType leaf) { 
    & $venvPath 
    pytest tests
    pipenv run pyinstaller YouTube-Scraper-windows.spec `
        --noconfirm `
        --clean
} 
else {
    # create spec for first time
    & $venvPath 
    pytest tests
    pipenv run pyi-makespec main.py `
        --onefile `
        --name "YouTube-Scraper-windows" `
        --paths="src\" `
        --icon='main.ico' `
        --add-data "src\data\;src\data" `
        --hidden-import src `
        --exclude-module cv2 `
        --exclude-module numpy 
}

#######################################
# TODO noconsole flag breaks chromedriver 
# for fix see https://stackoverflow.com/questions/41728959/how-to-capture-the-output-of-a-long-running-program-and-present-it-in-a-gui-in-p

#######################################
#? QT MODERN PACKAGE
#? edit qtmodern data as per https://github.com/gmarull/qtmodern/issues/34

# import importlib
# from pathlib import Path
# package_imports = [['qtmodern', ['resources/frameless.qss', 'resources/style.qss']]]

# added_file = []
# for package, files in package_imports:
#     proot = Path(importlib.import_module(package).__file__).parent
#     added_file.extend((proot / f, package) for f in files) #? unpack in datas: , *added_file


#######################################
#? to use __debug__ :
# run with basic optimizations
# python -O -m PyInstaller myscript.py