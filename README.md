# arxify - arXiv Packaging Tool
`arxify` is a command line tool that packages latex projects into an arXiv-compatible archives.
It removes comments from you *.tex files and removes any files that are not needed during the compile process.
The latter is achieved by compiling the project once and observing which files are being accessed by the compiler using [watchdog](https://github.com/gorakhargosh/watchdog).

## Installation
Install `arxify` via
```bash
pip install arxify
```

## Usage
Call with your latex main file and a target filename for the resulting zip archive:
```bash
arxify /path/to/root/main.tex /path/to/output.zip
```

By default `arxify` will assume that the root directory of your project is the parent directory of your main *.tex file.
Should that not be the case, specify the root directory with the `-r` option:
```bash
arxify /path/to/root/subdir/main.tex /path/to/output.zip -r /path/to/root/
```

By default `arxify` will attempt to compile your project using `pdflatex` and `bibtex`.
Currently supported are also `lualatex` and `biber`, which can be selected via
```bash
arxify /path/to/root/main.tex /path/to/output.zip -c lualatex -b biber
```

If you wish to include files into the archive that are not used by the compiler, specify them with the `-i` option:
```bash
arxify /path/to/root/main.tex /path/to/output.zip -i /path/to/root/a_file.txt /path/to/root/another_file.txt
```
