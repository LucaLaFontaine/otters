
from functools import wraps
import inspect
from glob import glob

# within package/mymodule1.py, for example
import pkgutil
import yaml

import pandas as pd
from datetime import date, timedelta, time, datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from otters.wrangle.file_loader import import_config



class Graph():
    def __init__(self, df=pd.DataFrame(), plot=True, **kwargs):

        # An apparently good way to load a static file in the tree of the package, not the caller. 
            # This is the default config for plots and is overwritten by everything
        default_conf_binary = pkgutil.get_data(__name__, "conf.yaml")
        default_conf = yaml.load(default_conf_binary, Loader=yaml.FullLoader)

        # Default kwarg values, later updated with the passed kwargs
        options = {
            'title' : '',
            'df' : df,
            'graphCols' : df.columns,
            'xTitle' : '',
            'yTitle' : '',     
        }
        options.update(default_conf)
        options.update(kwargs)
        
        # unpack the arguments and assign them to self.{argName}
        for arg in options.keys():
            self.__setattr__(arg, options[arg])
        self.config = options

        if plot:
            self.plot = Plot(self)

        return
    
    def __repr__(self):
            return f"Graph(name='{self.title}', cols={self.df.columns})"
    
    def show(self):
        self.plot.fig.show()
        return

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
        self.full_setup()


    def __repr__(self):
                return f"Plot(name='{self.title}', cols={self.df.columns})"

    def full_setup(self, fig=None):
        self.createPlot(fig)
        self.setYAxisRange()
        self.formatYAxis()
        if self.df.index.inferred_type == "datetime64":
            self.timeFormatXAxis()
        else:
            self.formatXAxis()
        return
    def createPlot(self, fig=None):
        """
        Creates a plot in the EPS style. Most of this crap is formatting
        We add here the trendline(s), the legend, x/y axes.
        """
        if fig:
            self.fig = fig
        else:
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
        )
        self.fig.update_legends(
            title='', 
            orientation='h',
            yanchor='top', 
            xanchor='center', 
            xref='container', 
            yref='container', 
            y=0.9, x=0.5
        )
        return
    
    def addLines(self, cols=None, **kwargs):
        if not cols:
            cols = self.df.columns
        df = self.df.loc[:, cols]
        for col in cols:
            self.fig.add_trace(
                go.Scatter(
                    y=df[col],
                    x=df.index,
                    mode='lines',
                    name=col,
                    showlegend=True,
                    **kwargs
                )
            )
        self.formatYAxis()
        return
    
    def addAreaLines(self, cols=None, stack_group='one', **kwargs):
        if not cols:
            cols = self.df.columns
        df = self.df.loc[:, cols]
        for col in cols:
            self.fig.add_trace(
                go.Scatter(
                    y=df[col],
                    x=df.index,
                    mode='lines',
                    name=col,
                    showlegend=True,
                    line=dict(width=0.5),
                    stackgroup=stack_group,
                    **kwargs
                )
            )
        self.formatYAxis()
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
    def timeFormatXAxis(self, scaleTimestamps=False):
        self.formatXAxis()
        self.tickFormat = self.config['tickFormat']
        self.xTickAngle = self.config['xTickAngle']
        self.xMaxTicks = self.config['xMaxTicks']
        self.dTick = self.config['dTick']
        self.tick0 = self.config['tick0']

        # This is only really for ExPS. This should arguably be replaced by just passing an **args thing into update_xaxes
        if scaleTimestamps:
            scaleDTick = self.scaleDTick()
        else:
            scaleDTick = None
        self.fig.update_xaxes(
            tickformat=self.tickFormat,
            tickangle=self.xTickAngle,
            tick0=datetime(self.tick0['year'], self.tick0['month'], self.tick0['day'], self.tick0['hour'], self.tick0['minute']),
            dtick=scaleDTick,
            )

    def formatYAxis(self):
        
        # need to handle both series 1-d and 2-d arrays
        if isinstance(self.df.squeeze(),pd.DataFrame):
            max_value = self.df.squeeze().max().max()
        elif isinstance(self.df.squeeze(),pd.Series):
            max_value = self.df.squeeze().max()
        else:
            raise TypeError("Please pass a DataFrame or Series")
        
        self.fig.update_yaxes(
            range=list([self.yAxisRange[0], max_value*self.yAxisRange[1]]),
            showline=True, 
            linewidth=1, 
            linecolor='#262626', 
            showgrid=True, 
            gridwidth=0.75, 
            gridcolor='rgba(235, 235, 235, 1)', 
            title_text=self.yTitle,
            )
        
        # Remove some stuff off the secondary axis by default
        self.fig['layout']['yaxis2']['title'] = ''
        self.fig['layout']['yaxis2']['showgrid'] = False
        
    def boundYAxis(self):
        """
        **Should be replaced by the folloifing:**
        self.fig.update_yaxes(autorange="max", autorangeoptions_include=0)  

        Bounds the range of each y axis to the traces currently present on the plot
        This is way too complicated, but I need to move on
        """
        # Get all the y_maxes on the plot and their y axis
        y_maxes = [{'yaxis':item['yaxis'], 'max':item['y'].max()} for item in self.fig.data]

        # Create a dict of the y_maxes sorted by max. Then update another dict with the highest max for that axis, creating a "set" of the axes with the highest max
        y_maxes_set = {}
        y_maxes_dict = [{ymax['yaxis'] : ymax['max']} for ymax in sorted(y_maxes, key=lambda x: x['max'])]
        for axis in y_maxes_dict:
            y_maxes_set.update(axis)

        # the primary axis is 'null' so that's how I'm checking for a secondary axis. 
            # Notice this will only work with 2 axes, but who cares
        for axis in y_maxes_set.items():
            if axis[0]:
                sec_y = True
            else:
                sec_y=False
            self.fig.update_yaxes(range=[0,axis[1]], secondary_y=sec_y)
        return
    
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
    
    def sparklines(self, cols=None, colWidth=3, yTitles=None, **kwargs):
        if not cols:
            cols = self.df.columns
        # for col in cols:
        
        if not yTitles:
            yTitles = ['' for col in cols]
        elif type(yTitles) is str:
            yTitles = [yTitles for col in cols]

        from math import ceil
        numRows = ceil(len(cols)/colWidth)
        fig = make_subplots(
            rows=numRows, 
            cols=colWidth,
            subplot_titles=cols
        )
        
        self.full_setup(fig=fig)

        ctr = 0
        for row in range(1, numRows+1):
            for i, col in enumerate(cols[row*colWidth-colWidth:row*colWidth]):
                self.fig.add_trace(
                    go.Scatter(
                        x=self.df.index, 
                        y=self.df[col],
                        name=col
                    ),
                    row=row, 
                    col=i+1
                    )
                try:
                    self.fig.update_yaxes(title_text=yTitles[ctr], row=row, col=i+1)
                    # Simple and dirty, but also readable lol
                    ctr += 1
                except Exception as e:
                    raise IndexError("It's likely that you passed a list of the wrong length for your 'yTitles'") from e

        self.fig.update_layout(
            height=numRows*400, 
            width=self.config['plotWidth'],
            title_text=self.title,
        )

        self.fig.update_yaxes(autorange="max", autorangeoptions_include=0)
        return
