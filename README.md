# Minimal SSO Example with FastAPI and PostgreSQL

This project demonstrates a minimal Single Sign-On (SSO) implementation using FastAPI, PostgreSQL, and OAuth2 with Google and Microsoft.

## Setup

1. Clone the repository
2. Create a virtual environment and activate it
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in the required values
5. Generate a secret key and add it to `.env`:
   ```python
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

Start the FastAPI server:
```bash
cd src
fastapi run main.py --reload --port 3002
```

## Database Setup

1. Create a directory for PostgreSQL data:
   ```bash
   mkdir pgdata
   ```

2. Start the PostgreSQL database:
   ```bash
   cd db
   docker compose up -d
   ```

3. Run the initial database setup script:
   ```bash
   docker exec -i sso_example_db psql -U postgres < init_db.sql
   ```

## Verifying Database Setup

To check if the tables have been created correctly, run:

```bash
docker exec -i sso_example_db psql -U postgres -c "\dt"
```

This command will list all tables in the database. You should see `users` and `tokens` table listed.

## Cleaning Up

To clean up all created resources, run:

```bash
cd db
chmod +x cleanup.sh
./cleanup.sh
```

This script will stop and remove the Docker containers, and delete the pgdata directory.
