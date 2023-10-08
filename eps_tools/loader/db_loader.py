import sqlite3
from sqlite3 import Error
import collections
import pandas as pd
import requests
import json

def create_db(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        print(e)
    finally:
        if conn:
            conn.close()


def create_conn(db_file):
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)

    return conn


def create_table(conn, table_name, df):
    df = df.copy()
    df.reset_index(inplace=True)
    queryStr = f"CREATE TABLE IF NOT EXISTS {table_name} (`index` integer primary key,"
    for col in df.columns:
        colName = "_".join(col.split(" "))
        dtype = df[col].dtype

        if dtype == "object":
            queryStr = queryStr + f"{colName} text not null,"
        elif dtype == "datetime64[ns]":
            queryStr = queryStr + f"{colName} text not null,"
        elif dtype == "float64":
            queryStr = queryStr + f"{colName} float not null,"
        elif dtype == "float64":
            queryStr = queryStr + f"{colName} float not null,"
        else:
            raise Exception(f"There is no case for dtype {dtype}, please add one")
            exit()
    queryStr = queryStr.removesuffix(",") + ");"

    sql_create_features_table = queryStr
    try:
        conn.execute(sql_create_features_table)
    except Error as e:
        print(e)


def load(conn, table_name, df):
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
 
def close_conn(conn):
    conn.close()
    
    
def ts2str(col):
    """
    This will break if you pass a column that is a datetime[64]. make type ambivalent
    """
    col = col.dt.strftime("%Y-%m-%d %H-%M")
    return col

def read_sql(conn, query):
    df = pd.read_sql(query, conn)
    return df


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

    lat = df.loc[df.index == 'mack', 'latitude'][0]
    long = df.loc[df.index == 'mack', 'longitude'][0]

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