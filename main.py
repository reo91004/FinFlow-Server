from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import firebase_admin
from firebase_admin import credentials, firestore, auth
import yfinance as yf
from jose import JWTError, jwt, ExpiredSignatureError
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from typing import Optional
from pydantic import BaseModel
import requests

# Firebase 초기화
cred = credentials.Certificate(
    "key/finflow-7e697-firebase-adminsdk-e10q8-270beafc23.json"
)
firebase_admin.initialize_app(cred)
db = firestore.client()

# FastAPI 초기화 및 CORS 설정
app = FastAPI()
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
    expire = datetime.now() + (
        expires_delta if expires_delta else timedelta(minutes=15)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


# JWT 검증 함수
def verify_jwt(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user = {
            "uid": payload.get("uid"),
            "email": payload.get("sub"),
        }
        if not user["uid"]:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {e}")


@app.post("/register")
async def register_user(user: dict):
    try:
        uid = user.get("uid")
        email = user.get("email")
        if not uid or not email:
            raise HTTPException(status_code=400, detail="Invalid data")
        # 추가 로직 필요 시 여기에
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/token")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
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


import requests


def get_logo_url(symbol: str) -> str:
    """
    주식 티커로 기업 로고 URL을 가져옵니다.
    :param symbol: 주식 티커
    :return: 로고 이미지 URL
    """
    try:
        # 주식 티커와 기업 도메인 매핑
        company_domains = {
            "QQQ": "invesco.com",
            "AAPL": "apple.com",
            "GOOGL": "google.com",
            "MSFT": "microsoft.com",
            "AMZN": "amazon.com",
            "TSLA": "tesla.com",
            "FB": "facebook.com",
            "NVDA": "nvidia.com",
            "NFLX": "netflix.com",
            "BABA": "alibaba.com",
            "INTC": "intel.com",
            "CSCO": "cisco.com",
            "ORCL": "oracle.com",
            "ADBE": "adobe.com",
            "PYPL": "paypal.com",
            "CMCSA": "comcast.com",
            "PEP": "pepsico.com",
            "KO": "coca-cola.com",
            "NKE": "nike.com",
            "PFE": "pfizer.com",
        }

        # 티커를 대문자로 변환하여 도메인 조회
        domain = company_domains.get(symbol.upper())
        if not domain:
            print(f"Domain for {symbol} not found.")
            return ""

        # Clearbit Logo API를 사용하여 로고 URL 생성
        logo_url = f"https://logo.clearbit.com/{domain}"
        response = requests.get(logo_url)
        if response.status_code == 200:
            return logo_url
        else:
            print(f"Logo not found for domain {domain}.")
    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}")
    except Exception as e:
        print(f"Error fetching logo: {e}")

    return ""


@app.get("/searchStocks")
async def search_stocks(query: str, token: str = Depends(oauth2_scheme)):
    if not query:
        raise HTTPException(status_code=400, detail="Query parameter is required")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid: Optional[str] = payload.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        ticker = yf.Ticker(query)
        info = ticker.info
        history = ticker.history(period="5d")
        current_price = info.get("currentPrice") or (
            history["Close"].iloc[-1] if not history.empty else None
        )

        if not info and history.empty:
            raise HTTPException(status_code=404, detail="Stock data is not available")

        previous_close = history["Close"].iloc[-2]
        change_percent = ((current_price - previous_close) / previous_close) * 100

        logo_url = (
            get_logo_url(info.get("symbol", query)) or "https://via.placeholder.com/50"
        )

        stock_data = {
            "name": info.get("longName", "Unknown"),
            "symbol": info.get("symbol", query),
            "currentPrice": round(current_price, 2) if current_price else 0,
            "currency": info.get("currency", "Unknown"),
            "high52Week": info.get("fiftyTwoWeekHigh", "N/A"),
            "low52Week": info.get("fiftyTwoWeekLow", "N/A"),
            "changePercent": round(change_percent, 2) if change_percent else 0.0,
            "logo": logo_url,
        }
        return stock_data

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error retrieving stock data: {str(e)}"
        )


class AddStockRequest(BaseModel):
    symbol: str
    name: str
    currentPrice: float
    currency: str
    quantity: int


