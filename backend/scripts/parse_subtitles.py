# -*- coding: utf-8 -*-
"""
Phase 0: 折棒锐评字幕解析 → 台词引用库
=======================================
输入: materials/电视剧吐槽/*.txt（285 期 ASR 字幕，纯文本无时间戳）
输出: materials/字幕台词/台词引用库.json + 锚定场景清单.md

台词检测策略（样本已验证）：
- 引导语正则: "曹操是这么说的" "董卓是这么回答的" "他说" 等
- 台词 = 引导语后接续 1-5 行（到评论信号词/换说话人为止）
- 排除 up 主自称（折棒/周望/之棒/直棒/志棒/哲蚌）
- ASR 错字修正：与 5376 条原著台词库 difflib ≥0.82 匹配 → 用原著规范台词
"""
import re
import os
import json
import difflib
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

SUBTITLE_DIR = 'materials/电视剧吐槽'
OUT_DIR = 'materials/字幕台词'
SCRIPT_JSON = 'materials/script_ocr/台词/全部台词.json'  # 5376 条原著台词

# 角色别名 → 规范名（复用 extract_dialogues.py 的子集）
CHARACTERS = {
    '曹操': '曹操', '孟德': '曹操', '曹孟德': '曹操', '曹公': '曹操', '曹阿瞒': '曹操', '阿瞒': '曹操', '丞相': '曹操',
    '曹丕': '曹丕', '曹植': '曹植', '曹彰': '曹彰', '曹仁': '曹仁', '曹洪': '曹洪',
    '夏侯惇': '夏侯惇', '夏侯渊': '夏侯渊', '许褚': '许褚', '张辽': '张辽',
    '张合': '张郃', '张颌': '张郃', '徐晃': '徐晃', '于禁': '于禁', '庞德': '庞德',
    '荀彧': '荀彧', '荀或': '荀彧', '郭嘉': '郭嘉', '程昱': '程昱', '贾诩': '贾诩',
    '司马懿': '司马懿', '仲达': '司马懿', '杨修': '杨修',
    '刘备': '刘备', '刘玄德': '刘备', '玄德': '刘备', '刘皇叔': '刘备', '皇叔': '刘备',
    '诸葛亮': '诸葛亮', '孔明': '诸葛亮', '诸葛孔明': '诸葛亮', '军师': '诸葛亮',
    '关羽': '关羽', '关云长': '关羽', '云长': '关羽', '关公': '关羽', '君侯': '关羽', '关将军': '关羽',
    '张飞': '张飞', '翼德': '张飞', '赵云': '赵云', '赵子龙': '赵云', '子龙': '赵云',
    '马超': '马超', '黄忠': '黄忠', '魏延': '魏延', '庞统': '庞统', '凤雏': '庞统',
    '姜维': '姜维', '马良': '马良', '马谡': '马谡', '刘禅': '刘禅', '刘封': '刘封',
    '关平': '关平', '周仓': '周仓', '王平': '王平', '廖化': '廖化', '法正': '法正',
    '孙权': '孙权', '孙仲谋': '孙权', '周瑜': '周瑜', '公瑾': '周瑜', '大都督': '周瑜',
    '鲁肃': '鲁肃', '吕蒙': '吕蒙', '陆逊': '陆逊', '黄盖': '黄盖', '程普': '程普',
    '孙坚': '孙坚', '孙策': '孙策', '诸葛瑾': '诸葛瑾', '张昭': '张昭',
    '董卓': '董卓', '董相国': '董卓', '相国': '董卓', '吕布': '吕布', '奉先': '吕布', '温侯': '吕布',
    '陈宫': '陈宫', '高顺': '高顺', '袁绍': '袁绍', '本初': '袁绍',
    '袁术': '袁术', '袁公路': '袁术', '刘表': '刘表', '刘璋': '刘璋',
    '王允': '王允', '王司徒': '王允', '貂蝉': '貂蝉', '李傕': '李傕', '郭汜': '郭汜',
    '张角': '张角', '张宝': '张宝', '张梁': '张梁', '袁隗': '袁隗', '袁太傅': '袁隗',
    '华雄': '华雄', '颜良': '颜良', '文丑': '文丑', '张绣': '张绣', '张鲁': '张鲁',
    '蔡瑁': '蔡瑁', '张允': '张允', '蒋干': '蒋干', '徐庶': '徐庶',
    '许攸': '许攸', '沮授': '沮授', '审配': '审配', '田丰': '田丰',
    '汉献帝': '汉献帝', '献帝': '汉献帝', '天子': '汉献帝', '少帝': '汉献帝', '陛下': '汉献帝',
    '小黄门': '小黄门', '司马师': '司马师', '司马昭': '司马昭', '曹睿': '曹睿',
    '邢道荣': '邢道荣', '庞德公': '庞德公', '水镜先生': '水镜先生',
}

