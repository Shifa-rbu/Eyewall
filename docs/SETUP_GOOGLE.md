# Google Credential & Integration Setup

This document describes how to configure Google Gemini credentials, run key verification, and manage runtime behavior for Eyewall.

## Environment Variables

Server-side Gemini configuration relies on the following environment variables:

- `GEMINI_API_KEY` (or `GOOGLE_API_KEY`): Server-side API key for Google Gemini model access.
- `EYEWALL_GEMINI_MODEL`: Optional model pin override (e.g. `gemini-3.7-flash`).
- `EYEWALL_GEMINI_DAILY_BUDGET`: Conservative daily call budget (default `15`).

### Security Rules
1. Keep API keys strictly server-side in environment variables.
2. Never add credentials to `app.js`, `static/ai.js`, HTML, committed JSON, or request URLs.
3. API keys must never be logged or rendered in browser responses.

## Model Discovery & Preference Order

Model discovery dynamically queries `https://generativelanguage.googleapis.com/v1beta/models` to find usable Flash-class models:

1. `gemini-3.7-flash`
2. `gemini-3.8-flash`
3. `gemini-3.6-flash`
4. `gemini-3.5-flash`
5. `gemini-3.5-flash-lite`

If no key is set or no model is available, the server seamlessly degrades to the template fallback.

## Live Key Verification

To verify a live Gemini API key and test model availability against Google's live API:

```bash
export GEMINI_API_KEY="your-actual-gemini-api-key"
python3 scripts/verify_google.py
```

Note: Live model discovery must be validated with a real key before claiming live API integration.
