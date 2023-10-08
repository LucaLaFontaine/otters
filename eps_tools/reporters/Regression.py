"""
We're gonna use scikit-learn regression for now. This should be abstract enough to change the package out or build models from scratch wihtou haffecting the API
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


class Models():
    def __init__(self):
        self.models = {}
        return
    def regression(self, x, y, name='', **kwargs):
        if not name:
            name = f'Regress{len(self.models)}'

        reg = Regression(x, y, name, parent=self, **kwargs)
        self.models.update({name: reg})
        return
    def tabulateModels(self):
        modelTable = {}
        for model in self.models.values():
            modelStructure = {
                model.name: {
                    'start' : model.start,
                    'end' : model.end,
                    'R2': model.score,
                    'CV (low confidence)': model.cv,
                    'Intercept': model.reg.intercept_,
                    'Coef(s)': ['{:,.2f}'.format(coef) for coef in model.reg.coef_[0]],
                    'Description': model.description
                }
            }
            modelTable.update(modelStructure)
        pd.options.display.float_format = '{:,.3f}'.format
        dfModels = pd.DataFrame(modelTable)
        return dfModels

class Model():
    """
    The generic model object. Gets associate to a list of models and parents specific models such as the Regression object
    """
    def __init__(self, x, y, name, **kwargs):
        self.name = name

        # Default kwarg values, later updated with the passed kwargs
        options = {
            'start' : None,
            'end' : None,
            'description' : '',
            'fit_intercept' : True,     
        }
        options.update(kwargs)

        # unpack the arguments and assign them to self.{argName}
        for arg in options.keys():
            self.__setattr__(arg, options[arg])

        self.x = pd.DataFrame(x)
        self.x = self.x.loc[(self.x.index >= self.start) & (self.x.index <= self.end), :]

        self.y = pd.DataFrame(y)
        self.y = self.y.loc[(self.y.index >= self.start) & (self.y.index <= self.end), :]

        return

class Regression(Model):
    def __init__(self, x, y, name, parent=None, **kwargs):
        self.parent = parent
        super().__init__(x, y, name, **kwargs)

        self.regress()
        self.getR2()
        self.getCV()
        return 
    
    def regress(self):

        if self.start and self.end:
            self.X = self.x.loc[(self.x.index >= self.start) & (self.x.index <= self.end), :]
        else:
            self.X = self.x

        if self.start and self.end:
            self.Y = self.y.loc[(self.y.index >= self.start) & (self.y.index <= self.end), :]
        else:
            self.Y = self.y

        self.reg = LinearRegression(fit_intercept=self.fit_intercept).fit(self.X, self.Y)
        return
    
    def getR2(self):
        self.score = self.reg.score(self.X, self.Y)
        return
    
    def stats(self):
        string = f"""
        R2: {self.score}
        Intercept: {self.reg.intercept_}
        Coef(s): {self.reg.coef_}
        """.replace(' ', '')
        print(string)
        return
    
    def getCV(self):
        mean = self.y[self.y != 0].mean()
        std = self.y[self.y != 0].std()

        self.cv = std/mean*100
        return self.cv
