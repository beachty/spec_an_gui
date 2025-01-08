from .core.sane import SANE
from .core.spectral_analyzer import SpectralAnalyzer
from .core.prb_reading import PRBReading
from .gui.main_window import SpectralAnalyzerGUI

__version__ = "0.1.0"
__author__ = "Tyler Beach"
__license__ = "MIT"

# Configure package-wide logging
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('spectral_analyzer.log')
    ]
)

logger = logging.getLogger(__name__)

# Expose main classes at package level
__all__ = [
    'SANE',
    'SpectralAnalyzer',
    'PRBReading',
    'SpectralAnalyzerGUI'
]