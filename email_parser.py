import re
import os
import json
import base64
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime


def parse_with_gemini(subject: str, body: str, sender: str) -> dict | None:
    """Use Gemini API to extract company and job title when regex fails."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return None

    prompt = f"""Extract job application info from this email. Reply ONLY with valid JSON.

Email sender: {sender[:100]}
Email subject: {subject[:200]}
Email body (first 500 chars): {(body or '')[:500]}

Reply with exactly this JSON format:
{{"company": "Company Name", "job_title": "Job Title"}}

Rules:
- If no job title found, use "Unknown Position"
- If no company found, use "Unknown Company"
- Keep job title concise (e.g. "AI Engineer", "ML Ops Engineer II")
- Do not include job req numbers like JR12345 in the title"""

    try:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'
        res = requests.post(url, json={
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {'temperature': 0, 'maxOutputTokens': 100},
        }, timeout=10)
        res.raise_for_status()
        text = res.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        # Strip markdown code fences if present
        text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text.strip())
        data = json.loads(text)
        return {
            'company': data.get('company', 'Unknown Company'),
            'job_title': data.get('job_title', 'Unknown Position'),
        }
    except Exception as e:
        print(f'[gemini] parse failed: {e}')
        return None

# ------------------------------------------------------------------
# Platform detection config
# ------------------------------------------------------------------
PLATFORMS = {
    'LinkedIn': {
        'domains': ['linkedin.com'],
        'subject_kw': ['application was sent', 'application submitted', 'applied for', 'your application'],
    },
    'Indeed': {
        'domains': ['indeed.com', 'indeedjobs.com'],
        'subject_kw': ['your application', 'indeed application', 'applied to'],
    },
    'Glassdoor': {
        'domains': ['glassdoor.com'],
        'subject_kw': ['application submitted', 'applied', 'your application'],
    },
    'Greenhouse': {
        'domains': ['greenhouse.io'],
        'subject_kw': ['application received', 'we received your application', 'thank you for applying'],
    },
    'Lever': {
        'domains': ['hire.lever.co', 'lever.co'],
        'subject_kw': ['application received', 'thank you for applying'],
    },
    'Workday': {
        'domains': ['myworkday.com', 'wd1.myworkdayjobs.com', 'wd3.myworkdayjobs.com', 'wd5.myworkdayjobs.com'],
        'subject_kw': ['application submitted', 'application received'],
    },
    'iCIMS': {
        'domains': ['icims.com'],
        'subject_kw': ['application received', 'thank you for applying'],
    },
    'SmartRecruiters': {
        'domains': ['smartrecruiters.com'],
        'subject_kw': ['application received', 'thank you for applying'],
    },
    'BambooHR': {
        'domains': ['bamboohr.com'],
        'subject_kw': ['application received'],
    },
}

APPLICATION_SUBJECT_KEYWORDS = [
    # Standard confirmations
    'application received',
    'application submitted',
    'application confirmation',
    'has received your application',
    'received your application',
    'we received your application',
    'successfully submitted your',
    # Thank you variants
    'thank you for applying',
    'thanks for applying',
    'thanks for your application',
    'thank you for your application',
    'thank you for your interest',
    'thanks for your interest',
    'thank you for your interest in',
    'thank you from',
    # Application sent/status
    'your application to',
    'your application for',
    'application was sent',
    'application update',
    'successfully applied',
    'applied for the position',
    'applying to',
    'applied to',
    'job application',
]

# ── Rejection signals ──────────────────────────────────────────
REJECTION_SUBJECT_KEYWORDS = [
    'not moving forward',
    'not to move forward',
    'unfortunately',
    'we regret',
    'regret to inform',
    'not selected',
    'not been selected',
    'not a match',
    'no longer being considered',
    'position has been filled',
    'decided to move forward with other',
    'chosen to move forward with other',
    'we will not be moving',
    'not be proceeding',
    'application was not successful',
    'unsuccessful',
    'not shortlisted',
]

REJECTION_BODY_KEYWORDS = [
    # Direct "not moving forward" phrases
    'not to move forward',
    'not moving forward with your',
    'decided not to move forward',
    'have decided not to move forward',
    'we have decided not to move forward',
    'not moving forward in the process',
    'not to move forward in the process',
    # Unfortunately / regret
    'unfortunately',
    'we regret to inform',
    'regret to let you know',
    'we are sorry to inform',
    # Not selected
    'not selected for',
    'have not been selected',
    'not been selected',
    'not moving forward with you',
    # Pursuing other candidates
    'decided to pursue other candidates',
    'decided to move forward with other candidates',
    'chosen to move forward with another',
    'moving forward with other candidates',
    'moving forward with another candidate',
    'decided to move forward with another',
    # Position filled / closed
    'position has been filled',
    'role has been filled',
    'position is no longer available',
    # Other signals
    'no longer being considered',
    'not a match for',
    "doesn't meet",
    'does not meet',
    'we will not be moving forward',
    'not be proceeding with your application',
    'after carefully considering your background',
    'after careful consideration, we',
    'we have decided not to',
    'difficult decision',
    'other candidates whose experience',
    'other candidates whose background',
    'wish you the best in your search',
    'wish you the best of luck in your search',
    'we will keep your resume on file',
]

# ── Selection / positive signals ───────────────────────────────
SELECTED_SUBJECT_KEYWORDS = [
    'interview invitation',
    'invitation to interview',
    'we would like to interview',
    'schedule an interview',
    'next steps',
    'moving forward with you',
    'pleased to inform',
    'congratulations',
    'offer of employment',
    'job offer',
    'offer letter',
    'you have been selected',
    'excited to move forward',
    'want to connect',
    'phone screen',
    'technical assessment',
    'coding challenge',
    'take-home assessment',
]

SELECTED_BODY_KEYWORDS = [
    'pleased to inform you',
    'we would like to invite you',
    'like to schedule',
    'like to set up',
    'moving forward with your application',
    'move forward with you',
    'excited to move forward',
    'next step in our',
    'phone screen',
    'phone interview',
    'video interview',
    'technical interview',
    'offer of employment',
    'pleased to offer',
    'thrilled to offer',
    'formal offer',
    'congratulations',
    'you have been selected',
]

# Map detected intent to status
SELECTED_STATUS_MAP = [
    # (body/subject keyword, status to assign)
    ('offer of employment', 'Offer'),
    ('job offer',           'Offer'),
    ('offer letter',        'Offer'),
    ('pleased to offer',    'Offer'),
    ('thrilled to offer',   'Offer'),
    ('formal offer',        'Offer'),
    ('technical interview', 'Technical Interview'),
    ('coding challenge',    'Technical Interview'),
    ('take-home assessment','Technical Interview'),
    ('technical assessment','Technical Interview'),
    ('phone screen',        'Phone Screen'),
    ('phone interview',     'Phone Screen'),
    ('video interview',     'Phone Screen'),
]


def _detect_email_type(subject: str, body: str) -> str:
    """Return 'application' | 'rejection' | 'selected' | 'unknown'.

    Priority order:
      1. Body rejection keywords  — body is the ground truth
      2. Body selection keywords
      3. Subject rejection keywords
      4. Subject application keywords
      5. Subject selection keywords
    """
    sl = subject.lower()
    bl = (body or '').lower()

    # 1. Body rejection — highest priority (catches "Thank you...unfortunately" emails)
    for kw in REJECTION_BODY_KEYWORDS:
        if kw in bl:
            return 'rejection'

    # 2. Body selection
    for kw in SELECTED_BODY_KEYWORDS:
        if kw in bl:
            return 'selected'

    # 3. Subject rejection
    for kw in REJECTION_SUBJECT_KEYWORDS:
        if kw in sl:
            return 'rejection'

    # 4. Subject application
    for kw in APPLICATION_SUBJECT_KEYWORDS:
        if kw in sl:
            return 'application'

    # 5. Subject selection
    for kw in SELECTED_SUBJECT_KEYWORDS:
        if kw in sl:
            return 'selected'

    return 'unknown'


def _resolve_selected_status(subject: str, body: str) -> str:
    """Pick the most specific status for a positive email."""
    combined = (subject + ' ' + (body or '')).lower()
    for keyword, status in SELECTED_STATUS_MAP:
        if keyword in combined:
            return status
    return 'Phone Screen'  # default positive step


def is_job_application_email(subject: str, sender: str) -> bool:
    sl = subject.lower()
    for kw in APPLICATION_SUBJECT_KEYWORDS:
        if kw in sl:
            return True
    sender_l = sender.lower()
    for platform, cfg in PLATFORMS.items():
        for domain in cfg['domains']:
            if domain in sender_l:
                for kw in cfg['subject_kw']:
                    if kw in sl:
                        return True
    return False


def detect_platform(sender: str, subject: str) -> str:
    sender_l = sender.lower()
    for platform, cfg in PLATFORMS.items():
        for domain in cfg['domains']:
            if domain in sender_l:
                return platform
    return 'Direct/Other'


def _clean(text: str) -> str:
    """Strip common trailing/leading noise from extracted strings."""
    text = text.strip()
    text = re.sub(r'<[^>]+>', '', text)               # remove HTML tags
    text = re.sub(r'^[*•\-–—\s]+', '', text)          # strip leading bullets/asterisks
    text = re.sub(r'[*•]+', '', text)                  # remove remaining asterisks/bullets
    text = re.sub(r'^(?:in the|in a|for the|for a|the|a)\s+', '', text, flags=re.I)  # strip leading articles
    text = re.sub(r'\s*[|–—]\s*$', '', text)          # trailing separators
    text = re.sub(r'[!]+$', '', text)                  # trailing exclamation marks
    text = re.sub(r'^[A-Z]{0,5}\d{5,}\s+', '', text)  # strip leading req numbers e.g. JR2014497, 200650082
    text = re.sub(r'\s+[A-Z]{0,5}\d{5,}$', '', text)  # strip trailing req numbers e.g. "Data Scientist 200650082"
    text = text.strip().strip('.,;:')
    return text[:120]


# Phrases that indicate a body sentence was grabbed instead of a real title.
# Also used by database.py for cleanup — import _JUNK_TITLE_PHRASES from here.
# Merged from the former _JUNK_TITLE_CLEANUP and _JUNK_TITLE_PHRASES_DB in database.py.
_JUNK_TITLE_PHRASES = [
    'we will', 'will contact', 'will reach', 'reach out', 'contact you',
    'has been received', 'we will review', 'if there is a fit',
    'interested in joining', "we're thrilled", "we are thrilled",
    "we're excited", "we are excited", 'thank you', 'any open role',
    'open roles', 'joining our team', 'shape a brighter', 'financial future',
    'at sofi', 'at qventus', 'at databricks', 'good fit', 'seems like',
    'move forward', 'your application', 'keep your', 'in touch',
    'time for the', 'at this time', 'this open', 'open position',
    'the position', 'this position', 'a position', 'the role',
    'this role', 'a role', 'the opportunity', 'this opportunity',
    'see if your', 'qualifications match', 'our needs', 'a career',
    'career opportunity', 'career at', 'see if', 'match our',
    'our team', 'our company',
]

# Single common words that are never job titles
_JUNK_SINGLE_WORDS = {
    'this', 'that', 'the', 'our', 'your', 'their', 'its', 'a', 'an',
    'we', 'you', 'they', 'it', 'he', 'she', 'here', 'there', 'i',
    'some', 'any', 'all', 'one', 'time', 'now', 'soon', 'more',
    'role', 'position', 'opportunity', 'job', 'opening',
}

# ── Module-level compiled job-title pattern constants ──────────────────────
_JOB_KEYWORDS = r'(?:Engineer|Scientist|Analyst|Developer|Architect|Researcher|Manager|Director|Lead|Specialist|Consultant|Associate|Intern|Designer|Strategist|Coordinator|Programmer|Administrator)'
_JOB_PATTERN = re.compile(
    rf'(?:^|(?<=[\n\-–:,\s]))(\b(?:(?:Senior|Sr|Staff|Principal|Lead|Junior|Jr|Associate|Founding|Applied|Full[- ]?Stack|Fullstack|Entry[- ]Level|Mid[- ]Level|Mid|Head\s+of)\s+)?(?:[A-Za-z][A-Za-z/]*\s+){{0,3}}{_JOB_KEYWORDS}(?:\s+(?:I{{1,3}}|IV|V|\d+))?)(?=[,.\n;(\s]|$)',
    re.M,
)
_JOB_KW_RE = re.compile(
    r'\b(?:Engineer|Scientist|Analyst|Developer|Architect|Researcher|Manager|Director|Lead|Specialist|Consultant|Associate|Intern|Designer|Strategist|Coordinator|Programmer|Administrator)\b',
    re.I,
)


def _has_job_keyword(text: str) -> bool:
    """Return True only if text contains a real job title keyword."""
    return bool(_JOB_KW_RE.search(text or ''))


def _is_junk_title(text: str) -> bool:
    """Return True if the extracted title is actually a body sentence."""
    if not text:
        return True
    stripped = text.strip().strip('.,;:').strip()
    t = stripped.lower()

    # Single-word false positives
    if t in _JUNK_SINGLE_WORDS:
        return True

    # Must be at least 2 words to be a real job title
    words = stripped.split()
    if len(words) < 2:
        return True

    if any(phrase in t for phrase in _JUNK_TITLE_PHRASES):
        return True
    if t.startswith(('at ', 'we ', 'has ', 'i ', 'our ', 'you ', 'if ', 'in the ')):
        return True
    if len(words) > 10:   # more than 10 words → sentence, not a title
        return True
    return False


def _company_from_sender(sender: str) -> str | None:
    """Extract company name from sender display name or email domain."""
    # 1. Try display name: "Snap HR <snapchat@myworkday.com>" → "Snap"
    display_match = re.match(r'^"?([^"<]+?)"?\s*<', sender)
    if display_match:
        display = display_match.group(1).strip()
        # Remove noise words from display name
        noise = r'\b(hr|recruiting|talent|careers|jobs|team|noreply|no.reply|do.not.reply|notifications|hiring|worldwide|worldwide recruiting)\b'
        cleaned = re.sub(noise, '', display, flags=re.I).strip().strip('-').strip()
        if cleaned and len(cleaned) > 2 and not re.match(r'^[\W\d]+$', cleaned):
            return _clean(cleaned)

    # 2. For Workday: extract subdomain as company name
    # "orionadvisor@myworkday.com" → "Orion Advisor"
    # "snapchat@myworkday.com" → "Snapchat"
    # "verily@myworkday.com" → "Verily"
    workday_match = re.search(r'([a-zA-Z0-9\-]+)@(?:[a-z0-9]+\.)?myworkday(?:jobs)?\.com', sender)
    if workday_match:
        subdomain = workday_match.group(1).lower()
        skip_subdomains = {'workday', 'noreply', 'no-reply', 'notifications', 'ryder'}
        if subdomain not in skip_subdomains:
            # Convert camelCase or hyphen-separated to words
            name = re.sub(r'([a-z])([A-Z])', r'\1 \2', subdomain)
            name = name.replace('-', ' ').replace('_', ' ')
            return name.title()

    # 3. Fall back to email domain
    m = re.search(r'@([a-zA-Z0-9\-]+)\.(com|ai|io|co|org|net)', sender)
    if not m:
        return None
    domain = m.group(1).lower()
    skip = {'gmail', 'yahoo', 'outlook', 'hotmail', 'greenhouse', 'lever',
            'workday', 'icims', 'smartrecruiters', 'bamboohr', 'indeed',
            'linkedin', 'glassdoor', 'jobvite', 'taleo', 'successfactors',
            'myworkdayjobs', 'noreply', 'no-reply', 'notifications',
            'careers', 'jobs', 'talent', 'recruiting', 'hr', 'uber',
            'email', 'mail', 'us', 'ycombinator'}
    if domain in skip:
        return None
    return domain.replace('-', ' ').title()


def extract_company_and_title(subject: str, body: str, platform: str, sender: str = ''):
    company, title = None, None
    s = subject

    if platform == 'LinkedIn':
        m = re.search(r'application was sent to\s+(.+?)(?:\s*[-–|]|$)', s, re.I)
        if m:
            company = _clean(m.group(1))
        m = re.search(r'applied for\s+(.+?)\s+at\s+(.+?)(?:\s*[-–|]|$)', s, re.I)
        if m:
            title, company = _clean(m.group(1)), _clean(m.group(2))

    elif platform == 'Indeed':
        m = re.search(r'application to\s+(.+?)\s+at\s+(.+?)(?:\s+has|\s*[-–|]|$)', s, re.I)
        if m:
            title, company = _clean(m.group(1)), _clean(m.group(2))

    elif platform == 'Greenhouse':
        m = re.search(r'(?:received|confirmation)[^\w]+(.+?)\s+at\s+(.+?)(?:\s*[-–|]|$)', s, re.I)
        if m:
            title, company = _clean(m.group(1)), _clean(m.group(2))

    # ── Generic subject patterns ───────────────────────────────────
    if not company:
        # "Thank you for applying to / interest in Cohere Health"
        m = re.search(
            r'(?:applying to|applied to|application to|application at|submitted to|applying at|interest in|interest in joining)\s+(.+?)(?:\s+for\s+|\s*[-–|,!]|$)',
            s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "Cohere Health - Application Received"  "Ryder - Thank You for your interest"
        m = re.search(r'^([A-Z][A-Za-z0-9\s&.,!]{2,40}?)\s*[-–|]\s*(?:application|thank|we received|your)', s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "Operio has received your application"  "Thomson Reuters received your application"
        m = re.search(r'^([A-Z][A-Za-z0-9\s&.,!]{2,40}?)\s+(?:has received|received)\s+your\s+application', s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "Orion Application Update"  "Raindrop Application Update"
        m = re.search(r'^([A-Z][A-Za-z0-9\s&.,!]{2,40}?)\s+application\s+update', s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "Thank you for your interest in NVIDIA"  "Thanks for your interest in Apple"
        m = re.search(r'(?:thank you for your interest in|thanks for your interest in)\s+(.+?)(?:\s*[!.,]|$)', s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "Thank you from NVIDIA"
        m = re.search(r'thank you from\s+(.+?)(?:\s*[!.,]|$)', s, re.I)
        if m:
            company = _clean(m.group(1))

    if not company:
        # "we've received your Tesla application"  "received your IBM job application"
        m = re.search(r"received your\s+(.+?)\s+(?:job\s+)?application", s, re.I)
        if m:
            candidate = _clean(m.group(1))
            if len(candidate.split()) <= 3:   # short = company name, not a sentence
                company = candidate

    if not title:
        m = re.search(
            r'(?:application for|applied for|position of|role of|applying for)\s+(.+?)(?:\s+at\s+|\s*[-–|]|$)',
            s, re.I)
        if m:
            candidate = _clean(m.group(1))
            if not _is_junk_title(candidate):
                title = candidate

    if not title:
        # "successfully submitted your IBM job application - 79649 - Entry level AI/ML Engineer: SVL"
        m = re.search(r'job application\s*[-–]\s*\d+\s*[-–]\s*(.+?)$', s, re.I)
        if m:
            candidate = _clean(m.group(1))
            if not _is_junk_title(candidate):
                title = candidate

    if not company or not title or title == 'Unknown Position':
        # "Your application for Pingo AI - Founding AI Systems Engineer"
        # "Your application for CompanyName - Job Title"
        m = re.search(r'(?:application for|applying for)\s+([A-Z][A-Za-z0-9\s&.]+?)\s*[-–]\s*(.+?)$', s, re.I)
        if m:
            part1 = _clean(m.group(1))
            part2 = _clean(m.group(2))
            if not company and len(part1.split()) <= 4:
                company = part1
            if (not title or title == 'Unknown Position') and not _is_junk_title(part2):
                title = part2

    if not title or title == 'Unknown Position':
        # Subject: "Pingo AI - Founding AI Systems Engineer" (without "application for")
        m = re.search(r'^([A-Z][A-Za-z0-9\s&.]{2,30}?)\s*[-–]\s*([A-Z][A-Za-z0-9\s/,.()\-]{5,80}?)$', s, re.I)
        if m:
            part1 = _clean(m.group(1))
            part2 = _clean(m.group(2))
            # part2 must differ from part1 and not be junk
            if part1.lower() != part2.lower() and not _is_junk_title(part2):
                if not company:
                    company = part1
                title = part2

    # ── Body patterns ──────────────────────────────────────────────
    if body:
        body_patterns_company = [
            r'^(?:company|employer|organization)\s*:\s*(.+?)$',
        ]
        body_patterns_title = [
            # Structured label: value
            r'^(?:position|role|job title|title|job)\s*:\s*(.+?)$',
            r'(?:opening|opportunity)\s*:\s*(.+?)$',

            # "interest in the <Title> position/role/opportunity/job opening"  (Yahoo, Raindrop, Artera)
            r'interest in (?:the\s+)?(.+?)\s+(?:position|role|opportunity|job\s+opening|job\b)',
            # "interest in the <Title> at Company"
            r'interest in (?:the\s+)?(.+?)\s+at\s+\w',

            # "applying to the <Title> role"  (Snap, Skydio)
            r'applying to (?:the\s+)?(.+?)\s+(?:role|position|opportunity)',
            # "submitting your application to the <Title> role"
            r'submitting your application to (?:the\s+)?(.+?)\s+(?:role|position|opportunity)',

            # "application for <Title> role/position/opportunity"
            r'(?:applied for|applying for|application for)\s+(?:the\s+)?(.+?)\s+(?:position|role|opportunity)',
            # "application for <Title>." — sentence ends with Our/We/The/Your/If  (LangChain)
            r'(?:applied for|applying for|application for)\s+(?:the\s+)?([A-Z][^\n]{3,80}?)\.\s+(?:Our|We|The|Your|If)',
            # "application for <Title>." — ends with period or newline
            r'(?:applied for|applying for|application for)\s+(?:the\s+)?([A-Z][^\n.]{3,80}?)\s*[.\n]',
            # "application for <Title>" — end of string
            r'(?:applied for|applying for|application for)\s+(?:the\s+)?([A-Z][^\n]{3,80}?)(?:\s*$)',

            # "applying for our <Title> position"  (Cohere Health, SoFi)
            r'applying to our\s+(.+?)\s+(?:position|role)',
            r'applied to our\s+(.+?)\s+(?:position|role)',

            # "your application for the <Title> role"
            r'your application for (?:the\s+)?([A-Z][^\n.]{3,80}?)\s+(?:role|position|opportunity)',
            r'your application for (?:the\s+)?([A-Z][^\n.]{3,80}?)\s*[.\n]',

            # "received your application for <Title>"  (incl. "our", comma-terminated)
            r'received your application for (?:our\s+)?(?:the\s+)?(.+?)\s+(?:role|position|opportunity)',
            r'received your application for (?:our\s+)?(?:the\s+)?([A-Z][^\n.]{3,80}?)[,.\n]',

            # "application to the <Title> role"  (Cohere)
            r'application to (?:the\s+)?(.+?)\s+(?:role|position|opportunity)',

            # "thank you for applying to the <Title> role"  (Snap)
            r'(?:thank you for applying|thanks for applying) to (?:the\s+)?(.+?)\s+(?:role|position|opportunity)',
            r'(?:thank you for applying|thanks for applying) to (?:the\s+)?([A-Z][^\n,]{3,80}?),',

            # "for the <Title> position/role" (Cohere Health rejection style)
            r'\bfor the\s+(.+?)\s+(?:position|role)(?:\s+at\b|\s*[.,\n]|$)',

            # "position of / role of <Title>"
            r'(?:position of|role of)\s+(.+?)(?:\s+at\s+|\s*[,.\n])',

            # "you've applied for the <Title> position/role"
            r"you(?:'ve| have) applied (?:for(?: the)?)\s+(.+?)\s+(?:position|role|opening)",
            # "You've applied to CTIO AI Engineering Manager" (PwC/Workday style)
            r"you(?:'ve| have) applied to\s+(.+?)(?:\s*[.\n]|$)",

            # Ryder-style: embedded forwarded subject in body
            # "Subject: Name - REQ123 AI/ML Engineer III (C1393700)"
            r'Subject:\s+[^-\n]+-\s+[A-Z0-9]+\s+(.+?)(?:\s*\([^)]+\))?\s*$',
            r'Subject:\s+.+?[-–]\s*(.+?)(?:\s*\([^)]+\))?\s*$',
        ]

        if not company:
            for pat in body_patterns_company:
                m = re.search(pat, body, re.I | re.M)
                if m:
                    candidate = _clean(m.group(1))
                    if candidate and len(candidate) < 60:
                        company = candidate
                        break

        if not title:
            for pat in body_patterns_title:
                m = re.search(pat, body, re.I | re.M)
                if m:
                    candidate = _clean(m.group(1))
                    # Must contain a real job keyword, not match company name, not be junk
                    if (candidate and not _is_junk_title(candidate)
                            and candidate.lower() != (company or '').lower()
                            and re.search(r'\b(?:Engineer|Scientist|Analyst|Developer|Architect|Researcher|Manager|Director|Lead|Specialist|Consultant|Associate|Intern|Designer|Strategist|Coordinator|Programmer|Administrator)\b', candidate, re.I)):
                        title = candidate
                        break

    # ── Universal job-keyword extractor (subject + body fallback) ────
    # Captures any phrase containing a common job title keyword
    # e.g. "AI/ML Engineer III", "Senior Data Scientist", "ML Research Lead"

    # ── Run _JOB_PATTERN first on subject + body ──────────────────
    if not title or title == 'Unknown Position':
        for text in [s, body or '']:
            for m in _JOB_PATTERN.finditer(text):
                candidate = _clean(m.group(1))
                if candidate and not _is_junk_title(candidate):
                    title = candidate
                    break
            if title and title != 'Unknown Position':
                break

    # ── Validate body-extracted title: must contain a job keyword ──
    if title and title != 'Unknown Position' and not _has_job_keyword(title):
        title = None

    # ── Last resort: extract company from sender domain ────────────
    if not company and sender:
        company = _company_from_sender(sender)

    # Final cleanup — strip trailing ! and * from company
    if company:
        company = _clean(company)
        # If all lowercase (e.g. "apexanalytix"), apply title case
        if company == company.lower():
            company = company.title()
    if title:
        title = _clean(title)
        if _is_junk_title(title):
            title = None

    return company or 'Unknown Company', title or 'Unknown Position'


def extract_location(body: str):
    if not body:
        return None
    patterns = [
        r'location[:\s]+(.+?)(?:\n|\r|<|$)',
        r'job location[:\s]+(.+?)(?:\n|\r|<|$)',
        r'\b(Remote|Hybrid|On-?site)\b',
    ]
    for pat in patterns:
        m = re.search(pat, body, re.I)
        if m:
            loc = m.group(1).strip() if m.lastindex else m.group(0).strip()
            return loc[:80]
    return None


def _decode_part(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='ignore')
    except Exception:
        return ''


def _html_to_text(html: str) -> str:
    """Strip HTML tags and decode entities to produce plain text."""
    # Remove style and script blocks entirely first
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.I | re.S)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.I | re.S)
    # Block elements → newlines
    text = re.sub(r'<(br|p|div|tr|li|h[1-6])[^>]*>', '\n', text, flags=re.I)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = text.replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_body(payload: dict) -> str:
    """Extract best plain text from email payload, falling back to HTML."""
    plain_parts = []
    html_parts = []

    mime = payload.get('mimeType', '')
    data = payload.get('body', {}).get('data', '')

    if mime == 'text/plain' and data:
        plain_parts.append(_decode_part(data))
    elif mime == 'text/html' and data:
        html_parts.append(_decode_part(data))

    for part in payload.get('parts', []):
        part_mime = part.get('mimeType', '')
        part_data = part.get('body', {}).get('data', '')
        if part_mime == 'text/plain' and part_data:
            plain_parts.append(_decode_part(part_data))
        elif part_mime == 'text/html' and part_data:
            html_parts.append(_decode_part(part_data))
        elif part.get('parts'):
            nested = extract_body(part)
            if nested:
                plain_parts.append(nested)

    if plain_parts:
        return ''.join(plain_parts)[:6000]
    if html_parts:
        return _html_to_text(''.join(html_parts))[:6000]
    return ''


def _extract_company_from_status_email(subject: str, body: str) -> str | None:
    """Best-effort company extraction from rejection/selection emails."""
    s = subject
    subject_patterns = [
        # "Thank you for your interest in Reddit"
        r'(?:thank you for your interest in|thanks for your interest in|interest in joining)\s+([A-Za-z0-9\s&.,]+?)(?:\s*[!.,]|$)',
        # "Thank you from NVIDIA"
        r'thank you from\s+([A-Za-z0-9\s&.,]+?)(?:\s*[!.,]|$)',
        # "Google - Application Update"  "Ryder - Thank You"
        r'^([A-Z][A-Za-z0-9\s&.,]{2,40?})\s*[-–|:]\s',
        # "your application at / with Google"
        r'(?:with|at|from|interview with)\s+([A-Z][A-Za-z0-9\s&.,]+?)(?:\s*[-–,|]|\s+team|\s+is|\s+has|\s*$)',
    ]
    for pat in subject_patterns:
        m = re.search(pat, s, re.I)
        if m:
            candidate = _clean(m.group(1))
            if 2 < len(candidate) < 60:
                return candidate

    # Body fallback
    if body:
        body_patterns = [
            r'application (?:for|to)\s+.{0,60}?\bat\s+([A-Z][A-Za-z0-9\s&.,]{2,40}?)(?:\s*[,.\n!])',
            r'(?:interest in|applying to|applied to)\s+([A-Z][A-Za-z0-9\s&.,]{2,40}?)(?:\s*[,.\n!])',
            r'(?:The\s+)?([A-Z][A-Za-z0-9\s&.,]{2,30}?)\s+[Tt]eam\b',
        ]
        for pat in body_patterns:
            m = re.search(pat, body)
            if m:
                candidate = _clean(m.group(1))
                if 2 < len(candidate) < 60:
                    return candidate

    return None


def parse_email(msg_data: dict):
    """
    Returns a dict with key 'type':
      - type='application' → new application data
      - type='rejection'   → {type, email_id, company, email_date}
      - type='selected'    → {type, email_id, company, new_status, email_date}
      - None if not a job email
    """
    headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
    subject = headers.get('Subject', '')
    sender  = headers.get('From', '')
    date_str = headers.get('Date', '')

    email_date = datetime.now().isoformat()
    try:
        email_date = parsedate_to_datetime(date_str).isoformat()
    except Exception:
        pass

    platform = detect_platform(sender, subject)
    body = extract_body(msg_data.get('payload', {}))
    email_type = _detect_email_type(subject, body)

    if email_type == 'unknown':
        # Still check platform-based application detection
        if not is_job_application_email(subject, sender):
            return None
        email_type = 'application'

    if email_type == 'application':
        company, job_title = extract_company_and_title(subject, body, platform, sender)
        location = extract_location(body)
        return {
            'type': 'application',
            'company': company,
            'job_title': job_title,
            'location': location or 'Not specified',
            'applied_at': email_date,
            'source': platform,
            'email_id': msg_data.get('id'),
            'status': 'Applied',
        }

    if email_type == 'rejection':
        company = _extract_company_from_status_email(subject, body)
        _, job_title = extract_company_and_title(subject, body, platform, sender)
        return {
            'type': 'rejection',
            'email_id': msg_data.get('id'),
            'company': company,
            'job_title': job_title if job_title != 'Unknown Position' else None,
            'email_date': email_date,
            'subject': subject,
        }

    if email_type == 'selected':
        company = _extract_company_from_status_email(subject, body)
        new_status = _resolve_selected_status(subject, body)
        _, job_title = extract_company_and_title(subject, body, platform, sender)
        return {
            'type': 'selected',
            'email_id': msg_data.get('id'),
            'company': company,
            'new_status': new_status,
            'job_title': job_title if job_title != 'Unknown Position' else None,
            'email_date': email_date,
            'subject': subject,
        }

    return None
