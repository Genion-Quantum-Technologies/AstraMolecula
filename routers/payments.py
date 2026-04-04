from dotenv import load_dotenv
load_dotenv()
import os
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from square import Square
from square.environment import SquareEnvironment
from square.core.api_error import ApiError

from astra_molecula.core.security.auth import get_current_user
from astra_molecula.db.models.user import User
from astra_molecula.db.services.user_service import UserService
from typing import Annotated
from fastapi import Depends

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
    amount: float
    planId: str | None = None

@router.post('')
async def create_payment(
    payload: PaymentRequest,
    current_user: User = Depends(get_current_user)
):
    if not payload.sourceId or not payload.amount:
        raise HTTPException(status_code=400, detail='Missing payment data')

    idempotency_key = str(uuid.uuid4())

    try:
        # In squareup v44+, this returns CreatePaymentResponse or raises ApiError
        payment_response = square.payments.create(
            source_id=payload.sourceId,
            idempotency_key=idempotency_key,
            amount_money={
                'amount': int(round(payload.amount * 100)),
                'currency': 'USD',
            },
            note=f'Plan: {payload.planId}',
        )

        # Success path
        payment = payment_response.payment

        if payload.planId:
            UserService.process_successful_payment(
                user_id=current_user.id, 
                plan_id=payload.planId
            )

        return {
            'success': True,
            'paymentId': payment.id,
            'newPlan': payload.planId
        }

    except ApiError as e:
        print('Square API error:', e.body)
        # Extract the first error detail if available
        error_detail = 'Payment processing failed'
        if e.body and 'errors' in e.body and len(e.body['errors']) > 0:
            error_detail = e.body['errors'][0].get('detail', error_detail)
        
        raise HTTPException(status_code=400, detail=error_detail)
    except Exception as e:
        print('General payment error:', str(e))
        raise HTTPException(status_code=500, detail=str(e))
