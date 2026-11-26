# Task Manager bot

Separate FastAPI + aiogram project for `@taskmanager787_bot`. It does not use a
Telegram Mini App. The Telegram bot supports `/add` and `/tasks`; inline buttons
complete or delete tasks. Netlify hosts a small web page that adds, completes,
and deletes the same owner's tasks through the FastAPI backend on Render.

## Local run

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env`; enter the bot token and a private
   `WEB_ACCESS_KEY`.
3. Run `uvicorn app.main:app --reload`.
4. Open `http://127.0.0.1:8000/health`.

## Deploy

1. Publish this folder as a **private GitHub repository**; `.env` is ignored.
2. Create a Render Web Service from that repository using `render.yaml`.
3. Set `BOT_TOKEN`, your Telegram numeric ID as `WEB_USER_ID`, and a long
   random `WEB_ACCESS_KEY` in Render environment.
4. Create a Netlify site from the same GitHub repository. Build settings are
   in `netlify.toml`.
5. Set Netlify `BACKEND_URL` to the Render HTTPS service URL and deploy.
6. Set Render `CORS_ORIGINS` to the exact Netlify site origin and redeploy.
7. Enter the Render `WEB_ACCESS_KEY` on the Netlify site to use the task list.

SQLite is used by default. Render's free service filesystem is not persistent
across all redeploys, so use persistent storage or a managed database for
important task data.
