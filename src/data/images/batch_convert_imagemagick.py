# Small utility to quickly convert
# any flat png icon to the desired colors
# USAGE:
# drop imgs to convert in a "to_be_converted" folder
# not reccommended to delete these images afterwards
# -> automatically sync new color folders

import os
import subprocess
import shutil

BASEDIR = os.path.dirname(__file__)


def command_run(cmd):
    completed = subprocess.run(["powershell", "-Command", cmd], capture_output=True)
    if completed.returncode != 0:
        print("An error occured: %s" % completed.stderr)
    else:
        print("Command executed successfully!")


# folders to create in #HEX, rgb(r,g,b) or string format
COLORS = ["black", "grey", "white", "#8AB4F8", "#438EC8", "#009534", "#8b0000"]

for color in COLORS:
    dest_folder = os.path.join(BASEDIR, color)
    if not os.path.exists(dest_folder):
        os.mkdir(dest_folder)
    # drop images here. duplicates in destination won't be converted
    source_folder = os.path.join(BASEDIR, "to_be_converted")
    for dirpath, dirnames, files in os.walk(source_folder):
        for file in files:
            dest_file = os.path.join(dest_folder, file)
            if file.endswith(".png") and not os.path.exists(dest_file):
                img = os.path.join(dirpath, file)
                shutil.copy(img, dest_folder)
                # the image will be overridden
                my_command = f'magick convert {dest_file} -fill "{color}" -colorize 100 {dest_file} '
                command_run(my_command)
