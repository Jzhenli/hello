BRIEFCASE_VERSION = "0.4.2"
NUITKA_VERSION = "2.7.12"
PBS_RELEASE = "20260508"

PBS_PYTHON_VERSIONS = {
    "3.10": "3.10.20",
    "3.11": "3.11.15",
    "3.12": "3.12.13",
}

ARCH_CONFIGS = {
    "armv7": {
        "pbs_target": "armv7-unknown-linux-gnueabihf",
        "pkg_suffix": "armv7",
        "extra_index_url": "https://www.piwheels.org/simple",
    },
    "aarch64": {
        "pbs_target": "aarch64-unknown-linux-gnu",
        "pkg_suffix": "aarch64",
        "extra_index_url": None,
    },
}

STRIPPED_STDLIB_MODULES = [
    "tkinter", "idlelib", "lib2to3",
    "pydoc_data", "curses", "tty", "webbrowser",
]
