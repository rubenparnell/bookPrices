import requests
import base64
from urllib.parse import urlparse, parse_qs
import webbrowser
import time
import json
from config import client_id, client_secret, redirect_uri

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
AUTH_URL = "https://auth.ebay.com/oauth2/authorize"


def encode_credentials():
    credentials = f"{client_id}:{client_secret}"
    return "Basic " + base64.b64encode(credentials.encode()).decode()


def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f)


def load_json(filename):
    try:
        with open(filename, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def get_new_tokens_via_auth():
    print("🔐 Starting manual authentication...")

    scopes = "https://api.ebay.com/oauth/api_scope"

    consent_url = (
        f"{AUTH_URL}?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope={scopes}"
    )

    webbrowser.open(consent_url)
    print("Opened browser. Please log in and paste the FULL redirect URL.")

    redirect_response = input("Paste URL here: ").strip()

    parsed = urlparse(redirect_response)
    code = parse_qs(parsed.query).get("code", [None])[0]

    if not code:
        raise Exception("❌ No authorization code found in URL.")

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": encode_credentials()
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code != 200:
        print(response.text)
        response.raise_for_status()

    tokens = response.json()

    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    access_expiry = time.time() + tokens["expires_in"]
    refresh_expiry = time.time() + tokens["refresh_token_expires_in"]

    # Save BOTH tokens
    save_json("ebayAccessToken.json", {
        "access_token": access_token,
        "expiry_time": access_expiry
    })

    save_json("ebayRefreshToken.json", {
        "refresh_token": refresh_token,
        "expiry_time": refresh_expiry
    })

    print("✅ New tokens generated and saved.")

    return access_token, access_expiry


def refresh_access_token(refresh_token):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": encode_credentials()
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }

    response = requests.post(TOKEN_URL, headers=headers, data=data)

    if response.status_code != 200:
        print("❌ Refresh failed:", response.text)
        raise Exception("Refresh token invalid")

    tokens = response.json()

    access_token = tokens["access_token"]
    access_expiry = time.time() + tokens["expires_in"]

    save_json("ebayAccessToken.json", {
        "access_token": access_token,
        "expiry_time": access_expiry
    })

    print("🔄 Access token refreshed.")

    return access_token, access_expiry


def setup_tokens():
    # Load saved tokens
    access_data = load_json("ebayAccessToken.json")
    refresh_data = load_json("ebayRefreshToken.json")

    # If no refresh token → full auth required
    if not refresh_data:
        return get_new_tokens_via_auth()

    refresh_token = refresh_data["refresh_token"]
    refresh_expiry = refresh_data["expiry_time"]

    # If refresh token expired → full auth
    if time.time() > refresh_expiry:
        print("⚠️ Refresh token expired.")
        return get_new_tokens_via_auth()

    # If access token exists and valid → use it
    if access_data and time.time() < access_data["expiry_time"]:
        print("✅ Using existing access token.")
        return access_data["access_token"], access_data["expiry_time"]

    # Otherwise → refresh access token
    try:
        print("🔄 Refreshing access token...")
        return refresh_access_token(refresh_token)

    except Exception:
        print("⚠️ Refresh failed. Re-authenticating...")
        return get_new_tokens_via_auth()