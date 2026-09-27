import asyncio
from starlette.middleware.base import BaseHTTPMiddleware

# add this --middleware delay_middleware.ArtificialDelayMiddleware to deployment

class ArtificialDelayMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Trigger delay on inference routes AND the Prometheus metrics endpoint
        target_paths = ["/v1/chat/completions", "/v1/completions", "/metrics"]

        if any(path in request.url.path for path in target_paths):
            # Force a 30-second delay to trigger client/scraper timeouts
            await asyncio.sleep(30.0)

        return await call_next(request)
