from clean import Normalize
from random import choices, randint, choice
from pathlib import Path
from shutil import make_archive

SYMBOLS = list(Normalize.CYRILLIC_SYMBOLS + "&#)(%@!)")
EXTENSIONS = ['jpeg', 'png', 'jpg', 'svg', 'avi', 'mp4', 'mov', 'mkv', 
              'doc', 'docx', 'txt', 'pdf', 'xlsx', 'pptx', 
              'mp3', 'ogg', 'wav', 'm4a', 'amr', 
              'zip', 'tar', 
              'py', 'ini']

OPTIONS = {1: "file",
           2: "dir"}

BASE_FOLDER = "tresh"

MAX_LEVEL = 4
MAX_ITEMS = 7

def gen_rand_name(option: int):
    length = randint(5, 20)
    name = "".join(choices(SYMBOLS, k=length))
    if option == 1:
        name += "." + choice(EXTENSIONS)

    return name

def create_archive(path: Path):
    format = path.suffix[1:]
    folder = Path(path.parent, path.stem)
    folder.mkdir(exist_ok=True)
    make_archive(folder, format, folder)

def create_new_path(option: int, base: Path):
    name = gen_rand_name(option)
    path = Path(base, name)
    if option == 1 and path.suffix not in (".tar", ".zip"):
        path.touch()
    elif option == 1 and path.suffix in (".tar", ".zip"):
        create_archive(path)
    else:
        path.mkdir(exist_ok=True)
    return path

def create_tree(path: Path, level: int):
    for i in range(1, MAX_ITEMS+1):
        new_path = create_new_path(randint(1,2), path)
        if new_path.is_dir() and level > 0:
            create_tree(new_path, level-1)

if __name__ == "__main__":
    path = Path(BASE_FOLDER)
    path.mkdir(exist_ok=True)
    create_tree(path, MAX_LEVEL)

