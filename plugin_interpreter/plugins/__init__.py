"""
This __init__ file imports all exported classes from
the plugin files in the ./plugins directory, except
__pycache__ or itself.
"""

from os import listdir as _listdir, path as _path

for _file in _listdir(_path.dirname(_path.realpath(__file__))):
    if _file.startswith('__'):
        continue
    _mod_name = _file[:-3]
    exec('from .' + _mod_name + ' import *')
