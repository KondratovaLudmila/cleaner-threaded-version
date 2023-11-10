import logging
from sys import argv
from pathlib import Path
from shutil import unpack_archive
from concurrent.futures import ThreadPoolExecutor
from threading import RLock
from time import time

class Normalize():

    CYRILLIC_SYMBOLS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюяєіїґ"
    TRANSLATION = ("a", "b", "v", "g", "d", "e", "e", "j", "z", "i", "j", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u",
                "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya", "je", "i", "ji", "g")

    def __init__(self):
        self.TRANS_DICT = self.gen_trans_dict()

    def gen_trans_dict(self) -> dict:
        """Generate transliteration dictionary for normalizing operations

        Returns:
            dict: dictionary like: 
                key - cyrilic symbol
                value - latinic transliteration
        """
        trans_dict = {}
        for c, l in zip(self.CYRILLIC_SYMBOLS, self.TRANSLATION):
            trans_dict[ord(c)] = l
            trans_dict[ord(c.upper())] = l.upper()

        return trans_dict

    def normalize(self, name: str) -> str:
        """Transliterate all cyrilic symbols to latinic 
        and replace all not numeric or alphabet symbols to '_'

        Args:
            name (str): string to normalize

        Returns:
            str: normalized string
        """
        normalized_name = ""
        
        for char in name:
            if char.isalnum():
                normalized_name += self.TRANS_DICT.get(ord(char), char)
            else:
                normalized_name += "_"
        
        return normalized_name

