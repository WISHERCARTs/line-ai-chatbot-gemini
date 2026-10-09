"""Force dummy credentials before main.py is imported, so tests never touch real keys."""
import os

os.environ["LINE_CHANNEL_SECRET"] = "test-channel-secret"
os.environ["LINE_CHANNEL_ACCESS_TOKEN"] = "test-access-token"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
