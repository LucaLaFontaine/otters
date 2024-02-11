### How to generate docs:

`pdoc -t "dark mode" src/otters -o ./docs`

### How to update the package:

1. Update the code and commit it
2. update the verion in the toml file
3. run: `py -m build`
4. install with the following: `pip install -e "path/to/folder with setup.py"`