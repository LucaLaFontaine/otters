import pandas as pd
import numpy as np
from datetime import timedelta
import gc
import re 

class VirtualMeter:
    def __init__(self, df):
        self.df = df
        self.AHUs = {}
    
    def cleanColNamesEMS(self, filterWords=[], index=-1, identifier=' - ', verbose=False):
        df = self.df.copy()
        colNames = df.columns
        # For each column name, split up the name by instance of ' - ' and then take the last instance. 
        colNames = [' - '.join(re.split('\s-\s', x)[-2:]) for x in colNames]
        # print(colNames)
        # Create a big string from the columns and treat them altogether
        x=".".join(colNames)

        # remove one word at a time
        for word in filterWords:
            x=x.replace(word,"")
        x=x.replace('Temperature' , 'Temp')
        x=x.replace('Outside Air Temp' , 'OAT')
        x=x.replace('Running' , 'On')
        x=x.replace('Gen Assy' , 'GA')
        x=x.replace('Percentage' , '%')
            # x=x.replace(' °F' , '')
        x=x.replace(r'% %' , '%')

        # split up the cols again
        colNames =x.split(".")
        # print(colNames)
        df.columns = colNames

        if verbose==True:
            # Display columns
            print(df.columns)

        self.df = df.copy()
        gc.collect()
        return


    def splitEntities(self, identifiers, paddingDigits=False):
        """
        Splits a df into seperate entities (i.e AHUs, chillers, etc) based on a common identifier.  

        Example: if you have a list of tags from AHUs 1-15, all with the prefix 'BIW AHU {number}' you can separate them by ahu number.  

        The func takes the id with '*' as a wildcard and tries each number from 1 - maxNum to get the tags associated to that number. 
        There should be a trailing space on the identifier as that's the complete term. 

        There can be missing tag numbers, it'll ignore empty tags.

        **Parameters:**  
        >**identifiers:** *list of dictionaries, Required*

        >**paddingDigits:** *bool, default:* `False`  
        >>Defines whether the numbers in the tags have 0-padding. Eg: 01, 02, etc.

        **Returns:**  
        >**list of DataFrames**

        Example:
        ```
        identifiers = [
            {'id':'Biw Ahu * ', 'maxNum':17} 
        ]
        ```
        """
        df = self.df.copy()
        entities = []
        for identifier in identifiers:
            for i in range(1, identifier['maxNum']+1):
                if paddingDigits != False:
                    regex = re.compile(identifier['id'].replace('*', str(i).zfill(paddingDigits)).lower())
                else:
                    regex = re.compile(identifier['id'].replace('*', str(i)).lower())
                matches = [colName for colName in df.columns if re.search(regex, colName.lower())]
                # Matches
                if not df.loc[:, matches].empty:
                    entities.append(df.loc[:, matches])

        return entities
    
    def createAHU(self, df, name=''):
        ahu = AHU(self, df, name)
        self.AHUs.update({name:ahu})

        return

class AHU():
    """
    Urmom
    """
    def __init__(self, parent, df, name):
        self.parent = parent
        self.df = df
        self.name = name
        return