# up 主自称变体（排除）
UP_VARIANTS = {'折棒', '周望', '之棒', '直棒', '志棒', '哲蚌', '吃蛋挞的折棒', '蛋挞'}

# 引导语模式：说话人 + 明确台词句式
# 强句式（"是这么说的/回答的/说"）→ 台词概率高
# 说话人必须直接命中角色词典（且非 up 主自称），拒绝"按原着"等修饰词
STRONG_LEAD = re.compile(
    r'(?P<sp>[一-鿿·]{1,6}?)(?:是这么说的|是这样说的|是这么回答的|是这么说的呀|是这么回答的呀|说)'
)

# 引导语中的修饰词黑名单：说话人后面跟着这些 → 不是"X说"而是"X按原着说"（台词归属存疑）
LEAD_BLOCKERS = ('按原着', '按照', '原着', '剧中', '剧里', '在这段', '这段里', '刚刚', '刚才', '之前', '之前说', '才', '还', '又')

# 评论信号词：台词接续在此结束
COMMENT_SIGNALS = ['咱们', '这剧', '编剧', '所以说', '这个编剧', '新三国的', '我觉得', '你看', '真的', '作为一个',
                   '这想', '这是', '问题', '槽点', '名场面', '这段', '然后', '所以', '就是', '而且', '但是',
                   '那你想', '那你董卓', '敢情', '这鹰犬', '来表现', '但实际', '不是', '为什么', '怎么', '呢',
                   '吧', '啊', '呀', '了', '吗', '啥', '根本', '完全', '属实', '真的吗']

# 台词特征：一句"像台词"的话通常包含角色口吻词（第一人称/命令/称谓）
SPEECH_HINTS = ['我', '你', '咱', '朕', '臣', '末将', '大人', '主公', '丞相', '将军', '陛下',
                '请', '快', '来', '去', '杀', '给', '报', '听', '问', '乃', '是', '有', '无']

# 叙述特征：出现即不是台词（吐槽/评论句）
NARRATION_MARKS = ['吐槽', '表现', '想表现', '这段', '这剧', '编剧', '所以', '然后', '真的',
                   '作为', '一个', '这词', '咋', '呢', '吗', '啊', '吧', '呀', '点', '种',
                   '来', '去', '是', '就', '都', '也', '还', '更', '最', '很', '太', '真']

# 文件名 → 期号/标题
FILE_PAT = re.compile(r'锐评新三国(?P<num>\d+|re\d+)?[：:](?P<title>[^—]+?)[—]')


def norm(text: str) -> str:
    """归一化：去标点空白"""
    return re.sub(r'[\s，。！？、；：“”「」（）·…\-\d]', '', text)


def load_script_quotes() -> list[dict]:
    """加载 5376 条原著台词库"""
    if not os.path.exists(SCRIPT_JSON):
        logger.warning(f'原著台词库缺失: {SCRIPT_JSON}')
        return []
    with open(SCRIPT_JSON, encoding='utf-8') as f:
        return json.load(f)


