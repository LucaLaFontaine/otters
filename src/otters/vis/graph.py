
from functools import wraps
import inspect

import pandas as pd
from datetime import date, timedelta, time, datetime
# import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class Graph():
    def __init__(self, df=pd.DataFrame(), **kwargs):


        # Default kwarg values, later updated with the passed kwargs
        options = {
            'title' : '',
            'df' : df,
            'graphCols' : df.columns,
            'xTitle' : '',
            'yTitle' : '',     
        }
        options.update(kwargs)
        # unpack the arguments and assign them to self.{argName}
        for arg in options.keys():
            self.__setattr__(arg, options[arg])

        self.config = options
        # self.cols = config['graphCols'].split(',')
        return
    
    def __repr__(self):
            return f"Graph(name='{self.title}', cols={self.df.columns})"
        

class Plot(Graph):
    def __init__(self, parent):
        self.parent = parent
        self.config = self.parent.config   
        self.df = self.parent.df 
        self.title = self.parent.title
        self.xTitle	= self.parent.xTitle
        self.yTitle	= self.parent.yTitle
        self.width = self.config['plotWidth']
        self.height = self.config['plotHeight'] or (self.width*self.config['aspectRatio'])
        self.lineColours = self.config['lineColours']
        self.margin = self.config['margin']
        self.setYAxisRange()
        self.createPlot()


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
            title_text=self.parent.title, 
            title_x=0.5,
            legend=dict(title='', orientation='h',yanchor='top',xanchor='center', y=1.1, x=0.48),
        )
        return
    
    def addLine(self):
        self.fig.add_trace(
            go.Scatter(
                y=self.df.squeeze(),
                x=self.df.index,
                mode='lines',
                name=self.yTitle,
                showlegend=True
            )
        )
        return
    
    def addScatter(self):
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
            range=list([self.yAxisRange[0], self.df.squeeze().max()*self.yAxisRange[1]]),
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
    
    def setYAxisRange(self):
        self.yAxisRange = self.config['yAxisRange']
        if type(self.yAxisRange) == str:
            self.yAxisRange = [eval(x) for x in self.yAxisRange.split(', ')]

    def createTimeline(self, df):
        """
        Creates a standalone timeline from a supplied events DataFrame  

        Paramaters:
        df: DataFrame, Required
        > Should be format: ['Timsetamp', 'Name'].  
        It only takes the first 2 columns so you can put like a description or whatever after. Eventually a description will be rolled into hover text
        
        """
        df['ZeroCol'] = 1
        # Add just the time series
        self.fig.add_trace(
            go.Scatter(
                y=[0],
                x=[self.df.index.min()],
                mode='lines',
                name=self.title,
                showlegend=False
            )
        )
        padding = timedelta(days=30)
        self.fig.update_xaxes(
            range=[self.df.index.min()-padding, self.df.index.max()+padding],
            tickfont=dict(
                size=15,
            ),
            ticklabelposition = 'outside right',
            title='If anyone knows how to style a timeline email me at luka@aol.com',
            # title
            # gridcolor='#000'

        )


        from random import randint, uniform
        import textwrap

        colours = [
            'rgba(8, 84, 158,1)',
            'rgba(255, 136, 62,1)',
            'rgba(146, 92, 59,1)',
            'rgba(204, 158, 115,1)',
            'rgba(223, 197, 79,1)',
            'rgba(148, 0, 28,1)',            
        ]

        yPos = [0, 0.3, 0.60, 0.9]


        i=0 # don't leave this implementation this way with the i
        for row in self.df.iterrows():
            colour = 'rgba(8, 84, 158,1)'
            colour2 = 'rgba(255, 136, 62,1)'
            
            ran = round(uniform(-1, 1), 1)
            self.fig.add_vline(x=row[0], line_width=5, line_color=colour)
            self.fig.add_annotation(y=1-(yPos[i%4]),
                            x=row[0],
                            text="<b>"+row[1][1]+":<br>"+"<br>".join(textwrap.wrap(row[1][0],width =13, break_long_words=False))+"</b>",
                            showarrow=False,
                            # yshift=20, 
                            xshift=-2.5,
                            xanchor='left',
                            font=dict(color = colour),
                            # xref="paper",
                            align='left',
                            bgcolor=f'rgba(255, 255, 255, 1)',
                            bordercolor=colour2,
                            borderwidth=3,
                            borderpad=2,
                            )
            
            i += 1
            
        self.fig.update_yaxes(
            visible = False,
            
        )
        return
