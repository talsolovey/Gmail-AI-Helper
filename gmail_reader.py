import os
from google.oauth2.credentials import Credentials
from requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying the email scope, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


# Authenticate and connect to Gmail API
def authenticate_gmail_api():
    """Authenticate the user and connect to Gmail API"""
    creds = None
    # The file token.json stores the user's access and refresh tokens,
    # and is created automatically when the authorization flow completes for
    # the first time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Build the service
    service = build('gmail', 'v1', credentials=creds)
    return service


# Get the emails from the Gmail inbox
def get_emails(service):
    """Fetch the most recent emails from the inbox"""
    try:
        # Call the Gmail API to fetch the inbox
        results = service.users().messages().list(userId='me',
                                                  labelIds=['INBOX'],
                                                  q="is:unread").execute()
        messages = results.get('messages', [])

        if not messages:
            print('No new messages found.')
        else:
            print('Messages:')
            for message in messages[:5]:  # Limit to first 5 emails
                msg = service.users().messages().get(userId='me',
                                                     id=message['id']).execute()
                payload = msg['payload']
                headers = payload['headers']

                # Extract subject and sender
                subject = ""
                sender = ""
                for header in headers:
                    if header['name'] == 'Subject':
                        subject = header['value']
                    if header['name'] == 'From':
                        sender = header['value']

                print(f"Subject: {subject}")
                print(f"Sender: {sender}")
                print("\n")

    except HttpError as error:
        print(f'An error occurred: {error}')


def main():
    """Authenticate and get emails"""
    service = authenticate_gmail_api()
    get_emails(service)


if __name__ == '__main__':
    main()
