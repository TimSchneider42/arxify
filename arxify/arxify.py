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

import inotify.adapters
import inotify.calls
import inotify.constants


def find_files(root: Path) -> List[Path]:
    own_files = (f for f in root.iterdir() if f.is_file())
    sub_files = (find_files(d) for d in root.iterdir() if d.is_dir())
    return list(chain(own_files, *sub_files))


def remove_comment(line: str):
    results = re.findall("((?:[^%]|%%)*%?).*", line)[:-1]
    if len(results) == 0:
        return ""
    return results[0]


def process_tex_file(path: Path) -> str:
    with path.open() as f:
        tex_code = f.read()
    lines = tex_code.split("\n")
    # Remove all comments
    lines_filtered = [remove_comment(l) for l in lines if not l.strip().startswith("%")]
    return "\n".join(lines_filtered)


def find_required_files(root: Path, main_tex_file_rel: Path, latex_out: Path, compiler: str = "pdflatex") -> Set[Path]:
    i = inotify.adapters.InotifyTree(str(root))

    proc = subprocess.Popen([compiler, "-output-directory", str(latex_out), str(main_tex_file_rel)], cwd=root)

    opened_files = []
    while proc.poll() is None:
        for event in i.event_gen(yield_nones=False, timeout_s=1.0):
            (_, type_names, path, filename) = event
            if "IN_ISDIR" not in type_names:
                opened_files.append(Path(path) / filename)
    for event in i.event_gen(yield_nones=False, timeout_s=0.0):
        (_, type_names, path, filename) = event
        if "IN_ISDIR" not in type_names:
            opened_files.append(Path(path) / filename)
    return set(opened_files)


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
            if tf.suffix == ".tex":
                new_content = process_tex_file(tf)
                with output_path.open("w") as f:
                    f.write(new_content)
            elif tf.suffix != ".bib":
                shutil.copy(tf, output_path)

        shutil.copy(latex_out / "{}.bbl".format(main_tex_file_rel.stem), zip_path)

        shutil.make_archive(str(Path(args.output_filename).resolve()), "zip", zip_path)


if __name__ == "__main__":
    main()
