from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
import os
import requests
import sqlite3
import datetime
import math
import uuid
import hashlib
import hmac
import base64
import json
import bcrypt
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'freshguard_super_secret_key_123!')

# Hugging Face Spaces の iframe 内でもクッキー（セッション）が正しく動作するための設定
app.config.update(
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_HTTPONLY=True
)

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
DATABASE = 'db.sqlite3'

# ─── パスワードハッシュヘルパー（BCrypt） ─────────────────────────
def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

# ─── 認証デコレータ ─────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': '認証が必要です。ログインしてください。'}), 401
            return redirect(url_for('login_view'))
        return f(*args, **kwargs)
    return decorated_function

# ─── データベース設定 ───────────────────────────────────

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # ユーザーテーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    
    # 在庫テーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            expiryDate TEXT NOT NULL,
            registeredAt TEXT NOT NULL,
            storageType TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            price REAL DEFAULT 0
        )
    ''')
    
    # 設定テーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id TEXT PRIMARY KEY DEFAULT 'default',
            fridgeTemp REAL NOT NULL DEFAULT 4.0,
            regionTemp REAL DEFAULT 22.0,
            location TEXT NOT NULL DEFAULT '東京都',
            lat REAL NOT NULL DEFAULT 35.6762,
            lon REAL NOT NULL DEFAULT 139.6503,
            lineUserId TEXT,
            saved_money REAL DEFAULT 0,
            lost_money REAL DEFAULT 0
        )
    ''')
    
    # シード状態を追跡するテーブルの作成
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS seed_tracker (
            seeded INTEGER PRIMARY KEY DEFAULT 0
        )
    ''')
    conn.commit()
    
    # ── データベースマイグレーション（マルチユーザー対応 & SDGs対応） ──
    # inventoryテーブルにuser_idカラムを追加（既存データ用）
    try:
        cursor.execute("ALTER TABLE inventory ADD COLUMN user_id TEXT DEFAULT 'default'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # 既にカラムが存在する場合
        
    # settingsテーブルにuser_idカラムを追加（既存データ用）
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN user_id TEXT DEFAULT 'default'")
        conn.commit()
    except sqlite3.OperationalError:
        pass # 既にカラムが存在する場合

    # inventoryテーブルにpriceカラムを追加
    try:
        cursor.execute("ALTER TABLE inventory ADD COLUMN price REAL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # settingsテーブルにsaved_moneyカラムを追加
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN saved_money REAL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # settingsテーブルにlost_moneyカラムを追加
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN lost_money REAL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # デフォルト設定の挿入（移行・互換用）
    cursor.execute("SELECT COUNT(*) FROM settings WHERE id = 'default'")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO settings (id, user_id, fridgeTemp, regionTemp, location, lat, lon)
            VALUES ('default', 'default', 4.0, 22.0, '東京都', 35.6762, 139.6503)
        ''')
        conn.commit()
        
    # 初期サンプルデータのシード（初回起動時のみ）
    cursor.execute("SELECT COUNT(*) FROM seed_tracker")
    is_seeded = cursor.fetchone()[0] > 0
    if not is_seeded:
        now = datetime.datetime.now()
        def add_days(n):
            return (now + datetime.timedelta(days=n)).strftime('%Y-%m-%d')
        def sub_iso(n):
            return (now - datetime.timedelta(days=n)).isoformat()
            
        sample_items = [
            (str(uuid.uuid4()), 'default', '牛乳', 'dairy', add_days(3), sub_iso(1), 'fridge', 1.0, '本', 'fresh', '早めに飲む'),
            (str(uuid.uuid4()), 'default', '豚ひき肉', 'meat', add_days(1), sub_iso(2), 'fridge', 300.0, 'g', 'warning', ''),
            (str(uuid.uuid4()), 'default', 'キャベツ', 'vegetable', add_days(5), sub_iso(1), 'fridge', 1.0, '玉', 'fresh', '半分にカット済'),
            (str(uuid.uuid4()), 'default', '豆腐', 'other', add_days(-1), sub_iso(5), 'fridge', 1.0, '丁', 'danger', ''),
            (str(uuid.uuid4()), 'default', 'ヨーグルト', 'dairy', add_days(7), sub_iso(2), 'fridge', 1.0, '個', 'fresh', ''),
            (str(uuid.uuid4()), 'default', 'ほうれん草', 'vegetable', add_days(2), sub_iso(1), 'fridge', 1.0, '袋', 'warning', '')
        ]
        cursor.executemany('''
            INSERT INTO inventory (id, user_id, name, category, expiryDate, registeredAt, storageType, quantity, unit, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_items)
        cursor.execute("INSERT INTO seed_tracker (seeded) VALUES (1)")
        conn.commit()
        
    conn.close()

# アプリ起動時にデータベースを初期化
init_db()


# ─── バックグラウンド定期アラートスケジューラ ─────────────────
import threading
import time

def start_background_scheduler():
    def job():
        app.logger.info("Starting background alert scheduler...")
        while True:
            try:
                now = datetime.datetime.now()
                # 毎日朝 8:00 にアラート判定を実行
                if now.hour == 8 and now.minute == 0:
                    app.logger.info("Executing scheduled daily alert check...")
                    with app.app_context():
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        # LINE IDが設定されている全ユーザーの設定を取得
                        cursor.execute('SELECT * FROM settings WHERE lineUserId IS NOT NULL AND lineUserId != ""')
                        settings_rows = cursor.fetchall()
                        
                        for settings_row in settings_rows:
                            settings = dict(settings_row)
                            line_user_id = settings.get('lineUserId')
                            user_id = settings.get('user_id')
                            
                            if line_user_id and user_id:
                                cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
                                item_rows = cursor.fetchall()
                                
                                danger_items = []
                                warning_items = []
                                
                                for row in item_rows:
                                    item = dict(row)
                                    status, display_days = calculate_deterioration(item, settings)
                                    if status == 'danger':
                                        days_text = "今日まで" if display_days == 0 else f"{abs(display_days)}日超過" if display_days < 0 else "今日中"
                                        danger_items.append(f"- {item['name']} ({days_text})")
                                    elif status == 'warning':
                                        warning_items.append(f"- {item['name']} (あと {display_days} 日)")
                                        
                                if danger_items or warning_items:
                                    message_text = "⚠️ 賞味期限アラート ⚠️\n冷蔵庫内の食材の賞味期限が迫っています！\n"
                                    if danger_items:
                                        message_text += f"\n🔴 本日まで/期限切れ:\n" + "\n".join(danger_items) + "\n"
                                    if warning_items:
                                        message_text += f"\n🟡 あと1〜3日:\n" + "\n".join(warning_items) + "\n"
                                    message_text += "\nお早めにお召し上がりください！🍳"
                                    
                                    send_push_message(line_user_id, message_text)
                        conn.close()
                # 1分待機して再チェック（重複防止のためsleepは60秒）
                time.sleep(60)
            except Exception as e:
                app.logger.error(f"Error in scheduler job: {e}")
                time.sleep(60)

    thread = threading.Thread(target=job, daemon=True)
    thread.start()

# バックグラウンドスケジューラを起動
start_background_scheduler()

# ─── Q10温度予測ヘルパー ─────────────────────────────────

def calculate_deterioration(item, settings):
    """サーバー側でQ10則に基づいて劣化ステータスを計算する（LINE通知用）"""
    try:
        expiry_date = datetime.datetime.strptime(item['expiryDate'].split('T')[0], '%Y-%m-%d')
        # registeredAt の ISO 8601 形式の解析
        reg_str = item['registeredAt'].split('.')[0].replace('Z', '')
        if 'T' in reg_str:
            registered_date = datetime.datetime.strptime(reg_str, '%Y-%m-%dT%H:%M:%S')
        else:
            registered_date = datetime.datetime.strptime(reg_str, '%Y-%m-%d %H:%M:%S')
    except Exception as e:
        # 解析に失敗した場合はデフォルトで現在日付を基準にする
        expiry_date = datetime.datetime.now()
        registered_date = datetime.datetime.now()
        
    now = datetime.datetime.now()
    
    # 日数の算出
    total_days = max(0, (expiry_date - registered_date.replace(hour=0, minute=0, second=0, microsecond=0)).days)
    display_days_left = (expiry_date - now.replace(hour=0, minute=0, second=0, microsecond=0)).days
    
    current_temp = 10.0
    base_temp = 10.0
    
    storage_type = item.get('storageType', 'fridge')
    if storage_type == 'fridge':
        current_temp = settings.get('fridgeTemp', 4.0)
        base_temp = 10.0  # 要冷蔵は10℃基準
    elif storage_type == 'freezer':
        current_temp = -18.0  # 冷凍庫温度
        base_temp = -18.0
    elif storage_type == 'room':
        current_temp = settings.get('regionTemp') if settings.get('regionTemp') is not None else 25.0
        base_temp = 25.0  # 常温基準
        
    # Q10加速率
    acceleration_rate = math.pow(2.0, (current_temp - base_temp) / 10.0)
    
    # 登録からの経過日数
    days_passed = max(0, (now - registered_date).days)
    effective_days_passed = days_passed * acceleration_rate
    
    # 実効残存日数
    effective_days_left = max(0.0, total_days - effective_days_passed)
    
    status = 'fresh'
    if effective_days_left <= 1.0:
        status = 'danger'
    elif effective_days_left <= 3.0:
        status = 'warning'
        
    return status, display_days_left

# ─── ページルート ──────────────────────────────────────

@app.route('/register', methods=['GET', 'POST'])
def register_view():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'ユーザー名とパスワードを入力してください。'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ユーザー名の重複チェック
        cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'error': 'このユーザー名は既に使われています。'}), 400
            
        user_id = str(uuid.uuid4())
        hashed = hash_password(password)
        created_at = datetime.datetime.now().isoformat()
        
        try:
            cursor.execute('INSERT INTO users (id, username, password_hash, created_at) VALUES (?, ?, ?, ?)',
                           (user_id, username, hashed, created_at))
            # 新規ユーザーのデフォルト設定を作成
            cursor.execute('''
                INSERT INTO settings (id, user_id, fridgeTemp, regionTemp, location, lat, lon)
                VALUES (?, ?, 4.0, 22.0, '東京都', 35.6762, 139.6503)
            ''', (str(uuid.uuid4()), user_id))
            conn.commit()
        except Exception as e:
            conn.close()
            return jsonify({'error': f'登録中にエラーが発生しました: {str(e)}'}), 500
            
        conn.close()
        return jsonify({'success': '登録が完了しました。ログインしてください。'}), 201
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login_view():
    if 'user_id' in session:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form
            
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'error': 'ユーザー名とパスワードを入力してください。'}), 400
            
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user_row = cursor.fetchone()
        conn.close()
        
        if not user_row:
            return jsonify({'error': 'ユーザー名またはパスワードが正しくありません。'}), 401
            
        user = dict(user_row)
        if not check_password(password, user['password_hash']):
            return jsonify({'error': 'ユーザー名またはパスワードが正しくありません。'}), 401
            
        # セッションの開始
        session['user_id'] = user['id']
        session['username'] = user['username']
        
        return jsonify({'success': 'ログインしました。', 'redirect': url_for('index')}), 200
        
    return render_template('login.html')

@app.route('/logout')
def logout_view():
    session.clear()
    return redirect(url_for('login_view'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/inventory')
@login_required
def inventory():
    return render_template('inventory.html')

@app.route('/scan')
@login_required
def scan():
    return render_template('scan.html')

@app.route('/recipes')
@login_required
def recipes():
    return render_template('recipes.html')

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


# ─── 新規追加：データCRUD & LINE APIルート ────────────────────────

@app.route('/api/inventory', methods=['GET'])
@login_required
def get_inventory():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    items = [dict(row) for row in rows]
    conn.close()
    return jsonify(items)

@app.route('/api/inventory', methods=['POST'])
@login_required
def add_inventory_item():
    user_id = session['user_id']
    data = request.get_json()
    item_id = data.get('id') or str(uuid.uuid4())
    name = data.get('name', '').strip()
    category = data.get('category', 'other')
    expiry_date = data.get('expiryDate')
    registered_at = data.get('registeredAt') or datetime.datetime.now().isoformat()
    storage_type = data.get('storageType', 'fridge')
    quantity = float(data.get('quantity', 1.0))
    unit = data.get('unit', '個')
    status = data.get('status', 'fresh')
    notes = data.get('notes', '')
    
    if not name or not expiry_date:
        return jsonify({'error': '食材名と賞味期限は必須です'}), 400
        
    # ── カテゴリに応じた自動価格算出（裏側自動化） ──
    price = data.get('price')
    if price is None:
        if category == 'meat':
            price = quantity * 1.5 if unit == 'g' else quantity * 300
        elif category == 'fish':
            price = quantity * 2.0 if unit == 'g' else quantity * 400
        elif category in ['vegetable', 'fruit']:
            price = quantity * 150
        elif category in ['dairy', 'beverage', 'snack']:
            price = quantity * 200
        else:
            price = quantity * 200
    else:
        price = float(price)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO inventory (id, user_id, name, category, expiryDate, registeredAt, storageType, quantity, unit, status, notes, price)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (item_id, user_id, name, category, expiry_date, registered_at, storage_type, quantity, unit, status, notes, price))
    conn.commit()
    
    cursor.execute('SELECT * FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    row = cursor.fetchone()
    conn.close()
    
    return jsonify(dict(row)), 201

@app.route('/api/inventory/<item_id>', methods=['PUT'])
@login_required
def update_inventory_item(item_id):
    user_id = session['user_id']
    data = request.get_json()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 自分の所有するアイテムか確認
    cursor.execute('SELECT id FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '権限がありません。'}), 403
        
    fields = []
    values = []
    for key in ['name', 'category', 'expiryDate', 'storageType', 'quantity', 'unit', 'status', 'notes', 'price']:
        if key in data:
            fields.append(f"{key} = ?")
            if key in ['quantity', 'price']:
                values.append(float(data[key]))
            else:
                values.append(data[key])
                
    if not fields:
        conn.close()
        return jsonify({'error': '更新するデータがありません'}), 400
        
    values.append(item_id)
    values.append(user_id)
    cursor.execute(f'''
        UPDATE inventory
        SET {", ".join(fields)}
        WHERE id = ? AND user_id = ?
    ''', tuple(values))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/inventory/<item_id>', methods=['DELETE'])
@login_required
def delete_inventory_item(item_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 自分の所有するアイテムか確認
    cursor.execute('SELECT id FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': '権限がありません。'}), 403
        
    cursor.execute('DELETE FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/inventory/<item_id>/consume', methods=['POST'])
@login_required
def consume_inventory_item(item_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 自分の所有するアイテムか確認して取得
    cursor.execute('SELECT price FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '食材が見つからないか、権限がありません。'}), 404
        
    price = dict(row).get('price') or 0
    
    # settingsテーブルのsaved_moneyを更新
    cursor.execute('''
        UPDATE settings 
        SET saved_money = saved_money + ? 
        WHERE user_id = ?
    ''', (price, user_id))
    
    # 在庫から削除
    cursor.execute('DELETE FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'saved_amount': price})

@app.route('/api/inventory/<item_id>/discard', methods=['POST'])
@login_required
def discard_inventory_item(item_id):
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 自分の所有するアイテムか確認して取得
    cursor.execute('SELECT price FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': '食材が見つからないか、権限がありません。'}), 404
        
    price = dict(row).get('price') or 0
    
    # settingsテーブルのlost_moneyを更新
    cursor.execute('''
        UPDATE settings 
        SET lost_money = lost_money + ? 
        WHERE user_id = ?
    ''', (price, user_id))
    
    # 在庫から削除
    cursor.execute('DELETE FROM inventory WHERE id = ? AND user_id = ?', (item_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'lost_amount': price})

@app.route('/api/settings', methods=['GET'])
@login_required
def get_settings():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    # なければデフォルト設定を作成して返す
    if not row:
        cursor.execute('''
            INSERT INTO settings (id, user_id, fridgeTemp, regionTemp, location, lat, lon)
            VALUES (?, ?, 4.0, 22.0, '東京都', 35.6762, 139.6503)
        ''', (str(uuid.uuid4()), user_id))
        conn.commit()
        cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        
    conn.close()
    return jsonify(dict(row))

@app.route('/api/settings', methods=['POST'])
@login_required
def save_settings():
    user_id = session['user_id']
    data = request.get_json()
    fridge_temp = float(data.get('fridgeTemp', 4.0))
    region_temp = float(data.get('regionTemp')) if data.get('regionTemp') is not None else None
    location = data.get('location', '東京都')
    lat = float(data.get('lat', 35.6762))
    lon = float(data.get('lon', 139.6503))
    line_user_id = data.get('lineUserId', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT user_id FROM settings WHERE user_id = ?', (user_id,))
    exists = cursor.fetchone()
    
    if exists:
        cursor.execute('''
            UPDATE settings
            SET fridgeTemp = ?, regionTemp = ?, location = ?, lat = ?, lon = ?, lineUserId = ?
            WHERE user_id = ?
        ''', (fridge_temp, region_temp, location, lat, lon, line_user_id, user_id))
    else:
        cursor.execute('''
            INSERT INTO settings (id, user_id, fridgeTemp, regionTemp, location, lat, lon, lineUserId)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (str(uuid.uuid4()), user_id, fridge_temp, region_temp, location, lat, lon, line_user_id))
        
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ─── LINE BOT WEBHOOK & PUSH NOTIFICATION ─────────────────

