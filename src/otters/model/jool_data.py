import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values

from datetime import datetime
import logging

def jool_db_conn(database="jool_data",
                        host="localhost",
                        user="postgres",
                        password="luca",
                        port="5432"):
    return psycopg2.connect(database=database,
                        host=host,
                        user=user,
                        password=password,
                        port=port)

def open_equipment_csv(equipment_csv='all_conns_in_pub.csv', delimiter=';', decimal=','):
    df = pd.read_csv(equipment_csv, delimiter=delimiter, decimal=decimal)
    df.columns = [col.replace("METER.", "") for col in df.columns]
    return df
    
def change_children_to_parents(df):

    df = df.copy()

    if df['REFERENCE'].apply(lambda x: len(df.loc[df['PARENT_CHILD'] == x, "REFERENCE"].unique())).max() > 1:
        double_parent = df['REFERENCE'].apply(lambda x: len(df.loc[df['PARENT_CHILD'] == x, "REFERENCE"])).sort_values(ascending=False)
        raise ValueError("There are multiple parents for one of the rows in the supplied equipment list")

    def check_parent_exists(df, x):
       check = df.loc[df['PARENT_CHILD'] == x, "REFERENCE"].unique()
       if len(check) > 0:
           return check[0] 
       else:
           return None 

    df['PARENT'] = df['REFERENCE'].apply(lambda x: check_parent_exists(df, x)) 

    df.drop(columns=['PARENT_CHILD', 'ATTACHED_SYSTEM'], inplace=True)
    df.reset_index(drop=True, inplace=True)

    df.drop_duplicates(inplace=True)

    return df 

def update_equipment_from_csv(conn):
    """
    Updates or inserts equipment data from a csv from JOOL directly. You have to manually downl9oad the csv from a database in jool called luca_connections or something
    """
    df = open_equipment_csv()
    df = df.loc[:, ['REFERENCE', 'NAME']]
    df = df.dropna(axis=1)
    df.drop_duplicates(inplace=True) 

    records = df.drop_duplicates(subset=['REFERENCE']).to_dict("records")

    sql = """
        INSERT INTO Equipment (reference, name)
        VALUES %s
        ON CONFLICT (reference) DO NOTHING
    """
    values = [(col['REFERENCE'], col['NAME']) for col in records]
    with conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()
    
    return

def update_equipment_parents(conn):
    df = open_equipment_csv()

    # Add the reference as the name if it's empty:
    df['NAME'] = df.apply(lambda x: x['NAME'] if x['NAME'] else x['REFERENCE'], axis=1)
    # return df
    df = change_children_to_parents(df)
    df = df.fillna('')
    # return df
    records = df.to_dict("records")

    sql = """
        UPDATE Equipment t1
        SET parent = t2.EquipmentID
        FROM (values %s) f(v1, v2)
        LEFT JOIN Equipment as t2 on t2.reference = f.v1 
        WHERE t1.reference = f.v2;
    """
    values = [(col['PARENT'], col['REFERENCE']) for col in records]
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

    df = df.loc[:, ['REFERENCE', 'ATTACHED_SYSTEM']]
    df.replace(np.nan, None, inplace=True)
    
    records = df.to_dict("records")
    records = [(col['REFERENCE'], col['ATTACHED_SYSTEM']) for col in records]

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
    inner join DataStreams ds on ds.DataStreamID = td.data_stream
    inner join equipment e on e.equipmentid = ds.equipment
    WHERE e.reference = %s;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (reference, ))
        ref_to_id = cur.fetchone()[0] # {'EQ-001': 1, 'EQ-002': 2, ...}
    
    if ref_to_id:
        return ref_to_id
    else:
        return datetime(2000, 1, 1)

def update_equipment_data(conn, reference, jool, config, start_date=None, end_date=None):
    """
    I need this to be a class so that I can pass the jool object and the config to the class, but one thing at a time.
    """
    if not start_date:
        start_date = get_stream_max_date(conn, reference)
    if not end_date: 
        end_date = datetime.now()
        
    data = {
        "from": start_date.strftime(format="%Y-%m-%dT%H:%M:00.000Z"), 
        "to": end_date.strftime(format="%Y-%m-%dT%H:%M:00.000Z"),
        "selection" : [reference],
    }
    logging.info(f"updating reference {reference} from {data['from']} to {data['to']}")
    bearer_auth = jool.get_bearer_auth(**config)
    df = jool.data_call(data, bearer_auth, config, True)
    # return df
    # cur = conn.cursor()
    cur = conn.cursor()
    for channel in df['CHANNEL.REFERENCE'].unique():
        channel_df = df.loc[df['CHANNEL.REFERENCE'] == channel, :]
        try: 
            cur.execute("BEGIN;")
            ds_values = [(col['CHANNEL.REFERENCE'], col['REFERENCE'], col['CHANNEL.CNL_DAC_UNIT']) for col in channel_df.loc[:, ['CHANNEL.REFERENCE', 'METER.REFERENCE','CHANNEL.CNL_DAC_UNIT']].drop_duplicates().to_dict('records')]
            data_stream_sql = """
            INSERT INTO DataStreams (name, equipment, unit)
            SELECT DISTINCT ON (f.v1, e.EquipmentID) f.v1, e.EquipmentID, f.v3 
            FROM (values %s) as f(v1, v2, v3)
            JOIN Equipment as e on e.reference = f.v2
            ON CONFLICT (name, equipment) 
            DO UPDATE SET unit = EXCLUDED.unit;
            """

            td_values = [(col['Timestamp'], col['RAWDATA.VALUE'], col['CHANNEL.REFERENCE']) for col in channel_df.reset_index().loc[:, ['Timestamp','RAWDATA.VALUE', 'CHANNEL.REFERENCE']].drop_duplicates().to_dict('records')]
            time_data_sql = """
            INSERT INTO TimeDataValues (timestamp, value, data_stream)
            SELECT DISTINCT ON (f.v1, ds.datastreamid) f.v1, f.v2, ds.datastreamid
            FROM (values %s) f(v1, v2, v3)
            JOIN DataStreams as ds on ds.name = f.v3
            ON CONFLICT (timestamp, data_stream) 
            DO UPDATE SET value = EXCLUDED.value;
            """
            execute_values(cur, data_stream_sql, ds_values)
            execute_values(cur, time_data_sql, td_values)
            # logging.info(ds_values)
            cur.execute("END;")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Transaction on {channel} failed:", e)
        
    cur.close()
    logging.info(f"update of {reference} complete")
    return 

