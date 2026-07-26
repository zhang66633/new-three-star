import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

HY3_API_KEY = os.getenv("HY3_API_KEY", "")
HY3_BASE_URL = os.getenv("HY3_BASE_URL", "")
HY3_MODEL = os.getenv("HY3_MODEL", "")

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

MAX_TOKENS_VERDICT = 800
MAX_TOKENS_WORLDVIEW = 3000
TEMPERATURE = 0.85
