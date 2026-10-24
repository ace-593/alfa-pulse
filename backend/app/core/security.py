from datetime import timedelta

import jwt
from pwdlib import PasswordHash

from app.core.entities import now
from app.core.exceptions import AppError


class JwtSecurity:
    def __init__(self, key: str):
        if len(key) < 32:
            raise ValueError("JWT secret must contain at least 32 characters")
        self.key = key
        self.passwords = PasswordHash.recommended()

    def password_hash(self, password):
        return self.passwords.hash(password)

    def password_matches(self, password, encoded):
        return self.passwords.verify(password, encoded)

    def access_token(self, user_id, session_id):
        return jwt.encode(
            {
                "sub": user_id,
                "sid": session_id,
                "iat": now(),
                "exp": now() + timedelta(minutes=15),
                "iss": "alfa-pulse",
                "aud": "alfa-pulse-api",
            },
            self.key,
            algorithm="HS256",
        )

    def decode(self, token):
        try:
            return jwt.decode(
                token,
                self.key,
                algorithms=["HS256"],
                issuer="alfa-pulse",
                audience="alfa-pulse-api",
                options={"require": ["exp", "iat", "sub", "sid", "iss", "aud"]},
            )
        except jwt.InvalidTokenError as exc:
            raise AppError(401, "INVALID_TOKEN", "Токен недействителен или истёк") from exc
