from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth, OAuthError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, ForeignKey, select
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from datetime import datetime, timedelta
import jwt
import os
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ENV = os.getenv('ENV', 'development')
config = Config('../.env')
SECRET_KEY = config('SECRET_KEY', cast=str)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
# FRONTEND_URL = config('FRONTEND_URL')
FRONTEND_URL = '/' # set dummy index page

DATABASE_URL = config('DATABASE_URL', cast=str)
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    provider = Column(String)
    sso_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Token(Base):
    __tablename__ = "tokens"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    access_token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

ALLOWED_PROVIDERS = ['google', 'microsoft']

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, expire

async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> Optional[User]:
    token = request.cookies.get("access_token")
    if not token:
        logger.info("No token provided in cookies")
        return None
    
    if token.startswith("Bearer "):
        token = token[7:]  # Remove 'Bearer ' prefix

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            logger.warning("Token payload does not contain user ID")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
        stmt = select(User).where(User.id == uuid.UUID(user_id))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            logger.warning(f"User not found for ID: {user_id}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        
        return user
    except Exception as e:
        logger.warning("Token has expired")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get('/auth/status')
async def auth_status(current_user: Optional[User] = Depends(get_current_user)):
    if current_user:
        return JSONResponse(content={"isAuthenticated": True, "user": {"email": current_user.email, "name": current_user.name, "sso_metadata": current_user.sso_metadata}})
    return JSONResponse(content={"isAuthenticated": False})

@app.get('/login/{provider}')
async def login_oauth(provider: str, request: Request, current_user: Optional[User] = Depends(get_current_user)):
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider")
    
    if current_user:
        return RedirectResponse(url=FRONTEND_URL)
    
    redirect_uri = request.url_for('auth', provider=provider)
    return await oauth.create_client(provider).authorize_redirect(request, redirect_uri)

@app.get('/auth/{provider}/callback')
async def auth(provider: str, request: Request, db: AsyncSession = Depends(get_db)):
    if provider not in ALLOWED_PROVIDERS:
        raise HTTPException(status_code=400, detail="Invalid provider")

    try:
        token = await oauth.create_client(provider).authorize_access_token(request)
    except OAuthError as error:
        raise HTTPException(status_code=400, detail=str(error))
    
    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(status_code=400, detail="Invalid user info received")

    stmt = select(User).where(User.email == user_info['email'])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        user = User(
            email=user_info['email'],
            name=user_info.get('name', user_info['email']),
            provider=provider,
            sso_metadata=user_info
        )
        db.add(user)
    else:
        user.name = user_info.get('name', user.name)
        user.sso_metadata = user_info
    
    await db.commit()
    await db.refresh(user)
    
    access_token, expire = create_access_token(data={"sub": str(user.id)})
    token_record = Token(user_id=user.id, access_token=access_token, expires_at=expire)
    db.add(token_record)
    await db.commit()
    
    response = RedirectResponse(url='/dashboard')
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=ENV == 'production',
        samesite='lax' if ENV == 'development' else 'strict',
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return response

@app.get('/logout')
async def logout(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url=FRONTEND_URL)
    if token.startswith("Bearer "):
        token = token[7:]
    stmt = select(Token).where(Token.access_token == token)
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()
    if token_record:
        await db.delete(token_record)
        await db.commit()
    response = JSONResponse(content={"message": "Logged out successfully"})
    # response = RedirectResponse(url=FRONTEND_URL)
    response.delete_cookie("access_token")
    return response

@app.get('/metadata-debug')
async def metadata_debug(current_user: User = Depends(get_current_user)):
    if not current_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return {
        'message': f"Logged in as {current_user.name}",
        'email': current_user.email,
        'provider': current_user.provider,
        'sso_metadata': current_user.sso_metadata
    }

@app.get('/')
async def index(current_user: User = Depends(get_current_user)):
    if not current_user:
        return 'this is landing, you are not logged in, you are not allowed to access dashboard'
    else:
        message = f"this is landing, you are logged in as {current_user.name} you can now access dashboard"
        return message
    
@app.get('/dashboard')
async def dashboard(current_user: User = Depends(get_current_user)):
    if not current_user:
        return RedirectResponse(url=FRONTEND_URL)
    else:
        message = f"this is dashboard, you are logged in as {current_user.name} using email: {current_user.email}"
        return message