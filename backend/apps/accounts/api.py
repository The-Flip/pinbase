"""Auth API endpoints: status, login, logout."""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import authenticate, login, logout
from ninja import Router, Schema

auth_router = Router(tags=["auth", "private"])


class AuthStatusSchema(Schema):
    is_authenticated: bool
    id: Optional[int] = None
    username: Optional[str] = None


class LoginSchema(Schema):
    username: str
    password: str


class ErrorSchema(Schema):
    detail: str


@auth_router.get("/me/", response=AuthStatusSchema)
def auth_me(request):
    """Return current session's authentication state.

    Always succeeds (no auth required). Returns is_authenticated=False for
    anonymous users.
    """
    if request.user.is_authenticated:
        return {
            "is_authenticated": True,
            "id": request.user.id,
            "username": request.user.username,
        }
    return {"is_authenticated": False}


@auth_router.post(
    "/login/",
    response={200: AuthStatusSchema, 400: ErrorSchema},
)
def auth_login(request, payload: LoginSchema):
    """Authenticate with username and password.

    Creates a session on success. Returns 400 with detail message on failure.
    """
    user = authenticate(request, username=payload.username, password=payload.password)
    if user is None:
        return 400, {"detail": "Invalid username or password."}
    login(request, user)
    return {
        "is_authenticated": True,
        "id": user.id,
        "username": user.username,
    }


@auth_router.post("/logout/", response=AuthStatusSchema)
def auth_logout(request):
    """End the current session."""
    logout(request)
    return {"is_authenticated": False}
