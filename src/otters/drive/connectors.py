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
        url = config['api_url']+config['dataset']
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


class JoolConnectorV2(JoolConnector):
    """
    Version 2 of the JoolConnector designed for the new federated OIDC login flow.

    The JOOL platform moved from a server-rendered ASP.NET login form to a federated
    architecture: IdentityServer (api-auth host) delegates authentication to Keycloak
    (external IdP). The old ``get_bearer_auth`` scraped ``__RequestVerificationToken``
    and ``ReturnUrl`` from the IdentityServer HTML form, which no longer exists.

    This class preserves the same public interface (``get_bearer_auth``, ``data_call``,
    ``get_reference_data``) so that callers in ``otters.model.jool_data`` and elsewhere
    can switch from ``JoolConnector`` to ``JoolConnectorV2`` with no other changes.

    Auth strategy (in order of preference):
        1. Cached access token that has not yet expired.
        2. Refresh-token exchange (avoids a full re-login).
        3. Resource Owner Password Credentials (ROPC) grant — a single token-endpoint
           POST, no browser-form scraping required.
        4. Full Authorization Code + PKCE flow following the IdentityServer → Keycloak
           redirect chain with ``requests.Session`` (browser-equivalent, resilient to
           Keycloak form field name changes).
    """

    def __init__(self, USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="", config=None):
        super().__init__(USER=USER, PASSWORD=PASSWORD, root_url=root_url, tenant_url=tenant_url, token_url=token_url, auth_url=auth_url, config=config)
        self._access_token = None
        self._token_expiry = None
        self.refresh_token = None

    def _resolve_credentials(self, USER=None, PASSWORD=None):
        """Return (username, password), preferring explicit args over env vars."""
        username = USER if USER is not None else os.getenv('user')
        password = PASSWORD if PASSWORD is not None else os.getenv('password')
        if not username or not password:
            raise ValueError("JoolConnectorV2 requires credentials: pass USER/PASSWORD or set 'user'/'password' env vars.")
        return username, password

    def _store_tokens(self, token_response):
        """Cache access token, refresh token, and expiry from a token-endpoint JSON response."""
        self._access_token = token_response.get('access_token')
        expires_in = token_response.get('expires_in', 3600)
        self._token_expiry = datetime.now() + timedelta(seconds=expires_in)
        if 'refresh_token' in token_response:
            self.refresh_token = token_response['refresh_token']

    def _token_is_valid(self):
        """True if a cached access token exists and has more than 60s of life left."""
        return (
            self._access_token is not None
            and self._token_expiry is not None
            and datetime.now() < self._token_expiry - timedelta(seconds=60)
        )

    def refresh_bearer_auth(self, root_url="", token_url="/connect/token", refresh_token=None):
        """
        Exchange a refresh token for a new access token.

        :param root_url: Base URL of the IdentityServer (e.g. ``https://...api-auth...``).
        :param token_url: Token endpoint path (default ``/connect/token``).
        :param refresh_token: A refresh token string. If omitted, uses ``self.refresh_token``.
        :return: New access token string.
        :raises RuntimeError: If no refresh token is available or the exchange fails.
        """
        rt = refresh_token if refresh_token is not None else self.refresh_token
        if not rt:
            raise RuntimeError("No refresh token available — call get_bearer_auth() first.")

        resp = requests.post(
            url=root_url + token_url,
            data={
                "grant_type": "refresh_token",
                "client_id": "Frontend",
                "refresh_token": rt,
            },
        )
        if resp.status_code != 200 or 'access_token' not in resp.json():
            self.refresh_token = None
            raise RuntimeError(f"Refresh token exchange failed: HTTP {resp.status_code} — {resp.text}")

        self._store_tokens(resp.json())
        return self._access_token

    def get_bearer_auth(self, USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="", *args, **kwargs):
        """
        Get a bearer access token from the new federated JOOL login flow.

        Tries (in order): cached token → ROPC → Authorization Code + PKCE fallback.

        Parameters
        ----------
        USER : str, optional
            Username. Falls back to ``os.getenv('user')``.
        PASSWORD : str, optional
            Password. Falls back to ``os.getenv('password')``.
        root_url : str
            IdentityServer base URL (e.g. ``https://publinergie-ca-api-auth.prod.emm.metronlab.tech``).
        tenant_url : str
            Tenant / redirect URI (e.g. ``https://publinergie-ca.jool.energy``).
        token_url : str
            Token endpoint path (e.g. ``/connect/token``).
        auth_url : str
            Authorize endpoint path (e.g. ``/connect/authorize``).

        Returns
        -------
        str
            The bearer access token.
        """
        if self._token_is_valid():
            return self._access_token

        username, password = self._resolve_credentials(USER, PASSWORD)

        if not token_url:
            token_url = "/connect/token"
        if not auth_url:
            auth_url = "/connect/authorize"

        # Strategy 1: Resource Owner Password Credentials (single request, no scraping)
        token = self._get_bearer_ropec(username, password, root_url, tenant_url, token_url)
        if token:
            return token

        # Strategy 2: Full Authorization Code + PKCE (browser-equivalent redirect chain)
        token = self._get_bearer_auth_code(username, password, root_url, tenant_url, token_url, auth_url)
        if token:
            return token

        raise RuntimeError("All authentication strategies failed. Check credentials, config URLs, and network access.")

    def _get_bearer_ropec(self, username, password, root_url, tenant_url, token_url):
        """Attempt Resource Owner Password Credentials grant. Returns token or None."""
        try:
            resp = requests.post(
                url=root_url + token_url,
                data={
                    "grant_type": "password",
                    "client_id": "Frontend",
                    "username": username,
                    "password": password,
                    "scope": "Web.Api.Display Web.Api.User offline_access openid",
                    "acr_values": f"tenant:{tenant_url}",
                },
            )
            if resp.status_code == 200 and 'access_token' in resp.json():
                self._store_tokens(resp.json())
                return self._access_token
        except requests.RequestException:
            pass
        return None

    def _get_bearer_auth_code(self, username, password, root_url, tenant_url, token_url, auth_url):
        """
        Full Authorization Code + PKCE flow through the IdentityServer → Keycloak
        redirect chain. Uses ``requests.Session`` to maintain cookies across hosts.

        Returns access token string, or None on failure.
        """
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36",
        })

        code_challenge = self.create_code_challenge()

        auth_params = {
            "client_id": "Frontend",
            "redirect_uri": tenant_url,
            "response_type": "code",
            "scope": "Web.Api.Display Web.Api.User offline_access openid",
            "code_challenge": code_challenge["challenge"],
            "code_challenge_method": "S256",
            "acr_values": f"tenant:{tenant_url}",
        }

        # Follow the redirect chain: IdentityServer → Keycloak login page (HTML form)
        try:
            r_auth = session.get(root_url + auth_url, params=auth_params, allow_redirects=True)
        except requests.RequestException:
            return None

        # Parse the final login form (Keycloak or IdentityServer, depending on redirect chain).
        # Extract ALL hidden inputs dynamically — don't hardcode field names.
        soup = BeautifulSoup(r_auth.content, features="html.parser")
        form = soup.find("form")
        if not form:
            return None

        action = form.get("action")
        if not action:
            return None
        # Resolve relative action URLs against the page we landed on
        login_post_url = urllib.parse.urljoin(r_auth.url, action)

        # Collect every hidden input so the login POST mirrors the browser exactly
        form_data = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name and inp.get("type", "").lower() in ("hidden", "text"):
                form_data[name] = inp.get("value", "")
        form_data["username"] = username
        form_data["password"] = password

        # Submit credentials — follow redirects through Keycloak → IdentityServer → tenant callback.
        # The final URL will contain ?code=... (the authorization code).
        try:
            resp = session.post(login_post_url, data=form_data, allow_redirects=True)
        except requests.RequestException:
            return None

        # Extract the authorization code from the final URL or redirect history.
        code = self._extract_auth_code(resp)
        if not code:
            return None

        # Exchange the authorization code for tokens at the token endpoint.
        try:
            token_resp = requests.post(
                url=root_url + token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": "Frontend",
                    "redirect_uri": tenant_url,
                    "code": code,
                    "code_verifier": code_challenge["verifier"],
                },
                allow_redirects=False,
            )
        except requests.RequestException:
            return None

        if token_resp.status_code == 200 and 'access_token' in token_resp.json():
            self._store_tokens(token_resp.json())
            return self._access_token
        return None

    def _extract_auth_code(self, resp):
        """
        Extract the ``code`` query parameter from a redirect response.

        Checks the final response URL and every ``Location`` header in the redirect
        history, since the code may appear in any hop.
        """
        candidates = []
        if resp.url:
            candidates.append(resp.url)
        for r in resp.history:
            loc = r.headers.get('Location')
            if loc:
                candidates.append(loc)

        for url in candidates:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if 'code' in params:
                return params['code'][0]
        return None

    def get_reference_data(self, reference, start_date=None, end_date=None, config=None):
        """
        Fetch raw data for a single reference over a date range.

        Overrides the v1 method to use a cached or refreshed token when available,
        avoiding a full re-login on every call.

        :param reference: The meter/equipment reference string.
        :param start_date: Start datetime (defaults to 1 year ago).
        :param end_date: End datetime (defaults to now).
        :param config: Config dict with ``root_url``, ``token_url``, ``tenant_url``,
                       ``auth_url``, ``api_url``, ``dataset``, ``timezone``.
                       Falls back to ``self.config`` if omitted.
        :return: DataFrame of raw data.
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)
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
            "selection": [reference],
        }

        # Try cached token, then refresh token, then full auth
        if self._token_is_valid():
            bearer_auth = self._access_token
        else:
            bearer_auth = None
            if self.refresh_token:
                try:
                    bearer_auth = self.refresh_bearer_auth(
                        root_url=config.get("root_url", ""),
                        token_url=config.get("token_url", "/connect/token"),
                    )
                except RuntimeError:
                    bearer_auth = None
            if not bearer_auth:
                bearer_auth = self.get_bearer_auth(**config)

        df = self.data_call(data, bearer_auth, config, True)
        return df