from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import secrets
import os
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Настройка пути к БД
def get_db_path():
    # На Render пробуем разные пути
    if 'RENDER' in os.environ:
        paths_to_try = [
            '/opt/render/project/src/bot_database.db',
            '/var/lib/render/bot_database.db',
            '/tmp/bot_database.db'
        ]
        for path in paths_to_try:
            try:
                # Проверяем возможность записи
                test_file = open(path, 'a')
                test_file.close()
                logger.info(f"✅ Используем путь к БД: {path}")
                return path
            except Exception as e:
                logger.warning(f"❌ Путь {path} недоступен: {e}")
                continue
        # Fallback
        return '/tmp/bot_database.db'
    else:
        # Локально
        return 'bot_database.db'

DB_PATH = get_db_path()
logger.info(f"🚀 Итоговый путь к БД: {DB_PATH}")

def init_db():
    """Инициализация базы данных"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    balance INTEGER DEFAULT 0,
                    referrals INTEGER DEFAULT 0,
                    referral_code TEXT UNIQUE,
                    floors INTEGER DEFAULT 1,
                    total_referral_income INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица платежей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    method TEXT,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица рефералов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS referrals (
                    referral_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER,
                    referred_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            conn.close()
            logger.info("✅ База данных успешно инициализирована")
            return True
            
        except Exception as e:
            logger.error(f"❌ Попытка {attempt + 1} не удалась: {e}")
            if attempt == max_retries - 1:
                logger.error("❌ Не удалось инициализировать БД после всех попыток")
                return False
            continue

def get_db_connection():
    """Получить соединение с БД с обработкой ошибок"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        return None

def get_or_create_user(user_id, username=None):
    """Получить или создать пользователя"""
    try:
        # Валидация user_id
        if not user_id:
            return None
            
        user_id = int(user_id)
        
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        # Пробуем найти пользователя
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        # Если нет - создаем
        if not user:
            referral_code = secrets.token_hex(8)
            cursor.execute(
                'INSERT INTO users (user_id, username, referral_code) VALUES (?, ?, ?)',
                (user_id, username, referral_code)
            )
            conn.commit()
            logger.info(f"✅ Создан новый пользователь: {user_id}")
        
        # Получаем данные пользователя
        cursor.execute('''
            SELECT user_id, username, balance, referrals, referral_code, floors, total_referral_income 
            FROM users WHERE user_id = ?
        ''', (user_id,))
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
                'total_referral_income': user[6] or 0,
                'referral_link': f"https://t.me/BuildYourTowerBot?start=ref{user[4]}"
            }
        return None
        
    except Exception as e:
        logger.error(f"❌ Ошибка в get_or_create_user: {e}")
        return None

# ==================== API ENDPOINTS ====================

@app.route('/')
def home():
    """Главная страница"""
    return jsonify({
        "status": "success", 
        "message": "🚀 Сервер Build Your Tower работает!",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            {"path": "/api/test", "methods": ["GET", "POST"], "description": "Тест API"},
            {"path": "/api/stats", "methods": ["POST"], "description": "Получить статистику"},
            {"path": "/api/payment", "methods": ["POST"], "description": "Пополнение баланса"},
            {"path": "/api/buy_floor", "methods": ["POST"], "description": "Купить этаж"},
            {"path": "/api/referral", "methods": ["POST"], "description": "Реферальная система"},
            {"path": "/api/debug", "methods": ["GET"], "description": "Отладочная информация"}
        ]
    })

@app.route('/api/test', methods=['GET', 'POST'])
def test_api():
    """Тестовый endpoint"""
    return jsonify({
        "status": "success", 
        "message": "✅ API работает отлично!",
        "timestamp": datetime.now().isoformat(),
        "database_path": DB_PATH,
        "environment": "Render" if 'RENDER' in os.environ else "Local"
    })

