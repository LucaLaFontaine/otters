def get100LowestValues(df, minVal=0):
    """ExPS Exclusive
    Gets the 100 lowest values from all the data provided in df
    It will filter anything lower than minVal, so it'll ignore negative or blank values if minVal=0
    The timestamp must be the index
    returns a df containing rows with a lowest val from one of the columns
    """
    # Delete dupes. Important that timestamp is the index. This will eventually kill me, I can feel it in my bones
    df = df[~df.index.duplicated(keep='first')]
    
    keepIndex = []
    # We get the lowest 100 for every column and add them to a list
    for col in df.columns:
        keepIndex.extend(df.sort_values(col).loc[df[col] > minVal, :].index[0:100])
        
    # Set just means we drop dupes
    keepIndex = list(set(keepIndex))
    
    # Then we keep rows that contain a lowest value from one of the columns
    df = df.loc[keepIndex, :]
    
    return df