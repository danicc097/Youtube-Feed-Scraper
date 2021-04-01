$venvPath = "c:/Users/danic/MyPython/.venv/Scripts/Activate.ps1"
$specPath = "YouTube-Scraper-windows.spec"
if (Test-Path $specPath -PathType leaf) { 
    & $venvPath 
    pipenv run pyinstaller YouTube-Scraper-windows.spec `
        --noconfirm `
        --clean
} 
else {
    # create spec for first time
    pipenv run pyi-makespec main.py `
        --onefile `
        --name "YouTube-Scraper-windows" `
        --paths="src\" `
        --icon='main.ico' `
        --add-data "src\data\;src\data" `
        --hidden-import src `
        --hidden-import qtmodern `
        --exclude-module cv2 `
        --exclude-module numpy 
}

#* edit qtmodern data as per https://github.com/gmarull/qtmodern/issues/34

# import importlib
# from pathlib import Path
# package_imports = [['qtmodern', ['resources/frameless.qss', 'resources/style.qss']]]

# added_file = []
# for package, files in package_imports:
#     proot = Path(importlib.import_module(package).__file__).parent
#     added_file.extend((proot / f, package) for f in files) #? unpack in datas: , *added_file
