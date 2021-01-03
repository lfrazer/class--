# class--
Convert C++ classes to plain C structs for use with IDA / ghidra local types

# Instructions
Note: This script requires ctags-Universal to function.
pass ctags-Universal JSON output into this program to parse out class / structs from C++ headers (e.g. cmd>python classstripper.py typeinfo.json)
Important note:  Tell ctags not to sort to keep member variables in correct order
Example cmd line:  ctags --c++-kinds=+p --fields=+ianS --extras=+q --sort=no --output-format=json /pathto/yourcode/*.h > typeinfo.json
