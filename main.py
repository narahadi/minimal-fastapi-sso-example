from fastapi import FastAPI, Request
from starlette.config import Config

config = Config('.env')
app = FastAPI()

@app.get('/login/{provider}')
async def login_oauth():
    return

@app.get('/auth/{provider}/callback')
async def auth():
    return

@app.get('/dashboard')
async def dashboard():
    return

@app.get('/logout')
async def logout(request: Request):
    return