_script_cache: list[dict] | None = None  # 预处理后的原著台词库（预归一化）

def _prepare_script_cache(script_quotes: list[dict]) -> None:
    """预归一化原著台词库（一次性）"""
    global _script_cache
    if _script_cache is not None:
        return
    _script_cache = []
    for sq in script_quotes:
        s_norm = norm(sq['quote'])
        if len(s_norm) >= 4:
            _script_cache.append({**sq, '_norm': s_norm})


def match_script(quote: str, script_quotes: list[dict], threshold: float = 0.82) -> dict | None:
    """与原著台词库模糊匹配，返回最佳命中（预归一化 + 长度剪枝）"""
    _prepare_script_cache(script_quotes)
    q_norm = norm(quote)
    if len(q_norm) < 4 or not _script_cache:
        return None
    # 快速长度剪枝：目标长度 ±30% 或 ±10字 之外直接跳过
    lo = max(4, int(len(q_norm) * 0.7) - 5)
    hi = int(len(q_norm) * 1.3) + 5
    best = None
    best_score = 0.0
    for sq in _script_cache:
        s_norm = sq['_norm']
        if not (lo <= len(s_norm) <= hi):
            continue
        score = difflib.SequenceMatcher(None, q_norm, s_norm).ratio()
        if score > best_score:
            best_score = score
            best = sq
        if best_score >= 0.95:  # 足够好提前退出
            break
    if best and best_score >= threshold:
        return {**best, 'match_score': round(best_score, 3)}
    return None


def is_speech_like(content: str) -> bool:
    """判断一段文本是否"像角色台词"（过滤吐槽/叙述句）。

    策略：台词通常以第一人称/命令/称谓/判断开头（我/你/臣/陛下/快/请…），
    吐槽通常以评论词开头（这剧/编剧/所以/然后/作为…）。
    """
    head = content[:6]
    # 直接命中叙述特征
    for sig in COMMENT_SIGNALS:
        if head.startswith(sig):
            return False
    # 命中台词口吻 → 是台词
    if head[0] in ('我', '你', '咱', '朕', '臣', '末将', '主公', '丞相', '将军', '陛下', '大人', '快', '请', '来', '去', '杀', '报', '听', '问', '乃'):
        return True
    # 含台词高频词（3 字以上文本中）
    hint_count = sum(1 for h in SPEECH_HINTS if h in content)
    if len(content) >= 10 and hint_count >= 2:
        return True
    return False


# ═══ 原剧播放片段检测（新增）═══
# 折棒视频中直接播放原剧：台词以角色口吻连续出现（无引导语）
# 特征：句首第一人称/称谓/命令式 + 文言腔（咱家/末将/遵命/相国）+ 无吐槽词

# 原剧台词专属称谓（比吐槽句更"剧内"）
DRAMA_TERMS = ('咱家', '末将', '遵命', '领命', '相国', '司徒', '主公', '义父', '陛下', '天子', '奉先', '孟德', '玄德', '云长', '子龙', '孔明', '仲达', '公瑾', '子敬', '本初', '公路', '丞相', '将军', '大军', '甲士', '传命', '报', '禀')

# 吐槽句特征（用于切断原剧片段）
DRAMA_STOP = ('然后', '接下来', '总之', '所以', '但是', '不过', '其实', '真的', '哈哈', '这个', '这就是', '那', '咱', '我', '你看', '大家', '可以', '镜头', '编剧', '新三国', '原着', '三国演义', '吐槽', '观众', 'up', '视频', '期')

