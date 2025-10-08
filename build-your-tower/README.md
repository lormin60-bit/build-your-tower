# Build Your Tower Server

Сервер для игры Build Your Tower в Telegram.

## API Endpoints

- `GET /` - информация о сервере
- `GET/POST /api/test` - тест API
- `POST /api/stats` - статистика пользователя
- `POST /api/payment` - пополнение баланса
- `POST /api/buy_floor` - покупка этажа
- `POST /api/referral` - реферальная система
- `GET /api/debug` - отладочная информация
- `GET /api/health` - health check

## Развертывание на Render

1. Создать репозиторий GitHub
2. Создать Web Service на Render
3. Настроить Build Command: `pip install -r requirements.txt`
4. Настроить Start Command: `python app.py`