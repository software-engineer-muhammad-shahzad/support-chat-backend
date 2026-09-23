"""Single shared Gemini client for the whole documents app.

embeddings.py and generation.py each used to build their own
`genai.Client(api_key=...)` — same key, same config, just two redundant
client instances (and connection pools) doing identical setup. Both import
`client` from here instead.
"""

from django.conf import settings
from google import genai

client = genai.Client(api_key=settings.GEMINI_API_KEY)
