import sqlite3
from sqlite3 import Error
import collections
import pandas as pd
import requests
import json
from datetime import datetime, timedelta

def create_db(db_file: str) -> None:
    """
    Create an SQLite database if none exists.  
    Does not open a connection.
    
    **Parameters:**
    > **db_file:** *string, required*  
    >> The path to where the db will be created. Can be relative or absolute path. 

    **Returns:**  
    > **None**
    """
        
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def create_conn(db_file: str) -> sqlite3.Connection:
    """
    Create a connection (conn) to a SQLite database.  
    
    **Parameters:**
    > **db_file:** *string, required*  
    >> The path to the db. Can be relative or absolute path. 

    **Returns:**  
    > **SQLite Connection**
    """
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)

    return conn


##### TEST WHETHERVcreate_table IS DEPRECATED AFTER upsert

# def create_table(conn, table_name, df):
#     """
#     Create a table in a SQLite database if none exists.  
    
#     **Parameters:**
#     > **db_file:** *string, required*  
#     >> The path to where the db will be created. Can be relative or absolute path. 

#     **Returns:**  
#     > **None**
#     """
#     df = df.copy()
#     df.reset_index(inplace=True)
#     queryStr = f"CREATE TABLE IF NOT EXISTS {table_name} (`index` integer primary key,"
#     for col in df.columns:
#         colName = "_".join(col.split(" "))
#         dtype = df[col].dtype

#         if dtype == "object":
#             queryStr = queryStr + f"{colName} text not null,"
#         elif dtype == "datetime64[ns]":
#             queryStr = queryStr + f"{colName} text not null,"
#         elif dtype == "float64":
#             queryStr = queryStr + f"{colName} float not null,"
#         elif dtype == "float64":
#             queryStr = queryStr + f"{colName} float not null,"
#         else:
#             raise Exception(f"There is no case for dtype {dtype}, please add one")
#     queryStr = queryStr.removesuffix(",") + ");"

#     sql_create_features_table = queryStr
#     try:
#         conn.execute(sql_create_features_table)
#     except Error as e:
#         print(e)
########

def upsert(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame, primary_key: list | str='id', PK_type: str='INTEGER', verbose: bool = False) -> None:
    """
    Uploads data into a new or existing SQL table.  
    If data exists it won't replace it, and if data doesn't exist it will inject it in.  
    Can create new columns, but not new Foreign or Primary Keys

    **Parameters:**
    > **conn:** *SQLite Connection, required*  
    >> The connection to the SQLite db  

    > **table_name:** *string, required*  
    >> Name of the new/existing table. 

    > **df:** *DataFrame, required*
    >> pd.DataFrame containing all data to be loaded. Must contain the primary key somewhere, idk if it has to be in the beginning 

    > **primary_key:** *String, default: `'id'`*
    >> primary key of the SQL table. pretty sure this is required cause the funcion will break otherwise. 
    Not sure if this should be changed.

    > **PK_type:** *String or List, default: `'INTEGER'`*
    >> Pass in the primary key(s), which can be a string or multi-column list

    **Returns:** 
    > **None**
    """

    # The primary key needs to be either a string OR a list, so we have to force it to a list here.
    if type(primary_key) is str:
        PKs = [primary_key]
    else:
        PKs = primary_key
    # PKs = [f'"{key}"' for key in PKs]

    cur = conn.cursor()
    pragma = pd.read_sql_query(f"PRAGMA table_info({table_name})", conn)
    
    # Create the table with to_sql if it doesn't exist
    if pragma.empty:
        print(PKs)
        print()
        df.to_sql(table_name, conn, if_exists='replace', dtype={PK: f'{PK_type} PRIMARY KEY' for PK in PKs}, index=False)
        print(f'There was no table named {table_name}. One was created')
        return
    
    # Create the temp transfer table
    df.to_sql('transfer_tbl', conn, if_exists='replace', dtype={PK: f'{PK_type} PRIMARY KEY' for PK in PKs}, index=False)
    transfer_pragma = pd.read_sql_query(f"PRAGMA table_info(transfer_tbl)", conn)

    # Add new columns if they don't exist
    # keep in mind you can't add new primary key columns! Use add_primary_key()
    new_cols = [col for col in transfer_pragma.name if col not in list(pragma.name)]
    for col in new_cols:
        sql = f"""
            ALTER TABLE {table_name}
            ADD "{col}" {transfer_pragma.loc[transfer_pragma.name == col, 'type'][0]};
        """
        cur.execute(sql)

    for _, row in df.iterrows():
        row_dict = row.to_dict()

        # Cols and vals are set in different places, it make sense to separate them
        columns = list(row_dict.keys())
        values = list(row_dict.values())

    # Need to add the double quotes back to the columns to keep them separate in sql queries
    PKs = [f'"{key}"' for key in PKs]
    sql = f"""
        INSERT INTO {table_name}({', '.join([f'"{col}"' for col in columns])})
        SELECT {', '.join([f'"{col}"' for col in columns])}
        FROM transfer_tbl
        WHERE true
        ON CONFLICT({', '.join(PKs)})
        DO UPDATE SET
        {', '.join([f'"{col}"=excluded."{col}"' for col in columns])}"""
    if verbose:
        print(sql)
    cur.execute(sql)

    # Drop the transfer table once we're done with it
    cur.execute("DROP TABLE IF EXISTS transfer_tbl;")
    # I'm like pretty sure you can commit all this at the end. There were no issues in testing. I'm guessing it's also faster.
    conn.commit()
    return

