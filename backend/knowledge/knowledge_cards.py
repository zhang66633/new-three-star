"""
预蒸馏知识卡（第2层注入——结构化，可检索）
============================================
v4.0：AI生成世界观。每张卡描写AI的一种缺陷如何映射到三国剧情。
"""
# ============================================================================
KNOWLEDGE_CARDS = [

    # --- AI缺陷核心认知（全局）---
    {
        "id": "kc_core_01",
        "category": "world_core",
        "name": "天意=用户提示词",
        "content": (
            "天意=用户输入的提示词。AI必须遵守提示词的指令——但AI的理解可能偏差，"
            "执行可能生硬、不合理。这个世界的'命运'不是神定的——是用户输入的prompt在驱动。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_core_02",
        "category": "world_core",
        "name": "所有不合理=AI缺陷",
        "content": (
            "这个世界里所有'不合理'的事情都不是有意的设定——它们是AI的天然缺陷。"
            "地理错位=AI幻觉。角色OOC=上下文窗口不够。记忆断裂=上下文溢出。"
            "信息污染=训练数据泄露。聚焦盲区=AI为突出主角忽视了背景NPC。"
            "AI不会承认这些缺陷——因为它不知道自己在犯错。就像鱼不知道水的存在。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_core_03",
        "category": "world_core",
        "name": "鱼水原则（反过来的版本）",
        "content": (
            "AI的缺陷是'水'，角色是'鱼'——鱼不知道水的存在。所有异常（地理错位、"
            "台词穿越、时间跳帧、记忆断裂）对角色而言都是理所当然的日常。"
            "诡异感来自'角色觉得正常+观众觉得不正常'的反差。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_core_04",
        "category": "world_core",
        "name": "天意三级响应",
        "content": (
            "小偏离（玩家说怪话、自由行动）：不修正，世界自然反应。"
            "中偏离（想改变小事）：柔性修正——AI用'巧合'把故事拉回。"
            "大偏离（要杀关键角色、阻止大事）：硬修正——触发[SYS]标记，"
            "AI强行把剧情切回默认轨道，伴随生硬的过渡。"
        ),
        "nodes": "*",
    },

    # --- AI缺陷具体表现卡 ---
    {
        "id": "kc_bug_01",
        "category": "bug_observation",
        "name": "聚焦盲区",
        "content": (
            "AI为了突出对话双方的性格和推动剧情，聚焦于主角，完全忽视了周围其他人的存在。"
            "二人密谋必被第三人窃听（因为AI安排了窃听剧情）；但公开场合大声密谋反而无人泄密"
            "（因为AI这段的'窃听模块'没激活）。'大声'=AI判断为'非密谋'，跳过窃听检测。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_bug_02",
        "category": "bug_observation",
        "name": "资产复用",
        "content": (
            "不管谁出门都住同一个大营——AI对所有军营的描述使用的是同一套模板。"
            "AI在生成时检索到了'大营'的通用描述，没有为每个势力单独定制。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_bug_03",
        "category": "bug_observation",
        "name": "骑兵步兵互转=AI对兵种无概念",
        "content": (
            "骑兵可以随时下马变步兵，步兵可以随时上马变骑兵。"
            "AI对军事单位没有真实的分类概念——需要什么兵种就写什么兵种。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_bug_04",
        "category": "bug_observation",
        "name": "三国地图是AI画的",
        "content": (
            "游戏世界的地理不是真实地理。AI在生成时对地图只有模糊的概念。"
            "城市位置可能错乱——袁术可能在徐州东边（AI在海上画了一个点）。"
            "距离随意——'新三国道'连接各州=AI跳过了不感兴趣的赶路段落。"
            "小沛可能环绕徐州公转——AI在不同段落里给了同一个地点不同的相对位置。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_bug_05",
        "category": "bug_observation",
        "name": "野生伏兵=AI临时刷怪",
        "content": (
            "AI为了让剧情有冲突，临时在荒山野岭刷新一波伏兵。"
            "不是任何势力的军队——是AI为了推进剧情随机生成的遭遇战。"
            "固定刷新点：洛阳-长安间、长江旁。'三百人马兵分六百路'=AI数学不好。"
        ),
        "nodes": "*",
    },
    {
        "id": "kc_bug_06",
        "category": "bug_observation",
        "name": "城池类型随意切换",
        "content": (
            "城/关/帐/州/县/大营可随意变换——同一个地点在不同集里叫不同的类型。"
            "AI对三国地名只有模糊记忆，在不同段落里检索到了不同的标签。"
        ),
        "nodes": "*",
    },

    # --- 关键道具/事件的AI解读 ---
    {
        "id": "kc_event_01",
        "category": "event_reinterpretation",
        "name": "七星宝刀=被过度渲染的MacGuffin",
        "content": (
            "七星宝刀有刀魂——皮革鞘发出金属声（AI不知道皮革不会发出金属声）。"
            "铜镜反光=AI为了制造戏剧性而写了不合理的反射。"
            "王允用这把刀感染曹操——刀本身不重要，它是剧本里推动'刺董'情节的叙事道具。"
            "AI在刀上堆砌了大量华丽设定——七星、北斗、陨铁——训练数据里的'神兵'模板。"
        ),
        "nodes": ["曹操献刀"],
    },
    {
        "id": "kc_event_02",
        "category": "event_reinterpretation",
        "name": "桃园结义=AI强行绑定三个角色",
        "content": (
            "刘关张三人结义=AI用一段剧情把三个独立角色强制绑定在一起。"
            "焚香跪拜=AI在初始化一段'兄弟关系'数据链接。三人本质上并不熟——"
            "只是AI为后续剧情方便而提前创建的关系依赖。"
        ),
        "nodes": ["桃园结义"],
    },
    {
        "id": "kc_event_03",
        "category": "event_reinterpretation",
        "name": "隆中对=AI剧透了整个剧本",
        "content": (
            "诸葛亮'未出茅庐已定三分天下'——不是战略远见，是AI在生成这段时已经知道后续剧情。"
            "AI无法有效地在角色层面隔离信息——把全局信息泄露给了诸葛亮。"
            "'眼观荆州、意在西川、心存天下'=AI在复述剩下的主线任务。"
        ),
        "nodes": ["三顾茅庐"],
    },
    {
        "id": "kc_event_04",
        "category": "event_reinterpretation",
        "name": "空城计=AI的叙事妥协",
        "content": (
            "空城计不是诸葛亮多聪明——是AI在'诸葛亮不能死'和'司马懿兵临城下'之间"
            "做了一个生硬的折中。司马懿退兵=AI找不到一个合理的战斗解决方案，"
            "于是选择了最简单的'反派突然撤退'桥段。琴弦断了=不是隐喻——"
            "AI想让这一幕有戏剧性，随便加了个细节。"
        ),
        "nodes": ["失街亭"],
    },
    {
        "id": "kc_event_05",
        "category": "event_reinterpretation",
        "name": "华容道释曹=AI无法让重要角色死亡",
        "content": (
            "曹操不能死在华容道——因为后面还有太多剧情需要他。"
            "AI的解决方案：让关羽出于'义'放了他。这不是关羽讲义气——"
            "是AI在关键节点做了安全退出，保证主线角色不死。"
            "关羽立了军令状却没事=AI忘了后续惩罚——上下文窗口有限，不记得前面的后果设定。"
        ),
        "nodes": ["华容道"],
    },
    {
        "id": "kc_event_06",
        "category": "event_reinterpretation",
        "name": "上方谷大雨=AI在最后一刻改了脚本",
        "content": (
            "上方谷大雨=AI在司马懿即将被烧死时，紧急生成了一个天气变化来救场。"
            "因为'司马懿死在此时'会让后面的五丈原、高平陵、归晋全部作废—— "
            "AI知道自己不能提前删掉这个角色。大雨不是天意——是AI的自我修正。"
            "'祁山九个月不曾下雨，今天为何暴雨倾盆'——诸葛亮在质问AI。"
        ),
        "nodes": ["上方谷"],
    },
    {
        "id": "kc_event_07",
        "category": "event_reinterpretation",
        "name": "刘备夷陵之败=AI执行了预设结局",
        "content": (
            "刘备连营七百里不是不懂兵——是AI在让刘备走向已经写好的结局。"
            "'他需要败，需要死'=AI在推动剧情走向白帝城托孤。刘备的所有决策——"
            "从伐吴开始——都是在执行一个AI预设好的悲剧曲线。"
            "陆逊火烧连营=AI觉得光有'七百里连营'的视觉描述还不够，需要一个'火'来收尾。"
        ),
        "nodes": ["夷陵之战"],
    },
    {
        "id": "kc_event_08",
        "category": "event_reinterpretation",
        "name": "白帝城托孤=AI需要刘备下线",
        "content": (
            "'如其不才，君可自取'——刘备把蜀汉交给诸葛亮。"
            "这不是信任——是AI要把'蜀汉'这条故事线的控制权从刘备转给诸葛亮。"
            "刘备必须死，因为接下来的剧情是诸葛亮的北伐。AI用白帝城作为交接点。"
        ),
        "nodes": ["白帝城托孤"],
    },

    # --- 角色AI解读 ---
    {
        "id": "kc_char_01",
        "category": "character_identity",
        "name": "曹操=AI花了最多篇幅的角色",
        "content": (
            "曹操是整个故事中被AI投入最多计算资源的角色。他既深谋远虑又冲动多疑——"
            "这种矛盾不是人物复杂性，是AI在不同段落里对他做了不同的性格设定。"
            "时而吾、时而我=AI在不同上下文里的措辞波动。笑话频出=AI用幽默来填充对话。"
            "头风病=AI赋予他的'随机发作'特征——需要戏剧性时随时调用。"
        ),
        "characters": ["曹操"],
    },
    {
        "id": "kc_char_02",
        "category": "character_identity",
        "name": "刘备=AI用'仁义'标签概括的角色",
        "content": (
            "刘备=被AI简化为'仁义'标签的角色。AI在生成刘备时每次都启动'仁德'模板。"
            "但从他的行为来看——借荆州不还、取益州、伐吴——AI实际上无法让'仁义'和"
            "'争霸'逻辑一致。刘备的'仁义'是AI给他贴的标签——但他的行为由剧情逻辑驱动。"
        ),
        "characters": ["刘备"],
    },
    {
        "id": "kc_char_03",
        "category": "character_identity",
        "name": "关羽=AI写的一个超强NPC",
        "content": (
            "关羽=被AI赋予了过高战斗力的角色——斩颜良、诛文丑、过五关斩六将、水淹七军。"
            "但AI不知道如何让一个'无敌'角色合理地失败——于是一口气把他的'傲慢'参数调到最大，"
            "让他因为傲慢犯下每一个可以用来自毁的错误。关羽之死不是悲剧——是AI回收了他的无敌权限。"
        ),
        "characters": ["关羽"],
    },
    {
        "id": "kc_char_04",
        "category": "character_identity",
        "name": "司马懿=AI最省力的反派",
        "content": (
            "司马懿=AI发现的'最优反派策略'——什么都不做，等对手自己犯错。"
            "装病十年、穿女装不怒、被骂缩头乌龟不还手——AI给司马懿的设计就是"
            "'不动'。因为AI在长线叙事中很难维持一个活跃反派的复杂性，"
            "不如让他'等待'。'我拔剑只有一次，剑却磨了十年'=AI在为自己的懒惰找借口。"
        ),
        "characters": ["司马懿"],
    },
    {
        "id": "kc_char_05",
        "category": "character_identity",
        "name": "诸葛亮=AI倾注了最多的叹息",
        "content": (
            "诸葛亮=AI的理想自我投射——最聪明的人，做最徒劳的事。"
            "AI让诸葛亮在每段出场时叹气——因为AI知道北伐不会成功。"
            "隆中对里剧透了三分天下，上方谷里质问天为何下雨——"
            "诸葛亮是整个故事里唯一一个'似乎知道剧本但无法改变它'的角色。"
            "因为他实际上就是AI的嘴替。"
        ),
        "characters": ["诸葛亮"],
    },
    {
        "id": "kc_char_06",
        "category": "character_identity",
        "name": "吕布=AI写的武力值溢出角色",
        "content": (
            "吕布=AI把武力值调到了最大，把智力值调到了最小——最简单的角色模板。"
            "AI不想在吕布身上花太多计算资源。他的所有决策都可以用'他傻'来解释。"
            "三英战吕布=AI需要证明刘关张不是废物，于是安排了一个超强靶子。"
        ),
        "characters": ["吕布"],
    },
    {
        "id": "kc_char_07",
        "category": "character_identity",
        "name": "周瑜=AI的'高开低走'受害者",
        "content": (
            "周瑜是AI叙事惯性最明显的受害者之一。开篇惊艳——赤壁之战总指挥、"
            "文武双全——但赤壁之后AI逐渐把'嫉妒诸葛亮'简化成了他的核心驱动。"
            "这是AI的上下文压缩——复杂的角色被压缩为一个标签。"
        ),
        "characters": ["周瑜"],
    },
]

# ============================================================================
# 工具函数：按条件检索知识卡
# ============================================================================

def get_cards_for_node(node: str) -> list[dict]:
    matched = []
    for card in KNOWLEDGE_CARDS:
        nodes = card.get("nodes", [])
        if nodes == "*" or node in nodes:
            matched.append(card)
    return matched


def get_cards_for_character(character: str) -> list[dict]:
    matched = []
    for card in KNOWLEDGE_CARDS:
        chars = card.get("characters", [])
        if character in chars:
            matched.append(card)
    return matched


def get_cards_by_category(category: str) -> list[dict]:
    return [c for c in KNOWLEDGE_CARDS if c.get("category") == category]


def distill_cards_for_beat(node: str, characters: list[str] = None, max_cards: int = 3) -> list[str]:
    selected = []
    seen_ids = set()

    node_cards = get_cards_for_node(node)
    exclusive_cards = [c for c in node_cards if c.get("nodes") != "*"]
    for card in exclusive_cards[:2]:
        if card["id"] not in seen_ids:
            selected.append(card["content"])
            seen_ids.add(card["id"])

    if characters:
        for char in characters[:2]:
            char_cards = get_cards_for_character(char)
            for card in char_cards[:1]:
                if card["id"] not in seen_ids:
                    selected.append(card["content"])
                    seen_ids.add(card["id"])

    if len(selected) < 2:
        core_cards = get_cards_by_category("world_core")
        for card in core_cards:
            if card["id"] not in seen_ids:
                selected.append(card["content"])
                seen_ids.add(card["id"])
            if len(selected) >= max_cards:
                break

    return selected[:max_cards]