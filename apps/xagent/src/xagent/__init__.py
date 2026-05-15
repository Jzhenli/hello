"""XAgent - Lightweight Python IoT Gateway"""

__version__ = "0.0.20"

def main():
    """Lazy import main function to avoid circular import issues in compiled .so"""
    from xagent.main import main as _main
    return _main()

__all__ = ["main", "__version__"]