def load(conn: sqlite3.Connection, table_name: str, df: pd.DataFrame) -> None:
    """
    Dumly loads a DataFrame into a new or existing table.  
    If it loads into an existing table it will append to the table.  
    If a datetime column is found in the DataFrame it will turn tha into a SQL-readable timestamp and make it the index
    Never mind the fact that SQL has a time format and I just didn't know that when I wrote this 
    This func is definitely useful because upsert takes a long time
    This func is definitely useful because upsert takes a long time

    **Parameters:**
    > **conn:** *SQLite Connection, required*  
    >> The connection to the SQLite db  

    > **table_name:** *string, required*  
    >> Name of the new/existing table  

    > **df:** *DataFrame, required*
    >> Pandas DataFrame containing all data to be loaded. Must contain the primary key somewhere, idk if it has to be in the beginning  

    **Returns:** 
    > **None**
    """
    df = df.copy()
    df.columns = ["_".join(col.split(" ")) for col in df.columns]
              
    for col in df.columns:
        if df[col].dtype == 'datetime64[ns]':
            df[col] = ts2str(df[col])
        # elif df[col].dtype == 'floa
        
    df.reset_index(inplace=True)
    df.to_sql(table_name, conn, if_exists='append', index=True)
    return
        
def dedupe(conn: sqlite3.Connection, dedupe_cols: list, table_name: str) -> None:
    """
    Do not use.
    This function de-duplicates rows in a SQLite database but I'm pretty sure it has a bug somewhere and idk where it is.  
    Download the entire db and deduplicate it with pandas.  

    At some point Luca will change this to a funcion that takes your entire table into pandas chunks and dedupes the from there but he hasn't figure that out.  
    If you need this functionality with chunking (your db would have to be like 10+ GB), then let Luca know. 
    """

    dedupe_sql = f"""
    DELETE FROM {table_name}
    WHERE ROWID NOT IN (
        SELECT  min(ROWID)
        FROM    {table_name}
        GROUP BY
            {', '.join(dedupe_cols).removesuffix(',')}
    )"""
    cur = conn.cursor()
    cur.execute(dedupe_sql)
    conn.commit()
    return
    
def ts2str(col: pd.Series) -> pd.Series:
    """
    Turn a pd.datetime(I'm pretty sure) into a SQLite-readable string.  
    Most SQL flvaours have timestamps data types but sqlite3 does not.  
    
    **Parameters:**
    > **col:** *pd.Series, required*  
    >> The column object to be changed into a string. Pretty sure you can send a Series or DataFrame

    **Returns:**  
    > **pd.Series**
    """
    col = col.dt.strftime("%Y-%m-%d %H-%M")
    return col

def getNasaWeather(plant: str, dates: list = [datetime.today()-timedelta(days=365), datetime.today()], 
                   params=['T2M', 'RH2M'], type='Daily', units='C', 
                   db_loc="Z:\Data Governance\Databases\leidos_meta.db") -> pd.DataFrame:
    """
    Get the weather at a given plant from Nasa.  
    Assumes said plant is in the db.  

    <a href="https://power.larc.nasa.gov/#resources">Parameters can be found here</a>  
    Check the Resources > Parameter Dictionary dropdown  

    **Parameters:**  
    > **plant:** *str, required*  
    >> The name of the plant in the database  

    > **dates:** *list of dates, default: `[today-timedelta(days=365), today()]`*  
    >> Follows format: [start_date, end_date]. Pretty sure it can be a python date, a pd date, but not a string  

    > **params:** *list of strs, default: `['T2M', 'RH2M']`*  
    >> The type of data you want to receive from NASA. These can be found in the resources section of the Power LARC website.
    default: [temperature_at_2_meters, relative_humidity_at_2_meters]  

    > **type:** *String, default: `'Daily'`*  
    >> The frequency of the data. Pretty sure the options are `Daily` and `Hourly`

    > **units:** *String, default: `'C'`*  
    >> The units for temperatures. Only works for T2M right now. Can be `'C'` or `'F'`  

    > **db_loc:** *String, default: `"Z:\Data Governance\Databases\leidos_meta.db"`*  
    >> Path to the database with plant coordinates

    **Returns:**  
    > **pd.DataFrame**
    """

    query = f"""
    SELECT plant, latitude, longitude
    FROM plants;
    """
    conn = create_conn(db_loc)
    df = pd.read_sql(query, conn)
    df = df.loc[df['plant'] == plant, :].set_index('plant', drop=True)

    lat = df.loc[df.index == plant, 'latitude'][0]
    long = df.loc[df.index == plant, 'longitude'][0]

    requestURL = f"""
    https://power.larc.nasa.gov/api/temporal/{type.lower()}/point?
    parameters={','.join(params)}&community=RE&
    longitude={long}&latitude={lat}
    &start={dates[0].strftime('%Y%m%d')}
    &end={dates[1].strftime('%Y%m%d')}&format=JSON
    """.replace('\n', '').replace(' ', '')
    
    response = requests.get(url=requestURL, verify=True, timeout=30.00)
    if response.status_code == 404:
        raise Exception("404 error, the passed url was prolly not valid")
    # return response
    content = json.loads(response.content.decode('utf-8'))

    dfWeather = pd.DataFrame(content['properties']['parameter'])
    if type.lower() == 'daily':
        dfWeather.index = pd.to_datetime(dfWeather.index)
    elif type.lower() == 'hourly':
        dfWeather.index = pd.to_datetime(dfWeather.index, format="%Y%m%d%H")

    dfWeather.index.name = 'Timestamp'

    if units.lower() =='f':
        dfWeather['Temp (F)'] = dfWeather['T2M']*9/5+32
    else:
        dfWeather['Temp (C)'] = dfWeather['T2M']

    dfWeather.drop('T2M', axis=1, inplace=True)

    dfWeather[dfWeather == -999] = 0

    return dfWeather