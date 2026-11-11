"""Desktop OAuth: PKCE, state validation, random loopback port, no token copy/paste."""
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from .storage import data_dir

SCOPES = ['https://www.googleapis.com/auth/webmasters.readonly',
          'https://www.googleapis.com/auth/analytics.readonly']


class AuthError(Exception):
    pass


class TokenStore:
    service = 'seo-intelligence-local'

    def __init__(self):
        backend = keyring.get_keyring()
        # Reject plaintext/fallback backends; fail closed unless explicitly opted in.
        self.secure = type(backend).__module__.startswith(('keyring.backends.macOS', 'keyring.backends.Windows',
                                                         'keyring.backends.SecretService', 'keyring.backends.kwallet'))
        self.path = data_dir() / 'credentials.json'

    def read(self):
        if self.secure:
            raw = keyring.get_password(self.service, 'google')
        elif os.getenv('ALLOW_FILE_TOKENS', 'false').lower() == 'true':
            raw = self.path.read_text() if self.path.exists() else None
        else:
            return None
        return json.loads(raw) if raw else None

    def save(self, value):
        raw = json.dumps(value)
        if self.secure:
            keyring.set_password(self.service, 'google', raw)
        elif os.getenv('ALLOW_FILE_TOKENS', 'false').lower() == 'true':
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(raw)
            self.path.chmod(0o600)
        else:
            raise AuthError('No supported OS keychain. Configure one, or explicitly set ALLOW_FILE_TOKENS=true for a private local 0600 token file.')

    def delete(self):
        if self.secure:
            try:
                keyring.delete_password(self.service, 'google')
            except keyring.errors.PasswordDeleteError:
                pass
        self.path.unlink(missing_ok=True)


def credentials(store=None):
    store = store or TokenStore()
    value = store.read()
    if not value:
        return None, None
    cred = Credentials.from_authorized_user_info(value['credentials'])
    if cred.expired:
        try:
            cred.refresh(Request())
            value['credentials'] = json.loads(cred.to_json())
            store.save(value)
        except Exception:
            raise AuthError('Google authorization expired or was revoked. Disconnect and reconnect.') from None
    return cred, value['account']


class Login:
    def __init__(self, client_file=None, store=None):
        self.store = store or TokenStore()
        self.done = False
        self.error = None
        self.flow = InstalledAppFlow.from_client_secrets_file(
            client_file or os.getenv('GOOGLE_CLIENT_SECRETS', 'client_secret.json'),
            scopes=SCOPES, autogenerate_code_verifier=True)
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass  # Callback URL contains a credential; never log it.

            def do_GET(self):
                params = parse_qs(urlparse(self.path).query)
                if not secrets.compare_digest(params.get('state', [''])[0], owner.state):
                    self.send_error(400, 'Invalid OAuth state')
                    return
                try:
                    if 'error' in params or 'code' not in params:
                        raise AuthError('Authorization was denied. You can reconnect when ready.')
                    owner.flow.fetch_token(code=params['code'][0])
                    owner.store.save({'account': secrets.token_hex(24),
                                      'credentials': json.loads(owner.flow.credentials.to_json())})
                    message = b'Connected. Close this tab and return to SEO Intelligence.'
                except Exception:
                    owner.error = 'Authorization could not be saved. Check Google client configuration and local keychain, then reconnect.'
                    message = b'Connection failed. Return to SEO Intelligence.'
                owner.done = True
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(message)

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        self.server.timeout = 0.5
        self.flow.redirect_uri = f'http://127.0.0.1:{self.server.server_port}/'
        self.url, self.state = self.flow.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='true')
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        deadline = time.monotonic() + 180
        try:
            while not self.done and time.monotonic() < deadline:
                self.server.handle_request()
            if not self.done:
                self.error = 'Authorization timed out. Click Connect Google Account again.'
                self.done = True
        finally:
            self.server.server_close()
