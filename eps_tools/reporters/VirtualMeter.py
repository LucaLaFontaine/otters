import pandas as pd
import numpy as np
from datetime import timedelta

import re 

class VirtualMeter():
    def __init__(self, df):
        self.df = df
        self.AHUs = {}
        return
    
    def cleanColNamesEMS(self, filterWords=['Feedback ', ' Digital', 'Percentage ',], verbose=False):
        colNames = self.df.columns
        # For each column name, split up the name by instance of '- ' and then take the last instance. 
        colNames = [x.split(' - ')[-1] for x in colNames]

        # Create a big string from the columns and treat them altogether
        x="-".join(colNames)

        # remove one word at a time
        for word in filterWords:
            x=x.replace(word,"")
        x=x.replace('Temperature' , 'Temp')
        x=x.replace('Outside Air Temp' , 'OAT')
        x=x.replace('Running' , 'On')
        x=x.replace('Gen Assy' , 'GA')

        # split up the cols again
        colNames =x.split("-")

        self.df.columns = colNames

        if verbose==True:
            # Display columns
            print(self.df.columns)
        return
    
    def splitEntities(self, identifiers):
        """
        Splits a df into seperate entities (i.e AHUs, chillers, etc) based on a common identifier.  

        Example: if you have a list of tags from AHUs 1-15, all with the prefix 'BIW AHU {number}' you can separate them by ahu number.  

        The func takes the id with '*' as a wildcard and tries each number from 1 - maxNum to get the tags associated to that number.  
        
        There can be missing tag numbers, it'll ignore empty tags.

        Paramters:
        identifiers: list of dictionaries, Required
        > dict format (from above example):
        >>{
        >> 'id': 'BIW AHU *',  
        >> 'maxNum' : '15',  
        >>}

        Returns: 
        list of DataFrames
        """
        df = self.df.copy()
        entities = []
        for identifier in identifiers:
            for i in range(1, identifier['maxNum']+1):
                regex = re.compile(identifier['id'].replace('*', str(i)).lower())
                matches = [colName for colName in df.columns if re.match(regex, colName.lower())]
                if not df.loc[:, matches].empty:
                    entities.append(df.loc[:, matches])

        return entities
    
    def createAHU(self, df, name=''):
        ahu = AHU(self, df, name)
        self.AHUs.update({name:ahu})

        return

class AHU():
    def __init__(self, parent, df, name):
        self.parent = parent
        self.df = df
        self.name = name
        return