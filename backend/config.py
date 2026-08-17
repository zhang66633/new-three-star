import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ── 双模型试验（experiment/dual-model）──
# 主控模型（Qwen3.5）：validator 8-PHASE 校验 + corrector 天意修正走它——指令遵循强，
# 补 DeepSeek 长指令漂移的短板。叙事（writer）仍走 DeepSeek（创意写作强项）。
# 未配置 QWEN_API_KEY 时自动回退 DeepSeek（单模型模式），不影响线上。
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.5-35b")

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")

MAX_TOKENS_VERDICT = 800

# ============================================================================
# v3.2 参数配置（基于 DeepSeek V4 官方推荐）
# ============================================================================
# 关键发现：
# 1. frequency_penalty / presence_penalty 在 V4 中不被支持（会被忽略）
# 2. V4 系统提示词遵守度弱 — 格式规则应嵌入用户消息
# 3. 创意写作官方推荐 temperature=1.5, top_p=0.9-0.95
# 4. temperature 和 top_p 不应同时大幅调整
# 5. Chat Prefix Completion (beta) 可以强制首token，保证格式

# 叙事生成参数
# V4 Pro 温度降低：1.3 产生幻觉，0.7 更稳定
PARAMS_NARRATIVE = {
    "temperature": 0.7,
}

# 玩家叙事生成参数（新三国 星空 /api/play）
# 玩家叙事需要保持人物一致性，温度比天意模式收敛
PARAMS_PLAY = {
    "temperature": 0.8,
}

# 格式转换参数（低温=更听话）
PARAMS_FORMAT = {
    "temperature": 0.3,
    "top_p": 0.9,
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
FORMAT_RULES = """【输出格式·必须严格遵守】
第一行输出面板：当前：节点·节拍 | 温度：X.X | 上下文：X% | 偏离度：X%
空一行
输出世界响应（脚本格式，200-400字）：
  [角色名] 台词
  → 动作/环境
只写角色可感知的世界。不写天意，不写玩家，不写"你"。角色不"怔住"不"顿住"，荒诞是常态。
末尾必须输出3个[OPT]，缺一不可：
[OPT] 世界被怎样改写的一句指令
[OPT] 另一句世界改写指令
[OPT] 又一句世界改写指令"""
