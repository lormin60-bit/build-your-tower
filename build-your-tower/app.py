# app.py
import sqlite3
import secrets
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Путь к базе данных для Render
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            floors INTEGER DEFAULT 1,
            total_referral_income INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            status TEXT DEFAULT 'completed'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()

def generate_referral_code():
    return secrets.token_hex(4)

def get_or_create_user(user_id, username=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        referral_code = generate_referral_code()
        cursor.execute(
            'INSERT INTO users (user_id, username, balance, referrals, referral_code, floors) VALUES (?, ?, 0, 0, ?, 1)',
            (user_id, username, referral_code)
        )
        conn.commit()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'user_id': user[0],
            'username': user[1],
            'balance': user[2] or 0,
            'referrals': user[3] or 0,
            'referral_code': user[4],
            'floors': user[5] or 1,
            'total_referral_income': user[6] or 0
        }
    return None

@app.route('/')
def home():
    return "🚀 Сервер работает! API доступен по /api/"

@app.route('/api/test', methods=['GET'])
def test_api():
    return jsonify({"status": "success", "message": "API работает отлично!"})

@app.route('/api/payment', methods=['POST'])
def handle_payment():
    try:
        data = request.json
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method', 'unknown')
        
        if not user_id or not amount:
            return jsonify({'status': 'error', 'message': 'Не указан user_id или amount'})
        
        user = get_or_create_user(user_id)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Пополняем баланс
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        
        # Записываем платеж
        cursor.execute('INSERT INTO payments (user_id, amount, status) VALUES (?, ?, ?)', 
                      (user_id, amount, 'completed'))
        
        conn.commit()
        
        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        new_balance = result[0] if result else 0
        
        conn.close()
        
        return jsonify({
            'status': 'success', 
            'new_balance': new_balance,
            'message': f'Баланс пополнен на {amount} руб.!'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/stats', methods=['POST'])
def get_stats():
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Не указан user_id'})
        
        user = get_or_create_user(user_id)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance, referrals, floors, total_referral_income, referral_code FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            stats = {
                'balance': result[0] or 0,
                'referrals': result[1] or 0,
                'floors': result[2] or 1,
                'total_referral_income': result[3] or 0,
                'referral_code': result[4],
                'referral_link': f"https://t.me/BuildYourTowerBot?start=ref{result[4]}"
            }
        else:
            stats = {
                'balance': 0,
                'referrals': 0,
                'floors': 1,
                'total_referral_income': 0,
                'referral_link': 'Ошибка загрузки'
            }
        
        conn.close()
        return jsonify({'status': 'success', 'data': stats})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/buy_floor', methods=['POST'])
def buy_floor():
    try:
        data = request.json
        user_id = data.get('user_id')
        floor_number = data.get('floor_number')
        
        if not user_id or not floor_number:
            return jsonify({'status': 'error', 'message': 'Не указан user_id или floor_number'})
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance, floors FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        current_balance = user[0] or 0
        current_floors = user[1] or 1
        floor_price = 500
        
        if current_balance < floor_price:
            return jsonify({'status': 'error', 'message': 'Недостаточно средств'})
        
        if floor_number != current_floors + 1:
            return jsonify({'status': 'error', 'message': 'Неверный номер этажа'})
        
        # Списание денег и увеличение этажей
        cursor.execute('UPDATE users SET balance = balance - ?, floors = floors + 1 WHERE user_id = ?', 
                      (floor_price, user_id))
        conn.commit()
        
        # Получаем обновленные данные
        cursor.execute('SELECT balance, floors FROM users WHERE user_id = ?', (user_id,))
        updated_user = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'new_balance': updated_user[0],
            'new_floors': updated_user[1],
            'message': f'Этаж {floor_number} построен!'
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/referral', methods=['POST'])
def handle_referral():
    try:
        data = request.json
        referrer_code = data.get('referrer_code')
        referred_id = data.get('referred_id')
        
        if not referrer_code or not referred_id:
            return jsonify({'status': 'error', 'message': 'Не указаны данные реферала'})
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Находим того кто пригласил по коду
        cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referrer_code,))
        referrer = cursor.fetchone()
        
        if referrer:
            referrer_id = referrer[0]
            
            # Проверяем не был ли уже приглашен
            cursor.execute('SELECT * FROM referrals WHERE referred_id = ?', (referred_id,))
            existing = cursor.fetchone()
            
            if not existing and referrer_id != referred_id:
                cursor.execute('INSERT INTO referrals (referrer_id, referred_id) VALUES (?, ?)', 
                              (referrer_id, referred_id))
                cursor.execute('UPDATE users SET referrals = referrals + 1 WHERE user_id = ?', (referrer_id,))
                conn.commit()
                
        conn.close()
        return jsonify({'status': 'success', 'message': 'Реферал зарегистрирован'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Инициализируем базу при запуске
init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)