from dotenv import load_dotenv
load_dotenv()
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from square import Square
from square.environment import SquareEnvironment

access_token = os.getenv("SQUARE_ACCESS_TOKEN")

router = APIRouter(
    prefix="/payments",
    tags=["Payments"]
)

# Initialize Square Client
square = Square(
    token=access_token,
    environment=SquareEnvironment.SANDBOX,
)

# Request body schema
class PaymentRequest(BaseModel):
    sourceId: str
    amount: int
    planId: str | None = None

@router.post('')
async def create_payment(payload: PaymentRequest):
    if not payload.sourceId or not payload.amount:
        raise HTTPException(status_code=400, detail='Missing payment data')

    idempotency_key = str(uuid.uuid4())

    try:
        result = square.payments.create(
            source_id=payload.sourceId,
            idempotency_key=idempotency_key,
            amount_money={
                'amount': payload.amount,
                'currency': 'USD',
            },
            note=f'Plan: {payload.planId}',
        )

        if result.errors:
            raise Exception(result.errors)

        payment = result.payment

        return {
            'success': True,
            'paymentId': payment.id,
        }

    except Exception as e:
        print('Square payment error:', e)

        error_detail = (
            e.args[0][0]['detail']
            if isinstance(e.args[0], list)
            else 'Payment processing failed'
        )

        raise HTTPException(status_code=500, detail=error_detail)
