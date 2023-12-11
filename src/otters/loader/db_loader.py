import sqlite3
from sqlite3 import Error
import collections
import pandas as pd
import requests
import json



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
##### It 

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

def upsert(conn, table_name, df, primary_key='id'):
    
    # Create the table with to_sql if it doesn't exist
    if pd.read_sql_query(f"PRAGMA table_info({table_name})", conn).empty:
        df.to_sql(table_name, conn, if_exists='replace', dtype={primary_key: 'INTEGER PRIMARY KEY'}, index=False)
        print(f'There was no table named {table_name}. One was created')
        return
    
    # Create the temp transfer table
    df.to_sql('transfer_tbl', conn, if_exists='replace', dtype={primary_key: 'INTEGER PRIMARY KEY'}, index=False)

    cur = conn.cursor()
    for _, row in df.iterrows():
        row_dict = row.to_dict()

        # Cols and vals are set in different places, it make sense to separate them
        columns = list(row_dict.keys())
        values = list(row_dict.values())

        sql = f"""
        INSERT INTO {table_name}({', '.join([f'"{col}"' for col in columns])})
            SELECT {', '.join([f'"{col}"' for col in columns])}
            FROM transfer_tbl
            WHERE true
            ON CONFLICT("Project No")
            DO UPDATE SET
            {', '.join([f'"{col}"=excluded."{col}"' for col in columns])}"""
        cur.execute(sql)

    # Drop the transfer table once we're done with it
    cur.execute("DROP TABLE IF EXISTS transfer_tbl;")
    # I'm like pretty sure you can commit all this at the end. There were no issues in testing. I'm guessing it's also faster.
    conn.commit()
    return


def load(conn, table_name, df):
    """
    Dumly loads a DataFrame into a new or existing table.  
    If it loads into an existing table it will append to the table.  
    If a datetime column is found in the DataFrame it will turn tha into a SQL-readable timestamp and make it the index
    Never mind the fact that SQL has a time format and I just didn't know that when I wrote this 

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
        
                
    cur = conn.cursor()
    df.reset_index(inplace=True)
    df.to_sql(table_name, conn, if_exists='append', index=True)
        
def dedupe(conn, dedupe_cols, table_name):
    """
    This function de-duplicates rows in a SQLite database but I'm pretty sure it has a bug somewhere and idk where it is.  
    Download the entire db and deduplicate it with pandas.  
    Don't flatter yourself into thinking you have enough data to warrant chunking your dataset.   
    You don't.  
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
    
    
def ts2str(col):
    """
    This will break if you pass a column that is a datetime[64]. make type ambivalent
    """
    col = col.dt.strftime("%Y-%m-%d %H-%M")
    return col


def getNasaWeather(plant, dates='urmom', params=['T2M', 'RH2M'], type='Daily', units='C', db_loc="Z:\Data Governance\Databases\leidos_meta.db"):
    """
    Get the weather at a given plant from Nasa  

    Assumes said plant is in the DB

    <a href="https://power.larc.nasa.gov/#resources">Parameters can be found here</a>  
    Check the Resources > Parameter Dictionary dropdown
    """
    query = f"""SELECT plant, latitude, longitude
    FROM plants;
    """
    conn = create_conn(db_loc)
    df = read_sql(conn, query)
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

    if units =='F':
        dfWeather['Temp (F)'] = dfWeather['T2M']*9/5+32
    else:
        dfWeather['Temp (C)'] = dfWeather['T2M']

    dfWeather.drop('T2M', axis=1, inplace=True)

    dfWeather[dfWeather == -999] = 0

    return dfWeather