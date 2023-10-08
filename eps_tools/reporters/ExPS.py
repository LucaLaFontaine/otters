import sys
sys.path.append(r'C:\Users\Luca\Documents\Data Science\ExPS Reports v2')

import pandas as pd
import numpy as np

import eps_tools.wrangler
import eps_tools.wrangler.wrangler as wrangler
from eps_tools.wrangler import *
# from eps_tools.wrangler import time_tools as time_tools
import eps_tools.loader as loader
from eps_tools.loader import *
from eps_tools.generators.ppt_gen import PPTGen
from eps_tools.generators.graph import Graph, Plot

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from datetime import timedelta



class ExPS():
    def __init__(self):
        self.config = file_loader.import_config()
        self.plant = self.config['plant']
        self.graphs = []

        return
    
    def getSQL(self, verbose=False):
        conn = db_loader.create_conn(self.config['db_file'])
        cursor = conn.cursor()
        query = f'''
        SELECT timestamp, {self.config['plant']}_kW
        FROM DTE_update
        '''

        dfSQL = pd.read_sql_query(query, conn)
        conn.close()

        dfSQL = time_tools.str2dt(dfSQL, drop=True)
        dfSQL.sort_index(inplace=True)
        dfSQL = dfSQL[~dfSQL.index.duplicated(keep='last')]

        if verbose:
            print(dfSQL.info())
            display(dfSQL.head())

        return dfSQL
    
    def getExcel(self, verbose=False):
        excelList = file_loader.getExcelDFs(self.config['dataFolder'])

        dfXl = pd.concat(excelList)
        dfXl = time_tools.str2dt(dfXl, drop=True)
        dfXl = dfXl[~dfXl.index.duplicated(keep='last')]

        if verbose:
            print(dfXl.info())
            display(dfXl.head())

        return dfXl
    
    def createPPT(self):
        self.reportFolder = self.config['reportFolder']
        self.PPT = PPTGen(self)
        return
    
    def savePPT(self):
        self.pptTitle = self.PPT.ExPSStyleName()
        self.PPT.savePPT(self.pptTitle)
        print(f'Saved to:\n{self.pptTitle}')
    
class Graph(Graph):
    def __init__(self, parent, config):
        super().__init__(config)
        self.parent = parent
        self.NPThreshold = config['NPThreshold']
        self.numWeeks = config['numWeeks']
        self.setDf()
       
        # self.DS	= config['DS'] Plant specific, assign in notebook
        # self.WS = config['WS']
        self.col = self.cols[0]
        self.plot = Plot(self)
        return
    
    def setDf(self):
        self.df = self.parent.dfAll.loc[:, self.config['graphCols']]
        self.df = time_tools.getLastNWeeks(self.df, self.numWeeks, hour=self.config['tick0']['hour'],
                                            minute=self.config['tick0']['minute'])
        
    
    def setLowAchieved(self):
        self.lowAchieved = int(round(self.parent.lowDf.loc[:, self.col].mean()))
        return
    
    def setLowPercentage(self):    
        self.lowPercentage = int(round((1-self.lowAchieved/self.avgProd), 2)*100)
        return
    def setAvgProd(self, rows):
        self.avgProd = int(self.getNRowAvg(self.df, rows=rows, ascending=False))
        return
    
    def getNRowAvg(self, dfCol, rows, ascending):
        colName = dfCol.squeeze().name
        return round(dfCol.squeeze().sort_values(ascending=ascending).reset_index().loc[:rows, colName].mean(), 0)
    
    def setDowntimeEvents(self, dropEventsBelowNRows=16, mergeWithinHours=12, mergeClose=True):
        
        if isinstance(self.df, pd.Series):
            self.df = self.df.to_frame()
        rowsBelowThreshold = self.df.applymap(lambda x: 1 if x and x > 0 and x < self.avgProd*(1-self.NPThreshold) else 0)
        
        eventsBelowThreshold = wrangler.gapAndIsland(rowsBelowThreshold)

        downtimeEventDates = []
        for event in eventsBelowThreshold:
            if round(event.mean()) == 1 and len(event) >= dropEventsBelowNRows:
                downtimeEventDates.append([event.index[0], event.index[-1]])

        if mergeClose:
            downtimeEventDates = wrangler.mergeCloseEvents(downtimeEventDates, mergeWithinHours=mergeWithinHours)

        self.downtimeEvents = []
        for event in downtimeEventDates:
            self.downtimeEvents.append(DowntimeEvent(self, event))

        return 
    