def extract_drama_lines(lines: list[str], script_quotes: list[dict]) -> list[dict]:
    """检测无引导语的原剧台词连续段（按说话人分组）。

    策略：找到台词特征行（句首口吻+称谓），向前/向后合并连续台词行；
    说话人用 CHARACTERS 在段内匹配（"末将想请示相国"→相国=董卓 无法直接定人，
    用整段上下文推断——优先取段内出现的角色名，否则标 ⚠待定）。
    """
    out = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        # 是否台词行：句首口吻 + 含称谓 + 非吐槽
        if (is_drama_line(line)):
            # 收集连续台词段
            seg = [line]
            j = i + 1
            while j < n and is_drama_line(lines[j]) and len(''.join(seg)) < 150:
                seg.append(lines[j])
                j += 1
            # 段内找说话人：段首附近可能已有角色名（如"董卓突然就化身名侦探"已在上文）
            text = ''.join(seg)
            sp = infer_drama_speaker(seg, text)
            matched = match_script(text, script_quotes) if script_quotes else None
            out.append({
                'episode': '?', 'ep_title': '', 'speaker': sp, 'raw': text,
                'canonical': matched['quote'] if matched else text,
                'chapter': matched['chapter'] if matched else None,
                'page': matched['page'] if matched else None,
                'match_score': matched['match_score'] if matched else None,
                'matched_from': 'script' if matched else 'none',
                'confidence': 'high' if matched else ('drama' if sp != '⚠待定' else 'low'),
                'mode': 'drama',
            })
            i = j
        else:
            i += 1
    return out


def is_drama_line(line: str) -> bool:
    """判定单行是否原剧台词（无引导语）。"""
    if len(line) < 4:
        return False
    # 吐槽特征 → 不是台词
    if any(line.startswith(s) for s in DRAMA_STOP):
        return False
    if any(s in line for s in COMMENT_SIGNALS):
        return False
    head = line[:4]
    # 口吻：第一人称/称谓/命令式开头
    if head[0] in ('我', '咱', '末', '臣', '你', '快', '请', '报', '禀', '遵', '领'):
        return True
    # 含原剧称谓（全段统计）
    if any(t in line for t in DRAMA_TERMS):
        return True
    return False


def infer_drama_speaker(seg: list[str], text: str) -> str:
    """从原剧片段推断说话人：段内/上文出现的角色名优先；自称称谓反推。"""
    # 段内直接出现的角色名（"孟德"→曹操 等别名也在 CHARACTERS）
    for name in CHARACTERS:
        if name in text:
            return CHARACTERS[name]
    # 自称反推：咱家→董卓；末将→未知武将；臣→大臣
    if '咱家' in text:
        return '董卓'
    return '⚠待定'


def parse_episode_drama(fn: str, script_quotes: list[dict]) -> tuple[list[dict], str]:
    """解析单期字幕的原剧台词片段 + up 主转述台词。"""
    with open(fn, encoding='utf-8') as f:
        lines = [l.strip() for l in f if l.strip()]
    fname = os.path.basename(fn)
    m = FILE_PAT.search(fname)
    ep_num = m.group('num') if m else '?'
    ep_title = m.group('title').strip() if m else fname[:30]

    # 1. 引导语模式（up 主转述）
    lead_quotes = parse_lead_quotes(lines, script_quotes, ep_num, ep_title)
    # 2. 原剧片段模式
    drama = extract_drama_lines(lines, script_quotes)
    for d in drama:
        d['episode'] = ep_num
        d['ep_title'] = ep_title
    return lead_quotes + drama, ep_title


