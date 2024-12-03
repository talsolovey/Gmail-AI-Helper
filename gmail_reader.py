import os
import json
import redis
from google.oauth2.credentials import Credentials
from gpt4all import GPT4All
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import matplotlib.pyplot as plt
from collections import Counter
from colorama import Fore, Style
from tqdm import tqdm
import subprocess

# Constants
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
EMAIL_CACHE_TTL = 14400  # 4 hours in seconds
LLM_CACHE_TTL = 14400  # 4 hours in seconds


# Check if Redis is running via Docker
def check_redis_running():
    try:
        output = subprocess.check_output([
            "redis-cli", "ping"],
            stderr=subprocess.STDOUT
            ).decode().strip()
        if output == "PONG":
            print(Fore.GREEN + "Redis server is running." + Style.RESET_ALL)
        else:
            raise Exception("Redis server not responding as expected.")
    except subprocess.CalledProcessError:
        print(
            Fore.RED +
            "Redis server is not running."
            "Ensure Docker Redis container is active." +
            Style.RESET_ALL)
        exit(1)


# Initialize Redis connection with retry logic
def initialize_redis():
    try:
        client = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True
            )
        if client.ping():
            print(
                Fore.GREEN +
                "Connected to Redis successfully!" +
                Style.RESET_ALL
                )
        return client
    except redis.ConnectionError as e:
        print(
            Fore.RED +
            f"Redis connection error: {e}. Ensure Redis container is running."
            + Style.RESET_ALL)
        exit(1)


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

    return build('gmail', 'v1', credentials=creds)


# Fetch and cache emails
def get_cached_emails(service, max_results=10):
    cache_key = "emails_cache"
    cached_emails = redis_client.get(cache_key)

    if cached_emails:
        print(Fore.BLUE + "Fetched emails from Redis cache." + Style.RESET_ALL)
        return json.loads(cached_emails)

    emails = get_emails(service, max_results)
    redis_client.setex(cache_key, EMAIL_CACHE_TTL, json.dumps(emails))
    print(
        Fore.YELLOW +
        "Fetched emails from Gmail and cached them." +
        Style.RESET_ALL)
    return emails


# Get the emails from the Gmail inbox
def get_emails(service, max_results=10):
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
            for message in messages[:10]:
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


# Process LLM responses with Redis cache
def process_email_with_llm_cached(model, subject, sender):
    cache_key = f"llm_response:{subject}:{sender}"
    cached_response = redis_client.get(cache_key)

    if cached_response:
        print(
            Fore.BLUE +
            f"LLM response fetched from cache for email '{subject}'." +
            Style.RESET_ALL
            )
        return cached_response

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

    Respond exactly in this format (do not use tables, Markdown,
    or any other formatting):
    Category: <category>
    Priority: <priority>
    Requires Response: <yes/no>
    """

    response = model.generate(
        f"{system_prompt}\n\n{user_prompt}",
        max_tokens=20
        ).strip()
    redis_client.setex(cache_key, LLM_CACHE_TTL, response)
    print(
        Fore.YELLOW +
        f"LLM response cached for email '{subject}'." +
        Style.RESET_ALL
        )
    return response


# Generate analytics with Matplotlib
def display_email_insights(insights):
    # Category distribution
    categories = [email['category'] for email in insights]
    category_counts = Counter(categories)

    plt.figure()
    plt.pie(
        category_counts.values(),
        labels=category_counts.keys(),
        autopct='%1.1f%%'
        )
    plt.title("Email Category Distribution")
    plt.show()

    # Top senders per category
    category_senders = [f"{email['category']} - {email['sender']}"
                        for email in insights]
    top_senders = Counter(category_senders).most_common(5)

    senders, counts = zip(*top_senders)
    plt.figure()
    plt.bar(senders, counts)
    plt.title("Top 5 Senders per Category")
    plt.xlabel("Sender - Category")
    plt.ylabel("Count")
    plt.xticks(rotation=45)
    plt.show()


def main():
    """Authenticate, fetch emails, and process them."""
    # Check Redis server status
    check_redis_running()

    # Initialize Redis
    global redis_client
    redis_client = initialize_redis()

    # Authenticate with Gmail API
    service = authenticate_gmail_api()

    # Fetch the last 100 emails
    emails = get_emails(service, max_results=100)

    # Initialize the model
    model = GPT4All("Llama-3.2-3B-Instruct-Q4_0.gguf")

    email_insights = []

    # Process each email
    for email in tqdm(emails, desc="Processing emails with LLM", unit="email"):
        subject = email['subject']
        sender = email['sender']
        print(f"\nProcessing email from {sender} with subject: {subject}\n")

        try:
            result = process_email_with_llm_cached(model, subject, sender)
            print(Fore.GREEN + f"response from LLM:\n{result}" +
                  Style.RESET_ALL)

            # Parse response and remove indentations
            lines = [
                line.strip() for line in result.splitlines() if line.strip()]

            if len(lines) != 3:
                raise ValueError("Malformed LLM response")

            category = lines[0].split(": ")[1].strip()
            priority = lines[1].split(": ")[1].strip()
            requires_response = lines[2].split(": ")[1].strip()

            email_insights.append({
                'subject': subject,
                'sender': sender,
                'category': category,
                'priority': priority,
                'requires_response': requires_response
            })

        except Exception as e:
            print(Fore.RED + f"Error processing email: {e}" + Style.RESET_ALL)

    # Display analytics
    display_email_insights(email_insights)


if __name__ == '__main__':
    main()