class CleanFolder():
    FORMATS_DICT = {"images": {'JPEG', 'PNG', 'JPG', 'SVG'},
                    "video": {'AVI', 'MP4', 'MOV', 'MKV'},
                    "documents": {'DOC', 'DOCX', 'TXT', 'PDF', 'XLSX', 'PPTX'},
                    "audio": {'MP3', 'OGG', 'WAV', 'M4A','AMR'},
                    "archives": {'ZIP', 'GZ', 'TAR'},
                    }

    def __init__(self, path: str, max_threads: int=10):
        self.__path = None
        self.path = Path(path)
        self.target_pathes = self.gen_formats_path_set()
        self.known_formats = set()
        self.unknown_formats = set()
        self.normalizer = Normalize()
        self.thread_pool = []
        self.folders = []
        self.executor = ThreadPoolExecutor(max_threads)
        self.locker = RLock()

    @property
    def path(self):
        return self.__path
    
    @path.setter
    def path(self, path: Path) -> None:
        """If the path is exists and is a directory sets __path atribute
        path: Path object folder for sorting 
        """
        if  path.exists() and path.is_dir():
            self.__path = path
        else:
            raise ValueError("Invalid path")


    def get_target_folder(self, extension: str) -> Path:
        """Searching destination folder by given extention

        Args:
            extension (str): file extention

        Returns:
            str: destination folder
        """
        new_folder = ""

        extension = extension.upper()
        for file_type in self.FORMATS_DICT:
            if extension in self.FORMATS_DICT[file_type]:
                new_folder = file_type
                break
        
        for path in self.target_pathes:
            if path.name.lower() == new_folder.lower():
                return path

        return None

    def gen_unique_name(self, path: Path) -> Path:
        """If path name is not unique generates a unique path name
        with given path name + index
        use this method for correct renamin files and folders

        Args:
            path (Path): path 

        Returns:
            Path: unique path name
        """
        new_path = path
        start_name = path.name.removesuffix(path.suffix)
        idx = 0
        while new_path.exists():
            idx += 1
            new_name = start_name + str(idx) + new_path.suffix
            new_path = new_path.with_name(new_name)

        return new_path

    def gen_formats_path_set(self) -> set:
        """Generates destination folders for different file formats based on path atribute

        Returns:
            set: set of destination pathes
        """
        formats_path_set = set()

        for file_type in self.FORMATS_DICT:
            formats_path_set.add(self.path.joinpath(file_type))

        return formats_path_set

    def handle_file(self, file_path: Path):
        """Search for correct directory for file by it's extension
        if it is nessesery normalize file name

        Args:
            file_path (Path): file to handle
        """
        new_name = self.normalizer.normalize(file_path.stem)
        new_name += file_path.suffix
        extension = file_path.suffix.removeprefix(".")
        target_path = self.get_target_folder(extension)
        
        with self.locker:
            if target_path:
                self.known_formats.add(extension)
            else:
                target_path = file_path.parent
                self.unknown_formats.add(extension)
        
        target_path.mkdir(exist_ok=True)

        target_path = target_path.joinpath(new_name)
        if target_path != file_path:
            self.execute_in_thread(self.move_file, file_path, target_path)
    

    def move_file(self, old_path: Path, new_path: Path):
        """Moving file to new_path dirrectory
        if file with such name has already exist in destination directory
        generate a unique name and moves file correctly
        """
        while True:
            try:
                old_path.rename(new_path)
                break
            except:
                new_path = self.gen_unique_name(new_path)

    
    def handle_folders(self, folders: [Path]) -> None:
        """If is nessecery renames folders in list

        Args:
            folders (list[Path]): list of folders for handling
        """
        while folders:
            folder_path = folders.pop()
            if not folder_path.exists():
                continue
            new_name = self.normalizer.normalize(folder_path.stem)
            if not any(folder_path.iterdir()):
                try:
                    folder_path.rmdir()
                except OSError:
                    print(f"Can not remove directory {folder_path}")
            elif new_name != folder_path.name:
                target_path = folder_path.parent.joinpath(new_name)
                self.move_file(folder_path, target_path)
    

    def scan_dir(self, cur_dir: Path) -> None:
        """Look up recursively for files and folders
        if file is meeted handle it
        if folder is meeted adds it to self.folders

        Args:
            cur_dir (Path): directore to look up

        Returns: None
        """
        logging.info(f"Scinning {str(cur_dir)}...")
        for cur_path in cur_dir.iterdir():
            if cur_path in self.target_pathes:
                continue
            
            if cur_path.is_file():
                self.handle_file(cur_path)
            elif cur_path.is_dir():
                with self.locker:
                    self.folders.append(cur_path)
                self.execute_in_thread(self.scan_dir, cur_path)


    def execute_in_thread(self, command, *args):
        """Adds command to thread pool"""
        future = self.executor.submit(command, *args)
        self.thread_pool.append(future)


    def wait_for_result(self) -> list:
        """Collect all results from all threads
        Return list of results
        """
        result = []
        for future in self.thread_pool:
            result.append(future.result())
        self.thread_pool = []
        return result


    def postprocessing(self):
        """Additional proccessing of formats folders
        currently available only archives: all archive 
        files in folder archives will be unpacked
        source archive files will be removed
        """
        logging.info("Postprocessing started...")
        for folder in self.target_pathes:
            logging.info(f"{folder.name}")
            if not folder.exists():
                continue

            if folder.name == "archives":
                for arch in folder.iterdir():
                    if arch.is_dir():
                        continue
                    self.execute_in_thread(self.handle_archive, arch)

            for obj in folder.iterdir():
                logging.info("{:<5}{}".format("", obj.name))

    def handle_archive(self, path: Path):
        """Unpack an archive and remove source file after
        """
        folder = path.parent
        unpack_archive(path, Path(folder, path.stem))
        path.unlink()

def main() -> bool:
    if len(argv) < 2:
        print("There is no directory for sorting!")
        return 1
    logging.basicConfig(level=logging.INFO, format='%(message)s')
    working_folder = Path(argv[1])

    cleaner = CleanFolder(working_folder)

    start = time()

    cleaner.scan_dir(cleaner.path)
    # We need to wait untill all files wil be moved to formats directorys
    # to start handling folders and start postprocessing
    cleaner.wait_for_result()
    cleaner.handle_folders(cleaner.folders)
    cleaner.postprocessing()

    finish = time() - start

    logging.info(f"Total time {finish}")
    print(f"Known file formats: {','.join(cleaner.known_formats)}")
    print(f"Unknown file formats: {','.join(cleaner.unknown_formats)}")
    
    cleaner.executor.shutdown()

    return 0

if __name__ == '__main__':
    
    main()