def parse_lead_quotes(lines: list[str], script_quotes: list[dict], ep_num: str, ep_title: str) -> list[dict]:
    """引导语模式（up 主转述台词，如"曹操是这么说的"）。"""

    quotes_out = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = STRONG_LEAD.search(line)
        if not m:
            i += 1
            continue
        sp_raw = m.group('sp')
        # 修饰词拦截：说话人后面紧跟"按原着/刚刚"等 → 归属存疑跳过
        tail = line[m.end():]
        if any(tail.startswith(b) for b in LEAD_BLOCKERS):
            i += 1
            continue
        sp = CHARACTERS.get(sp_raw)
        if not sp or sp_raw in UP_VARIANTS:
            i += 1
            continue
        # 台词内容 = 引导语之后 + 后续行（到评论信号/换说话人）
        content = line[m.end():].strip()
        j = i + 1
        while j < n and len(content) < 120:
            nxt = lines[j]
            # 评论信号词开头 → 停（但要容忍台词自身的短句）
            if any(nxt.startswith(sig) for sig in COMMENT_SIGNALS):
                # 若当前已收集到足够台词（≥12字）则停；否则跳过该行继续（短评论夹在台词中）
                if len(content) >= 12:
                    break
            # 新引导语（换说话人）→ 停
            m2 = STRONG_LEAD.search(nxt)
            if m2 and CHARACTERS.get(m2.group('sp')) and CHARACTERS.get(m2.group('sp')) != sp:
                break
            content += nxt
            j += 1
        content = content.strip()
        if len(content) < 6:
            i = max(i + 1, j)
            continue
        # 台词特征校验：过滤吐槽/叙述句（如"董卓问曹操为什么来的这么慢"）
        if not is_speech_like(content):
            i = max(i + 1, j)
            continue
        # ASR 错字修正：与原著匹配
        matched = match_script(content, script_quotes) if script_quotes else None
        quotes_out.append({
            'episode': ep_num,
            'ep_title': ep_title,
            'speaker': sp,
            'raw': content,
            'canonical': matched['quote'] if matched else content,
            'chapter': matched['chapter'] if matched else None,
            'page': matched['page'] if matched else None,
            'match_score': matched['match_score'] if matched else None,
            'matched_from': 'script' if matched else 'none',
            'confidence': 'high' if matched else 'low',
            'mode': 'lead',
        })
        i = max(i + 1, j)
    return quotes_out


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    script_quotes = load_script_quotes()
    logger.info(f'原著台词库: {len(script_quotes)} 条')

    all_quotes = []
    ep_anchors = []
    files = sorted(os.listdir(SUBTITLE_DIR))
    parsed = 0
    for fn in files:
        if not fn.endswith('.txt'):
            continue
        path = os.path.join(SUBTITLE_DIR, fn)
        qs, title = parse_episode_drama(path, script_quotes)
        all_quotes.extend(qs)
        ep_anchors.append({'episode': qs[0]['episode'] if qs else '?', 'title': title, 'file': fn, 'quotes': len(qs)})
        parsed += 1
        if parsed % 50 == 0:
            logger.info(f'已解析 {parsed}/{len(files)}')

    # 输出引用库
    out_json = os.path.join(OUT_DIR, '台词引用库.json')
    with open(out_json, 'w', encoding='utf-8') as f:
        json.dump(all_quotes, f, ensure_ascii=False, indent=1)

    # 输出锚定清单
    out_md = os.path.join(OUT_DIR, '锚定场景清单.md')
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write('# 折棒锐评字幕 → 剧情锚定清单\n\n')
        f.write(f'> 共 {len(ep_anchors)} 期 | 台词引用 {len(all_quotes)} 条\n\n')
        f.write('| 期号 | 标题（梗点） | 台词数 |\n|------|--------------|--------|\n')
        for a in ep_anchors:
            f.write(f"| {a['episode']} | {a['title']} | {a['quotes']} |\n")

    # 统计
    matched = sum(1 for q in all_quotes if q['matched_from'] == 'script')
    high = sum(1 for q in all_quotes if q['confidence'] == 'high')
    logger.info(f'完成: {parsed} 期, {len(all_quotes)} 条台词, 原著命中 {matched} ({matched/max(len(all_quotes),1)*100:.0f}%), 高置信 {high}')
    logger.info(f'输出: {out_json}')
    logger.info(f'输出: {out_md}')


if __name__ == '__main__':
    main()