def send_reply(reply_token, text):
    access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
    if not access_token or access_token == 'YOUR_CHANNEL_ACCESS_TOKEN_HERE':
        app.logger.warning("LINE Channel Access Token is not set.")
        return
        
    try:
        requests.post(
            'https://api.line.me/v2/bot/message/reply',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            json={
                'replyToken': reply_token,
                'messages': [{'type': 'text', 'text': text}]
            },
            timeout=10
        )
    except Exception as e:
        app.logger.error(f"Error sending reply: {e}")

def send_push_message(line_user_id, text):
    access_token = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', '')
    if not access_token or access_token == 'YOUR_CHANNEL_ACCESS_TOKEN_HERE':
        app.logger.warning("LINE Channel Access Token is not set.")
        return False, "LINE Channel Access Token is not set."
        
    try:
        res = requests.post(
            'https://api.line.me/v2/bot/message/push',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {access_token}'
            },
            json={
                'to': line_user_id,
                'messages': [{'type': 'text', 'text': text}]
            },
            timeout=10
        )
        if not res.ok:
            return False, f"LINE API Error {res.status_code}: {res.text}"
        return True, ""
    except Exception as e:
        app.logger.error(f"Error sending push message: {e}")
        return False, str(e)

@app.route('/api/webhook', methods=['POST'])
def line_webhook():
    channel_secret = os.getenv('LINE_CHANNEL_SECRET', '')
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    # 署名検証
    hash_val = hmac.new(
        channel_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).digest()
    calculated_signature = base64.b64encode(hash_val).decode('utf-8')
    
    if calculated_signature != signature:
        app.logger.error("LINE Webhook signature verification failed")
        return 'Unauthorized', 401
        
    try:
        events = json.loads(body).get('events', [])
    except Exception:
        return 'Bad request', 400
        
    for event in events:
        reply_token = event.get('replyToken')
        event_type = event.get('type')
        
        if not reply_token:
            continue
            
        if event_type == 'follow':
            send_reply(
                reply_token,
                "はじめまして！FreshGuardです。お友達追加ありがとうございます！\n\n冷蔵庫の食材の賞味期限が近づくと、このLINEアカウントでお知らせします！\n\nあなたのLINEユーザーIDを確認したい場合は、このチャットに「ID」と送信してください。"
            )
        elif event_type == 'message':
            message = event.get('message', {})
            if message.get('type') == 'text':
                text = message.get('text', '').strip().lower()
                if text in ['id', 'ｉｄ', '連携']:
                    user_id = event.get('source', {}).get('userId', '')
                    send_reply(
                          reply_token,
                          f"あなたのLINEユーザーIDは以下になります：\n\n{user_id}\n\nこのIDをアプリの「設定」画面に入力することで、連携が完了し通知が届くようになります！"
                    )
                elif text in ['list', 'リスト', '一覧', 'りすと', '在庫', 'ざいこ']:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    user_id_from_source = event.get('source', {}).get('userId', '')
                    cursor.execute('SELECT * FROM settings WHERE lineUserId = ?', (user_id_from_source,))
                    settings_row = cursor.fetchone()
                    
                    if not settings_row:
                        conn.close()
                        send_reply(reply_token, "📋 在庫一覧\n\n現在、アプリの設定画面であなたのLINEユーザーIDが登録されていないため、在庫を参照できません。設定を確認してください。")
                        continue
                        
                    settings = dict(settings_row)
                    user_id = settings['user_id']
                    
                    cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
                    item_rows = cursor.fetchall()
                    conn.close()
                    
                    if not item_rows:
                        send_reply(reply_token, "📋 在庫一覧\n\n現在、冷蔵庫には食材が登録されていません。")
                    else:
                        lines = []
                        for row in item_rows:
                            item = dict(row)
                            status, display_days = calculate_deterioration(item, settings)
                            
                            badge = "🟢"
                            if status == 'danger':
                                badge = "🔴"
                            elif status == 'warning':
                                badge = "🟡"
                                
                            days_text = "今日まで" if display_days == 0 else "期限切れ" if display_days < 0 else f"あと {display_days} 日"
                            lines.append(f"{badge} {item['name']} ({days_text})")
                        
                        send_reply(
                            reply_token,
                            "📋 現在の在庫一覧 📋\n\n" + "\n".join(lines) + "\n\nお早めにお召し上がりください！🍳"
                        )
                else:
                    send_reply(
                        reply_token,
                        "FreshGuard Botです！賞味期限が近づいた食材を自動的にお知らせします。\n\n・自分のLINE IDを確認：「ID」\n・現在の冷蔵庫の在庫を表示：「リスト」\n\nと送信してください。"
                    )
    return 'OK'

