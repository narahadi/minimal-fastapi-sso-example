# Minimal SSO Example with FastAPI

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
fastapi run main.py --reload --port 3002
```