class DowntimeEvent():
    def __init__(self, parent, dates):
        self.parent = parent
        self.startTime = dates[0]
        self.endTime = dates[1]
        self.eventDurationHours = (self.endTime-self.startTime).total_seconds()/3600
        self.setTargets()
        self.setAvgNonProd()
        return
    
    def setTargets(self):
        if self.eventDurationHours<=12:
            self.targetPercentage = 0.3

        elif self.eventDurationHours<=24:
            self.targetPercentage = 0.5

        elif self.eventDurationHours>=24:
            self.targetPercentage = 0.82

        else:
            self.targetPercentage = 1

    def setAvgNonProd(self):
        actualAvgRows = 16
        dfCol = self.parent.df
        colName = dfCol.squeeze().name

        self.actualNPAvg = int(self.parent.getNRowAvg(dfCol.loc[(dfCol.index>=self.startTime) & (dfCol.index<=self.endTime), colName], rows=actualAvgRows, ascending=True))
        self.targetNPAvg = int(self.parent.avgProd*(1-self.targetPercentage))

class Plot(Plot):
    def __init__(self, parent):
        self.parent = parent
        # self.config = self.parent.configupdate_yaxes
        # self.df = self.parent.df
        # self.yAxisRange = self.parent.config['yAxisRange']
        super().__init__(self.parent)
        self.formatYAxisUnits()
        return
    
    def addLegendLabels(self):

        # This is just the legend object for DT events
        self.fig.add_trace(
                go.Scatter(
                    y=[0, 0],
                    x = [self.df.index[0]],
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
        self.fig.add_trace(
            go.Scatter(y=[0, 0],
                    x = [self.df.index[0]],
                    name="Actual Achieved Non-Prouction kW",
                    mode='lines',
                    # fill='toself',
                    # fillcolor='rgba(226,240,217,1)',
                    line=dict(color='black',
                                )
                    )
            )

        self.fig.add_trace(
            go.Scatter(y=[0, 0],
                x = [self.df.index[0]],
                name="Target kW",
                mode='lines',
                # fill='toself',
                # fillcolor='rgba(226,240,217,1)',
                line=dict(color='red',
                            )
                )
        )
        return
    
    def addAvgProdLine(self):
        """
        Add the avgProd and lowAcheived indicators to the graph
        Currently the figure is not supplied/returned, that'll have to change for abstraction
        """

        # To unpack the y value: take lowDf first column, sort it to get the lowest 100 in the df, take the top 100, average those and round to the final number
        
        self.fig.add_hline(y=self.parent.avgProd, line_width=3, line_dash="dot", line_color="#4472C4")
        self.fig.add_annotation(y=self.parent.avgProd,
                        text="<b>{:,} kW".format(self.parent.avgProd),
                        showarrow=False,
                        yshift=15, 
                        font=dict(color = '#4472C4'),
                        xref="paper",
                        x=0.03,
                        bgcolor='rgba(255,255,255,0.7)',
                        )
        # This is just legend item for actual
        self.fig.add_trace(
                go.Scatter(y=[0, 0],
                        x = [self.df.index[0]],
                        name="Average Normal Production kW",
                        mode='lines',
                        # fill='toself',
                        # fillcolor='rgba(226,240,217,1)',
                        line=dict(color='#4472C4',
                                    dash='dot',
                                    )
                        )
                )
        
    def addLowAchievedLine(self):

            # fig.add_trace(go.Scatter(y=[4, 2, 1], mode="lines"), row=1, col=1)
        self.fig.add_hline(y=self.parent.lowAchieved, line_width=3, line_dash="dot", line_color="#E2AC00")
        self.fig.add_annotation(y=self.parent.lowAchieved,
                        text="<b>{:,} kW<br>({}%)</b>".format(self.parent.lowAchieved, round(100*(1-self.parent.lowAchieved/self.parent.avgProd))),
                        showarrow=False,
                        yshift=20, 
                        font=dict(color = '#7F6000'),
                        xref="paper",
                        x=0.03,
                        bgcolor='rgba(255,255,255,0.7)'
                        )
        # This is just legend item for target
        self.fig.add_trace(
                go.Scatter(y=[0, 0],
                        x = [self.df.index[0]],
                        name="Lowest Achieved kW",
                        mode='lines',
                        # fill='toself',
                        # fillcolor='rgba(226,240,217,1)',
                        line=dict(color='#E2AC00',
                                    dash='dot',
                                    )
                        )
                )

    def addWTAPSchedule(self):
        """
        Add the specific WTAP production count indicators\n
        Currently the figure is not supplied/returned, that'll have to change for abstraction
        """
        
        dfBuilt = pd.read_excel(self.config['scheduleFile'])
        dfBuilt.set_index('Date', inplace=True)
        # drop the date column
        dfBuilt.drop('Day', axis=1, inplace=True)
        # Get the relevant dates in dfBuilt
        dfBuilt = time_tools.getLastNWeeks(dfBuilt, self.parent.numWeeks)
        dfBuilt.fillna(0, inplace=True)

        if self.parent.DS == True or self.parent.WS == True:
            self.fig.update_yaxes(
                showline=False,
                showgrid=False, 
                title_text="Build Count", 
                secondary_y=True,
            )

        if self.parent.DS == True:
            DS_shifts = []

            for shift in self.config['WTAPSchedule'].values():
                if shift['start']:
                    shiftBuilt = dfBuilt[shift['title']['DS']]
                    start = shift['start']
                    end = shift['end']
                    DS_shifts.append(self.granulizeData(shiftBuilt, start, end))
            DSBuilt = pd.concat(DS_shifts).sort_index()

            DSTrace = go.Bar(y=DSBuilt,
                        x = DSBuilt.index,
                        name="DS Built",
                        marker=dict(color='rgba(135, 206, 235, 0.15)',
                                    line=dict(color='rgba(0, 0, 0, 0)'
                                    ),
                        ),
            ) 
            self.fig.add_trace(DSTrace,
                secondary_y=True,
            )
            self.fig.update_yaxes(
                secondary_y=True,
            )

        if self.parent.WS == True:
            WS_shifts = []

            for shift in self.config['WTAPSchedule'].values():
                if shift['start']:
                    shiftBuilt = dfBuilt[shift['title']['WS']]
                    start = shift['start']
                    end = shift['end']
                    WS_shifts.append(self.granulizeData(shiftBuilt, start, end))
            WSBuilt = pd.concat(WS_shifts).sort_index()            
            
            WSTrace = go.Bar(y=WSBuilt,
                x = WSBuilt.index,
                name="WS Production",
                marker=dict(color='rgba(235,164,135,0.15)',
                            line=dict(color='rgba(0, 0, 0, 0)'
                            ),
                ),
            )   
            self.fig.add_trace(WSTrace,
                            secondary_y=True,
            )
            self.fig.update_yaxes(
                secondary_y=True,
            )

            
        self.fig.update_layout(
            bargap=0,
            barmode='stack',
        )
        
        # Once again the most complicated section in the code is this func.
        # We go get the 'full_figure_for_dev' method which returns us the entire dataset and config of the figure
        # We crawl that set for traces on y2, and take the max y axis of each y2 trace
        # we add the all the trace maxes together to give the max possible bar height
        # we just take that number as yAxisMax because we can't go over it 
        # This should not be this complex. refactoring the code wuold make this a lot simpler and more robust. 
        full_fig = self.fig.full_figure_for_development(warn=False)
        # print(full_fig.data)
        # if len([x for x in full_fig.data if x['yaxis'] == 'y2']) > 0:
        self.y2AxisMax = sum([max(x['y'], default=0) if x['yaxis'] == 'y2' else 0 for x in full_fig.data])
        # else:
            # self.y2AxisMax = 0

        self.fig.update_yaxes(
            secondary_y=True,
            range=list([self.yAxisRange[0], int(self.y2AxisMax)])
        )
        return
    
    def createDTEventLabel(self, event):
        """
        Create downtime labels downtime event (list of dicts)
        Adds them directly to the passed figure
        Currently the figure is not returned, that'll have to change for abstraction
        """

        # dfCol = dfCol.to_frame()
        # Achieved Line
        self.fig.add_shape(type='line',
                    x0=event.startTime,
                    y0=event.actualNPAvg,
                    x1=event.endTime,
                    y1=event.actualNPAvg,
                    line=dict(width=3, color='Black',),
                    )
        # Target Line
        self.fig.add_shape(type='line',
                    x0=event.startTime,
                    y0=event.targetNPAvg,
                    x1=event.endTime,
                    y1=event.targetNPAvg,
                    line=dict(width=3, color='Red',),
                    )
        
        # if config['options']['DS'][i] == False and config['options']['WS'][i] == False:
            # Downtime Square
        self.fig.add_shape(x0=event.startTime,
                    fillcolor='rgba(226,240,217,1)',
                    opacity=0.5,
                    y0=0,
                    layer='below',
                    x1=event.endTime,
                    y1=1,
                    line=dict(width=0),
                    yref='paper',
                    )
        
        #instead of fretting about label proximity just scale the label frequency to the timescale.  
        # Downtime achieved label.
        self.fig.add_annotation(text="<b>{:,} kW<br>({}%)</b>".format(event.actualNPAvg, round(100*(1-event.actualNPAvg/self.parent.avgProd))),
                        # editable=True,
                    showarrow=False,
                    # yshift=-20, 
                    font=dict(color = 'black'),
                    yref="paper",
                    x=(event.startTime+(event.endTime-event.startTime)/2),
                    y=1,
                    )
        # Downtime achieved label.
        self.fig.add_annotation(text="<b>{:,} kW<br>({}%)</b>".format(event.targetNPAvg, round(100*(1-event.targetNPAvg/self.parent.avgProd))),
                    showarrow=False,
                    # yshift=-20, 
                    font=dict(color = 'red'),
                    yref="paper",
                    x=(event.startTime+(event.endTime-event.startTime)/2),
                    y=0.91,
                    ) 
        
        return

    def granulizeData(self, series, start, end):

        for row in list(zip(series.index, series.values)):
            now = start
            while now <= end:
                series.loc[row[0]+pd.Timedelta(hours=now)] = row[1]
                now = now+1
            series.drop(row[0], inplace=True) # Clears the row you started with
        return series
    
    def showLastYear(self, dfAll):

        dfPastAll = time_tools.overlayPast(dfAll, 364)
        # Remove columns not in this plot
        dfPastAll = dfPastAll.loc[:, self.df.columns+'_past']
        # dfPast = self.df.join(dfPastAll.loc[:, self.df.columns+'_past'], how='outer')
        dfPast = pd.concat([dfPastAll, self.df], axis=1)
        dfPast = dfPast.loc[(dfPast.index >= self.df.index.min()) & (dfPast.index <= self.df.index.max())]
        for col in dfPast.columns:
            if '_past' in col:
                self.fig.add_trace(
                    go.Scatter(
                        y=dfPast.loc[:, col],
                        x=dfPast.index,
                        mode='lines',
                        name='Last Year kW',
                        showlegend=True,
                        line=dict(color='#FF883E',) 
                    )
                )

        self.fig.update_yaxes(secondary_y=False,
            range=list([self.yAxisRange[0], dfPast.max().max()*self.yAxisRange[1]]),
        )
        
        return
    
    def showLastWeek(self, dfAll):
        
        dfPastAll = time_tools.overlayPast(dfAll, 7)
        # Remove columns not in this plot
        dfPastAll = dfPastAll.loc[:, self.df.columns+'_past']
        # dfPast = self.df.join(dfPastAll.loc[:, self.df.columns+'_past'], how='outer')
        dfPast = pd.concat([dfPastAll, self.df], axis=1)
        dfPast = dfPast.loc[(dfPast.index >= self.df.index.min()) & (dfPast.index <= self.df.index.max())]
        for col in dfPast.columns:
            if '_past' in col:
                self.fig.add_trace(
                    go.Scatter(
                        y=dfPast.loc[:, col],
                        x=dfPast.index,
                        mode='lines',
                        name='Last Week kW',
                        showlegend=True,
                        line=dict(color='#A14494',) 
                    )
                )

        self.fig.update_yaxes(secondary_y=False,
            range=list([self.yAxisRange[0], dfPast.max().max()*self.yAxisRange[1]]),
        )
        
        return
    
    def formatYAxisUnits(self):
        self.fig.update_yaxes(
            tickformat=",",
            )