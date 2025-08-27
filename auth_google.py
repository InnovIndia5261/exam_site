# auth_google.py
import streamlit as st
from urllib.parse import urlencode
from authlib.integrations.requests_client import OAuth2Session

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "openid email profile"

class GoogleOAuth:
    def __init__(self):
        try:
            cfg = st.secrets.get("google", {})
        except Exception:
            cfg = {}
        self.client_id = cfg.get("client_id")
        self.client_secret = cfg.get("client_secret")
        self.redirect_uri = cfg.get("redirect_uri")
        self.enabled = bool(self.client_id and self.client_secret and self.redirect_uri)

    def login_button(self, label="Sign in with Google"):
        if not self.enabled:
            st.caption("Google OAuth not configured.")
            return None
        params = st.query_params
        code = params.get("code")
        if code:
            session = OAuth2Session(self.client_id, self.client_secret, scope=SCOPE, redirect_uri=self.redirect_uri)
            token = session.fetch_token(TOKEN_URL, code=code)
            userinfo = session.get("https://www.googleapis.com/oauth2/v3/userinfo").json()
            return userinfo
        else:
            auth_params = {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "scope": SCOPE,
                "access_type": "online",
                "include_granted_scopes": "true",
                "prompt": "consent"
            }
            url = f"{AUTH_URL}?{urlencode(auth_params)}"
            st.link_button(label, url, type="primary")
            return None
