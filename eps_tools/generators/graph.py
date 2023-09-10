
from functools import wraps
import inspect

from datetime import datetime
from datetime import date, timedelta, time, datetime
# import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class Graph():
    def __init__(self, df, config={}):
        self.df = df
        self.config = config
        self.title = config['title']
        self.xTitle	= config['xTitle']
        self.yTitle	= config['yTitle']
        self.cols = config['graphCols'].split(',')
        return

class Plot(Graph):
    def __init__(self, df, parent, config):
        super().__init__(df, config)
        self.parent = parent
        self.config = config
        self.width = self.config['plotWidth']
        self.height = self.config['plotHeight'] or (self.width*self.config['aspectRatio'])
        self.lineColours = self.config['lineColours']
        self.margin = self.config['margin']

        self.yAxisRange = self.config['yAxisRange']


    def createPlot(self):
        """
        Creates a plot in the EPS style. Most of this crap is formatting
        We add here the trendline(s), the legend, x/y axes.
        """
        self.fig = make_subplots(specs=[[{"secondary_y": True}]])

        self.fig.update_layout(
            colorway=self.lineColours,
            width=self.width,
            height=self.height,
            margin=self.margin,
            paper_bgcolor="white", 
            plot_bgcolor="white",
            title_text=self.title, 
            title_x=0.5,
            legend=dict(title='', orientation='h',yanchor='top',xanchor='center', y=1.1, x=0.48),
        )
        return
    
    def addLine(self, col):
        self.fig.add_trace(
            go.Scatter(
                y=self.df[col],
                x=self.df.index,
                mode='lines',
                name=self.yTitle,
                showlegend=True
            )
        )
        return

    def formatXAxis(self):

        self.fig.update_xaxes(
        showline=True, linewidth=1, 
        linecolor='#262626', 
        showgrid=True, 
        gridwidth=0.75, 
        gridcolor='rgba(235, 235, 235, 1)', 
        title_text=self.xTitle,
        )

        return
    def timeFormatXAxis(self):
        self.formatXAxis()
        
        self.tickFormat = self.config['tickFormat']
        self.xTickAngle = self.config['xTickAngle']
        self.xMaxTicks = self.config['xMaxTicks']
        self.dTick = self.config['dTick']
        self.tick0 = self.config['tick0']

        self.fig.update_xaxes(
            tickformat=self.tickFormat,
            tickangle=self.xTickAngle,
            tick0=datetime(self.tick0['year'], self.tick0['month'], self.tick0['day'], self.tick0['hour'], self.tick0['minute']),
            dtick=self.scaleDTick(),
            )

    def formatYAxis(self):
        self.fig.update_yaxes(
            range=list([self.yAxisRange[0], self.df.max().max()*self.yAxisRange[1]]),
            showline=True, 
            linewidth=1, 
            linecolor='#262626', 
            showgrid=True, 
            gridwidth=0.75, 
            gridcolor='rgba(235, 235, 235, 1)', 
            title_text=self.yTitle,
            )
    
    def scaleDTick(self):
        dateDifference = (self.df.index[-1]-self.df.index[0]).days
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