from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="arxify",
    version="1.0.0",
    description="Pack a latex project into an arxiv compatible archive.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/TimSchneider42/arxify",
    author="Tim Schneider",
    author_email="tim@robot-learning.de",
    license="MIT",
    packages=find_packages(),
    install_requires=[
        "inotify==0.2.10"
    ],
    classifiers=[
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.10",
    ],
    entry_points = {
        "console_scripts": [
            "arxify=arxify:main"
        ]
    }
)
