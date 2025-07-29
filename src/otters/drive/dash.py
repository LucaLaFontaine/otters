# Plotly's Figure Friday challenge. See more info here: https://community.plotly.com/t/figure-friday-2024-week-32/86401
import dash
import pandas as pd
from dash import Dash, html, dcc, Input, Output, State, callback, Patch
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

class RegressionViewer(Dash):
    def __init__(self, models, mapping=None, external_stylesheets=[dbc.themes.BOOTSTRAP]):
        super().__init__(external_stylesheets=external_stylesheets)

        self.models = models
        self.mapping = mapping

        self.create_dashboard()

    def create_dashboard(self):

        reg_dropdown = html.Div(
            [
                dbc.Label("Select a regression", html_for="reg_dropdown"),
                dcc.Dropdown(
                    id="reg_dropdown",
                    options=sorted(list(self.models.models.keys())),
                    value=list(self.models.models.keys())[0],
                    clearable=False,
                    maxHeight=600,
                    optionHeight=50
                ),
            ],  className="mb-4",
        )

        control_panel = dbc.Card(
            dbc.CardBody(
                [reg_dropdown ],
                className="bg-light",
            ),
            className="mb-4"
        )

        heading = html.H1("Regression Viewer",className="bg-secondary text-white p-2 mb-4")

        about_card = dcc.Markdown(
            """
            Look at all regressions in the file
            """)

        info = dbc.Accordion([
            dbc.AccordionItem(about_card, title="About this tool", ),
        ],  start_collapsed=True)

        self.layout = dbc.Container(
            [
                dcc.Store(id="store-selected", data={}),
                heading,
                dbc.Row([
                    dbc.Col([control_panel], md=3),
                    dbc.Col([info], md=3),
                ]),
                dbc.Row([
                    dbc.Col(
                        [
                            dcc.Markdown(id="title"),
                            html.Div(id="bar-chart-card", className="mt-4"),
                        ],  md=9
                    ),
                ]),
                
            ],
            fluid=True,
        )

        @self.callback(
            Output("store-selected", "data"),
            Input("reg_dropdown", "value"),
        )
        def pin_selected_report(company):
            dfD = self.models.models[company].df.droplevel(0, axis=1)
            records = dfD.to_dict("records")
            return {"pinnedTopRowData": records}

        @self.callback(
            Output("bar-chart-card", "children"),
            Input("store-selected", "data"),
            Input("reg_dropdown", "value"),
        )
        def make_bar_chart(data, regName):
            regFon = self.models.models[regName]
            lp = regFon.model_component_graph(title=f'{regName}', mapping=self.mapping, just_baseline=False, tickFormat="%Y-%m-%d")
            y_hat_cols = [col for col in regFon.df.columns if col[0] == "Y_hat"]
            lp.plot.addLines(y_hat_cols, yaxis='y2')
            lp.plot.addLines([regFon.df.loc[:, ('Y', slice(None))].columns[0]], yaxis='y2')
            lp.plot.fig.update_layout(legend={'traceorder':'normal'})
            lp.plot.fig.update_layout(width=1300)
            lp.plot.fig.update_layout(separators="* .*")
            print(regFon.getRegEquation())
            print(f"r2: {regFon.score:.4f}, cv: {regFon.getCVRMSE(just_baseline=True):.4f}")
            return dbc.Card([
                dcc.Graph(figure=lp.plot.fig, style={"height":250}, config={'displayModeBar': False})
            ])

    def show(self):
        self.run(debug=True)