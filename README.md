### How to generate docs:

`pdoc -t "dark mode" src/otters -o ./docs`  
I've replaced this with sphinx but i haven't actually configured anything

### How to update the package:

1. Update the code and commit it
2. Update the verion in the toml file (optional but advised if you want to sit at the big kid's table)
3. Run: `py -m build` (I'm genuinely not sure if this is necessary)
4. Install with the following: `pip install git+https://github.com/LucaLaFontaine/otters.git`  
    4.1. requirements.txt > `otters @ git+https://github.com/LucaLaFontaine/otters.git`
5. You can update normally with `pip update otters`