def get_all_equipment(conn):
    cur = conn.cursor()

    equipment_sql = """
    SELECT e.reference as reference from equipment e
    """
    cur.execute(equipment_sql, ())
    df = pd.DataFrame(cur.fetchall(), columns=[desc.name for desc in cur.description])

    return df

def get_all_children(conn, ref,recursive=False, connections=None):
    cur = conn.cursor()
    ref_col = "reference"
    child_col = "child"
    
    if not connections:
        connections = {}

    children_sql = """
    select e1.reference, e2.reference as child from Equipment e1
    left join Equipment e2 on e1.equipmentid = e2.parent
    where e1.reference = %s
    """
    cur.execute(children_sql, (ref, ))
    df = pd.DataFrame(cur.fetchall(), columns=[desc.name for desc in cur.description])

    children = df.loc[df[ref_col] == ref, child_col].unique().tolist()
    children = filter(lambda x: x==x, children)
    
    connections.setdefault("children", []).extend(children)
    
    if recursive:
        for child in children:
            connections = get_all_children(child, df, recursive=recursive, connections=connections)
    
    return connections

def get_all_connections(conn, ref, recursive=False, get_attachments=True, connections=None):
    cur = conn.cursor()
    ref_col = "reference"
    attached_col = "connection"

    connections = get_all_children(conn, ref, recursive=False, connections=None)
    
    # Get the attachments at just this level
    attached_sql = """
    SELECT e.reference as reference, e1.reference as connection from EquipmentConnections ec
    left join Equipment e on ec.equipment = e.equipmentid
    left join Equipment e1 on ec.equipment_connection = e1.equipmentid
    where e.reference = %s
    """
    cur.execute(attached_sql, (ref, ))
    df = pd.DataFrame(cur.fetchall(), columns=[desc.name for desc in cur.description])

    if get_attachments:
        attachments = df.loc[df[ref_col] == ref, attached_col].unique().tolist()
        attachments = filter(lambda x: x==x, attachments)
    else:
        attachments = []
    connections.setdefault("attached", []).extend(attachments)


    if recursive:
        for child in connections["children"]:
            connections = get_all_children(conn, child, recursive=recursive, connections=connections)

    return {name: list(set(values)) for name, values in connections.items()}

def get_equipment_data(conn, reference, start_date="", end_date=""):
    sql = """
    SELECT
        e.reference AS equipment,
        ds.name AS datastream,
        tdv.timestamp,
        tdv.value
    FROM
        equipment e
    JOIN
        datastreams ds ON ds.equipment = e.equipmentid
    JOIN
        timedatavalues tdv ON tdv.data_stream = ds.datastreamid
    WHERE
        e.reference = %s
        AND tdv.timestamp >= %s
        AND tdv.timestamp <= %s
    ORDER BY
        tdv.timestamp;
    """
    if not start_date:
        start_date = datetime(2000, 1, 1)
    if not end_date:
        end_date = datetime.now()

    df = pd.read_sql_query(sql, conn, params=(reference, start_date, end_date))

    df_piv = df.pivot_table(index='timestamp', columns='datastream', values='value')

    return df_piv

def resample_jool_data(df, period="15min"):

    if df.empty:
        return df    
    
    max_cols = [col for col in df.columns if "ETAT" in col]
    mean_cols = [col for col in df.columns if col not in max_cols]

    df_max = df.loc[:, max_cols].resample(period).max()
    df_mean = df.loc[:, mean_cols].resample(period).mean()

    df = pd.concat([df_max, df_mean], axis=1)

    return df

def get_list_connections(conn, reference, children=True, attachments=True):
    connections = get_all_connections(conn, reference, get_attachments=attachments)
    connections = [ref for ref_type in connections.values() for ref in ref_type]
    connections = list(set(connections))
    connections = [connection for connection in connections if connection]
    return connections
