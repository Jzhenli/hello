import sys
import platform
import struct
from functools import lru_cache


@lru_cache(maxsize=None)
def get_os_platform() -> str:
    """
    Determine the current operating system platform.
    Returns: "Windows", "Android", "Linux (ARM)", "Linux (x86)", "Linux (RISC-V)", "macOS", "Other"
    """
    # Android must be checked first, otherwise it will be misidentified as Linux
    if hasattr(sys, "getandroidapilevel") or sys.platform == "android":
        return "Android"

    if sys.platform == "win32":
        return "Windows"

    if sys.platform == "linux":
        machine = platform.machine().lower()
        
        # ARM architectures
        if machine in ("aarch64", "arm64", "armv8l", "armv7l", "armv6l"):
            return "Linux_arm"
        # x86 architectures (Explicitly handle i386/i686)
        if machine in ("x86_64", "amd64", "i386", "i686"):
            return "Linux_x86"
            
        return "Linux_unknown"

    if sys.platform == "darwin":
        return "macOS"

    return "Unknown"


@lru_cache(maxsize=None)
def get_os_bitness() -> int:
    """
    Determine the bitness of the operating system.
    Returns: 64 or 32
    """
    machine = platform.machine().lower()
    plat = get_os_platform()

    if plat == "Windows":
        # AMD64, x86_64, or ARM64 are 64-bit Windows
        return 64 if machine in ("amd64", "x86_64", "arm64") else 32

    # Android and Linux (ARM) share the exact same bitness logic
    if plat in ("Android", "Linux_arm"):
        # aarch64 / arm64 -> 64-bit
        # armv8l / armv7l / armv6l -> 32-bit (armv8l = ARMv8 chip running AArch32)
        return 64 if machine in ("aarch64", "arm64") else 32

    if plat == "Linux_x86":
        return 64 if machine in ("x86_64", "amd64") else 32

    if plat == "Linux_unknown":
        # riscv64 -> 64-bit, riscv32 -> 32-bit
        return 64 if machine == "riscv64" else 32

    if plat == "macOS":
        # All macOS versions supported by recent Python are 64-bit
        return 64

    # Fallback
    return 64 if sys.maxsize > 2**32 else 32


@lru_cache(maxsize=None)
def get_python_bitness() -> int:
    """
    Determine the bitness of the current Python process.
    Returns: 64 or 32

    Note: 32-bit Python can run on a 64-bit OS, so they might not match.
    """
    return struct.calcsize("P") * 8


# ============ Usage Example ============
if __name__ == "__main__":
    plat = get_os_platform()
    os_bit = get_os_bitness()
    py_bit = get_python_bitness()

    print(f"OS Platform     : {plat}")
    print(f"OS Bitness      : {os_bit}-bit")
    print(f"Python Bitness  : {py_bit}-bit")

    # Common usage scenarios
    if plat == "Android" and os_bit == 64 and py_bit == 32:
        print("32-bit Python running on 64-bit Android. Consider upgrading Python.")
    elif plat == "Linux_arm" and os_bit == 32:
        print("32-bit ARM Linux. Memory limit is around 3-4GB.")
