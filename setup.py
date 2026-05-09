from setuptools import setup, find_packages
from pathlib import Path

with open("requirements.txt", "r", encoding="utf-8") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

long_description = Path("README.md").read_text(encoding="utf-8") if Path("README.md").exists() else ""

setup(
    name="SonicFlame Player",
    version="1.1.0",
    description="Modern desktop audio player with album art, smart playlist, and metadata caching",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ramzes",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "sonicflame=main:main",
            "musicplayer=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Multimedia :: Sound/Audio :: Players",
    ],
    license="MIT",
    keywords="music player audio mp3 flac m4a pyside6 pyqt6",
)
