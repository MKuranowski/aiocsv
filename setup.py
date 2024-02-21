from setuptools import setup, Extension


setup(ext_modules=[Extension(name="aiocsv._parser", sources=["aiocsv/_parser.c"])])
