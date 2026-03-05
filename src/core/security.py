"""Core security module for JWT tokens, password hashing, and OAuth."""

import datetime
import uuid
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config.logging import logger
from src.config.settings import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    Args:
        plain_password: The plain text password
        hashed_password: The hashed password

    Returns:
        True if passwords match, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password.

    Args:
        password: The plain text password

    Returns:
        The hashed password
    """
    return pwd_context.hash(password)


class TokenPayload:
    """JWT token payload."""

    def __init__(
        self,
        sub: str,
        exp: datetime.datetime,
        iat: datetime.datetime,
        jti: str,
        type: str = "access",
    ) -> None:
        """Initialize the token payload.

        Args:
            sub: Subject (user ID)
            exp: Expiration time
            iat: Issued at time
            jti: JWT ID (token ID)
            type: Token type (access or refresh)
        """
        self.sub = sub
        self.exp = exp
        self.iat = iat
        self.jti = jti
        self.type = type

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JWT encoding.

        Returns:
            Dictionary representation
        """
        return {
            "sub": self.sub,
            "exp": self.exp,
            "iat": self.iat,
            "jti": self.jti,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TokenPayload":
        """Create from dictionary.

        Args:
            data: Dictionary with token data

        Returns:
            TokenPayload instance
        """
        # JWT decodes exp and iat as Unix timestamps (integers), convert to datetime
        exp = data["exp"]
        iat = data["iat"]

        # Convert Unix timestamps to datetime if they are integers
        if isinstance(exp, (int, float)):
            exp = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
        if isinstance(iat, (int, float)):
            iat = datetime.datetime.fromtimestamp(iat, tz=datetime.timezone.utc)

        return cls(
            sub=data["sub"],
            exp=exp,
            iat=iat,
            jti=data["jti"],
            type=data.get("type", "access"),
        )


def create_access_token(
    subject: str,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """Create an access token.

    Args:
        subject: Subject (usually user ID)
        expires_delta: Optional custom expiration

    Returns:
        Encoded JWT access token
    """
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=settings.access_token_expire_minutes
        )

    payload = TokenPayload(
        sub=str(subject),
        exp=expire,
        iat=datetime.datetime.now(datetime.timezone.utc),
        jti=str(uuid.uuid4()),
        type="access",
    )

    encoded_jwt = jwt.encode(
        payload.to_dict(),
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    logger.debug(f"Created access token for user {subject}")
    return encoded_jwt


def create_refresh_token(
    subject: str,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """Create a refresh token.

    Args:
        subject: Subject (usually user ID)
        expires_delta: Optional custom expiration

    Returns:
        Encoded JWT refresh token
    """
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=settings.refresh_token_expire_days
        )

    payload = TokenPayload(
        sub=str(subject),
        exp=expire,
        iat=datetime.datetime.now(datetime.timezone.utc),
        jti=str(uuid.uuid4()),
        type="refresh",
    )

    encoded_jwt = jwt.encode(
        payload.to_dict(),
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    logger.debug(f"Created refresh token for user {subject}")
    return encoded_jwt


def decode_token(token: str) -> TokenPayload | None:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token to decode

    Returns:
        TokenPayload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return TokenPayload.from_dict(payload)
    except JWTError as e:
        logger.warning(f"Failed to decode token: {e}")
        return None


def verify_token(token: str, token_type: str | None = None) -> TokenPayload | None:
    """Verify a token and check its type.

    Args:
        token: The JWT token to verify
        token_type: Expected token type (access or refresh)

    Returns:
        TokenPayload if valid, None otherwise
    """
    payload = decode_token(token)
    if not payload:
        return None
    if token_type is None or payload.type == token_type:
        return payload
    return None


def get_token_expiry(token: str) -> datetime.datetime | None:
    """Get the expiration time of a token.

    Args:
        token: The JWT token

    Returns:
        Expiration datetime, or None if invalid
    """
    payload = decode_token(token)
    if not payload:
        return None
    expiry = payload.exp
    if isinstance(expiry, datetime.datetime) and expiry.tzinfo is not None:
        return expiry.astimezone().replace(tzinfo=None)
    return expiry


def is_token_expired(token: str) -> bool:
    """Check if a token is expired.

    Args:
        token: The JWT token

    Returns:
        True if expired, False otherwise
    """
    payload = decode_token(token)
    if not payload:
        return True

    return datetime.datetime.now(datetime.timezone.utc) >= payload.exp


class OAuthProvider:
    """OAuth provider configuration."""

    GOOGLE = "google"
    APPLE = "apple"


class OAuthUserInfo:
    """OAuth user information."""

    def __init__(
        self,
        provider: str,
        provider_id: str,
        email: str,
        display_name: str | None = None,
        avatar_url: str | None = None,
        locale: str | None = None,
    ) -> None:
        """Initialize OAuth user info.

        Args:
            provider: OAuth provider name
            provider_id: Provider-specific user ID
            email: User email
            display_name: Optional display name
            avatar_url: Optional avatar URL
            locale: Optional user locale
        """
        self.provider = provider
        self.provider_id = provider_id
        self.email = email
        self.display_name = display_name
        self.avatar_url = avatar_url
        self.locale = locale

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "provider": self.provider,
            "provider_id": self.provider_id,
            "email": self.email,
            "display_name": self.display_name,
            "avatar_url": self.avatar_url,
            "locale": self.locale,
        }


def verify_google_token(token: str) -> OAuthUserInfo | None:
    """Verify a Google OAuth token.

    Args:
        token: Google ID token

    Returns:
        OAuthUserInfo if valid, None otherwise

    Note:
        This is a placeholder implementation. In production, use the
        google-auth library to properly verify Google ID tokens.
    """
    try:
        import google.auth.transport.requests
        import google.oauth2.id_token

        request = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(
            token,
            request,
            audience=settings.google_oauth_client_id,
        )

        return OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            provider_id=id_info["sub"],
            email=id_info["email"],
            display_name=id_info.get("name"),
            avatar_url=id_info.get("picture"),
            locale=id_info.get("locale"),
        )
    except Exception as e:
        logger.error(f"Failed to verify Google token: {e}")
        return None


def verify_apple_token(token: str) -> OAuthUserInfo | None:
    """Verify an Apple OAuth token.

    Args:
        token: Apple ID token

    Returns:
        OAuthUserInfo if valid, None otherwise

    Note:
        This is a placeholder implementation. In production, use the
        pyjwt library to verify Apple ID tokens with Apple's public keys.
    """
    try:
        payload = jwt.decode(
            token,
            key="",  # Apple's public key (need to fetch from Apple)
            algorithms=["RS256"],
            audience=settings.apple_oauth_client_id,
            issuer="https://appleid.apple.com",
            options={"verify_signature": False},  # Only for development
        )

        return OAuthUserInfo(
            provider=OAuthProvider.APPLE,
            provider_id=payload["sub"],
            email=payload.get("email"),
            display_name=None,  # Apple doesn't provide name in token
            avatar_url=None,
            locale=None,
        )
    except Exception as e:
        logger.error(f"Failed to verify Apple token: {e}")
        return None
