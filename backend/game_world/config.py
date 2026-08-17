import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_BETA_URL = os.getenv("DEEPSEEK_BETA_URL", "https://api.deepseek.com/beta")  # Chat Prefix Completion
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

HY3_API_KEY = os.getenv("HY3_API_KEY", "")
HY3_BASE_URL = os.getenv("HY3_BASE_URL", "")
HY3_MODEL = os.getenv("HY3_MODEL", "")

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

MAX_TOKENS_VERDICT = 800
MAX_TOKENS_WORLDVIEW = 3000
TEMPERATURE = 0.7  # 旧值，保留兼容。v3.2 使用 PARAMS_NARRATIVE

# ============================================================================
# v3.2 参数配置（基于 DeepSeek V4 官方推荐）
# ============================================================================
# 关键发现：
# 1. frequency_penalty / presence_penalty 在 V4 中不被支持（会被忽略）
# 2. V4 系统提示词遵守度弱 — 格式规则应嵌入用户消息
# 3. 创意写作官方推荐 temperature=1.5, top_p=0.9-0.95
# 4. temperature 和 top_p 不应同时大幅调整
# 5. Chat Prefix Completion (beta) 可以强制首token，保证格式

# 叙事生成参数（temperature=1.3，在创意和格式之间取平衡）
PARAMS_NARRATIVE = {
    "temperature": 1.3,
    "top_p": 0.95,
}

# 格式转换参数（低温=更听话）
PARAMS_FORMAT = {
    "temperature": 0.3,
    "top_p": 0.9,
}

# 选项生成参数（中等温度+高top_p=多样但不离谱）
PARAMS_OPTIONS = {
    "temperature": 0.7,
    "top_p": 0.95,
}

# 停止序列：防止模型在输出完成后继续写字
# V4 完全支持 stop 参数 — 匹配到任一字符串立即停止
# 注意：不用 "\n\n[" — 会误伤正常 "[角色名]" 对话行
STOP_SEQUENCES = [
    "\n\nUser:",  # 防止幻觉用户回合
    "---",        # 场景分隔符
    "【系统",     # 防止幻觉系统指令
]

# 格式规则（嵌入用户消息，不放在system prompt——V4对system prompt遵守弱）
FORMAT_RULES = """【输出格式】
- [角色名] 台词
- → 动作
- [SYS] 独立行
- [OPT] 独立行
- 不写解释和开头语。"""