@app.route('/api/stats', methods=['POST'])
def get_stats():
    """Получить статистику пользователя"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'})
            
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({'status': 'error', 'message': 'Не указан user_id'})
        
        logger.info(f"📊 Запрос статистики для user_id: {user_id}")
        
        user_data = get_or_create_user(user_id)
        
        if not user_data:
            return jsonify({'status': 'error', 'message': 'Ошибка получения данных пользователя'})
        
        return jsonify({
            'status': 'success', 
            'data': user_data
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /api/stats: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/payment', methods=['POST'])
def handle_payment():
    """Пополнение баланса"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'})
            
        user_id = data.get('user_id')
        amount = data.get('amount')
        method = data.get('method', 'unknown')
        
        if not user_id or not amount:
            return jsonify({'status': 'error', 'message': 'Не указан user_id или amount'})
        
        # Валидация amount
        try:
            amount = int(amount)
            if amount <= 0:
                return jsonify({'status': 'error', 'message': 'Сумма должна быть положительной'})
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Неверный формат суммы'})
        
        logger.info(f"💰 Пополнение баланса: user_id={user_id}, amount={amount}, method={method}")
        
        # Получаем/создаем пользователя
        user_data = get_or_create_user(user_id)
        if not user_data:
            return jsonify({'status': 'error', 'message': 'Ошибка создания пользователя'})
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Ошибка подключения к БД'})
            
        cursor = conn.cursor()
        
        # Пополняем баланс
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
        
        # Записываем платеж
        cursor.execute('INSERT INTO payments (user_id, amount, method) VALUES (?, ?, ?)', 
                      (user_id, amount, method))
        
        conn.commit()
        
        # Получаем новый баланс
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        new_balance = result[0] if result else 0
        
        conn.close()
        
        logger.info(f"✅ Баланс пополнен: user_id={user_id}, новый баланс={new_balance}")
        
        return jsonify({
            'status': 'success', 
            'new_balance': new_balance,
            'message': f'Баланс пополнен на {amount} руб.!'
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /api/payment: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/buy_floor', methods=['POST'])
def buy_floor():
    """Покупка этажа"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'})
            
        user_id = data.get('user_id')
        floor_number = data.get('floor_number')
        
        if not user_id or not floor_number:
            return jsonify({'status': 'error', 'message': 'Не указан user_id или floor_number'})
        
        logger.info(f"🏗️ Покупка этажа: user_id={user_id}, floor_number={floor_number}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Ошибка подключения к БД'})
            
        cursor = conn.cursor()
        
        cursor.execute('SELECT balance, floors FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Пользователь не найден'})
        
        current_balance = user[0] or 0
        current_floors = user[1] or 1
        floor_price = 500
        
        if current_balance < floor_price:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Недостаточно средств'})
        
        if floor_number != current_floors + 1:
            conn.close()
            return jsonify({'status': 'error', 'message': 'Неверный номер этажа'})
        
        # Списание денег и увеличение этажей
        cursor.execute('UPDATE users SET balance = balance - ?, floors = floors + 1 WHERE user_id = ?', 
                      (floor_price, user_id))
        conn.commit()
        
        # Получаем обновленные данные
        cursor.execute('SELECT balance, floors FROM users WHERE user_id = ?', (user_id,))
        updated_user = cursor.fetchone()
        
        conn.close()
        
        logger.info(f"✅ Этаж куплен: user_id={user_id}, новые этажи={updated_user[1]}, новый баланс={updated_user[0]}")
        
        return jsonify({
            'status': 'success',
            'new_balance': updated_user[0],
            'new_floors': updated_user[1],
            'message': f'Этаж {floor_number} построен!'
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /api/buy_floor: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/referral', methods=['POST'])
def handle_referral():
    """Реферальная система"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No JSON data provided'})
            
        referrer_code = data.get('referrer_code')
        referred_id = data.get('referred_id')
        
        if not referrer_code or not referred_id:
            return jsonify({'status': 'error', 'message': 'Не указаны данные реферала'})
        
        logger.info(f"👥 Реферал: referrer_code={referrer_code}, referred_id={referred_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Ошибка подключения к БД'})
            
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
                
                # Увеличиваем счетчик рефералов
                cursor.execute('UPDATE users SET referrals = referrals + 1 WHERE user_id = ?', (referrer_id,))
                
                # Начисляем бонусы
                cursor.execute('UPDATE users SET balance = balance + 100, total_referral_income = total_referral_income + 100 WHERE user_id = ?', (referrer_id,))
                cursor.execute('UPDATE users SET balance = balance + 50 WHERE user_id = ?', (referred_id,))
                
                conn.commit()
                logger.info(f"✅ Реферал зарегистрирован: referrer_id={referrer_id}, referred_id={referred_id}")
                
        conn.close()
        return jsonify({'status': 'success', 'message': 'Реферал зарегистрирован'})
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /api/referral: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/debug', methods=['GET'])
def debug_info():
    """Отладочная информация"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'status': 'error', 'message': 'Ошибка подключения к БД'})
            
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM payments')
        payment_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM referrals')
        referral_count = cursor.fetchone()[0]
        
        # Информация о БД
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'status': 'success',
            'debug_info': {
                'total_users': user_count,
                'total_payments': payment_count, 
                'total_referrals': referral_count,
                'tables': [table[0] for table in tables],
                'database_path': DB_PATH,
                'environment': 'Render' if 'RENDER' in os.environ else 'Local',
                'timestamp': datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"❌ Ошибка в /api/debug: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check для мониторинга"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            db_status = "healthy"
        else:
            db_status = "unhealthy"
            
        return jsonify({
            "status": "success",
            "health": {
                "server": "healthy",
                "database": db_status,
                "timestamp": datetime.now().isoformat()
            }
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "health": {
                "server": "healthy", 
                "database": "unhealthy",
                "error": str(e)
            }
        })

# Инициализация при запуске
if __name__ == '__main__':
    logger.info("🚀 Запуск сервера Build Your Tower...")
    logger.info(f"📊 Путь к БД: {DB_PATH}")
    
    if init_db():
        logger.info("✅ Сервер готов к работе")
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        logger.error("❌ Не удалось запустить сервер из-за ошибок БД")