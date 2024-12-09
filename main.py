from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import firebase_admin
from firebase_admin import credentials, firestore

# Firebase 초기화
cred = credentials.Certificate(
    "key/finflow-7e697-firebase-adminsdk-e10q8-270beafc23.json"
)
firebase_admin.initialize_app(cred)
db = firestore.client()

app = FastAPI()

# CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