@app.post("/portfolio")
async def add_stock_to_portfolio(
    stock: AddStockRequest, user: dict = Depends(verify_jwt)
):
    try:
        # 사용자 이메일 및 참조 설정
        user_email = user["email"]
        user_ref = db.collection("users").document(user_email)
        user_ref.set({"uid": user["uid"], "email": user_email}, merge=True)

        # 포트폴리오 참조 설정
        portfolio_ref = user_ref.collection("portfolio").document(stock.symbol)
        doc_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # 구매 데이터 생성 (유저 이메일 추가)
        purchase_data = {
            "purchaseDate": datetime.now(),
            "quantity": stock.quantity,
            "price": stock.currentPrice,
            "currency": stock.currency,
            "name": stock.name,
            "symbol": stock.symbol,
            "email": user_email,  # 필터링을 위한 이메일 추가
        }

        # 서브컬렉션에 데이터 저장
        purchase_ref = portfolio_ref.collection("purchases").document(doc_id)
        purchase_ref.set(purchase_data)

        return {"message": "Purchase recorded", "purchase": purchase_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_portfolio_calculation(user_email: str):
    # 이 씨발 파이어베이스 개쓰레기
    purchases_query = db.collection_group("purchases")
    purchases_docs = list(purchases_query.stream())

    # purchases 데이터가 비어 있을 경우 처리
    if not purchases_docs:
        print(f"No purchases found for user {user_email}.")
        return []

    # 데이터를 처리하여 포트폴리오 생성
    portfolio_data = {}
    for doc in purchases_docs:
        data = doc.to_dict()
        symbol = data.get("symbol")
        quantity = data.get("quantity", 0)
        price = data.get("price", 0.0)

        # 포트폴리오에 심볼별로 데이터 누적
        if symbol not in portfolio_data:
            portfolio_data[symbol] = {
                "total_quantity": 0,
                "total_cost": 0.0,
            }

        portfolio_data[symbol]["total_quantity"] += quantity
        portfolio_data[symbol]["total_cost"] += quantity * price

    # 결과를 저장할 리스트
    portfolio = []

    # 심볼별로 계산하여 결과 생성
    for symbol, data in portfolio_data.items():
        total_quantity = data["total_quantity"]
        total_cost = data["total_cost"]

        # 총 수량이 0인 경우 건너뛰기
        if total_quantity == 0:
            continue

        # 평균 구매 가격 계산
        buy_price = total_cost / total_quantity

        # yfinance로 현재 데이터 가져오기
        ticker = yf.Ticker(symbol)
        info = ticker.info

        current_price = info.get("regularMarketPrice", buy_price)
        dividend = info.get("dividendRate", 0.0)
        dividend_yield = (
            (info.get("dividendYield", 0.0) * 100) if info.get("dividendYield") else 0.0
        )
        daily_change = info.get("regularMarketChange", 0.0)

        total_profit = (current_price - buy_price) * total_quantity
        daily_profit = daily_change * total_quantity

        # 로고 URL 및 이름 설정 (get_logo_url 구현 필요)
        logo_url = get_logo_url(symbol) or "https://via.placeholder.com/50"
        name = info.get("longName", symbol)

        # 결과 추가
        portfolio.append(
            {
                "logo": logo_url,
                "name": name,
                "symbol": symbol,
                "amount": total_quantity,
                "buyPrice": round(buy_price, 2),
                "totalBuyPrice": round(total_cost, 2),
                "currentPrice": round(current_price, 2),
                "dividend": round(dividend, 2),
                "dividendYield": round(dividend_yield, 2),
                "totalProfit": round(total_profit, 2),
                "dailyProfit": round(daily_profit, 2),
            }
        )

    return portfolio


@app.get("/portfolio")
async def get_portfolio(user: dict = Depends(verify_jwt)):
    """
    포트폴리오 불러오기
    """
    try:
        user_email = user["email"]
        print(f"Fetching portfolio for user: {user_email}")  # 디버깅용 로그
        portfolio = get_portfolio_calculation(user_email)
        print(f"Portfolio data: {portfolio}")  # 디버깅용 로그
        return {"portfolio": portfolio}
    except Exception as e:
        print(f"Error fetching portfolio: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/portfolio/{symbol}")
async def delete_from_portfolio(symbol: str, user: dict = Depends(verify_jwt)):
    try:
        user_email = user["email"]
        user_ref = db.collection("users").document(user_email)
        portfolio_ref = user_ref.collection("portfolio").document(symbol)

        purchases_ref = portfolio_ref.collection("purchases")
        purchase_docs = purchases_ref.stream()
        for p in purchase_docs:
            p.reference.delete()

        portfolio_ref.delete()
        return {"message": f"Stock {symbol} and its purchases deleted from portfolio"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
