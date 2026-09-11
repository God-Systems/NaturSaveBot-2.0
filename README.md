# Natursavebot

Telegram-бот для личного сохранения сообщений, удалений, правок, медиа, задач и напоминаний.

## Быстрый запуск

1. Установите Python 3.12.
2. Создайте окружение и поставьте зависимости:

   ```bash
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Скопируйте настройки:

   ```bash
   cp .env.example .env
   ```

4. В `.env` заполните `BOT_TOKEN`, `OWNER_TELEGRAM_ID` и `ENCRYPTION_KEY`.
5. Запустите бота:

   ```bash
   python -m src.main
   ```

## Docker

```bash
cp .env.example .env
docker compose up -d --build
```

## Без ИИ

Бот работает без ИИ по умолчанию. Оставьте `LLM_PROVIDER=none` и не указывайте ключи OpenAI, Gemini или Anthropic.

Чтобы включить ИИ-функции, укажите провайдера и его ключ в `.env`:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=...
```

## Основные команды бота

- `/health` — состояние базы, папки медиа и подключений.
- `/settings` — настройки сохранения, автоответов, дайджеста и ИИ.
- `/search` — поиск по сохранённым сообщениям.
- `/deleted`, `/edits`, `/media` — сохранённые удаления, правки и медиа.
- `/remind`, `/todos`, `/digest` — напоминания, задачи и дайджест.

## Команды Userbot

- `.help` — список команд.
- `.status` — состояние Userbot.
- `.mute` / `.unmute` — скрывать новые сообщения в текущем чате.
- `.info` ответом на сообщение — информация о пользователе.
- `.type текст` — отправить текст после короткой имитации набора.
- `.repeat 3 текст` и `.spam_stop` — ограниченный повтор сообщений.

## Данные

- База: `data/app.db`.
- Медиа: `data/media`.
- Логи: `data/logs`.
- Резервные копии базы: `data/backups`.

Не передавайте файл `.env`, базу, медиа, логи или резервные копии третьим лицам.
