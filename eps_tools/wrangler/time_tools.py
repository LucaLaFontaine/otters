import pandas as pd
import gc
from datetime import datetime, timedelta, date, time
from dateutil.relativedelta import relativedelta, MO

def str2dt(df, timeCol='', drop=False, **datetime_args):
    """
Finds the timestamp in a dataframe, translates it to_datetime, renames it "Timestamp", and sets it as the index
Bumps the index to the first column if it isn't a timestamp

Parameters:
df: DataFrame, required
timeCol: string, Default: empty
    """
    df = df.copy()
    gc.collect()

    commonNames = ['timestamp', 'Timestamp', 'Date/Time', 'Date']
    names = [timeCol] if timeCol else commonNames
    defaultName = 'Timestamp' # Rename cols to this
    df.reset_index(inplace=True, drop=drop)
    
    # Get matches with names in the df
    matches = list(set(df.columns) & set(names))

    if not matches:
        raise Exception(f"No timestamp columns found.")
    elif len(matches) > 1:
        raise Exception(f"There are multiple possible timestamps in your df, shown here:\n{matches}")
    else:
        df[defaultName] = pd.to_datetime(df[matches[0]], **datetime_args)
        df.set_index(df[defaultName], drop=True, inplace=True)
        df.drop([defaultName, matches[0]], axis=1, inplace=True, errors='ignore')
    return df


def getLastNWeeks(df, n, weekday=0, hour=0, minute=0):
    """
Get the last n weeks of data starting this past 'weekday' where (0=Monday, 6=Sunday)
It's import that the timestamp is already in the index

Parameters:
df: DataFrame, required
n: int, required
weekday: int, Default 0 (0=Monday, 6=Sunday)
    """
    # Get the last monday as the root of the week. subtract n weeks from there and add weekdays in that week
    dayOne = date.today() + relativedelta(weekday=(MO(-(n+1)))) + timedelta(days=weekday)

    # Get the first row in the the df
    startDatetime = datetime.combine(dayOne, time(hour, minute))
    
    df = df.loc[df.index >= startDatetime, :]
    return df