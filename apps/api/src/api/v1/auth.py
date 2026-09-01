from fastapi import APIRouter, status

from src.api.deps import DbSession
from src.schemas.auth import LoginRequest, SignupRequest, TokenResponse, UserResponse
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: DbSession) -> UserResponse:
    user = AuthService(db).signup(email=payload.email, password=payload.password)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    service = AuthService(db)
    user = service.authenticate(email=payload.email, password=payload.password)
    token = service.issue_token(user)
    return TokenResponse(access_token=token)
