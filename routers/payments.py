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

print('access_token:', access_token)
print('Environment:', SquareEnvironment)

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

    print('sourceId:', payload.sourceId)
    print('amount:', payload.amount)
    print('planId:', payload.planId)
    print('idempotencyKey:', idempotency_key)

    try:
        result = square.payments.create_payment(
            body={
                'source_id': payload.sourceId,
                'idempotency_key': idempotency_key,
                'amount_money': {
                    'amount': payload.amount,
                    'currency': 'USD',
                },
                'note': f'Plan: {payload.planId}',
            }
        )

        if result.is_error():
            raise Exception(result.errors)

        payment = result.body.get('payment')

        return {
            'success': True,
            'paymentId': payment.get('id'),
        }

    except Exception as e:
        print('Square payment error:', e)

        error_detail = (
            e.args[0][0]['detail']
            if isinstance(e.args[0], list)
            else 'Payment processing failed'
        )

        raise HTTPException(status_code=500, detail=error_detail)
