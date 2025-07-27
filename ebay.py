import requests
from base64 import b64encode
import base64
from urllib.parse import urlparse, parse_qs
import webbrowser
import time
import json
from config import client_id, client_secret, redirect_uri

def setup_tokens():
    # REFRESH TOKEN:
    try:
        # Load the token and expiry time from the file
        with open("ebayRefreshToken.json", "r") as token_file:
            token_data = json.load(token_file)
        refresh_token = token_data["refresh_token"]
        expiry_time = token_data["expiry_time"]
    except FileNotFoundError:
        expiry_time = 0

    # Check if token is still valid (optional)
    if time.time() > expiry_time:
        print("Refresh token expired. Please refresh.")
        # Define all the scopes based on your requirements - what I need to use
        scopes = (
            "https://api.ebay.com/oauth/api_scope "
        )

        # Set the target endpoint for the consent request in production
        consent_endpoint_production = "https://auth.ebay.com/oauth2/authorize"
        token_endpoint = "https://api.ebay.com/identity/v1/oauth2/token"

        # Define the consent URL
        consent_url = (
            f"{consent_endpoint_production}?"
            f"client_id={client_id}&"
            f"redirect_uri={redirect_uri}&"
            f"response_type=code&"
            f"scope={scopes}"
        )

        # Open the consent URL in the default web browser
        webbrowser.open(consent_url)

        print("Opening the browser. Please grant consent in the browser.")

        # Retrieve the authorization code from the user after they grant consent
        authorization_code_url = input("Enter the authorization code URL: ")

        # Parse the URL to extract the authorization code
        parsed_url = urlparse(authorization_code_url)
        query_params = parse_qs(parsed_url.query)
        authorization_code = query_params.get('code', [])[0]

        # Make the authorization code grant request to obtain the token
        payload = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": redirect_uri
        }

        # Encode the client credentials for the Authorization header
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = b64encode(credentials.encode()).decode()

        # Set the headers for the token request
        token_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {encoded_credentials}"
        }

        # Make the POST request to the token endpoint
        response = requests.post(token_endpoint, headers=token_headers, data=payload)

        # Check the response
        if response.status_code == 200:
            # Parse and print the response JSON
            response_json = response.json()
            print("Response containing the User access token:")
            print(response_json)

            try:
                new_token = response_json
                print(new_token)
                expiry_time = time.time() + new_token["refresh_token_expires_in"]

                # Save token and expiry time to a file
                token_data = {"refresh_token": new_token["refresh_token"], "expiry_time": expiry_time}
                with open("ebayRefreshToken.json", "w") as token_file:
                    json.dump(token_data, token_file)

                print("New refresh token and expiry time saved to file.")

            except requests.exceptions.RequestException as e:
                print("Error:", e)
        else:
            print(f"Error: {response.status_code}, {response.text}")

    else:
        print("Valid refesh token.")


    # ACCESS TOKEN:

    # Load the token and expiry time from the file
    with open("ebayAccessToken.json", "r") as token_file:
        token_data = json.load(token_file)
    access_token = token_data["access_token"]
    expiry_time = token_data["expiry_time"]

    # Check if token is still valid (optional)
    if time.time() > expiry_time:
        print("Access token expired. Refreshing.")
        
        # Base URL for token endpoint
        token_url = "https://api.ebay.com/identity/v1/oauth2/token"

        # Function to encode credentials for authorization header
        def encode_credentials():
            credentials = f"{client_id}:{client_secret}"
            encoded_credentials = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
            return f"Basic {encoded_credentials}"

        # Function to refresh access token
        def refresh_access_token():
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": encode_credentials()
            }
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "scope": "https://api.ebay.com/oauth/api_scope"  # Replace with your desired scopes
            }
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()
            return response.json()

        try:
            new_token = refresh_access_token()
            expiry_time = time.time() + new_token["expires_in"]

            # Save token and expiry time to a file
            token_data = {"access_token": new_token["access_token"], "expiry_time": expiry_time}
            with open("ebayAccessToken.json", "w") as token_file:
                json.dump(token_data, token_file)

            access_token = new_token["access_token"]
            
            print("New access token and expiry time saved to file.")

        except requests.exceptions.RequestException as e:
            print("Error:", e)

    else:
        print("Valid access token.")

    return access_token, expiry_time
