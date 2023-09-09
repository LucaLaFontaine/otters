import sqlite3
from sqlite3 import Error
import collections


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
    queryStr = f"CREATE TABLE IF NOT EXISTS {table_name} (index integer primary key,"
    for col in df.columns:
        colName = "_".join(col.split(" "))
        dtype = df[col].dtype

        if dtype == "object":
             queryStr = queryStr + f"{colName} text not null,"
        elif dtype == "datetime64[ns]":
              queryStr = queryStr + f"{colName} text not null,"
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

    df.columns = ["_".join(col.split(" ")) for col in df.columns]
              
    for col in df.columns:
            if df[col].dtype == 'datetime64[ns]':
                df[col] = ts2str(df[col])
                
    cur = conn.cursor()
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
    col = col.dt.strftime("%Y-%m-%d %H-%M")
    return col
