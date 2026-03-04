import os
import json
import datetime
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# We need readonly scope to fetch channel details
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]
CREDENTIALS_FILE = "client_secret.json"
ACCOUNTS_FILE = "accounts.json"

def _load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_accounts(accounts):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)

def get_accounts():
    """Returns a list of connected accounts suitable for the frontend."""
    accounts = _load_accounts()
    return [
        {
            "id": acc_id,
            "title": acc_data.get("title", "Unknown Channel"),
            "thumbnail": acc_data.get("thumbnail", "")
        }
        for acc_id, acc_data in accounts.items()
    ]

def link_new_account():
    """
    Initiates the OAuth flow to link a new YouTube channel,
    fetches the channel details, and stores the credentials.
    """
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"Missing {CREDENTIALS_FILE} for YouTube API.")
        
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    # Run local server to allow user login
    creds = flow.run_local_server(port=0)
    
    # Build a temporary service to fetch channel info
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.channels().list(
        part="snippet",
        mine=True
    )
    response = request.execute()
    
    if not response.get("items"):
        raise ValueError("Could not find a YouTube channel associated with this account.")
        
    channel = response["items"][0]
    channel_id = channel["id"]
    title = channel["snippet"]["title"]
    thumbnail = channel["snippet"]["thumbnails"]["default"]["url"]
    
    accounts = _load_accounts()
    accounts[channel_id] = {
        "title": title,
        "thumbnail": thumbnail,
        "credentials": json.loads(creds.to_json())
    }
    _save_accounts(accounts)
    
    return {
        "id": channel_id,
        "title": title,
        "thumbnail": thumbnail
    }

def get_authenticated_service(account_id=None):
    accounts = _load_accounts()
    
    if not accounts:
        raise ValueError("No YouTube accounts connected. Please link an account first.")
        
    if not account_id:
        # Default to the first account if none specified
        account_id = list(accounts.keys())[0]
        
    if account_id not in accounts:
        raise ValueError(f"Account '{account_id}' not found.")
        
    acc_data = accounts[account_id]
    creds = Credentials.from_authorized_user_info(acc_data["credentials"], SCOPES)
    
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save updated credentials
            acc_data["credentials"] = json.loads(creds.to_json())
            _save_accounts(accounts)
        else:
            raise ValueError(f"Credentials for account '{account_id}' are invalid and cannot be refreshed.")
            
    return build("youtube", "v3", credentials=creds)

def upload_video(file_path, title, description, tags=None, category_id="22", privacy_status="private", publish_at=None, account_id=None):
    youtube = get_authenticated_service(account_id)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": category_id
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    if publish_at:
        # publish_at should be ISO 8601 (YYYY-MM-DDThh:mm:ss.sZ)
        body["status"]["publishAt"] = publish_at
        body["status"]["privacyStatus"] = "private" # Must be private to schedule

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        except Exception as e:
            print(f"An error occurred while uploading: {e}")
            raise e

    print(f"Video uploaded successfully. Video ID: {response['id']}")
    return response['id']

