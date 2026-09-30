# Google credential setup status

This revision does not implement Gemini or Earth Engine calls. The health endpoint therefore reports both products as unavailable, and the UI uses a template advisory. Do not add credentials expecting either endpoint to become live.

When those integrations are implemented:

1. Keep API keys and service-account credentials on the server only, in environment variables or a managed secret store.
2. Never add credentials to app.js, HTML, committed JSON, or request URLs.
3. Validate the selected account, scopes, quota, error handling, and keyless behavior before reporting a service as configured.
4. Use least-privilege credentials and rotate any secret that may have entered source control.

For local development, .env.example names the intended variables. Copy it to .env only after the adapters exist. The environment-file loader is server-side.
