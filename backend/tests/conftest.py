import os

# Ensure a predictable token/settings for every test, regardless of any
# real .env on the machine running the suite.
os.environ.setdefault("JARVIS_API_TOKEN", "test-token")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
