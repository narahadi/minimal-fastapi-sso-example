from fastapi import FastAPI, Request
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError
from starlette.middleware.sessions import SessionMiddleware

config = Config('.env')
app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=config('SECRET_KEY'))

oauth = OAuth(config)
oauth.register(
    name='google',
    client_id=config('GOOGLE_CLIENT_ID'),
    client_secret=config('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)
oauth.register(
    name='microsoft',
    client_id=config('MICROSOFT_CLIENT_ID'),
    client_secret=config('MICROSOFT_CLIENT_SECRET'),
    server_metadata_url=f"https://login.microsoftonline.com/{config('MICROSOFT_TENANT_ID')}/v2.0/.well-known/openid-configuration",
    client_kwargs={'scope': 'openid email profile'}
)

@app.get('/login/{provider}')
async def login_oauth(provider: str, request: Request):
    redirect_uri = request.url_for('auth', provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)

@app.get('/auth/{provider}/callback')
async def auth(provider: str, request: Request):
    try:
        token = await oauth.create_client(provider).authorize_access_token(request)
    except OAuthError as error:
        return {"error": str(error)}

@app.get('/dashboard')
async def dashboard():
    return {'message':'dashboard page'}

@app.get('/logout')
async def logout():
    return