import pandas as pd
import numpy as np

def gapAndIsland(dfCol):
    """
    Takes an np.series data type (ie. a df single column)
    returns the entire column broken up into sections where all the numbers are the same. 
    Good for iterating on an events column or tracking flags. 

    new: dfCol can be df with one column or series

    **Parameters:**  
    > **dfCol: *a single df column or series, Required***  

    **Returns:**  
    > **Series**
    """
    return np.split(dfCol.squeeze(), np.where(np.diff(dfCol.squeeze()) != 0)[0]+1)

def mergeCloseEvents(events, mergeWithinHours=12, i=1):
    """
    Merges events that are close so we don't get bunches of events. Not entirely necessary but it makes it cleaner. 
    Recursive function, so it takes each event and calculates if it's within "mergeWithinHours" (in hours) of the last event. 
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

def compare_lists(strings, patterns):
    """
    IN DEVELOPMENT
    I orifinally used this in Agg Data fro ABI to get all the valid cols from a list in a df. it's easier to just show the code:  
    `sumCols = [col for col in df.columns if compareList(list(col), sumCols)]`  

    I think this would have ustility in matching a combo of strings against a series, but I didn't use it that way. 

    **Returns:**  
    > **boolean**  
    """
    for string in strings:
        for pattern in patterns:
            if pattern in string:
                return True
    return False 



def find_strs(S):
    """
    Find all the unique strings in a series.  
    Usefull for finding string errors in an otherwise numeric column

    Normally you would want to search all the string columns in a df. YOu can jsut loop over all the columns with the type `object`  
    
    **Parameters:**  
    > **S: *Series, Required***  

    **Returns:**  
    > **list**  
    """
    num_mask = pd.to_numeric(S, errors='coerce').isnull()
    if num_mask.sum() > 0:
        # return num_mask.loc[num_mask == True]
        return list(S[num_mask == True].unique())
    
def two_letter_month_to_number(date):
    """Undocumented  
    Source: C:\Users\LucaLafontaine\AKONOVIA\EMO - Documents\002-ALCOVI\22-673 VSL - Ajustement Lufa\1-Intrant\Factures\Énergir\read_JCI_data.ipynb
    """
    month_mappings = {
        "JA":"01",
        "FE":"02",
        "MR":"03",
        "AL":"04",
        "MA":"05",
        "JN":"06",
        "JL":"07",
        "AU":"08",
        "SE":"09",
        "OC":"10",
        "NO":"11",
        "DE":"12",
    }
    
    for month, number in month_mappings.items():
        date = date.replace(month, number)
    
    return date