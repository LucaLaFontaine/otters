import os
from os import walk
import pandas as pd
import numpy as np
import yaml
import sqlite3
from sqlite3 import Error
from datetime import date, timedelta, time, datetime

import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
#it would make sense to have a functions config file that imports functions from a central database and then you carry that config around and import from there so that you don't have to add the central database to path. Another day maybe. 

# generate docs with pdoc using: "pdoc --html {name of this file}"

import sys
sys.path.append(r"Z:\Data Governance\pipLocal\Tools\ExPS Reports")
          
def importConfig(cwd, fileName='config'):
    # Import a config file from the folder of the script. 
    try:
        config_file = f'{cwd}{fileName}.yaml'
        print(config_file)
        with open(config_file) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
    except:
        print("There doesn't appear to be a config file for this script. If the code doesn't fail that's probably fine")
    return config

def createSQLConnection(db_file):
    """ create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        print('Sqlite3 Version: '+sqlite3.version)
    except Error as e:
        print(e)
    # finally:
    #     if conn:
    #         conn.close()
    return conn

def scaleDTick(df):
    dateDifference = (df.index[-1]-df.index[0]).days
    print(dateDifference)
    if dateDifference < 1:
        dTick=86400000.0/24
    elif dateDifference < 2:
        dTick=86400000.0*0.25
    elif dateDifference < 7:
        dTick=86400000.0*1
    elif dateDifference < 14:
        dTick=86400000.0*1
    elif dateDifference < 24:
        dTick='D1'
    elif dateDifference < 32:
        dTick=86400000.0*3
    elif dateDifference < 168:
        dTick=86400000.0*7
    else:
        dTick='M1'
    return dTick

def getLastNWeeks(df, n, config):
    """ Get the last n weeks of data starting this past Monday (days would be better but..)
    It's import that the timestamp is the index
    """
    lastMonday = date.today() - timedelta(days=date.today().weekday())
    startDate = datetime.combine((lastMonday - timedelta(days=7*n)), time(config['tick0'][3], config['tick0'][4]))
    
    try:
        df = df.loc[df.index >= startDate, :].drop_duplicates(keep='first')
    except:
        df = df.loc[df.index >= startDate, :].to_frame().drop_duplicates(keep='first')
    return df

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

def get100LowestPercent(lowAchieved, avgProd):
    """ExPS Exclusive
    Gets the 100 lowest values as percentage off production average from all the data in the df. 
    """
    
    return int(round((1-lowAchieved/avgProd), 2)*100)


def getProductionMean(dfCol, nWeeks, config, nEvents=100, ascending=False):
    """Mean of nEvents (default 100 events or 25 hours) over last n weeks for each week i guess?
    Accepts a single column and n of weeks to average over
    """
    
    dfCol = dfCol.to_frame()
    dfCol = getLastNWeeks(dfCol, nWeeks, config)
    print(f'nEvents: {nEvents}')
    avgProd = round(dfCol.loc[dfCol[dfCol.columns[0]]>=0, :].sort_values(dfCol.columns[0], ascending=ascending).head(nEvents).mean())
    return int(avgProd[0])

def getFilesInFolder(path):
    fileList = []
    for (dirpath, dirnames, files) in walk(path):
        print(path)
        for file in files:
            print(file)
            if (file.endswith('.xlsm') or file.endswith('.xlsx')) and '$' not in file:
                fileList.append(file)
        break
    print(fileList)
    return fileList

def createDFFromData(book):
    df = pd.read_excel(book)
    # totalCols
    totalCols = df.shape[1]
    return df

def timeStr2Ts64(df):
    # This function takes a df with a timestamp that python will understand and turns it into a timestamp that everybody understands.
    # It doesn't deal with time changes but passing a variable here would be the easiest way.
    # Returns the entire df, fixed

    # timestamp names to try:
    timestampNames = ['timestamp', 'Timestamp', 'Date/Time', 'Date']

    for timestampName in timestampNames:
        if timestampName in df.columns:
            if timestampName == 'Timestamp':
                # Need to remove timestamp if it's already there or the thing gets mad'
                timestampCol = df[timestampName]
                df.drop(timestampName, axis=1, inplace=True)
                df.insert(0, 'Timestamp', timestampCol.astype('datetime64[ns]'))
            else:
                try:
                    df.insert(0, 'Timestamp', df[timestampName].astype('datetime64[ns]'))
                except:
                    # I'm assuming that if this throws an error then there are 2 timestamp columns. we'll just drop this one.
                    print("Either there are 2 timestamp columns or the timestamp column is messed up. Try a different method.")
                    pass
                df.drop(timestampName, axis="columns", inplace=True)
    return df

def createGraph(df, config, i):
    """
    Creates a graph in the EPS style. Most of this crap is formatting
    We add here the trendline(s), the legend, x/y axes.
    """
    # fig = go.Figure()
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for col in df.columns:
        fig.add_trace(
            go.Scatter(
                y=df[col],
                x=df.index,
                mode='lines',
                name='kW',
                showlegend=True
            )
        )
    fig.update_layout(
        colorway=config['lineColours'],
        width=config['graphWidth'],
        height=config['aspectRatio']*config['graphWidth'],
        margin=dict(l=30, r=10, t=100, b=60),
        paper_bgcolor="white", 
        plot_bgcolor="white",
        title_text=config['chartTitle'][i], 
        title_x=0.5,
        legend=dict(title='', orientation='h',yanchor='top',xanchor='center', y=1.1, x=0.48),
    )

    fig.update_xaxes(
        tickformat='%a %d/%b/%y %H',
        tickangle=config['xTickAngle'],
        tick0=datetime(config['tick0'][0], config['tick0'][1], config['tick0'][2], config['tick0'][3]),
        dtick=gf.scaleDTick(df),
        showline=True, linewidth=1, 
        linecolor='#262626', 
        showgrid=True, 
        gridwidth=0.75, 
        gridcolor='rgba(235, 235, 235, 1)', 
        title_text=config['xTitle'],
        )

    fig.update_yaxes(
        range=list([config['yAxisRange'][0], df.max().max()*config['yAxisRange'][1]]),
        showline=True, 
        linewidth=1, 
        linecolor='#262626', 
        showgrid=True, 
        gridwidth=0.75, 
        gridcolor='rgba(235, 235, 235, 1)', 
        title_text=config['yTitle'],
        )

    # This is just the legend object for DT events
    fig.add_trace(
            go.Scatter(
                y=[0, 0],
                x = [df.index[0]],
                name="Non-Production",
                mode='lines',
                fill='toself',
                fillcolor='rgba(226,240,217,1)',
                line=dict(
                    color='rgba(226,240,217,1)',
                    )
                )
            )
    
    # These 2 are legend objects for target and achieved. they're pretty static so i think they can go in here. 
    fig.add_trace(
        go.Scatter(y=[0, 0],
                   x = [df.index[0]],
                  name="Actual Achieved Non-Prouction kW",
                   mode='lines',
                   # fill='toself',
                  # fillcolor='rgba(226,240,217,1)',
                   line=dict(color='black',
                            )
                  )
        )

    fig.add_trace(
        go.Scatter(y=[0, 0],
               x = [df.index[0]],
              name="Target kW",
               mode='lines',
               # fill='toself',
              # fillcolor='rgba(226,240,217,1)',
               line=dict(color='red',
                        )
              )
    )
    return fig

def consecutive(data):
    """Should be renamed to gapAndIsland
    takes an np.series data type (ie. a df single column)
    returns the entire column broken up into sections where all the numbers are the same. 
    Good for iterating on an events column or tracking flags. 
    """
    return np.split(data, np.where(np.diff(data) != 0)[0]+1)

def mergeCloseEvents(DT_events, i):
    """Merges events that are close so we don't get bunches of events. Not entirely necessary but it makes it cleaner. 
    Recursive function, so it takes each event and calculates if it's within 3600sec of the last event. 
    If so it adds this event to the last event and deletes this event.
    returns the new list of events
    """
    if i >= len(DT_events):
        return DT_events
    elif ((DT_events[i][0]-DT_events[i-1][-1]).total_seconds()/3600)<=12:
        DT_events[i-1][-1] = DT_events[i][-1]
        DT_events.pop(i)
        DT_events = mergeCloseEvents(DT_events, i)
    else:
        mergeCloseEvents(DT_events, i+1)
    return DT_events

def getNonProdLines(dfCol, avgProd, NPLimit, config):
    """Gets the achieved line and value, and the target line and value
    takes a single column from the df and returns a list of dicts containing relevant info
    """
    
    dfCol = dfCol.to_frame()
    
    ### Line Section
    
    # Ok this is fucking stupid. you need to assign the list to a value 'x', then mask is the if True statement and where is the if False statement. 
    # Fuck you Guido
    # but anyway what we're doing is taking downtime values from this particular column
    x = dfCol.loc[:, dfCol.columns[0]]
    events = x.mask(x < avgProd*(1-NPLimit), 1).where(x < avgProd*(1-NPLimit), 0)
    events = consecutive(events)
    
    # return a list of downtime events
    DT_events = []
    for item in events:
        # if the grouping rounds to on (ie. 1) (there could be some errors) and the grouping is longer than 16 events, or 4 hours
        if round(item.mean()) == 1 and len(item) >= 16:
            DT_events.extend([[item.index[0], item.index[-1]]])
    DT_events = mergeCloseEvents(DT_events, 1)
    
    ### End Lines Section
    
    ### Numbers Section
    
    # Apply the industry targets manually here for 12, 24, >24 hours
    listEvents = []
    for event in DT_events:
        if (event[1]-event[0]).total_seconds()/3600<=12:
            targetPerc = 0.3
        elif (event[1]-event[0]).total_seconds()/3600<=24:
            targetPerc = 0.5
        elif (event[1]-event[0]).total_seconds()/3600>=24:
            targetPerc = 0.82
        else:
            targetPerc = 1
        
        # nEvents should be 16 events or 4 hours across the board hewre for stellants
        # This is the threshold to calculate the avg non prod.
        nEvents = 16
        Dict = {'DT_event' : event, 
                'event_actual': getProductionMean(dfCol.loc[(dfCol.index>=event[0]) & (dfCol.index<=event[1]), dfCol.columns[0]].sort_values().head(100), 100, config, nEvents=nEvents, ascending=True), 
                'event_target' : int(avgProd*(1-targetPerc))
               }
        listEvents.append(Dict)    
    return listEvents

def createDTEventLabel(DT_event, actual, target, avgProd, fig, config, i):
    """
    Create downtime labels downtime event (list of dicts)
    Adds them directly to the passed figure
    Currently the figure is not returned, that'll have to change for abstraction
    """
    
    # dfCol = dfCol.to_frame()
    # Achieved Line
    fig.add_shape(type='line',
                x0=DT_event[0],
                y0=actual,
                x1=DT_event[1],
                y1=actual,
                line=dict(width=3, color='Black',),
                 )
    # Target Line
    fig.add_shape(type='line',
                x0=DT_event[0],
                y0=target,
                x1=DT_event[1],
                y1=target,
                line=dict(width=3, color='Red',),
                 )
    
    if config['options']['DS'][i] == False and config['options']['WS'][i] == False:
        # Downtime Square
        fig.add_shape(x0=DT_event[0],
                      fillcolor='rgba(226,240,217,1)',
                     opacity=0.5,
                    y0=0,
                      layer='below',
                    x1=DT_event[1],
                    y1=1,
                    line=dict(width=0),
                    yref='paper',
                     )
    
    #instead of fretting about label proximity just scale the label frequency to the timescale.  
    # Downtime achieved label.
    fig.add_annotation(text="<b>{:,} kW<br>({}%)</b>".format(actual, round(100*(1-actual/avgProd))),
                       # editable=True,
                   showarrow=False,
                   # yshift=-20, 
                   font=dict(color = 'black'),
                   yref="paper",
                   x=(DT_event[0]+(DT_event[1]-DT_event[0])/2),
                   y=1,
                  )
    # Downtime achieved label.
    fig.add_annotation(text="<b>{:,} kW<br>({}%)</b>".format(target, round(100*(1-target/avgProd))),
                   showarrow=False,
                   # yshift=-20, 
                   font=dict(color = 'red'),
                   yref="paper",
                   x=(DT_event[0]+(DT_event[1]-DT_event[0])/2),
                   y=0.91,
                  ) 
    
    return

def addProdIndicators(df, lowAchieved, avgProd):
    """
    Add the avgProd and lowAcheived indicators to the graph
    Currently the figure is not supplied/returned, that'll have to change for abstraction
    """

    # To unpack the y value: take lowDf first column, sort it to get the lowest 100 in the df, take the top 100, average those and round to the final number
    
    fig.add_hline(y=avgProd, line_width=3, line_dash="dot", line_color="#4472C4")
    fig.add_annotation(y=avgProd,
                       text="<b>{:,} kW".format(avgProd),
                       showarrow=False,
                       yshift=15, 
                       font=dict(color = '#4472C4'),
                       xref="paper",
                       x=0.03,
                       bgcolor='rgba(255,255,255,0.7)',
                      )
    # This is just legend item for actual
    fig.add_trace(
            go.Scatter(y=[0, 0],
                       x = [df.index[0]],
                      name="Average Normal Production kW",
                       mode='lines',
                       # fill='toself',
                      # fillcolor='rgba(226,240,217,1)',
                       line=dict(color='#4472C4',
                                 dash='dot',
                                )
                      )
            )

        # fig.add_trace(go.Scatter(y=[4, 2, 1], mode="lines"), row=1, col=1)
    fig.add_hline(y=lowAchieved, line_width=3, line_dash="dot", line_color="#E2AC00")
    fig.add_annotation(y=lowAchieved,
                       text="<b>{:,} kW<br>({}%)</b>".format(lowAchieved, round(100*(1-lowAchieved/avgProd))),
                       showarrow=False,
                       yshift=20, 
                       font=dict(color = '#7F6000'),
                       xref="paper",
                       x=0.03,
                       bgcolor='rgba(255,255,255,0.7)'
                      )
    # This is just legend item for target
    fig.add_trace(
            go.Scatter(y=[0, 0],
                       x = [df.index[0]],
                      name="Lowest Achieved kW",
                       mode='lines',
                       # fill='toself',
                      # fillcolor='rgba(226,240,217,1)',
                       line=dict(color='#E2AC00',
                                 dash='dot',
                                )
                      )
            )

def WTAPProdInd(config, DS, WS, i):
    """
    Add the specific WTAP production count indicators\n
    Currently the figure is not supplied/returned, that'll have to change for abstraction
    """
    
    path = "Z:\Clients\C117 (Leidos)\P19 DTE SEM\Participants\Stellantis\Excellent Plant Shutdown\\02 - EPS Performance Trackers\\05-WTAP\WTAP - Production by Shift.xlsx".replace('\\', '/')
    dfProd = pd.read_excel(path)
    dfProd.set_index('Date', inplace=True)

    if DS == True or WS == True:
        fig.update_yaxes(
            showline=False,
            showgrid=False, 
            title_text="Production Count", 
            secondary_y=True,
            # range=list([config['yAxisRange'][0], dsProd.max()*config['yAxisRange'][1]]),
        )

    if DS == True:
        dsShift1 = dfProd['DS Built 1st Shift']
        dsShift1.index = dsShift1.index+pd.Timedelta(hours=7)
        dsShift2 = dfProd['DS Built 2nd Shift']
        dsShift2.index = dsShift2.index+pd.Timedelta(hours=15)
        dsShift3 = dfProd['DS Built 3rd Shift']
        dsShift3.index = dsShift3.index+pd.Timedelta(hours=23)
        dsProd = pd.concat([dsShift1, dsShift2, dsShift3]).sort_index()

        dsProd = gf.getLastNWeeks(dsProd.to_frame(), config['options']['weeks'][i], config)

        dsProd = dsProd.loc[dsProd.index <= datetime.now() - timedelta(days=date.today().weekday()), :]

        fig.add_trace(
            go.Scatter(y=dsProd[0].resample('H').mean().fillna(method="ffill"),
                       x = dsProd.resample('H').mean().fillna(method="ffill").index,
                      name="DS Production",
                       stackgroup='one',

                       # mode='lines',
                       # fill='toself',
                      fillcolor='rgba(135, 206, 235, 0.15)',
                       line=dict(color='rgba(135, 206, 235, 0.2)',
                        # dash='dot',
                                ),
                      ),
        secondary_y=True,
            )
        
        fig.update_yaxes(
            secondary_y=True,
            range=list([config['yAxisRange'][0], dsProd.max()*config['yAxisRange'][1]]))

    if WS == True:    
        wsShift1 = dfProd['WS Built 1st Shift']
        wsShift1.index = wsShift1.index+pd.Timedelta(hours=7)
        wsShift2 = dfProd['WS Built 2nd Shift']
        wsShift2.index = wsShift2.index+pd.Timedelta(hours=15)
        wsShift3 = dfProd['WS Built 3rd Shift']
        wsShift3.index = wsShift3.index+pd.Timedelta(hours=23)
        wsProd = pd.concat([wsShift1, wsShift2, wsShift3]).sort_index()

        wsProd = gf.getLastNWeeks(wsProd.to_frame(), config['options']['weeks'][i], config)

        wsProd = wsProd.loc[wsProd.index <= datetime.now() - timedelta(days=date.today().weekday()), :]


        # Need to refactor generate alll traces AND THEN build the figure off that. 
        fig.add_trace(
                go.Scatter(y=wsProd[0].resample('H').mean().fillna(method="ffill"),
                           x = wsProd.resample('H').mean().fillna(method="ffill").index,
                          name="WS Production",
                           stackgroup='one',

                            # layer='below',
                           # mode='lines',
                           # fill='toself',
                          fillcolor='rgba(235,164,135,0.15)',
                           line=dict(color='rgba(235,164,135,0.2)',
                            # dash='dot',
                                    ),
                          ),
            secondary_y=True,
                )
        fig.update_yaxes(secondary_y=True,
                         range=list([config['yAxisRange'][0], wsProd.max()*config['yAxisRange'][1]]))
        
    if DS == True and WS == True:
        fig.update_yaxes(
            secondary_y=True,
            range=list([config['yAxisRange'][0], pd.concat([dsProd, wsProd]).max()*config['yAxisRange'][1]]))

    return

def showLastYear(df, dfRaw, fig):
    """
    Run if you want to overlay last year's consumption on the graph. Controlled in the config.
     Currently the figure is not supplied/returned, that'll have to change for abstraction
    """
    
    # print(dfRaw.loc[dfRaw.index > datetime(2021, 12, 29), :].head(50))
    columns = df.columns
    index = df.index
    dfRaw.index = dfRaw.index+pd.Timedelta(days=364)
    df = df.join(dfRaw, how='left', rsuffix='_raw')
    for col in columns:
        fig.add_trace(
            go.Scatter(
                y=df[col+'_raw'],
                x=df.index,
                mode='lines',
                name='Last Year kW',
                showlegend=True,
                line=dict(color='#FF883E',) 
            )
        )
    fig.update_yaxes(secondary_y=False,
        range=list([config['yAxisRange'][0], df.max().max()*config['yAxisRange'][1]]),
    )
    
    # print(df.loc[df.index > datetime(2022, 12, 29), :].head(50))
    
    return