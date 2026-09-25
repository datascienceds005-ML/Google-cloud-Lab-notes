"""
auth.py
JWT verification, equivalent to server.js's `decodeToken` (line 1660) and
the `authenticateToken` Express middleware (line 1669):

    function authenticateToken(req, res, next) {
      const authHeader = req.headers["authorization"];
      const token = authHeader && authHeader.split(" ")[1];
      if (!token) return res.status(401).json({ message: "No token provided" });
      jwt.verify(token, JWT_SECRET, (err, user) => {
        if (err) {
          const message = err.name === 'TokenExpiredError' ? 'Token has expired' : 'Invalid token';
          return res.status(403).json({ message });
        }
        req.user = user;
        next();
      });
    }

FastAPI has no middleware-per-route concept the way Express does; the
idiomatic equivalent is a Dependency that routes opt into via
`Depends(authenticate_token)`, injected as a parameter. Any route that had
`authenticateToken` as its second argument in server.js gets
`user: dict = Depends(authenticate_token)` here.
"""
from fastapi import Header, HTTPException
from jose import jwt, JWTError, ExpiredSignatureError

import config


def decode_token(token: str) -> dict | None:
    """Direct equivalent of decodeToken() — returns None on any failure
    instead of raising, exactly like the try/except in server.js."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        return None


async def authenticate_token(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency equivalent of authenticateToken middleware.
    Usage: `user: dict = Depends(authenticate_token)` in any router that
    had `authenticateToken` in its Express route signature.

    Preserves the exact same status codes and messages as the original:
      - 401 "No token provided" if the header is missing/malformed
      - 403 "Token has expired" if jwt.verify raised TokenExpiredError
      - 403 "Invalid token" for any other verification failure
    """
    token = None
    if authorization:
        parts = authorization.split(" ")
        if len(parts) == 2:
            token = parts[1]

    if not token:
        raise HTTPException(status_code=401, detail={"message": "No token provided"})

    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=403, detail={"message": "Token has expired"})
    except JWTError:
        raise HTTPException(status_code=403, detail={"message": "Invalid token"})

    # req.user = user  →  the decoded payload is returned and injected
    # into the route handler exactly like req.user was available there.
    return payload
