import os
import re
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

from database import (
    init_db, get_applications, add_application,
    update_application, delete_application,
    get_analytics, get_last_sync, log_sync,
    update_status_by_company, update_title_by_company, upsert_application,
)

app = Flask(__name__)
CORS(app)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['TEMPLATES_AUTO_RELOAD'] = True


@app.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, 'config.json')

init_db()

@app.context_processor
def inject_version():
    return {'ver': int(datetime.now().timestamp())}


# ── Config helpers ────────────────────────────────────────────────

def load_config():
    default = {
        'resume_folder': os.path.expanduser('~/Documents/Resumes'),
        'sync_days_back': 90,
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            saved = json.load(f)
        default.update(saved)
    return default


def save_config(config):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


# ── Routes ────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/applications', methods=['GET'])
def list_applications():
    filters = {
        'status': request.args.get('status') or None,
        'search': request.args.get('search') or None,
        'date_from': request.args.get('date_from') or None,
        'date_to': request.args.get('date_to') or None,
        'source': request.args.get('source') or None,
    }
    return jsonify(get_applications(filters))


@app.route('/api/applications', methods=['POST'])
def create_application():
    data = request.json
    if not data.get('company') or not data.get('job_title'):
        return jsonify({'error': 'company and job_title are required'}), 400
    success = add_application(data)
    return jsonify({'success': success})


@app.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_app(app_id):
    success = update_application(app_id, request.json)
    return jsonify({'success': success})


@app.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_app(app_id):
    delete_application(app_id)
    return jsonify({'success': True})


@app.route('/api/analytics')
def analytics():
    return jsonify(get_analytics())


@app.route('/api/config', methods=['GET'])
def get_config_route():
    return jsonify(load_config())


@app.route('/api/config', methods=['PUT'])
def update_config_route():
    config = load_config()
    config.update(request.json)
    save_config(config)
    return jsonify({'success': True})


@app.route('/api/open-resume', methods=['POST'])
def open_resume():
    folder = load_config().get('resume_folder', '')
    name = request.json.get('name', '')
    if not folder or not name:
        return jsonify({'error': 'Missing config or name'}), 400
    import subprocess
    # Try PDF file first, then folder
    pdf_path = os.path.join(folder, name + '.pdf')
    dir_path = os.path.join(folder, name)
    if os.path.exists(pdf_path):
        subprocess.Popen(['start', '', pdf_path], shell=True)
    elif os.path.exists(dir_path):
        subprocess.Popen(['explorer', dir_path])
    else:
        return jsonify({'error': 'File not found'}), 404
    return jsonify({'success': True})


@app.route('/api/resume-folders')
def list_resume_folders():
    folder = load_config().get('resume_folder', '')
    if not folder or not os.path.exists(folder):
        return jsonify([])
    try:
        items = []
        for f in os.listdir(folder):
            full = os.path.join(folder, f)
            if os.path.isdir(full):
                items.append(f)
            elif f.lower().endswith('.pdf'):
                items.append(os.path.splitext(f)[0])  # strip .pdf
        return jsonify(sorted(items))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/auto-assign-resumes', methods=['POST'])
def auto_assign_resumes():
    folder = load_config().get('resume_folder', '')
    if not folder or not os.path.exists(folder):
        return jsonify({'error': 'Resume folder not configured'}), 400

    # Build list of resume names (folders + PDFs without extension)
    resume_names = []
    for f in os.listdir(folder):
        full = os.path.join(folder, f)
        if os.path.isdir(full):
            resume_names.append(f)
        elif f.lower().endswith('.pdf'):
            resume_names.append(os.path.splitext(f)[0])

    def normalize(s):
        return re.sub(r'[^a-z0-9]', '', s.lower())

    def best_match(company):
        c = normalize(company)
        # Exact match first
        for r in resume_names:
            if normalize(r) == c:
                return r
        # One contains the other
        for r in resume_names:
            rn = normalize(r)
            if rn in c or c in rn:
                return r
        return None

    apps = get_applications({})
    assigned = 0
    for app_row in apps:
        if app_row.get('resume_folder'):
            continue  # already assigned
        match = best_match(app_row['company'])
        if match:
            update_application(app_row['id'], {'resume_folder': match})
            assigned += 1

    return jsonify({'success': True, 'assigned': assigned})


@app.route('/api/sync', methods=['POST'])
def sync_emails():
    try:
        from gmail_service import get_gmail_service, fetch_job_emails, get_message_detail
        from email_parser import parse_email

        config = load_config()
        service = get_gmail_service()

        force = request.json and request.json.get('force', False)
        days_back = int(config.get('sync_days_back', 90))
        after_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y/%m/%d')

        if not force:
            last_sync = get_last_sync()
            if last_sync:
                try:
                    last_dt = datetime.fromisoformat(last_sync['synced_at'])
                    after_date = (last_dt - timedelta(days=1)).strftime('%Y/%m/%d')
                except Exception:
                    pass

        messages = fetch_job_emails(service, after_date=after_date)

        emails_processed = 0
        new_applications = 0
        status_updates = 0
        errors = 0

        for msg in messages:
            try:
                msg_data = get_message_detail(service, msg['id'])
                parsed = parse_email(msg_data)
                if not parsed:
                    continue

                emails_processed += 1
                email_type = parsed.get('type')

                if email_type == 'application':
                    result = upsert_application(parsed)
                    if result == 'inserted':
                        new_applications += 1
                    elif result == 'updated':
                        status_updates += 1

                elif email_type == 'rejection':
                    company = parsed.get('company')
                    job_title = parsed.get('job_title')
                    if company and update_status_by_company(company, 'Rejected', job_title):
                        status_updates += 1
                    # Also update title even if already rejected
                    if company and job_title:
                        update_title_by_company(company, job_title)
                    print(f'[sync] Rejection from {company or "unknown"}: {parsed.get("subject", "")}')

                elif email_type == 'selected':
                    company = parsed.get('company')
                    new_status = parsed.get('new_status', 'Phone Screen')
                    job_title = parsed.get('job_title')
                    if company and update_status_by_company(company, new_status, job_title):
                        status_updates += 1
                    if company and job_title:
                        update_title_by_company(company, job_title)
                    print(f'[sync] Selected ({new_status}) from {company or "unknown"}: {parsed.get("subject", "")}')

            except Exception as e:
                errors += 1
                print(f'[sync] Error on {msg.get("id")}: {e}')

        log_sync(emails_processed, new_applications)

        return jsonify({
            'success': True,
            'emails_processed': emails_processed,
            'new_applications': new_applications,
            'status_updates': status_updates,
            'errors': errors,
        })

    except FileNotFoundError as e:
        return jsonify({'error': str(e), 'setup_required': True}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sync/status')
def sync_status():
    return jsonify(get_last_sync() or {})


@app.route('/api/credentials-check')
def credentials_check():
    creds_exists = os.path.exists(os.path.join(BASE_DIR, 'credentials.json'))
    token_exists = os.path.exists(os.path.join(BASE_DIR, 'token.pickle'))
    return jsonify({
        'credentials_json': creds_exists,
        'token_saved': token_exists,
    })


if __name__ == '__main__':
    print('\n  Job Application Tracker')
    print('  Open http://localhost:5000 in your browser\n')
    app.run(debug=True, port=5000, use_reloader=True)
