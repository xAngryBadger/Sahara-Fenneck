"""
Backends de integracao — cada modulo implementa uma ou mais acoes.
"""
from .gmail import send_gmail_summary
from .google_calendar import list_google_calendar_events
from .google_drive import upload_google_drive_csv
from .onedrive import upload_onedrive_csv
from .outlook import send_outlook_mail
from .outlook_calendar import list_outlook_calendar
from .sharepoint import upload_sharepoint_csv
from .teams import send_teams_summary
from .trello import trello_create_card, trello_list_boards

__all__ = [
    "send_gmail_summary",
    "list_google_calendar_events",
    "upload_google_drive_csv",
    "send_outlook_mail",
    "list_outlook_calendar",
    "upload_onedrive_csv",
    "upload_sharepoint_csv",
    "send_teams_summary",
    "trello_list_boards",
    "trello_create_card",
]
