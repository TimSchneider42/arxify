import argparse
import os
import re
import shutil
import subprocess
import sys
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import List, Set

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


def find_files(root: Path) -> List[Path]:
    own_files = (f for f in root.iterdir() if f.is_file())
    sub_files = (find_files(d) for d in root.iterdir() if d.is_dir())
    return list(chain(own_files, *sub_files))


def remove_comment(line: str):
    match = re.search(r'(?<!\\)%', line)
    if match:
        return line[:match.start()]
    else:
        return line

def remove_tikz_externalize(tex_code: str) -> str:
    if "\\usetikzlibrary" in tex_code:
        packages = re.findall(r'\\usetikzlibrary{([^,}]*)(?:,([^,}]*))*}', tex_code)[0]
        packages_filtered = [p for p in packages if p.strip() != "external" and p.strip() != ""]
        if len(packages_filtered) == 0:
            replacement = ""
        else:
            replacement = "\\usetikzlibrary{" + ",".join(packages_filtered) + "}"
        tex_code = re.sub(r'\\usetikzlibrary{[^}]*?}', lambda m: replacement, tex_code)
    if "\\tikzexternalize" in tex_code:
        # Remove tikzexternalize commands
        tex_code = re.sub(r'\\tikzexternalize(\[[^]]*\])?({})?', "", tex_code)
    return tex_code


def remove_tikz_externalize(tex_code: str) -> str:
    if "\\usetikzlibrary" in tex_code:
        packages = re.findall(r'\\usetikzlibrary{([^,}]*)(?:,([^,}]*))*}', tex_code)[0]
        packages_filtered = [p for p in packages if p.strip() != "external" and p.strip() != ""]
        if len(packages_filtered) == 0:
            replacement = ""
        else:
            replacement = "\\usetikzlibrary{" + ",".join(packages_filtered) + "}"
        tex_code = re.sub(r'\\usetikzlibrary{[^}]*?}', lambda m: replacement, tex_code)
    if "\\tikzexternalize" in tex_code:
        # Remove tikzexternalize commands
        tex_code = re.sub(r'\\tikzexternalize(\[[^]]*\])?({})?', "", tex_code)
    return tex_code


def process_tex_file(path: Path) -> str:
    with path.open() as f:
        tex_code = f.read()
    lines = tex_code.split("\n")
    # Remove all comments and disable tikz externalize if enabled
    lines_filtered = [remove_tikz_externalize(remove_comment(l)) for l in lines if not l.strip().startswith("%")]
    return "\n".join(lines_filtered)


class FileOpenHandler(FileSystemEventHandler):
    def __init__(self, opened_files: Set[Path]):
        self.opened_files = opened_files

    def on_opened(self, event):
        if not event.is_directory:
            self.opened_files.add(Path(event.src_path))


def find_required_files(root: Path, main_tex_file_rel: Path, latex_out: Path, compiler: str = "pdflatex") -> Set[Path]:
    opened_files = set()

    # Set up the watchdog observer and event handler
    event_handler = FileOpenHandler(opened_files)
    observer = Observer()
    observer.schedule(event_handler, str(root), recursive=True)

    # Start observing
    observer.start()

    try:
        # Run the LaTeX compiler
        proc = subprocess.Popen([compiler, "-output-directory", str(latex_out), str(main_tex_file_rel)], cwd=root)
        proc.wait()
    finally:
        # Stop observing
        observer.stop()
        observer.join()

    return opened_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("main_tex_file", type=str, help="Main tex file of the project.")
    parser.add_argument("output_filename", type=str, help="Filename of the output *.zip file.")
    parser.add_argument("-c", "--compiler", choices=["pdflatex", "lualatex"], default="pdflatex",
                        help="Compiler used to compile the project (default: pdflatex).")
    parser.add_argument("-b", "--bibliography-processor", choices=["bibtex", "biber"], default="bibtex",
                        help="Which program to use for processing the bibliography (default: bibtex).")
    parser.add_argument("-i", "--include", nargs="+", default=(),
                        help="Include these files, whether they are needed or not.")
    parser.add_argument(
        "-r", "--root", type=str, help="Root directory of the project (default: parent of the main tex file).")
    args = parser.parse_args()

    main_tex_file = Path(args.main_tex_file).resolve()
    if args.root is None:
        root = main_tex_file.parent
    else:
        root = Path(args.root).resolve()
        assert str(main_tex_file).startswith(str(root))
    main_tex_file_rel = main_tex_file.relative_to(root)

    with TemporaryDirectory() as td:
        td_path = Path(td)
        tmp_root = td_path / "root"
        latex_out = td_path / "out"
        zip_path = td_path / "zip"
        latex_out.mkdir()

        print("Copying files to temporary directory...")
        shutil.copytree(root, tmp_root)
        for f in tmp_root.glob("**/*.bst"):
            shutil.copy(f, latex_out / f.relative_to(tmp_root))
        print("Done copying files.")

        additional_files = [(f if f.is_absolute() else root / f).resolve() for f in map(Path, args.include)]
        additional_files_tmp = []
        for f in additional_files:
            if root not in f.parents:
                sys.stderr.write("Manually included file {} is not in a subdirectory of {}.".format(f, root))
                exit(1)
            if not f.exists():
                sys.stderr.write("Manually included file {} does not exist.".format(f, root))
                exit(1)
            new_path = tmp_root / f.relative_to(root)
            shutil.copy(f, new_path)
            additional_files_tmp.append(new_path)

        print("Stripping comments of tex files and disabling tikzexternalize...")
        for tf in tmp_root.rglob("*.tex"):
            new_content = process_tex_file(tf)
            with tf.open("w") as f:
                f.write(new_content)
        print("Done stripping comments.")

        required_files = find_required_files(tmp_root, main_tex_file_rel, latex_out, compiler=args.compiler)
        required_files.update(additional_files_tmp)

        if args.bibliography_processor == "biber":
            subprocess.check_call(["biber", "--input-directory", str(root), main_tex_file_rel.stem],
                                  cwd=latex_out)
        else:
            subprocess.check_call([args.bibliography_processor, main_tex_file_rel.stem], cwd=latex_out,
                                  env={"BIBINPUTS": str(root), **os.environ})

        print("The following files will be included in the zip:")
        for tf in required_files:
            print("  {}".format(tf.relative_to(tmp_root)))

        for tf in required_files:
            output_path = zip_path / tf.relative_to(tmp_root)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if tf.suffix != ".bib":
                shutil.copy(tf, output_path)

        shutil.copy(latex_out / "{}.bbl".format(main_tex_file_rel.stem), zip_path)

        output_path = Path(args.output_filename).resolve()
        if output_path.suffix == ".zip":
            output_path = output_path.with_suffix("")
        shutil.make_archive(str(output_path), "zip", zip_path)


if __name__ == "__main__":
    main()