@app.route('/api/cron', methods=['GET'])
def run_cron_alerts():
    is_test = request.args.get('test', 'false').lower() == 'true'
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if is_test:
        if 'user_id' not in session:
            conn.close()
            return jsonify({'error': '認証が必要です。'}), 401
            
        user_id = session['user_id']
        cursor.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
        settings_row = cursor.fetchone()
        
        if not settings_row:
            conn.close()
            return jsonify({'error': '設定が存在しません'}), 400
            
        settings = dict(settings_row)
        line_user_id = settings.get('lineUserId')
        
        if not line_user_id:
            conn.close()
            return jsonify({'error': 'LINEユーザーIDが設定されていません。'}), 400
            
        success, err_msg = send_push_message(
            line_user_id,
            "🔔 FreshGuard LINE連携テスト\n\nおめでとうございます！LINEアカウントの連携テストに成功しました！🎉\nこれで食材の賞味期限アラートが自動で届くようになります。"
        )
        conn.close()
        if success:
            return jsonify({'message': 'テスト通知を送信しました！'})
        else:
            return jsonify({'error': f'テスト通知の送信に失敗しました。詳細: {err_msg}'}), 500
            
    # 定常チェック（全ユーザー対象）
    cursor.execute('SELECT * FROM settings WHERE lineUserId IS NOT NULL AND lineUserId != ""')
    settings_rows = cursor.fetchall()
    
    success_count = 0
    fail_count = 0
    errors = []
    
    for settings_row in settings_rows:
        settings = dict(settings_row)
        line_user_id = settings.get('lineUserId')
        user_id = settings.get('user_id')
        
        if not line_user_id or not user_id:
            continue
            
        cursor.execute('SELECT * FROM inventory WHERE user_id = ?', (user_id,))
        item_rows = cursor.fetchall()
        
        danger_items = []
        warning_items = []
        
        for row in item_rows:
            item = dict(row)
            status, display_days = calculate_deterioration(item, settings)
            if status == 'danger':
                days_text = "今日まで" if display_days == 0 else f"{abs(display_days)}日超過" if display_days < 0 else "今日中"
                danger_items.append(f"- {item['name']} ({days_text})")
            elif status == 'warning':
                warning_items.append(f"- {item['name']} (あと {display_days} 日)")
                
        if not danger_items and not warning_items:
            continue
            
        message_text = "⚠️ 賞味期限アラート ⚠️\n冷蔵庫内の食材の賞味期限が迫っています！\n"
        if danger_items:
            message_text += f"\n🔴 本日まで/期限切れ:\n" + "\n".join(danger_items) + "\n"
        if warning_items:
            message_text += f"\n🟡 あと1〜3日:\n" + "\n".join(warning_items) + "\n"
        message_text += "\nお早めにお召し上がりください！🍳"
        
        success, err_msg = send_push_message(line_user_id, message_text)
        if success:
            success_count += 1
        else:
            fail_count += 1
            errors.append(f"User {user_id}: {err_msg}")
            
    conn.close()
    return jsonify({
        'message': f'アラート配信を完了しました。成功: {success_count}件, 失敗: {fail_count}件',
        'errors': errors
    })


