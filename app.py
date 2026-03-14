import os, random, uuid
from datetime import datetime
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify, flash)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'shawarma-secret-change-in-prod')

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, 'static', 'uploads')
DB_PATH    = os.path.join(BASE_DIR, 'shawarma.db')
ALLOWED    = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── DB helpers ─────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                played_at  TEXT,
                crash_at   REAL,
                stop_at    REAL,
                won        INTEGER,
                discount   REAL
            );
        ''')
        defaults = {
            'admin_password': generate_password_hash('admin'),
            'min_discount':   '5',
            'max_discount':   '40',
            'duration_sec':   '8',
            'shop_name':      'Shawarma Express',
            'logo_path':      '',
            'bg_path':        '',
        }
        for k, v in defaults.items():
            db.execute('INSERT OR IGNORE INTO settings VALUES (?,?)', (k, v))
        db.commit()


def get_setting(key, default=''):
    with get_db() as db:
        row = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
        return row['value'] if row else default


def set_setting(key, value):
    with get_db() as db:
        db.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, value))
        db.commit()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


# ── Auth helpers ────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


# ── Admin routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return redirect(url_for('dashboard') if session.get('admin') else url_for('login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect(url_for('dashboard'))
    error = None
    if request.method == 'POST':
        pw = request.form.get('password', '')
        stored = get_setting('admin_password')
        if check_password_hash(stored, pw):
            session['admin'] = True
            return redirect(url_for('dashboard'))
        error = 'Wrong password.'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/admin')
@admin_required
def dashboard():
    settings = {
        'shop_name':    get_setting('shop_name',    'Shawarma Express'),
        'min_discount': get_setting('min_discount', '5'),
        'max_discount': get_setting('max_discount', '40'),
        'duration_sec': get_setting('duration_sec', '8'),
        'logo_path':    get_setting('logo_path'),
        'bg_path':      get_setting('bg_path'),
    }
    return render_template('admin_dashboard.html', **settings)


@app.route('/admin/settings', methods=['POST'])
@admin_required
def save_settings():
    fields = ['shop_name', 'min_discount', 'max_discount', 'duration_sec']
    for f in fields:
        val = request.form.get(f, '').strip()
        if val:
            set_setting(f, val)

    new_pw = request.form.get('new_password', '').strip()
    if new_pw:
        set_setting('admin_password', generate_password_hash(new_pw))
        flash('Password updated.')

    flash('Settings saved.')
    return redirect(url_for('dashboard'))


@app.route('/admin/upload/<kind>', methods=['POST'])
@admin_required
def upload(kind):
    if kind not in ('logo', 'bg'):
        return 'Invalid', 400
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        flash('Invalid file.')
        return redirect(url_for('dashboard'))

    ext      = file.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f'{kind}_{uuid.uuid4().hex[:8]}.{ext}')
    file.save(os.path.join(UPLOAD_DIR, filename))
    set_setting(f'{kind}_path', filename)
    flash(f'{"Logo" if kind=="logo" else "Background"} updated.')
    return redirect(url_for('dashboard'))


@app.route('/admin/history')
@admin_required
def history():
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM history ORDER BY id DESC LIMIT 200'
        ).fetchall()

    # JSON summary for dashboard stats
    if request.args.get('json'):
        total     = len(rows)
        wins      = sum(1 for r in rows if r['won'])
        win_rate  = round(wins / total * 100, 1) if total else 0
        won_discs = [r['discount'] for r in rows if r['won']]
        avg_disc  = round(sum(won_discs) / len(won_discs), 1) if won_discs else 0
        return jsonify(total=total, wins=wins, win_rate=win_rate, avg_discount=avg_disc)

    return render_template('admin_history.html', rows=rows,
                           shop_name=get_setting('shop_name', 'Shawarma Express'))


# ── Game API ────────────────────────────────────────────────────────────────

@app.route('/api/start', methods=['POST'])
def api_start():
    try:
        mn  = float(get_setting('min_discount', '5'))
        mx  = float(get_setting('max_discount', '40'))
        dur = float(get_setting('duration_sec', '8'))
    except ValueError:
        mn, mx, dur = 5.0, 40.0, 8.0

    crash_at = round(random.uniform(mn, mx), 2)
    # How far along (0.0–1.0) the crash happens
    progress  = (crash_at - mn) / (mx - mn) if mx > mn else 0.5
    crash_ms  = int(progress * dur * 1000)

    session['game'] = {
        'crash_at':  crash_at,
        'crash_ms':  crash_ms,
        'min':       mn,
        'max':       mx,
        'dur_ms':    int(dur * 1000),
        'started_at': datetime.utcnow().isoformat(),
    }

    # Send crash_ms to drive the visual animation — the actual discount value
    # is validated server-side so sending crash_ms is acceptable for this
    # promotional game (anti-cheat is not a requirement).
    return jsonify(min=mn, max=mx, duration_ms=int(dur * 1000), crash_ms=crash_ms)


@app.route('/api/result', methods=['POST'])
def api_result():
    game = session.get('game')
    if not game:
        return jsonify(error='No active game'), 400

    data     = request.get_json(force=True)
    stop_ms  = data.get('stop_ms', -1)   # -1 = crashed (player did not stop)
    crashed  = stop_ms < 0

    crash_ms = game['crash_ms']
    mn       = game['min']
    mx       = game['max']
    dur_ms   = game['dur_ms']
    crash_at = game['crash_at']

    if crashed or stop_ms >= crash_ms:
        won      = False
        discount = 0.0
        stop_val = crash_at
    else:
        won      = True
        progress = stop_ms / dur_ms if dur_ms else 0
        # Reverse the client ease: smoothstep with 1.05 factor
        # simple approximation: clamp progress to [0,1] and use linear
        progress = max(0.0, min(1.0, progress))
        stop_val = round(mn + progress * (mx - mn), 1)
        # Ensure stop_val is below crash_at (server-authoritative)
        stop_val = min(stop_val, round(crash_at - 0.1, 1))
        discount = stop_val

    with get_db() as db:
        db.execute(
            'INSERT INTO history (played_at, crash_at, stop_at, won, discount) VALUES (?,?,?,?,?)',
            (datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
             crash_at, stop_val, int(won), discount)
        )
        db.commit()

    session.pop('game', None)
    return jsonify(won=won, discount=discount, crash_at=crash_at)


# ── Customer game page ──────────────────────────────────────────────────────

@app.route('/game')
def game():
    return render_template('game.html',
                           shop_name=get_setting('shop_name', 'Shawarma Express'),
                           logo_path=get_setting('logo_path'),
                           bg_path=get_setting('bg_path'),
                           min_discount=get_setting('min_discount', '5'),
                           max_discount=get_setting('max_discount', '40'))


# ── Bootstrap ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5003)
else:
    init_db()
