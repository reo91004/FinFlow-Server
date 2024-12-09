from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import firebase_admin
from firebase_admin import credentials, firestore, auth
import yfinance as yf
from jose import JWTError, jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os

# Firebase 초기화
cred = credentials.Certificate(
    "key/finflow-7e697-firebase-adminsdk-e10q8-270beafc23.json"
)
firebase_admin.initialize_app(cred)
db = firestore.client()

# FastAPI 초기화
app = FastAPI()

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# JWT 설정
load_dotenv()
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# JWT 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# 사용자 등록
@app.post("/register")
async def register_user(user: dict):
    try:
        uid = user.get("uid")
        email = user.get("email")

        if not uid or not email:
            raise HTTPException(status_code=400, detail="Invalid data")

        # Firestore에 사용자 정보 저장
        db.collection("users").document(uid).set(
            {
                "email": email,
                "created_at": firestore.SERVER_TIMESTAMP,
            }
        )
        return {"message": "User registered successfully"}
    except Exception as e:
        print(f"Error: {e}")  # 서버에서 에러 로그 확인
        raise HTTPException(status_code=500, detail=str(e))


# 사용자 로그인 및 토큰 발급
@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        # Firebase Authentication에서 사용자 확인
        user = auth.get_user_by_email(form_data.username)

        # 비밀번호 검증 (Firebase Authentication에서 직접 검증하도록 구현 필요)
        # 현재는 비밀번호를 검증하지 않고 이메일 확인만 처리

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email, "uid": user.uid},
            expires_delta=access_token_expires,
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except firebase_admin.exceptions.FirebaseError as e:
        print(f"Firebase Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/searchStocks")
async def search_stocks(query: str, token: str = Depends(oauth2_scheme)):
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")

        # JWT에서 사용자 정보 추출
        # try:
        #     payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        #     uid: str = payload.get("uid")
        #     if uid is None:
        #         raise HTTPException(status_code=401, detail="Invalid token")
        # except JWTError:
        #     raise HTTPException(status_code=401, detail="Invalid token")

        # yfinance를 사용하여 주식 데이터를 검색
        ticker = yf.Ticker(query)

        # 종가 가져오기
        info = ticker.info
        history = ticker.history(period="1d")
        current_price = history["Close"].iloc[-1] if not history.empty else None

        if not info and not current_price:
            raise HTTPException(status_code=404, detail="Stock not found")

        return {
            "name": info.get("longName", "Unknown"),
            "symbol": info.get("symbol", "Unknown"),
            "price": (
                current_price
                if current_price is not None
                else info.get("regularMarketPrice", 0)
            ),
            "currency": info.get("currency", "Unknown"),
        }
    except Exception as e:
        print(f"Error: {e}")  # 서버에서 에러 로그 확인
        raise HTTPException(status_code=500, detail=str(e))
