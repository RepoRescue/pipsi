import os
import sys
from configparser import ConfigParser
from importlib.metadata import distribution
from io import StringIO

pkg = sys.argv[1]
prefix = sys.argv[2]
dist = distribution(pkg)
seen = set()

for file in dist.files or ():
    path = os.path.realpath(os.fspath(dist.locate_file(file)))
    if path.startswith(prefix) and path not in seen:
        seen.add(path)
        print(path)

entry_points = dist.read_text('entry_points.txt')
if entry_points:
    parser = ConfigParser()
    parser.read_file(StringIO(entry_points))
    if parser.has_section('console_scripts'):
        for name, _ in parser.items('console_scripts'):
            path = os.path.join(prefix, name)
            if path not in seen:
                seen.add(path)
                print(path)
