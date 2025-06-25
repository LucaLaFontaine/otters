import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

from datetime import datetime
import logging

def jool_db_conn():
    return psycopg2.connect(database="jool_data",
                        host="localhost",
                        user="postgres",
                        password="luca",
                        port="5432")

def open_equipment_csv(equipment_csv='all_conns_in_pub.csv', delimiter=';', decimal=','):
    return pd.read_csv(equipment_csv, delimiter=delimiter, decimal=decimal)
    
def change_children_to_parents(df):

    df = df.copy()

    if df['METER.REFERENCE'].apply(lambda x: len(df.loc[df['METER.PARENT_CHILD'] == x, "METER.REFERENCE"].unique())).max() > 1:
        raise ValueError("There are multiple parents for one of the rows in the supplied equipment list")

    def check_parent_exists(df, x):
       check = df.loc[df['METER.PARENT_CHILD'] == x, "METER.REFERENCE"].unique()
       if len(check) > 0:
           return check[0]
       else:
           return None

    df['parent'] = df['METER.REFERENCE'].apply(lambda x: check_parent_exists(df, x)) 

    df.drop(columns=['METER.ID', 'METER.PARENT_CHILD', 'METER.ATTACHED_SYSTEM'], inplace=True)
    df.reset_index(drop=True, inplace=True)
    df.drop_duplicates(inplace=True)

    return df 

def update_equipment_from_csv(conn):
    """
    Updates or inserts equipment data from a csv from JOOL directly. You have to manually downl9oad the csv from a database in jool called luca_connections or something
    """
    df = open_equipment_csv()
    df = df.loc[:, ['METER.REFERENCE', 'METER.NAME']]
    df = df.dropna(axis=1)
    df.drop_duplicates(inplace=True) 

    records = df.drop_duplicates(subset=['METER.REFERENCE']).to_dict("records")

    sql = """
        INSERT INTO Equipment (reference, name)
        VALUES %s
        ON CONFLICT (reference) DO NOTHING
    """
    values = [(col['METER.REFERENCE'], col['METER.NAME']) for col in records]
    with conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()
    
    return

def update_equipment_parents(conn):
    df = open_equipment_csv()

    # Add the reference as the name if it's empty:
    df['METER.NAME'] = df.apply(lambda x: x['METER.NAME'] if x['METER.NAME'] else x['METER.REFERENCE'], axis=1)
    # return df
    df = change_children_to_parents(df)
    # return df
    records = df.to_dict("records")

    sql = """
        UPDATE Equipment t1
        SET parent = t2.EquipmentID
        FROM (values %s) f(v1, v2)
        LEFT JOIN Equipment as t2 on t2.reference = f.v1 
        WHERE t1.reference = f.v2;
    """
    values = [(col['parent'], col['METER.REFERENCE']) for col in records]
    # return values
    with conn.cursor() as cur:
        # cur.execute(sql, values)
        execute_values(cur, sql, values)
        conn.commit()
    
    return

def update_equipment_connections(conn):
    """
    Take the csv output from the connections file and use it to create all the connections in JOOL. 

    Doesn't do directionality, which it shouldn't but I will have to do eventually
    """
    df = open_equipment_csv()

    df = df.loc[:, ['METER.REFERENCE', 'METER.ATTACHED_SYSTEM']]
    df.replace(np.nan, None, inplace=True)
    
    records = df.to_dict("records")
    records = [(col['METER.REFERENCE'], col['METER.ATTACHED_SYSTEM']) for col in records]

    fetch_sql = """
        SELECT reference, equipmentID FROM equipment
        WHERE reference = ANY(%s)
    """ 
    
    values = list(set(list(sum(records, ()))))
    values.remove(None)
    # values = tuple(values)
    # return values

    with conn.cursor() as cur:
        cur.execute(fetch_sql, (values, ))
        ref_to_id = dict(cur.fetchall())  # {'EQ-001': 1, 'EQ-002': 2, ...}
        # result = conn.cursor().fetchone()
        conn.commit()

    # return ref_to_id 
    id_pairs = []
    for base_ref, conn_ref in records:
        base_id = ref_to_id.get(base_ref)
        conn_id = ref_to_id.get(conn_ref)
        if base_id is not None and conn_id is not None:
            id_pairs.append((base_id, conn_id))
        # else:
        #     print(f"Skipping pair ({base_ref}, {conn_ref}) — reference(s) not found.")
    upsert_sql = """
        INSERT INTO EquipmentConnections (equipment, equipment_connection)
        VALUES %s
        ON CONFLICT (equipment, equipment_connection)
        DO NOTHING
    """
    with conn.cursor() as cur:
        execute_values(cur, upsert_sql, id_pairs)
        conn.commit()

    cur.close()
    return 

def get_stream_max_date(conn, reference):

    sql = """
    SELECT MAX(timestamp) from TimeDataValues td
    left join DataStreams ds on ds.DataStreamID = td.data_stream
    left join equipment e on e.equipmentid = ds.equipment
    WHERE e.reference = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (reference, ))
        ref_to_id = cur.fetchall()[0][0] # {'EQ-001': 1, 'EQ-002': 2, ...}
    
    if ref_to_id:
        return ref_to_id
    else:
        return datetime(2000, 1, 1)

def update_equipment_data(conn, reference, jool, config):
    """
    I need this to be a class so that I can pass the jool object and the config to the class, but one thing at a time.
    """
        
    data = {
        "from": get_stream_max_date(conn, reference).strftime(format="%Y-%m-%dT%H:%M:00.000Z"), 
        "to": datetime.now().strftime(format="%Y-%m-%dT%H:%M:00.000Z"),
        "selection" : [reference],
    }
    logging.info(f"updating reference {reference} from {data['from']} to {data['to']}")
    bearer_auth = jool.get_bearer_auth(**config)
    df = jool.data_call(data, bearer_auth, config, True)
    # return df

    cur = conn.cursor()
    cur.execute("BEGIN;")

    for channel in df['CHANNEL.REFERENCE'].unique():
        try: 
            ds_values = [(col['CHANNEL.REFERENCE'], col['METER.REFERENCE'], col['CHANNEL.CNL_DAC_UNIT']) for col in df.drop_duplicates().to_dict('records')]
            data_stream_sql = """
            INSERT INTO DataStreams (name, equipment, unit)
            SELECT DISTINCT f.v1, e.EquipmentID, f.v3
            FROM (values %s) as f(v1, v2, v3)
            JOIN Equipment as e on e.reference = f.v2
            ON CONFLICT (name, equipment) 
            DO UPDATE SET unit = EXCLUDED.unit;
            """

            td_values = [(col['Timestamp'], col['RAWDATA.VALUE'], col['CHANNEL.REFERENCE']) for col in df.reset_index().drop_duplicates().to_dict('records')]
            time_data_sql = """
            INSERT INTO TimeDataValues (timestamp, value, data_stream)
            SELECT DISTINCT f.v1, f.v2, ds.datastreamid
            FROM (values %s) f(v1, v2, v3)
            JOIN DataStreams as ds on ds.name = f.v3
            ON CONFLICT (timestamp, data_stream) 
            DO UPDATE SET value = EXCLUDED.value;
            """
            execute_values(cur, data_stream_sql, ds_values)
            execute_values(cur, time_data_sql, td_values)
        except Exception as e:
            conn.rollback()
            print(f"Transaction on {channel} failed:", e)
        
    cur.close()
    logging.info(f"update of {reference} complete")
    return 