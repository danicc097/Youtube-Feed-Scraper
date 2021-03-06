specPath=YouTube-Scraper-linux.spec
if test -f "$specPath";
then
    pytest tests
    pipenv run pyinstaller YouTube-Scraper-linux.spec \
    --noconfirm \
    --clean
else 
    pytest tests
    pipenv run pyi-makespec main.py \
    --onefile \
    --noconsole \
    --name "YouTube-Scraper-linux" \
    --paths="src/" \
    --icon='main.ico' \
    --add-data "src/data/:src/data" \
    --hidden-import src \
    --exclude-module cv2 \
    --exclude-module numpy 
fi

#? QT MODERN PACKAGE
#? edit qtmodern data as per https://github.com/gmarull/qtmodern/issues/34

# import importlib
# from pathlib import Path
# package_imports = [['qtmodern', ['resources/frameless.qss', 'resources/style.qss']]]

# added_file = []
# for package, files in package_imports:
#     proot = Path(importlib.import_module(package).__file__).parent
#     added_file.extend((proot / f, package) for f in files) #? unpack in datas: , *added_file