import pandas as pd
import numpy as np

def get100LowestValues(df, minVal=1):
    """
Gets the 100 lowest values from each column provided in df
It will filter anything lower than minVal, so it'll ignore negative or blank values if minVal=1

Parameters:
df: DataFrame, required
minVal: int, default: 1  

Returns: DataFrame
    """    
    colList = []
    for col in df.columns:
        colSeries = df.loc[df[col] >= minVal, col].sort_values().head(100)
        colList.append(colSeries)

    df  = pd.concat(colList, axis=1)   
    return df

def getNRowAvg(self, rows, ascending):
    return round(self.df.sort_values(self.col, ascending=ascending).reset_index().loc[:rows, self.col].mean(), 0)

def gapAndIsland(dfCol):
    """Should be renamed to gapAndIsland
    takes an np.series data type (ie. a df single column)
    returns the entire column broken up into sections where all the numbers are the same. 
    Good for iterating on an events column or tracking flags. 

    new: dfCol can be df with one column or series
    """
    return np.split(dfCol.squeeze(), np.where(np.diff(dfCol.squeeze()) != 0)[0]+1)

def mergeCloseEvents(events, mergeWithinHours=12, i=1):
    """Merges events that are close so we don't get bunches of events. Not entirely necessary but it makes it cleaner. 
    Recursive function, so it takes each event and calculates if it's within 3600sec of the last event. 
    If so it adds this event to the last event and deletes this event.
    returns the new list of events
    """
    if i >= len(events):
        return events
    
    eventStart = events[i][0]
    eventEnd = events[i][-1]
    lastEventEnd = events[i-1][-1]

    if ((eventStart-lastEventEnd).total_seconds()/3600)<=mergeWithinHours:
        lastEventEnd = eventEnd
        events.pop(i)
        events = mergeCloseEvents(events, i = i)
        
    else:
        mergeCloseEvents(events, i=i+1)
    return events