from setuptools import Extension, setup

setup(ext_modules=[Extension(name="aiocsv._parser", sources=["aiocsv/_parser.c"])])
