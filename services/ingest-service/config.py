import os

NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
if not NEWS_API_KEY:
    raise RuntimeError("Missing required environment variable: NEWS_API_KEY")
NEWS_API_URL = "https://gnews.io/api/v4/search"

NEWSDATA_API_KEY = os.environ.get("NEWSDATA_API_KEY")
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
