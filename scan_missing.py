"""
Scans Gmail with a broad query to find job-related emails
that our current parser is missing. Prints their subjects.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from gmail_service import get_gmail_service, get_message_detail
from database import get_db

# Very broad query — catches almost any job/career email
BROAD_QUERY = (
    '(subject:(apply OR applied OR application OR "thank you" OR thanks OR '
    'interview OR offer OR hiring OR recruiting OR recruiter OR candidate OR '
    'position OR role OR job OR career OR opportunity) '
    'newer_than:180d) '
    '-subject:(newsletter OR unsubscribe OR sale OR discount OR invoice OR receipt)'
)

def already_in_db(email_ids):
    conn = get_db()
    rows = conn.execute('SELECT email_id FROM applications WHERE email_id IS NOT NULL').fetchall()
    conn.close()
    return {r['email_id'] for r in rows}

def main():
    print('Connecting to Gmail...')
    service = get_gmail_service()

    print('Fetching emails with broad query...')
    result = service.users().messages().list(
        userId='me', q=BROAD_QUERY, maxResults=500
    ).execute()
    messages = result.get('messages', [])
    print(f'Found {len(messages)} candidate emails\n')

    known_ids = already_in_db({m['id'] for m in messages})
    missing = [m for m in messages if m['id'] not in known_ids]
    print(f'{len(known_ids)} already in dashboard, {len(missing)} potentially missed\n')

    subjects = []
    for i, msg in enumerate(missing[:200]):
        try:
            data = service.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['Subject', 'From']
            ).execute()
            headers = {h['name']: h['value'] for h in data.get('payload', {}).get('headers', [])}
            subj   = headers.get('Subject', '(no subject)')
            sender = headers.get('From', '')
            subjects.append((subj, sender))
            if (i+1) % 20 == 0:
                print(f'  Scanned {i+1}/{len(missing[:200])}...')
        except Exception as e:
            pass

    print('\n' + '='*70)
    print('MISSED EMAIL SUBJECTS:')
    print('='*70)
    for subj, sender in sorted(subjects):
        safe_subj   = subj.encode('ascii', errors='replace').decode('ascii')
        safe_sender = sender.split('<')[0].strip()[:30].encode('ascii', errors='replace').decode('ascii')
        print(f'  [{safe_sender:30s}]  {safe_subj}')

    print(f'\nTotal missed: {len(subjects)}')

if __name__ == '__main__':
    main()
