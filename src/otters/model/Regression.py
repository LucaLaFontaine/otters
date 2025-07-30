"""
We're gonna use scikit-learn regression for now. This should be abstract enough to change the package out or build models from scratch wihtou haffecting the API
"""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from scipy import stats
from math import sqrt
import openpyxl

from ..vis.graph import Graph

class LinearRegression(LinearRegression):
    """
    LinearRegression class after sklearn's, but calculate t-statistics
    and p-values for model coefficients (betas).
    Additional attributes available after .fit()
    are `t` and `p` which are of the shape (y.shape[1], X.shape[1])
    which is (n_features, n_coefs)
    This class sets the intercept to 0 by default, since usually we include it
    in X.
    """

    def __init__(self, fit_intercept=True, copy_X=True,
                 n_jobs=1):
        self.fit_intercept = fit_intercept
        self.copy_X = copy_X
        self.n_jobs = n_jobs
        # if not "fit_intercept" in kwargs:
        #     kwargs['fit_intercept'] = False
        super(LinearRegression, self).__init__()

    def fit(self, X, y, n_jobs=1):
        self = super(LinearRegression, self).fit(X, y, n_jobs)

        sse = np.sum((self.predict(X) - y) ** 2, axis=0) / float(X.shape[0] - X.shape[1])
        se = np.array([
            np.sqrt(np.diagonal(sse[i] * np.linalg.inv(np.dot(X.T, X))))
                                                    for i in range(sse.shape[0])
                    ])

        self.t = self.coef_ / se
        self.p = 2 * (1 - stats.t.cdf(np.abs(self.t), y.shape[0] - X.shape[1]))
        return self

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
                    # 'CV (low confidence)': model.cv,
                    'CV-RMSE': f"{model.cvrmse:.1%}",
                    'Intercept': model.reg.intercept_,
                    'Coef(s)': ['{:,.2f}'.format(coef) for coef in model.reg.coef_[0]],
                    'P-Values': model.reg.p,
                    'N_Samples': model.y.shape[0],
                    # 'Description': model.description
                }
            }
            modelTable.update(modelStructure)
        pd.options.display.float_format = '{:,.3f}'.format
        dfModels = pd.DataFrame(modelTable)
        return dfModels
    
    # def cusum():


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
            'just_baseline' : True,  
            'mapping' : {},
        }
        options.update(kwargs)

        # unpack the arguments and assign them to self.{argName}
        for arg in options.keys():
            self.__setattr__(arg, options[arg])

        self.x = pd.DataFrame(x)
        self.X = self.x#
        # If you have no start and end this will fail
        # self.x = self.x.loc[(self.x.index >= self.start) & (self.x.index <= self.end), :]

        self.y = pd.DataFrame(y)
        self.Y = self.y
        # self.y = self.y.loc[(self.y.index >= self.start) & (self.y.index <= self.end), :]

        return

