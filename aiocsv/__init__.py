__title__ = "aiocsv"
__description__ = "Asynchronous CSV reading/writing"
__version__ = "1.2.3"

__url__ = "https://github.com/MKuranowski/aiocsv"
__author__ = "Mikołaj Kuranowski"
__email__ = "".join(chr(i) for i in [109, 107, 117, 114, 97, 110, 111, 119, 115, 107, 105,
                                     64, 103, 109, 97, 105, 108, 46, 99, 111, 109])

__copyright__ = "© Copyright 2020-2021 Mikołaj Kuranowski"
__license__ = "MIT"

from .readers import AsyncReader, AsyncDictReader
from .writers import AsyncWriter, AsyncDictWriter
