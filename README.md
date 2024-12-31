### How to generate docs:

`pdoc -t "dark mode" src/otters -o ./pdocs`  
I've replaced this with sphinx but i haven't actually configured anything

### How to update the package:

1. Update the code and commit it
2. Update the verion in the toml file (optional but advised if you want to sit at the big kid's table)
3. Run: `py -m build` (I'm genuinely not sure if this is necessary)
4. Install with the following: `pip install git+https://github.com/LucaLaFontaine/otters.git`  
    4.1. requirements.txt > `otters @ git+https://github.com/LucaLaFontaine/otters.git`
5. You can update normally with `pip install --force-reinstall --no-deps git+https://github.com/LucaLaFontaine/otters.git`  

### Reading PDFs
If you use any of the functions that read PDFs you will need tabula (the package downloads itself), which runs on java. This means you also need [java](https://www.java.com/en/download/manual.jsp) on your computer which we cannot download for you easily.  

Barring that you can follow the official instructions [here](!https://tabula-py.readthedocs.io/en/latest/getting_started.html) to get tabula working.