class Regression(Model):
    def __init__(self, x, y, name, parent=None, **kwargs):
        self.parent = parent
        super().__init__(x, y, name, **kwargs)

        self.regress()
        self.getR2()
        self.getCV()
        self.getCVRMSE()
        return 
    
    def regress(self):

        if self.start and self.end:
            self.x = self.x.loc[(self.x.index >= self.start) & (self.x.index <= self.end), :]
        else:
            self.x = self.x

        if self.start and self.end:
            self.y = self.y.loc[(self.y.index >= self.start) & (self.y.index <= self.end), :]
        else:
            self.y = self.y
        self.reg = LinearRegression(fit_intercept=self.fit_intercept).fit(self.x, self.y)
        return
    
    def getR2(self):
        self.score = self.reg.score(self.x, self.y)
        return
    
    def getCVRMSE(self, just_baseline=True):
        """
        Take the coefficient of variation of the residual.  

        Basically tells you the total error of the model against the actual

        **Parameters:**  
        >**None**

        **Returns:**  
        >**float**
        """
        
        # regenerate the df. not super efficient but needed to decide wheter to take morte than the baseline
        ## This line was resettin the just_baseline
            # self.just_baseline = just_baseline
        self.to_frame(just_baseline=just_baseline)
        df = self.df.copy()
        # if just_baseline==True:
        #     df = df.loc[(df.index >= self.start) & (df.index <= self.end)]
        # create the residuals/diff column temporarily
        df['residuals', 'diff'] = df.loc[:, ('Y', slice(None))].squeeze() - df.loc[:, ('Y_hat', slice(None))].squeeze()
        standard_error = np.std(df['residuals', 'diff'])    
        cvrmse = (1/df.loc[:, ('Y', slice(None))].mean())*standard_error
        self.cvrmse = cvrmse[0]
        return self.cvrmse
    
    def stats(self):
        string = f"""
        R2: {self.score}
        CV-RMSE: {self.cvrmse}
        Intercept: {self.reg.intercept_}
        Coef(s): {self.reg.coef_}
        """.replace(' ', '')
        print(string)
        return
    
    def getCV(self):
        mean = self.y[self.y != 0].mean()
        std = self.y[self.y != 0].std()

        self.cv = std/mean*100
        self.cv = self.cv[0]
        return self.cv
    
    def to_frame(self, just_baseline=None, mapping=None):
        if just_baseline != just_baseline:
            just_baseline = self.just_baseline
        if just_baseline:
            X = self.x.copy()  
            Y = self.y.copy()  
        else:
            X = self.X.copy()  
            Y = self.Y.copy()

        X.columns = pd.MultiIndex.from_product([['X'], X.columns, ])
        Y.columns = pd.MultiIndex.from_product([['Y'], Y.columns, ])
        Y_hat = self.reg.coef_*X
        Y_hat = Y_hat.sum(axis=1)
        Y_hat = Y_hat + self.reg.intercept_
        Y_hat.rename(('Y_hat', "Model"), inplace=True)
        Y_hat = Y_hat.to_frame()
        # Y_hat.rename(columns={"Y":"Y_hat"}, inplace=True)
        Y_hat.columns = Y_hat.columns.set_levels(['Y_hat'], level=0)
        X['intercept', 'intercept'] = self.reg.intercept_[0]

        self.df = pd.concat([Y_hat, Y, X], axis=1)

        if mapping:
            self.mapping = mapping
        
        self.df.rename(columns=self.mapping, level=-1, inplace=True)

        return self.df
    
    def model_component_graph(self, mapping=None, title='Model Component Graph', just_baseline=False, **kwargs):
        if mapping:
            print("mapping exists")
            self.mapping = mapping
        # self.remapColumnNames()
        # regenerate the df. not super efficient
        self.just_baseline = just_baseline
        self.to_frame()
        df = self.df.copy()
        df.loc[:, ('X', slice(None))] *= np.array(self.reg.coef_)
        # df.rename(columns=mapping, level=-1, inplace=True)
        lp = Graph(df, title=title, **kwargs)
        df.sort_index(ascending=[1, 0], inplace=True, axis=1)
        lp.plot.addAreaLines(df.loc[:, (['intercept', 'X'], slice(None))].columns)
        lp.plot.addLines(df.loc[:, ('Y', slice(None))].columns, level=slice(0, 2), line=dict(width=5, color="rgba(196, 30, 58, 1)"))
        lp.plot.addLines(df.loc[:, ('Y_hat', slice(None))].columns, line=dict(width=5, color="rgba(68, 114, 96, 1)"))
        return lp
    
    def getRegEquation(self, mapping=None):
        if mapping:
            self.mapping = mapping
        # self.remapColumnNames()

        equationXs = list(zip(self.df.loc[:, ("X", slice(None))].columns.get_level_values(-1), self.reg.coef_[0]))

        equationXs = ["[{}]*{:,.6g}".format(termName, termCoef) for termName, termCoef in equationXs]

        equationXs = " + ".join(equationXs)
        equationStr = """Modèle = {:,.6g} + {}""".format(self.reg.intercept_[0], equationXs)
        self.equation = equationStr
        
        return equationStr