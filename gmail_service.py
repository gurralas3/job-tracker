import os
import json
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
BASE_DIR = os.path.dirname(__file__)
CREDS_PATH = os.path.join(BASE_DIR, 'credentials.json')
TOKEN_PATH = os.path.join(BASE_DIR, 'token.pickle')

# Emails that confirm an application was submitted
APPLICATION_QUERY = (
    'subject:("application received" OR "application submitted" OR '
    '"application confirmation" OR "application update" OR '
    '"thank you for applying" OR "thanks for applying" OR '
    '"thank you for your application" OR "thanks for your application" OR '
    '"thank you for your interest" OR "thanks for your interest" OR '
    '"we received your application" OR "received your application" OR '
    '"has received your application" OR '
    '"successfully submitted your" OR '
    '"your application" OR "application was sent" OR '
    '"successfully applied" OR "applied for the position")'
)

# Rejection emails
REJECTION_QUERY = (
    'subject:(unfortunately OR "not moving forward" OR "not to move forward" OR '
    '"not selected" OR "regret to inform" OR "we regret" OR '
    '"position has been filled" OR "decided to move forward with other" OR '
    '"application was not successful" OR "not be proceeding" OR '
    '"application update" OR "your application status") '
    'newer_than:180d'
)

# Positive response / interview / offer emails
SELECTED_QUERY = (
    'subject:("interview invitation" OR "invitation to interview" OR '
    '"we would like to interview" OR "schedule an interview" OR '
    '"next steps" OR "offer of employment" OR "job offer" OR "offer letter" OR '
    '"phone screen" OR "technical interview" OR "coding challenge" OR '
    '"take-home assessment" OR "you have been selected" OR '
    '"pleased to inform" OR "moving forward with you") '
    'newer_than:180d'
)


def build_service_from_token(token_json: str, user_id=None):
    """Build Gmail service from a token stored in the database."""
    from database import save_gmail_token
    data = json.loads(token_json)

    creds = Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        scopes=data.get('scopes'),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Save refreshed token back to DB
        if user_id:
            data['token'] = creds.token
            data['expiry'] = creds.expiry.isoformat() if creds.expiry else None
            save_gmail_token(user_id, json.dumps(data))

    return build('gmail', 'v1', credentials=creds)


def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDS_PATH):
                raise FileNotFoundError(
                    'credentials.json not found in the job-tracker folder. '
                    'Please follow the setup guide in the dashboard.'
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'wb') as f:
            pickle.dump(creds, f)

    return build('gmail', 'v1', credentials=creds)


def _fetch_query(service, query, max_results=500):
    """Fetch message IDs for a single query, deduplicated."""
    messages = []
    seen = set()
    page_token = None

    while len(messages) < max_results:
        kwargs = {
            'userId': 'me',
            'q': query,
            'maxResults': min(100, max_results - len(messages)),
        }
        if page_token:
            kwargs['pageToken'] = page_token

        result = service.users().messages().list(**kwargs).execute()
        for m in result.get('messages', []):
            if m['id'] not in seen:
                seen.add(m['id'])
                messages.append(m)

        page_token = result.get('nextPageToken')
        if not page_token or not result.get('messages'):
            break

    return messages


def fetch_job_emails(service, after_date=None, max_results=500):
    """Fetch application + rejection + selection emails, deduplicated."""
    app_query = APPLICATION_QUERY
    if after_date:
        app_query += f' after:{after_date}'

    all_messages = {}

    for query in [app_query, REJECTION_QUERY, SELECTED_QUERY]:
        for m in _fetch_query(service, query, max_results=max_results):
            all_messages[m['id']] = m

    return list(all_messages.values())


def get_message_detail(service, msg_id):
    return service.users().messages().get(
        userId='me', id=msg_id, format='full'
    ).execute()
