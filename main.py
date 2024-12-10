from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import firebase_admin
from firebase_admin import credentials, firestore, auth
import yfinance as yf
from jose import JWTError, jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from pydantic import BaseModel

# ========================= Firebase 초기화 =========================
cred = credentials.Certificate(
    "key/finflow-7e697-firebase-adminsdk-e10q8-270beafc23.json"
)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ========================= FastAPI 초기화 및 CORS 설정 =========================
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 출처 허용
    allow_credentials=True,
    allow_methods=["*"],  # 모든 HTTP 메서드 허용
    allow_headers=["*"],  # 모든 헤더 허용
)

# ========================= JWT 설정 =========================
load_dotenv()
SECRET_KEY = os.environ.get("SECRET_KEY")  # 환경변수에서 키 가져오기
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# JWT 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    """
    JWT 액세스 토큰 생성 함수
    :param data: 토큰에 포함될 데이터
    :param expires_delta: 토큰 만료 시간
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# JWT 검증 함수
def verify_jwt(request: Request):
    """
    JWT 검증 함수
    :param request: FastAPI Request 객체
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token = auth_header.split(" ")[1]  # "Bearer " 뒤의 토큰 추출

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = {"uid": payload.get("sub"), "email": payload.get("email")}
        if not user["uid"]:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")


# ========================= 사용자 관리 =========================
@app.post("/register")
async def register_user(user: dict):
    """
    사용자 등록 API
    :param user: 사용자 UID와 이메일
    """
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


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    사용자 로그인 및 토큰 발급
    """
    try:
        user = auth.get_user_by_email(form_data.username)

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


# ========================= 주식 검색 =========================
@app.get("/searchStocks")
async def search_stocks(query: str, token: str = Depends(oauth2_scheme)):
    """
    주식 검색 API
    :param query: 검색할 주식의 티커
    """
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")

        # JWT에서 사용자 정보 추출
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            uid: str = payload.get("uid")
            if uid is None:
                raise HTTPException(status_code=401, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        # yfinance를 사용하여 주식 데이터 검색
        ticker = yf.Ticker(query)

        # 주식 정보 및 종가 가져오기
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


# ========================= 포트폴리오 관리 =========================
class AddStockRequest(BaseModel):
    symbol: str


@app.post("/portfolio")
async def add_to_portfolio(stock: AddStockRequest, user: dict = Depends(verify_jwt)):
    """
    포트폴리오에 주식 추가
    """
    try:
        user_ref = db.collection("users").document(user["uid"])
        user_ref.collection("portfolio").document(stock.symbol).set(
            {"symbol": stock.symbol}
        )
        return {"message": "Stock added to portfolio"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/portfolio")
async def get_portfolio(user: dict = Depends(verify_jwt)):
    """
    포트폴리오 불러오기
    """
    try:
        user_ref = db.collection("users").document(user["uid"])
        portfolio_ref = user_ref.collection("portfolio")
        portfolio_docs = portfolio_ref.stream()

        portfolio = [doc.to_dict() for doc in portfolio_docs]
        return {"portfolio": portfolio}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/portfolio/{symbol}")
async def delete_from_portfolio(symbol: str, user: dict = Depends(verify_jwt)):
    """
    포트폴리오에서 주식 삭제
    """
    try:
        user_ref = db.collection("users").document(user["uid"])
        portfolio_ref = user_ref.collection("portfolio").document(symbol)
        portfolio_ref.delete()
        return {"message": f"Stock {symbol} deleted from portfolio"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
