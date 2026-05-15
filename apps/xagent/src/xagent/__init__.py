"""XAgent - Lightweight Python IoT Gateway"""

__version__ = "0.0.20"

def main():
    from .main import main as _main
    return _main()

__all__ = ["main", "__version__"]
