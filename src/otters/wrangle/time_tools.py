import pandas as pd
import gc
from math import ceil
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta, MO

def str2dt(df, timeCol='', drop=True, index_name="Timestamp", **datetime_args):
    """
Finds the timestamp in a dataframe, translates it to_datetime, renames it "Timestamp", and sets it as the index
Bumps the index to the first column if it isn't a timestamp

Parameters:
df: DataFrame, required
timeCol: string, Default: empty

Returns: DataFrame
    """
    df = df.copy()
    gc.collect()

    commonNames = ['timestamp', 'Date/Time', 'Date', 'Time']
    names = [timeCol] if timeCol else commonNames
    df.reset_index(inplace=True, drop=drop)
    
    # Get matches with names in the df
    matches = [col for col in set(df.columns) if col.lower() in (name.lower() for name in names)]

    if not matches:
        raise Exception(f"No timestamp columns found.")
    elif len(matches) > 1:
        raise Exception(f"There are multiple possible timestamps in your df, shown here:\n{matches}")
    else:
        df[index_name] = pd.to_datetime(df[matches[0]], **datetime_args)
        df.set_index(df[index_name], drop=True, inplace=True)
        df.drop([index_name, matches[0]], axis=1, inplace=True, errors='ignore')
    return df

def time2timedelta(s, format='%H%M'):
    s = s.copy()
    s = s.squeeze()
    
    s = (pd.to_datetime(s.astype(str).str.zfill(4), format=format))
    s = pd.to_timedelta(s.dt.strftime('%H:%M:%S'))
    return s

def getLastNWeeks(df, n, weekday=0, hour=0, minute=0):
    """
Get the last n weeks of data starting this past 'weekday' where (0=Monday, 6=Sunday)
It's important that the timestamp is already in the index

Parameters:
df: DataFrame, required
n: int, required
weekday: int, Default 0 (0=Monday, 6=Sunday)

Returns: DataFrame
    """
    # Get the last monday as the root of the week. subtract n weeks from there and add weekdays in that week
    # We actually want n+1 because we want the week previous to this one in addition to the days so far of this week.
    dayOne = date.today() + relativedelta(weekday=(MO(-(n+1)))) + timedelta(days=weekday)

    # Get the first row in the the df
    startDatetime = datetime.combine(dayOne, time(hour, minute))
    if isinstance(df, pd.Series):
        df = df.to_frame()

    df = df.loc[df.index >= startDatetime, :]
    return df

def overlayPast(df, nDays):
    """
    Run if you want to overlay last year's consumption on the graph. Controlled in the config.
    Currently the figure is not supplied/returned, that'll have to change for abstraction
    """
    dfPast = df.copy()
    dfPast.index = df.index+pd.Timedelta(days=nDays)
    dfPast.columns = dfPast.columns+'_past'
    # df = df.join(dfPast, how='outer', rsuffix='_past')

    return dfPast


def selectiveResample(df, freq, meanCols, sumCols, colOrder=None):

    df = df.copy()

    dfMean = df.loc[:, meanCols].resample(freq).mean()
    dfSum = df.loc[:, sumCols].resample(freq).sum()

    df = pd.concat([dfMean, dfSum], axis=1)

    if colOrder:
        df = df[colOrder] 
        
    return df
