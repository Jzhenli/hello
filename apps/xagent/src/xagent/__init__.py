"""XAgent - Lightweight Python IoT Gateway"""

__version__ = "0.0.20"
from .main import main
# def main():
#     """Lazy import main function to avoid circular import issues in compiled .so"""
#     from xagent.main import main as _main
#     return _main()

__all__ = ["main", "__version__"]
