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

from bs4 import BeautifulSoup

def create_code_challenge() -> dict:
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

def get_bearer_auth(USER=None, PASSWORD=None, root_url="", tenant_url="", token_url="", auth_url="", **kwargs):
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
    code_challenge = create_code_challenge()

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
            "username": USER,
            "password": PASSWORD,
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