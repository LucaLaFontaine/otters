"""
Any code written to connect to data repositories like BMS, EMISs, and other websites
"""

import base64
import os
import hashlib
import requests
import re
import urllib
import sys
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

from otters.wrangle.time_tools import str2dt

class JoolConnector:
    def __init__(self, USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="", config=None):
        # self.get_bearer_auth(USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="")
        self.config = config
        return


    def create_code_challenge(self) -> dict:
        """
        Create a sha256 code challenge to send as an authentification method.  

        This format was developed specifically for JOOL

        Parameters
        ----------
        None
        
        Returns
        -------
        Dict
            |challenge : The code challenge   
            |verifier : The code verifier
        """

        code_verifier = base64.urlsafe_b64encode(os.urandom(40)).decode('utf-8')
        code_verifier = re.sub('[^a-zA-Z0-9]+', '', code_verifier)
        code_verifier, len(code_verifier)

        code_challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode('utf-8')
        code_challenge = code_challenge.replace('=', '')
        code_challenge, len(code_challenge)

        return {"challenge":code_challenge, "verifier":code_verifier} 

    def get_bearer_auth(self, USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="", *args, **kwargs):
        """
        Get a bearer authentication code from a website like JOOL  

        .. admonition::  todo  
            :class: attention

            Verify that all the required variables are non-null and throw a targeted error if not.

        Parameters
        ----------
        I really don't have time to complete this, please do it if you see this
        
        Returns
        -------
        String
            Returns the bearer auth as I think a string

        """

        # Create the code challenge to verify with the server that you are the client that you say you are
        code_challenge = self.create_code_challenge()

        # Deliver intent to connect to the site and collect the response
        data = {
            "client_id":"Frontend",
            "redirect_uri":tenant_url,
            "response_type":"code",
            "scope":"Web.Api.Display Web.Api.User offline_access openid",
            "code_challenge": code_challenge["challenge"],
            "code_challenge_method": "S256",
            "acr_values": f"tenant:{tenant_url}",
        }

        r_auth = requests.get(root_url+auth_url, params=data)
        # return r_auth
        # use the repsonse to set the cookie, return url, verification token, and get the form button I think
        cookie = r_auth.headers['Set-Cookie']
        soup = BeautifulSoup(r_auth.content, features="html.parser")
        
        return_url = soup.find("input", {"name":"ReturnUrl"}).get('value')
        return_url_encoded = requests.utils.quote(return_url, safe='')
        verificationToken = soup.find("input", {"name":"__RequestVerificationToken"}).get('value')

        # Send credentials to the login form along with the return url and verification token. collect the response
        resp = requests.post(
            url=root_url+"/auth/Account/Login?ReturnUrl="+return_url_encoded,
            data={
                "Origin": tenant_url,
                "Tenant": tenant_url,
                "ReturnUrl":return_url,
                "username": os.getenv('user'),
                "password": os.getenv('password'),
                "__RequestVerificationToken": verificationToken,
            }, 
            headers={"Cookie": cookie},
        )
    
        # To get the bearer auth code you need to intercept a code that gets passed during redirect. 
            # So you check the history for the "code" which you have to parse out of the url directly because the headers aren't decoded. we could probably decode them but this is easier
        redirect = resp.history[-1].headers['Location']
        query = urllib.parse.urlparse(redirect).query
        redirect_params = urllib.parse.parse_qs(query)
        code = redirect_params['code'][0]

        # Once you have this code you send that to the token server which exchanges codes for bearer_auth codes
            # Parse the bearer_auth out of the response and there you go. 
            # With this bearer_auth you can use the API as the user that collected it no questions asked.
        resp = requests.post(
            url=root_url+token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": "Frontend",
                "redirect_uri": tenant_url,
                "code": code,
                "code_verifier": code_challenge["verifier"],
            },
            allow_redirects=False
        )

        bearer_auth = resp.json()['access_token']
        return bearer_auth
    
    def data_call(self, data, bearer_auth, config, raw=False):
        """
        Makes a call to the jool system with 1 tag and a date range. 

        :param data: dict containing `from`, `to`, and  `tag`
        :type data: dict, required

        :param bearer_auth: string output of get_bearer_auth()
        :type bearer_auth: str, required

        :param config: The config for that site
        :type config: dict, required

        :param raw: Set to `True` to keep all the metada for database updates. If not it will rerturn a clean version for direct analysis
        :type raw: bool, default: `False`

        :return: DataFrame
        """

        headers = {"Authorization": f"Bearer {bearer_auth}"}
        url = config['root_url']+config['api_url']+config['dataset']
        r = requests.post(url, json=data, headers=headers)
        content = r.json()
        rows = content['tables'][0]['rows']
        columns = content['tables'][0]['columns']
        columns = [col['reference'] for col in columns]
        df = pd.DataFrame().from_records(rows)
        # return content

        # If the df is empty at this point name the columns and return an empty df
        if df.empty:
            return pd.DataFrame(columns=columns)
        df.columns = columns
        
        # return df
        df['METER.REFERENCE'] = data['selection'][0]

        df = str2dt(df, timeCol="RAWDATA.LOCAL_TIME_STAMP")
        # Jool holds time data in the database as UTC and changes "local" time on affichage. So even though this column says its local the actual data is UTC
        # Bref: You need to adjust the timezone to the relevant timezone
        df.index = df.index.tz_convert(config["timezone"])
        df.index = df.index.tz_localize(None, ambiguous='infer')

        df = df.loc[:, ['RAWDATA.VALUE', 'CHANNEL.REFERENCE', 'CHANNEL.CNL_DAC_UNIT', 'METER.REFERENCE']]

        if raw:
            return df
        
        df = df.pivot(columns='CHANNEL.REFERENCE', values='RAWDATA.VALUE')


        return df
    
    def get_all_children(self, ref, df, recursive=False, connections=None):
        ref_col = "METER.REFERENCE"
        child_col = "METER.PARENT_CHILD"
        
        if not connections:
            connections = {}

        children = df.loc[df[ref_col] == ref, child_col].unique().tolist()
        children = filter(lambda x: x==x, children)
        
        connections.setdefault("children", []).extend(children)
        
        if recursive:
            for child in children:
                connections = self.get_all_children(child, df, recursive=recursive, connections=connections)
        
        return connections

    def get_all_connections(self, ref, df, recursive=False, get_attachments=True, connections=None):
        ref_col = "METER.REFERENCE"
        attached_col = "METER.ATTACHED_SYSTEM"

        connections = self.get_all_children(ref, df, recursive=False, connections=None)
        
        # Get the attachments at just this level
        if get_attachments:
            attachments = df.loc[df[ref_col] == ref, attached_col].unique().tolist()
            attachments = filter(lambda x: x==x, attachments)
        else:
            attachments = []
        connections.setdefault("attached", []).extend(attachments)


        if recursive:
            for child in connections["children"]:
                connections = self.get_all_children(child, df, recursive=recursive, connections=connections)

        return connections
    
    def resample_jool_data(df, period="15min"):
        max_cols = [col for col in df.columns if "ETAT" in col]
        mean_cols = [col for col in df.columns if col not in max_cols]

        df_max = df.loc[:, max_cols].resample(period).max()
        df_mean = df.loc[:, mean_cols].resample(period).mean()

        df = pd.concat([df_max, df_mean], axis=1)

        return df
    
    def get_reference_data(self, reference, start_date=None, end_date=None, config=None):

        if not start_date:
            start_date = datetime.now() - timedelta(years=1)
        if not end_date: 
            end_date = datetime.now()
        
        if not config:
            if self.config:
                config = self.config
            else: 
                raise Exception("No config has been set")

        data = {
            "from": start_date.strftime(format="%Y-%m-%dT%H:%M:00.000Z"), 
            "to": end_date.strftime(format="%Y-%m-%dT%H:%M:00.000Z"),
            "selection" : [reference],
        }
        bearer_auth = self.get_bearer_auth(**config)
        df = self.data_call(data, bearer_auth, config, True)

        return df