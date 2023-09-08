import pandas as pd
import yaml
import os
from glob import glob
import inspect


class DataLoader:
    def __init__(self, configFile='config.yaml'):

        self.config = self.import_config() 

        return
    
    def import_config(self, configFolder=''):
        """
Import all config files from the supplied folder. Defaults to the root folder

Any files ending in 'config.yaml' will be treated. So you could have a formatting config called 'format.config.yaml'

Paramters:
    configFolder: string, default: empty
        """

        # Load any config files
        files = glob(os.getcwd()+configFolder+'/**/*config.yaml', recursive=True)
        files = [file.replace(os.getcwd(), '').lstrip('/\\') for file in files]
        # print(configFolder+'/**/*config.yaml')

        if files:
            print(f'Loading config files: {files}')
        else:
            configFile = 'config.yaml'
            self.func_dir_path = '/'.join(os.path.abspath(inspect.getfile(self.import_config)).split('\\')[0:-1])
            print(f"""There doesn't appear to be a config file in the root of your folder. \nLoading the default config from here:\n{self.func_dir_path}/{configFile}""")
            files.append(f'{self.func_dir_path}/{configFile}')

        config = {}
        for file in files:
            with open(file) as f:
                config.update(yaml.load(f, Loader=yaml.FullLoader))
                f.close()

        return config
    
    def getFiles(self, path='', recursive=False, fileTypes=[]):
        """
Get list of all files in a supplied path. Can pass file types

Paramters:
    path: string, default: empty
    recursive: bool, default: False

Returns: list
        """
        if path:
            path = path + '/'

        files = []
        for fileType in fileTypes:
            # Kinda lame but we get files in the root of the supplies folder and then any below if recursive=True
            files.extend(glob(path+fileType))

            if recursive == True:
                recFiles = glob(os.getcwd()+path+'/**/*'+fileType, recursive=recursive)
                files.extend([file.replace(os.getcwd(), '').lstrip('/\\') for file in recFiles])

            #  files.extend(glob(path'/**/*'+fileType, recursive=recursive))

        return list(set(files))
    
    def getExcelFiles(self, path='', recursive=False, **read_excel_params):
        """
Import all Excel files from a path into a DataFrame

If concatenating on index (0), frames will be joined one under the other
If on columns (1), key must be passed to join frames on. Joined one next to the other with a common index (indexCol)

Paramters:
    path: string, default: empty
    recursive: bool, default: False
    axis: int (index=0, col=1), default: 0
    indexCol: string, default: empty

Returns: DataFrame
        """
        fileTypes = ['xlsx', 'xlsm' , 'xls',]
        files = self.getFiles(path=path, recursive=recursive, fileTypes=fileTypes)

        dfList = []
        for file in files:
            chunk = pd.read_excel(file, read_excel_params)
            chunk.set_index('Date/Time', inplace=True)
            dfList.append(chunk)

        df = pd.concat(dfList, axis=1)
        return


    


if __name__ == "__main__":
    loader = DataLoader()
    config = loader.import_config()
    print(config)
    # return