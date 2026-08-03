from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("sadc-cft")
except PackageNotFoundError:
    # package isn't installed (e.g. running straight from source, no pip install at all)
    __version__ = "unknown"
