import sys
from importlib.metadata import version

pkg = sys.argv[1]
print(version(pkg))