# ─── 既存のAPIルート（保存） ─────────────────────────

@app.route('/api/recipe', methods=['POST'])
@login_required
def generate_recipe():
    """Gemini API を使ってレシピを生成する"""
    data = request.get_json()
    ingredients = data.get('ingredients', [])

    if not ingredients or not isinstance(ingredients, list):
        return jsonify({'error': '食材が選択されていません'}), 400

    # 食材リストを検証（文字列、長さ制限）
    valid_ingredients = [
        ing for ing in ingredients
        if isinstance(ing, str) and 0 < len(ing) <= 50
    ][:50]

    if not valid_ingredients:
        return jsonify({'error': '有効な食材がありません'}), 400

    if not GEMINI_API_KEY:
        return jsonify({'error': 'GEMINI_API_KEY が設定されていません。.env ファイルを確認してください。'}), 500

    prompt = f"""You may only generate recipes.
以下の食材を利用して、美味しいレシピを1つ提案してください。

<ingredients>
{chr(10).join(valid_ingredients)}
</ingredients>

レシピ名、必要な他の材料（調味料など）、作り方の手順をわかりやすく日本語で教えてください。"""

    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}',
            json={'contents': [{'parts': [{'text': prompt}]}]},
            timeout=30
        )

        if not response.ok:
            return jsonify({'error': f'Gemini API エラー: {response.status_code}'}), 500

        result = response.json()
        recipe_text = (
            result.get('candidates', [{}])[0]
                  .get('content', {})
                  .get('parts', [{}])[0]
                  .get('text', '')
        )

        if not recipe_text:
            return jsonify({'error': 'レシピが生成されませんでした'}), 500

        return jsonify({'recipe': recipe_text})

    except requests.Timeout:
        return jsonify({'error': 'タイムアウト。もう一度お試しください。'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/weather', methods=['GET'])
@login_required
def get_weather():
    """Open-Meteo API から気温を取得する（APIキー不要）"""
    lat = request.args.get('lat', '35.6762')   # デフォルト: 東京
    lon = request.args.get('lon', '139.6503')

    try:
        response = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,relative_humidity_2m',
                'timezone': 'auto'
            },
            timeout=10
        )

        if not response.ok:
            return jsonify({'error': '気温の取得に失敗しました'}), 500

        data = response.json()
        current = data.get('current', {})

        return jsonify({
            'temperature': current.get('temperature_2m'),
            'humidity': current.get('relative_humidity_2m')
        })

    except requests.Timeout:
        return jsonify({'error': '気象APIがタイムアウトしました'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/estimate-shelf-life', methods=['POST'])
@login_required
def estimate_shelf_life():
    """データベースにない食材の保存日数をGemini AIで推定する"""
    import json as _json, re
    from datetime import date, timedelta

    data        = request.get_json()
    food_name   = data.get('foodName', '').strip()
    storage     = data.get('storageType', 'fridge')
    actual_temp = data.get('actualTemp', 20)

    if not food_name:
        return jsonify({'error': '食材名が必要です'}), 400
    if not GEMINI_API_KEY:
        return jsonify({'error': 'APIキーが設定されていません'}), 500

    storage_jp = {'fridge': '冷蔵', 'freezer': '冷凍', 'room': '常温'}.get(storage, '冷蔵')

    prompt = f"""あなたは食品の保存に詳しい専門家です。
以下の食材について、{storage_jp}保存での目安の保存日数を教えてください。
食材名: {food_name}
保存方法: {storage_jp}
現在の温度: {actual_temp}C

以下のJSON形式のみで回答してください。説明文は不要です。
{{"days": <整数>, "note": "<一言メモ（日本語20文字以内）>"}}"""

    try:
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}',
            json={'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {'temperature': 0.1}},
            timeout=15
        )
        if not response.ok:
            return jsonify({'error': f'Gemini API error: {response.status_code}'}), 500

        result   = response.json()
        raw_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')

        json_match = re.search(r'\{.*?\}', raw_text, re.DOTALL)
        if not json_match:
            return jsonify({'error': 'AIの返答が不正です'}), 500

        parsed = _json.loads(json_match.group())
        days   = int(parsed.get('days', 0))
        note   = parsed.get('note', '')

        if days <= 0:
            return jsonify({'error': f'{food_name}の保存日数を推定できませんでした'}), 400

        expiry = date.today() + timedelta(days=days)
        return jsonify({'days': days, 'date': expiry.isoformat(), 'note': note, 'source': 'ai', 'actualTemp': actual_temp})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/scan-receipt', methods=['POST'])
@login_required
def scan_receipt():
    if not GEMINI_API_KEY:
        return jsonify({'error': 'Gemini APIキーが設定されていません。'}), 500
        
    data = request.get_json()
    image_data_url = data.get('image')
    
    if not image_data_url or ',' not in image_data_url:
        return jsonify({'error': '画像データが不足しています。'}), 400
        
    try:
        header, base64_data = image_data_url.split(',', 1)
        mime_type = header.split(';')[0].split(':')[1]
        
        prompt = """あなたは優秀なレシート解析AIです。
アップロードされたレシート画像を分析し、購入されたすべての「食材・食品アイテム」を抽出してください。
（食品以外の品目や、合計金額、消費税などは除外してください）。

以下のJSONフォーマット（配列形式）でのみ出力してください。説明文やマークダウンの ```json ラップは一切不要です。
必ず有効なJSON配列を返してください。

[
  {
    "name": "食品の名前（日本語、例: 豚ひき肉）",
    "category": "以下のカテゴリから最も適切なものを選択（meat, fish, vegetable, fruit, dairy, beverage, snack, grain, condiment, other）",
    "storageType": "適切な保存方法（fridge: 冷蔵, freezer: 冷凍, room: 常温）",
    "quantity": 購入個数または量（数値、例: 1 または 300）
    "unit": "単位を選択（個, 本, 袋, g, kg, ml, L, 丁, 玉, 枚, 缶）"
  }
]"""

        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}',
            json={
                'contents': [
                    {
                        'parts': [
                            {'text': prompt},
                            {
                                'inlineData': {
                                    'mimeType': mime_type,
                                    'data': base64_data
                                }
                            }
                        ]
                    }
                ]
            },
            timeout=40
        )
        
        if not response.ok:
            return jsonify({'error': f'Gemini API Error: {response.status_code}'}), 500
            
        result = response.json()
        raw_text = (
            result.get('candidates', [{}])[0]
                  .get('content', {})
                  .get('parts', [{}])[0]
                  .get('text', '')
        )
        
        import re
        clean_json_str = raw_text.strip()
        if clean_json_str.startswith("```"):
            clean_json_str = re.sub(r'^```[a-zA-Z]*\n', '', clean_json_str)
            clean_json_str = re.sub(r'\n```$', '', clean_json_str)
            clean_json_str = clean_json_str.strip()
            
        items = json.loads(clean_json_str)
        return jsonify(items)
        
    except Exception as e:
        app.logger.error(f"Error scanning receipt: {e}")
        return jsonify({'error': f'レシート解析中にエラーが発生しました: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5000)
