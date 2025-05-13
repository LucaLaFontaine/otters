import pytest

from otters.wrangle.time_tools import *


def test_str2dt_cols_are_strings():
    df = pd.DataFrame({1: [1, 2, 3], None: [4, 5, 6], 'C': [7, 8, 9]})
    # df['time'] = ['2021-01-01 00:00:00', '2021-01-01 01:00:00', '2021-01-01 02:00:00']
    df['Time'] = ['2021-01-01 00:00:00', '2021-01-01 01:00:00', '2021-01-01 02:00:00']
    
    df = str2dt(df)
    for col in df.columns:
        assert type(col) == str