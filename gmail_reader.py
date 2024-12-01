import os
from google.oauth2.credentials import Credentials
from gpt4all import GPT4All
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
def get_emails(service, max_results=2):
    """Fetch the most recent emails from the inbox"""
    try:
        # Call the Gmail API to fetch the inbox
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=max_results
            ).execute()
        messages = results.get('messages', [])
        email_data = []

        if not messages:
            print('No new messages found.')
        else:
            for message in messages[:2]:
                msg = service.users().messages().get(
                    userId='me',
                    id=message['id']
                    ).execute()
                payload = msg.get('payload', {})
                headers = payload.get('headers', [])

                # Extract email subject and sender
                subject = ""
                sender = ""
                for header in headers:
                    if header['name'] == 'Subject':
                        subject = header['value']
                    if header['name'] == 'From':
                        sender = header['value']

                if subject and sender:
                    email_data.append({
                        'subject': subject.strip(),
                        'sender': sender.strip()
                        })

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


# Categorize and prioritize emails using GPT4All
def process_email_with_llm(model, subject, sender):
    """Use GPT4All to process an email's details."""
    # System prompt to define assistant behavior
    system_prompt = "Cutting Knowledge Date: December 2023\n"
    "You are a helpful assistant."

    user_prompt = f"""
    Here is an email:
    - Subject: "{subject}"
    - Sender: "{sender}"

    Categorize this email into one of the following categories: "Work",
    "School", "Shopping", "Other".
    Rank the email's priority as "Urgent", "Important", or "Normal".
    Decide if the email requires a response ("Yes" or "No").

    Format your response exactly as follows:
    Category: <category>
    Priority: <priority>
    Requires Response: <yes/no>
    Do not include explanations and do not add code block
    """

    response = model.generate(f"{system_prompt}\n\n{user_prompt}",
                              max_tokens=20)
    return response.strip()


def main():
    """Authenticate, fetch emails, and process them."""
    # Authenticate with Gmail API
    service = authenticate_gmail_api()

    # Fetch the last 100 emails
    emails = get_emails(service, max_results=100)

    # Initialize the model
    model = GPT4All("Llama-3.2-3B-Instruct-Q4_0.gguf")

    # Process each email
    for email in emails:
        subject = email['subject']
        sender = email['sender']
        print(f"\nProcessing email from {sender} with subject: {subject}\n")

        try:
            result = process_email_with_llm(model, subject, sender)
            print(result)
        except Exception as e:
            print(f"Error processing email: {e}")


if __name__ == '__main__':
    main()
