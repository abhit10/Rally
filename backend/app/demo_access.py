"""Optional shared-key protection for a temporary, isolated demo server."""
import os
import secrets
from urllib.parse import parse_qs
from starlette.responses import JSONResponse

class DemoAccess:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        key = os.getenv('RALLY_DEMO_KEY', '')
        if key and scope['type'] in ('http', 'websocket'):
            query = parse_qs(scope.get('query_string', b'').decode())
            supplied = query.get('demo_key', [''])[0]
            if not secrets.compare_digest(supplied.encode(), key.encode()):
                if scope['type'] == 'websocket':
                    await send({'type': 'websocket.close', 'code': 1008})
                else:
                    await JSONResponse({'detail': 'Open the private demo access link to continue.'}, status_code=401)(scope, receive, send)
                return
            # Do not allow a remote demo visitor to open cameras or network URLs.
            if scope.get('path') == '/api/sessions/live':
                await JSONResponse({'detail': 'Camera connections are disabled for this public demo.'}, status_code=403)(scope, receive, send)
                return
        await self.app(scope, receive, send)
