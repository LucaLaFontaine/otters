import pandas as pd
import numpy as np
from otters.wrangle.time_tools import str2dt

def get100LowestValues(df, minVal=1):
    """
Gets the 100 lowest values from each column provided in df
It will filter anything lower than minVal, so it'll ignore negative or blank values if minVal=1

Parameters:
df: DataFrame, required
minVal: int, default: 1  

Returns: DataFrame
    """    
    # force the df to a DataFrame
    df = pd.DataFrame(df)
    colList = []
    for col in df.columns:
        colSeries = df.loc[df[col] >= minVal, col].sort_values().head(100)
        colList.append(colSeries)

    df  = pd.concat(colList, axis=1)   
    return df

def getNRowAvg(df, rows, ascending):
    # should be a series
    return round(df.sort_values(ascending=ascending).reset_index().loc[:rows].mean())

def gapAndIsland(dfCol):
    """
    Takes an np.series data type (ie. a df single column)
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
        events[i-1][-1] = events[i][-1]
        events.pop(i)
        events = mergeCloseEvents(events, i = i)
        
    else:
        mergeCloseEvents(events, i=i+1)
    return events

def extendTags(tags,  maxNum, exampleNum=1, missing=[],):
    """
    Use to extend a list of tags (usually tags in an EMS or files) for one grouping into many
    Say you have 5 tags each for 10 AHUs that you have to pull. Use this to generate all 50 tags from the first 5

    Parameters:
    tags: list, Required
    maxNum: int, Required, largest number in the set
    exampleNum: int, Default: 1, number you're replacing in the exmple set
    missing: list, Default: empty, any missing numbers in the set
    """
    extendedTags = []
    for i in range(1, maxNum+1):
        for j, tag in enumerate(tags):
            if i in missing:
                continue
            if tag.find(str(i)):
                extendedTags.append(tag.replace(str(exampleNum), str(i)))     
    return extendedTags

def merge_dfs(dfs):
    """
    Merge 2 or more dfs where you have some overlapping data.  
    Keeps the values randomly as far as I can tell, though it drops nan values

    **Parameters:**  
    > **dfs: *list of DataFrames/Series, Required***  
    >> It will take any number of dfs

    **Returns:**  
    > **Merged DataFrame**  
    """
    # Create the set of all columns in the list of dataframes
    allCols = []
    [allCols.extend(list(df.columns)) for df in dfs]
    allCols = list(set(allCols))

    # dfMerged = pd.DataFrame()
    mergedCols = []

    # for each column in allCols find the dfs with that columns and append them, sort the index (there are dupes)
    # then keep the first index. This will leave out the nans that sink to the bottom.
    # append each column to a list to concat into a def later 
    for col in allCols:
        mergedCol = pd.concat([df[col] for df in dfs if col in df.columns], ).sort_values()
        mergedCols.append(mergedCol[~mergedCol.index.duplicated(keep="first")])

    dfMerged = pd.concat(mergedCols, axis=1)
    return dfMerged
    

def merge_df_cols(df):
    # Takes the df and lines up all the same column one of top of each other. 
    # makes a second index with the count of like which instance of the column it is. 
        # is this the first instance of the column? the second? etc.
        # This means the index is now technically unique
    dfStack = (
        df.set_axis(
            pd.MultiIndex.from_arrays([
                df.columns,
                df.groupby(level=0, axis=1).cumcount()
            ]), 
            axis=1,
        )
        .stack(level=1)
    )

    # You'd think we could just sort index and drop the dupes but this will cause us to lose data. 
        # The columns aren't eindividually sorted with nulls first or last
    # So here we split the df by instance number. we can then update one instance into another in the next step. 
    dfInstances = []
    for i in range(0, dfStack.index.get_level_values(1).max()+1):
        dfInstances.append(dfStack.loc[dfStack.index.get_level_values(1) == i, :].droplevel(1))

    # combine_first essentially updates a df with another df, keeping actual values in favour of nulls
    # So here we just repeatedly update the new df (dfMerged) with each successive instance, keeping values in place of nulls. 
    # Keep in mind that this will keep later instances over newer ones. I think this is a good approach
        # This can be reversed by updating the instance wityh the merged instead. 
    # This will probably treat 0s as real values and not replace them which I don't love. 
    dfMerged = pd.DataFrame()
    for dfInstance in dfInstances:
        dfMerged = dfMerged.combine_first(dfInstance)

    return dfMerged

def extractFISTags(df):
    """
    Take a raw FIS data stream from a df and pivot it to a table. Outputs 2 dfs: the data and the units.  

    **Parameters:**  
    > **df: *DataFrame, Required***  
    >> Should be the raw, concatenated datastream from the raw files. 

    **Returns:**  
    > **dfAna**   
    >> Should be the raw, concatenated datastream from the raw files.   
    
    > **dfUnits**
    >> A df with just the units of the columns in dfAna
    """
    df = df.copy()
    # Remove unnamed columns
    df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
    # Reset the index
    df.reset_index(drop=True, inplace=True)
    # fill down the machine name so it applies to each row. This is essentially the column name
    df['Machine Name'].ffill(inplace=True)
    # "Sample Time" is the time column. Make it the index
    df = str2dt(df, timeCol='Sample Time', drop=True)

    # It's important to dedupe the timestamp/machine name combo before pivoting
    df = df.reset_index().drop_duplicates(['Timestamp', 'Machine Name']).set_index('Timestamp')
    dfAna = df.pivot(columns='Machine Name', values='Actual Value').dropna()
    dfAna.columns = [col.split(':: : ')[1].strip(' -') for col in dfAna.columns]

    # Now get the units
    dfUnits = df.pivot(columns='Machine Name', values='Units').dropna().T.iloc[:, 0]
    dfUnits.name = 'Units'

    return dfAna, dfUnits