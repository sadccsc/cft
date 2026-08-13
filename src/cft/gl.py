version=None
from cft import __version__

def titleFor(appName):
    return f"CFT (v{__version__}) — {appName}" if appName else f"CFT (v{__version__})"
