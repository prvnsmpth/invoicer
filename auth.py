import os
import json
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from config import TOKEN_FILE, CREDENTIALS_FILE, GOOGLE_CALENDAR_SCOPES


def authenticate():
    creds = None
    
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GOOGLE_CALENDAR_SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                raise FileNotFoundError(
                    f"Please download your OAuth2 credentials from Google Cloud Console "
                    f"and save them to {CREDENTIALS_FILE}"
                )
            
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), GOOGLE_CALENDAR_SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    return creds


def is_authenticated():
    if not TOKEN_FILE.exists():
        return False
    
    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), GOOGLE_CALENDAR_SCOPES)
        return creds and creds.valid
    except Exception:
        return False


def clear_credentials():
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        return True
    return False