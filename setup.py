from setuptools import setup, find_packages
from setuptools.extension import Extension
from os import getenv

# new release walkthrough:
# python3 -m pytest
# bump __version__
# python3 setup.py sdist bdist_wheel
# python3 -m twine upload dist/*filename*

if getenv("CYTHONIZE"):
    from Cython.Build import cythonize
    extensions = cythonize("aiocsv/_parser.pyx", language_level=3)

else:
    extensions = [Extension(
        name="aiocsv._parser",
        sources=["aiocsv/_parser.c"]
    )]


with open("readme.md", "r", encoding="utf-8") as f:
    readme = f.read()

setup(
    name="aiocsv",
    py_modules=["aiocsv"],
    ext_modules=extensions,
    packages=find_packages(include=["aiocsv"]),
    zip_safe=False,
    license="MIT",
    version="1.2.0",
    description="Asynchronous CSV reading/writing",
    long_description=readme,
    long_description_content_type="text/markdown",
    author="Mikołaj Kuranowski",
    author_email="".join(chr(i) for i in [109, 107, 117, 114, 97, 110, 111, 119, 115, 107, 105,
                                          64, 103, 109, 97, 105, 108, 46, 99, 111, 109]),
    url="https://github.com/MKuranowski/aiocsv",
    keywords="async asynchronous aiofiles csv tsv",
    install_requires="typing-extensions;python_version<='3.7'",
    python_requires=">=3.6, <4",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Framework :: AsyncIO",
        "Programming Language :: Python :: 3 :: Only"
    ]
)
