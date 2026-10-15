"""
Blue Margin — 100% Headless Automated FYERS Login via TOTP (Zero Clicks)
scripts/auto_fyers_login.py

Generates fresh FYERS access_token autonomously every morning without browser or human intervention:
1. Generates 6-digit TOTP code via pyotp
2. Performs send_login_otp -> verify_otp -> verify_pin
3. Exchanges auth code for fresh access_token
4. Saves directly to data/fyers_auth/access_token.txt
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import json
import urllib.parse
import requests
import pyotp
from fyers_apiv3 import fyersModel

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUTH_DIR = os.path.join(REPO_DIR, "data", "fyers_auth")
CREDS_FILE = os.path.join(AUTH_DIR, "credentials.json")
TOKEN_FILE = os.path.join(AUTH_DIR, "access_token.txt")
os.makedirs(AUTH_DIR, exist_ok=True)

CLIENT_ID = "3WWLJD8YE4-200"
SECRET_KEY = "HcdRhnann7HgpQYj"
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"

# Endpoints
BASE_VAGATOR = "https://api-t2.fyers.in/vagator/v2"
BASE_V3 = "https://api-t1.fyers.in/api/v3"

URL_SEND_OTP = f"{BASE_VAGATOR}/send_login_otp"
URL_VERIFY_TOTP = f"{BASE_VAGATOR}/verify_otp"
URL_VERIFY_PIN = f"{BASE_VAGATOR}/verify_pin"
URL_TOKEN = f"{BASE_V3}/token"

def create_template_if_missing():
    if not os.path.exists(CREDS_FILE):
        template = {
            "fy_id": "FAL11545",
            "pin": "YOUR_4_DIGIT_PIN",
            "totp_secret_key": "YOUR_FYERS_TOTP_SECRET_KEY"
        }
        with open(CREDS_FILE, "w", encoding="utf-8") as f:
            json.dump(template, f, indent=2)
        print(f"Created template credentials file at: {CREDS_FILE}")
        return False
    return True

def auto_login():
    creds = {}
    if os.path.exists(CREDS_FILE):
        try:
            with open(CREDS_FILE, "r", encoding="utf-8") as f:
                creds = json.load(f)
        except Exception:
            pass

    fy_id = os.environ.get("FYERS_FY_ID", creds.get("fy_id", "FAL11545")).strip()
    pin = os.environ.get("FYERS_PIN", str(creds.get("pin", ""))).strip()
    totp_secret = os.environ.get("FYERS_TOTP_KEY", creds.get("totp_secret_key", "")).replace(" ", "").strip()

    if pin in ("", "YOUR_4_DIGIT_PIN") or not totp_secret or totp_secret == "YOUR_FYERS_TOTP_SECRET_KEY":
        create_template_if_missing()
        print("\nPlease fill in your 4-digit PIN and TOTP_SECRET_KEY in data/fyers_auth/credentials.json or set FYERS_PIN / FYERS_TOTP_KEY env vars to enable 100% headless login.")
        return False

    print("=" * 80)
    print(f"INITIATING 100% HEADLESS FYERS TOTP AUTHENTICATION FOR {fy_id}")
    print("=" * 80)

    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    # Step 1: Send Login OTP (initializes request_key)
    print("Step 1: Sending login request...")
    res1 = session.post(URL_SEND_OTP, json={"fy_id": fy_id, "app_id": "2"}, headers=headers)
    d1 = res1.json()
    if d1.get("s") != "ok":
        # Fallback endpoint if api-t2 is alternate
        alt_url = "https://api-t1.fyers.in/vagator/v2/send_login_otp"
        res1 = session.post(alt_url, json={"fy_id": fy_id, "app_id": "2"}, headers=headers)
        d1 = res1.json()
        if d1.get("s") != "ok":
            print(f"Step 1 Failed: {d1}")
            return False

    request_key_1 = d1.get("request_key")
    print("Step 1 OK: Request Key obtained.")

    # Step 2: Generate & Verify TOTP
    print("Step 2: Generating and verifying 6-digit TOTP...")
    totp_now = pyotp.TOTP(totp_secret).now()
    res2 = session.post(URL_VERIFY_TOTP, json={"request_key": request_key_1, "otp": totp_now}, headers=headers)
    d2 = res2.json()
    if d2.get("s") != "ok":
        print(f"Step 2 (TOTP verification) Failed: {d2}")
        return False

    request_key_2 = d2.get("request_key")
    print("Step 2 OK: TOTP Verified successfully.")

    # Step 3: Verify 4-Digit Trading PIN
    print("Step 3: Verifying 4-digit Trading PIN...")
    res3 = session.post(URL_VERIFY_PIN, json={"request_key": request_key_2, "identity_type": "pin", "identifier": pin}, headers=headers)
    d3 = res3.json()
    if d3.get("s") != "ok":
        # Check alternate field name identity_pin
        res3 = session.post(URL_VERIFY_PIN, json={"request_key": request_key_2, "identity_pin": pin}, headers=headers)
        d3 = res3.json()
        if d3.get("s") != "ok":
            print(f"Step 3 (PIN verification) Failed: {d3}")
            return False

    data_token = d3.get("data", {}).get("token") or d3.get("data", {}).get("access_token")
    if not data_token:
        print(f"Step 3 Failed to retrieve data_token: {d3}")
        return False

    print("Step 3 OK: PIN Verified.")

    # Step 4: Exchange data_token for authorization code
    print("Step 4: Requesting Auth Code...")
    token_headers = {
        **headers,
        "Authorization": f"Bearer {data_token}"
    }
    payload_token = {
        "fyers_id": fy_id,
        "app_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "appType": "100",
        "code_challenge": "",
        "state": "None",
        "scope": "",
        "nonce": "",
        "response_type": "code",
        "create_cookie": True
    }
    res4 = session.post(URL_TOKEN, json=payload_token, headers=token_headers)
    d4 = res4.json()
    if d4.get("s") != "ok":
        print(f"Step 4 Failed: {d4}")
        return False

    redirect_url = d4.get("Url") or d4.get("data", {}).get("url")
    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)
    auth_code = params.get("auth_code", [None])[0]
    if not auth_code:
        print(f"Failed to extract auth_code from {redirect_url}")
        return False

    print("Step 4 OK: Auth Code extracted.")

    # Step 5: Generate Final Trading Access Token via SDK
    print("Step 5: Generating final Access Token...")
    fyers_session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type='code',
        grant_type='authorization_code'
    )
    fyers_session.set_token(auth_code)
    resp_token = fyers_session.generate_token()

    if resp_token.get("s") == "ok":
        access_token = resp_token.get("access_token")
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(access_token)
        try:
            import subprocess
            res = subprocess.run(["gh", "secret", "set", "FYERS_ACCESS_TOKEN"], input=access_token, text=True, capture_output=True)
            if res.returncode == 0:
                print("✓ Automatically synchronized FYERS_ACCESS_TOKEN to GitHub Secrets!")
        except Exception:
            pass
        print("=" * 80)
        print("SUCCESS! FRESH FYERS ACCESS TOKEN GENERATED AND SAVED TO data/fyers_auth/access_token.txt!")
        print("=" * 80)
        return True
    else:
        print(f"Step 5 Failed: {resp_token}")
        return False

if __name__ == "__main__":
    auto_login()
