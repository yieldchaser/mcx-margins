import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from fyers_apiv3 import fyersModel

CLIENT_ID = "3WWLJD8YE4-200"
SECRET_KEY = "HcdRhnann7HgpQYj"
REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"

def get_auth_url():
    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type='code',
        grant_type='authorization_code'
    )
    return session.generate_authcode()

def exchange_auth_code_for_token(auth_code_or_url):
    # Extract auth_code if full URL is passed
    if "auth_code=" in auth_code_or_url:
        import urllib.parse
        parsed = urllib.parse.urlparse(auth_code_or_url)
        params = urllib.parse.parse_qs(parsed.query)
        auth_code = params.get('auth_code', [None])[0]
    else:
        auth_code = auth_code_or_url.strip()
    
    if not auth_code:
        print("Error: Could not find auth_code.")
        return None
    
    session = fyersModel.SessionModel(
        client_id=CLIENT_ID,
        secret_key=SECRET_KEY,
        redirect_uri=REDIRECT_URI,
        response_type='code',
        grant_type='authorization_code'
    )
    session.set_token(auth_code)
    response = session.generate_token()
    
    if response.get("s") == "ok":
        access_token = response.get("access_token")
        # Save token to file
        os.makedirs("data/fyers_auth", exist_ok=True)
        with open("data/fyers_auth/access_token.txt", "w") as f:
            f.write(access_token)
        print("SUCCESS! Generated and saved Access Token!")
        return access_token
    else:
        print("Failed to generate token:", response)
        return None

def fetch_sample_data(access_token, symbol="MCX:NATURALGAS26OCTFUT"):
    fyers = fyersModel.FyersModel(client_id=CLIENT_ID, is_async=False, token=access_token, log_path="")
    
    # 1. Profile check
    profile = fyers.get_profile()
    print("\n--- FYERS USER PROFILE ---")
    print(profile)
    
    # 2. Fetch ground-truth 1-minute historical data (last 30 days)
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=30)
    
    payload = {
        "symbol": symbol,
        "resolution": "1",
        "date_format": "1",
        "range_from": start_dt.strftime("%Y-%m-%d"),
        "range_to": end_dt.strftime("%Y-%m-%d"),
        "cont_flag": "1",
        "oi_flag": "1"
    }
    
    print(f"\n--- FETCHING 1-MIN GROUND-TRUTH DATA FOR {symbol} ---")
    resp = fyers.history(data=payload)
    if resp.get("s") == "ok" and resp.get("candles"):
        candles = resp["candles"]
        cols = ["epoch", "open", "high", "low", "close", "volume", "oi"]
        df = pd.DataFrame(candles, columns=cols[:len(candles[0])])
        df['ts_ist'] = pd.to_datetime(df['epoch'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
        
        save_path = f"data/fyers_{symbol.replace(':', '_')}_1m.csv"
        df.to_csv(save_path, index=False)
        print(f"SUCCESS! Downloaded {len(df):,} ground-truth 1-minute candles to {save_path}!")
        print("\nFirst 3 rows:")
        print(df.head(3).to_string())
        print("\nLast 3 rows:")
        print(df.tail(3).to_string())
        return df
    else:
        print("Error fetching history:", resp)
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        token = exchange_auth_code_for_token(arg)
        if token:
            fetch_sample_data(token)
    else:
        print("Auth URL:")
        print(get_auth_url())
