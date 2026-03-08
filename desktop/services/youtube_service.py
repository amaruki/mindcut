import os
import glob
from core import youtube_api


def get_accounts():
    """Returns a list of connected accounts."""
    try:
        return youtube_api.get_accounts()
    except Exception as e:
        print(f"Error getting accounts: {e}")
        return []


def link_account():
    """Initiates OAuth flow to link a new channel. Blocking."""
    return youtube_api.link_new_account()


def upload_video(
    file_path,
    title,
    description,
    tags=None,
    category_id="22",
    privacy_status="private",
    publish_at=None,
    account_id=None,
):
    """Uploads a video to YouTube. Blocking."""
    return youtube_api.upload_video(
        file_path,
        title,
        description,
        tags,
        category_id,
        privacy_status,
        publish_at,
        account_id,
    )


def list_channel_videos(account_id=None, max_results=50):
    """Lists videos for the given account. Blocking."""
    return youtube_api.list_channel_videos(account_id, max_results)
