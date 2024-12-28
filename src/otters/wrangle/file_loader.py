"""
The file_loader module provides functions used to load data from files (excel, csv, pdf, etc) or into files.
"""
import pandas as pd
import yaml
import os
from glob import glob
import inspect

import openpyxl
from openpyxl.worksheet.dimensions import ColumnDimension, DimensionHolder
from openpyxl.utils import get_column_letter
os.environ["XLWINGS_LICENSE_KEY"] = "noncommercial"


def import_config(configFolder='', recursive=True):
    """
    Import all config files from the supplied folder. Defaults to the root folder  
    Any files ending in 'config.yaml' or 'config.xlsx' will be treated. So you could have a formatting config called 'format.config.yaml'  
    
    **Parameters:**
    > **configFolder:** *string, default: empty*  
    >> The relative path to the config folder. 

    > **recursive:** *boolean, default: `True`* 
    >> Returns all files in dir and sub-dirs if `True`. Only files in root dir if `False`.

    **Returns:**  
    > **dict*
    """

    # Load any config files
    if recursive == True:
        yamlFiles = glob(os.getcwd()+configFolder+'/**/*config.yaml', recursive=True)
        xlFiles = glob(os.getcwd()+configFolder+'/**/*config.xlsx', recursive=True)
    else:
        yamlFiles = glob(os.getcwd()+configFolder+'/./*config.yaml', recursive=False)
        xlFiles = glob(os.getcwd()+configFolder+'/./*config.xlsx', recursive=True)

    yamlFiles = [file.replace(os.getcwd(), '').lstrip('/\\') for file in yamlFiles]
    xlFiles = [file.replace(os.getcwd(), '').lstrip('/\\') for file in xlFiles]
    xlFiles = [file for file in xlFiles if '~' not in file]

    if yamlFiles or xlFiles:
        print(f'Loading config files: {yamlFiles+xlFiles}')
    else:
        configFile = 'config.yaml'
        func_dir_path = '/'.join(os.path.abspath(inspect.getfile(import_config)).split('\\')[0:-1])
        print(f"""There doesn't appear to be a config file in the supplied folder. No config was imported""")

    config = {}
    for file in yamlFiles:
        print(f"file: {file}")
        with open(file, encoding='utf8') as f:
            try:
                config.update(yaml.load(f, Loader=yaml.FullLoader))
            except:
                raise Exception("That didn't work, the bug shown above is likely a bug in your config file")
            f.close()

    for file in xlFiles:
        df = pd.read_excel(file)
        dictName = df.columns[0]
        df.columns = df.iloc[0 ,:]
        df = df.iloc[1: ,:]
        config.update({dictName: df.T.to_dict()})

    return config

def getFiles(path='*', recursive=False, fileTypes=['']):
    """
    Get list of all files in a supplied path. Can pass file types  

    **Parameters:**  
    > **path: *string, default: empty***  
    >> Pass a relative or absolute path

    > **recursive: *bool, default: False***  
    >> If True search recursively, meaning it will search the folder supplied and any subfolders.

    > **fileTypes: *list, default: empty list***  
    >> Example: ['.xlsx', '.xls']

    <a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ">Click here for more info</a>

    **Returns:**  
    > **list**  
    """
    files = []
    for fileType in fileTypes:
        files.extend(glob(path+fileType, recursive=recursive))

    return list(set(files))

def getExcelDFs(path='*', recursive=False, verbose=False,):
    """
    Import all Excel files from a path into a list of DataFrames  

    **Parameters:**
    > **path: *string, default: "\*"***  
    >> Pass a relative or absolute path

    > **recursive: *bool, default: False***  
    >> If True search recursively, meaning it will search the folder supplied and any subfolders.

    > **verbose: *bool, default: False***  
    >> If True prints each file as it's being imported.

    **Returns:**  
    > **list of DataFrames**  
    """
    fileTypes = ['.xlsx', '.xlsm' , '.xls',]
    files = getFiles(path=path, recursive=recursive, fileTypes=fileTypes)

    if verbose:
        print(f'File list:\n{files}\n')

    dfList = []
    for file in files:
        if verbose:
            print(f'Importing file: {file}')
        chunk = pd.read_excel(file,)
        dfList.append(chunk)
    return dfList

def getCSVDFs(path='*', recursive=False, verbose=False,):
    """
    Import all CSV files from a path into a list of DataFrames  

    **Parameters:**
    > **path: *string, default: "\*"***  
    >> Pass a relative or absolute path

    > **recursive: *bool, default: False***  
    >> If True search recursively, meaning it will search the folder supplied and any subfolders.

    > **verbose: *bool, default: False***  
    >> If True prints each file as it's being imported.

    **Returns:**  
    > **list of DataFrames**  
    """
    fileTypes = ['.csv',]
    files = getFiles(path=path, recursive=recursive, fileTypes=fileTypes)

    if verbose:
        print(f'File list:\n{files}\n')

    dfList = []
    for file in files:
        if verbose:
            print(f'Importing file: {file}')
        chunk = pd.read_csv(file,)
        dfList.append(chunk)
    return dfList

def formatData(wb_name, sheet='Sheet1'):
    """
    This will format an outputted excel file so it doesn't make your eyes bleed.  
    Most useful for outputting DataFrames to Excel.  
    Stole it from StackOverflow. It's not super optimal but it's concise which I like.

    **Parameters:**  
    > **wb_name: *str, Required***  
    >> The name of the file. Can be relative and prolly absolute

    > **sheet: *string, default: "Sheet1"*** 
    >> The name of the sheet. Leave blank if you didn't rename the sheet and it's the first/only one in the workbook.

    **Returns:**  
    > **None**
    """
    wb = openpyxl.load_workbook(wb_name)
    ws = wb[sheet]
    
    dim_holder = DimensionHolder(worksheet=ws)
    
    for col in range(ws.min_column, ws.max_column + 1):
        dim_holder[get_column_letter(col)] = ColumnDimension(ws, min=col, max=col, width=19)
    
    ws.column_dimensions = dim_holder

    for row in ws.iter_rows():
        for cell in row:      
            cell.alignment =  cell.alignment.copy(wrapText=True)
        break # Oof lol, a break in production. Somebody bonk this guy

    wb.save(wb_name)
    return

def save2xl(df, file='', sheet='Data', startCell=[3, 2], table=True, visible=False):
    import xlwings as xw
    """
    IN DEVELOPMENT, PROBABLY WILL NOT WORK  

    Saves a DataFrame to an excel file  
     
    It will either overwrite the sheet in an existing file or create a new one  

    Accepts relative or absolute paths  
    """
    if file:
        xw.Book(file).sheets[sheet]
    else:
        xw.Book().sheets[sheet]
    
    #     Clear Filters
    if sheet.api.AutoFilter:
        sheet.api.AutoFilter.ShowAllData()

    #get the number of columns/rows the query has
    queryCols, queryRows = createDF(sheet).shape
    print(queryCols)
#     queryRows = createDF(sheet).shape[0]
    #if queryCols is less than the # of columns the Python makes, we'll insert those columns as blanks and then paset the Python overtop.
    if (df.shape[1] > queryCols):
        for col in range(queryCols+2, df.shape[1]+2):
            sheet.api.Columns(queryCols+2).Insert()
    
    #Paste the treated DataFrame into excel
    sheet.range(startCell).expand('table').options(index=True, header=True, empty="0").value = df  

    sht = xw.Book(fileOut).sheets['Data']
    # Put an if here being like: If it's a timestamp then format it nicely as a timeseries
    return
