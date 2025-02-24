from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.schemas.transaction import (
    TransactionOut,
    DeleteResponse,
    TransactionListResponse
)
import app.crud.transaction as crud_transaction


router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    responses={
        400: {"description": "page 또는 per_page가 1보다 작은 경우", "content": {"application/json": {"example": {"detail": "Page와 per_page는 1 이상이어야 합니다."}}}},
        500: {"description": "데이터베이스 연결 오류", "content": {"application/json": {"example": {"detail": "데이터베이스 연결 오류"}}}},
    },
)
def read_transactions(page: int = 1, per_page: int = 10, db: Session = Depends(get_db)):
    """
    거래 내역 페이징 조회
    - page: 현재 페이지(1부터 시작)
    - per_page: 페이지당 건수
    """
    if page < 1 or per_page < 1:
        raise HTTPException(status_code=400, detail="Page와 per_page는 1 이상이어야 합니다.")

    try:
        skip = (page - 1) * per_page
        total_count = crud_transaction.get_transaction_count(db)
        transactions = crud_transaction.get_transactions(db, skip=skip, limit=per_page)
        return {
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "data": transactions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="데이터베이스 연결 오류")


@router.delete(
    "/transactions/{transaction_id}",
    response_model=DeleteResponse,
    responses={
        404: {"description": "존재하지 않는 transaction_id", "content": {"application/json": {"example": {"detail": "Transaction 찾을 수 없음"}}}},
        500: {"description": "데이터베이스 연결 오류", "content": {"application/json": {"example": {"detail": "데이터베이스 연결 오류"}}}},
    },
)
def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """
    거래 내역 삭제
    - transaction_id: 삭제할 거래 내역 ID
    """
    try:
        success = crud_transaction.delete_transaction(db, transaction_id)
        if not success:
            raise HTTPException(status_code=404, detail="Transaction 찾을 수 없음")
        return {"message": "트랜잭션 삭제 성공"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="데이터베이스 연결 오류")