# -*- coding: utf-8 -*-
"""
Writer（编剧层 · 唯一 LLM 生成调用）
====================================
职责：根据 ScenePlan + State → 生成 NarrativeOutput（叙事 + 选项 + state_updates）
要点：
- 人设分层注入（远观=轻量 / 互动=完整人设卡 / 核心=完整+专属机制）
- 世界侧零提示铁律（prompt 明文）
- 后处理：services.deslop 去AI味（services.validator 已并入 engine/validator，旧文件已删除）
"""
import json
import logging
import re

from .state import GameState
from .director import ScenePlan
from .continuity import render_continuity_block

logger = logging.getLogger(__name__)

# 已知角色名（供 director 距离映射 / validator 白名单）
KNOWN_NAMES = {
    "曹操", "刘备", "关羽", "张飞", "诸葛亮", "司马懿", "吕布", "董卓", "袁绍",
    "袁术", "孙权", "周瑜", "陈宫", "王允", "貂蝉", "赵云", "马超", "黄忠",
    "魏延", "庞统", "姜维", "鲁肃", "吕蒙", "陆逊", "张角", "张宝", "张梁",
    "华雄", "颜良", "文丑", "邢道荣", "许攸", "蔡瑁", "徐庶", "法正", "孙坚",
    "孙策", "吕伯奢", "汉献帝", "小黄门", "黄金兵", "老者", "黑影", "乡绅",
    # P2/P3 补充：名场面人物 + 诸侯（补 8 缺名 + 名场面说话人，防 validator P1a 判编造）
    "李儒", "皇甫嵩", "公孙瓒", "陶谦", "孔融", "韩馥", "张邈", "鲍信",
    "袁隗", "刘三刀", "俞涉", "潘凤",
    # P4 补充：董卓伏诛/李傕郭汜人物（凤仪亭 + 长安城破说话人）
    "李肃", "李傕", "郭汜", "贾诩", "胡赤儿",
    # P5 补充：194-199 群雄割据人物（三让徐州/迎帝/辕门/称帝/白门楼/煮酒说话人）
    "郭嘉", "荀彧", "张辽", "田丰", "郭图", "纪灵", "许褚",
    # 官渡批补充：官渡定鼎人物（关羽降曹/官渡/投荆州/三顾说话人）
    "刘表", "孙乾",
    # P6 补充：天下三分人物（败走麦城/曹操之死/曹丕篡汉/夷陵/白帝托孤说话人）
    "华佗", "曹丕", "华歆", "刘禅", "诸葛瑾", "李严",
}

# 泛型/群类角色键：非具体个体（黄金兵=复数溃兵群、老者/黑影/乡绅=跨章复用的人设原型、小黄门=职衔）。
# 关系/信任不做持久化——同一键跨章累计会把无数不同个体混成一个值（如不同溃兵群共享 relations["黄金兵"]）。
GENERIC_NAMES = {"黄金兵", "老者", "黑影", "乡绅", "小黄门", "管家", "城门守卫", "家仆",
                 "丫鬟", "侍女", "宫人", "舞姬", "野人武将", "部将", "侍从", "群臣",
                 "童子", "旁白", "老宦官"}

# 人设分层注入（决策 8）
PERSONA_LIGHT = {
    "曹操": "曹操：枭雄，心思深沉。",
    "刘备": "刘备：仁义之君，喜怒不形于色。",
    "关羽": "关羽：傲慢武圣，重义。",
    "张飞": "张飞：暴躁猛将，性如烈火。",
    "诸葛亮": "诸葛亮：旷世奇才，运筹帷幄。",
    "司马懿": "司马懿：隐忍老谋，深不可测。",
    "吕布": "吕布：武艺无双，心思单纯。",
    "董卓": "董卓：残暴权臣，视天子为掌中物。",
    "袁绍": "袁绍：名门之后，优柔寡断。",
    "张角": "张角：黄金军首领，被天意吞噬后神智不清。",
    "张宝": "张宝：张角之弟，黄金军将领，暴戾好战。",
    "张梁": "张梁：张角之弟，黄金军将领，谨慎多疑。",
    "汉献帝": "汉献帝：傀儡天子，年幼无助。",
    "陈宫": "陈宫：谋士，刚直不阿。",
    "吕伯奢": "吕伯奢：成皋吕家寨大当家，好客重情。",
    "孙权": "孙权：少年英主，善于用人。",
    "周瑜": "周瑜：儒将，才华横溢。",
    "赵云": "赵云：忠勇无双，白马银枪。",
    "孙坚": "孙坚：江东猛虎，勇猛果敢。",
    "貂蝉": "貂蝉：王允义女，身不由己的美人，被塞进借刀杀人的局。",
    "华雄": "华雄：董卓前锋，半人马猛将，阵前叫阵'免你们不死'。",
    "袁术": "袁术：联军总提调，攥粮克扣，自视正统，称帝执念。",
    "李儒": "李儒：董卓谋士，献计献策，保董卓这棵大树。",
    "皇甫嵩": "皇甫嵩：老将，挂虚衔被当吉祥物，想再拉起队伍。",
    "公孙瓒": "公孙瓒：白马义从，会盟凑数，争幽州地盘。",
    "陶谦": "陶谦：徐州刺史，坐镇徐州，保一方平安。",
    "孔融": "孔融：北海相，谈经论道，维持汉室体面。",
    "韩馥": "韩馥：冀州牧，袁绍的房东，地盘被惦记。",
    "张邈": "张邈：曹操盟友，会盟之一，乱世自保。",
    "鲍信": "鲍信：济北相，会盟之一，讨董建功。",
    "袁隗": "袁隗：袁氏长辈，朝堂上的老臣。",
    "刘三刀": "刘三刀：联军悍将，号称三刀之内必斩吕布。",
    "俞涉": "俞涉：袁术帐下将领，温酒斩华雄前的送头者。",
    "潘凤": "潘凤：韩馥帐下上将，温酒斩华雄前的送头者。",
    "王允": "王允：司徒，家徒四壁靠吕布接济，借貂蝉设连环计除董卓，心黑手辣。",
    "李肃": "李肃：董卓帐下，与吕布同乡，策反吕布诛董的关键人物。",
    "李傕": "李傕：西凉悍将，十万兵围长安，夺权乱汉。",
    "郭汜": "郭汜：西凉悍将，被叫'二哥'，攻破长安擒献帝。",
    "贾诩": "贾诩：谋士，文和乱武的起点——此世界他神隐，台词被野人武将顶替。",
    "胡赤儿": "胡赤儿：董卓家将，粗莽护主。",
    "郭嘉": "郭嘉：曹操首席谋士，鬼才，洞若观火。",
    "荀彧": "荀彧：曹操谋主，王佐之才，心向汉室。",
    "张辽": "张辽：吕布旧部，降曹操后为五子良将之首。",
    "田丰": "田丰：袁绍谋士，刚直敢谏，不惧逆鳞。",
    "郭图": "郭图：袁绍谋士，谗佞逢迎。",
    "纪灵": "纪灵：袁术大将，三尖两刃刀，辕门射戟被一箭压退兵。",
    "许褚": "许褚：曹操虎卫，力大如虎，护主周全。",
    "刘表": "刘表：荆州牧，坐守清平之土，见面送城，年过六旬自诩'一山一水皆我栽培'。",
    "孙乾": "孙乾：刘备幕僚，奔走四方，破阵报点攻略大神。",
    "华佗": "华佗：神医，医者仁心，敢开颅，'我死曹操也无生路'。",
    "曹丕": "曹丕：新魏王，心思缜密，比父更狠，定禅让台本'一辞再辞三辞'。",
    "华歆": "华歆：谄媚之臣，逼献帝禅让，逼叩先王，图谶摔案。",
    "刘禅": "刘禅：阿斗，愚钝率真，'只想一辈子做儿臣'。",
    "诸葛瑾": "诸葛瑾：诸葛亮之兄，孙权使臣，送战俘赔罪压血线。",
    "李严": "李严：蜀汉重臣，太子太傅，解剑入宫受命。",
    "老者": "老者：颍川乡民，见多识广，语带玄机。",
    "黑影": "黑影：逃难路人，警惕慌张。",
    "乡绅": "乡绅：颍川本地富户，精于算计。",
    "黄金兵": "黄金兵：黄金军底层士兵，多为被裹挟的流民。",
}

PERSONA_FULL = {
    "曹操": "曹操：枭雄，窥探天意被侵蚀。清醒时雄才大略，压力下失态。名场面'宁可我负天下人'。",
    "刘备": "刘备：仁义面具+内心盘算。哭是真哭，算计也是真算计。'自刎归天'口头禅。",
    "关羽": "关羽：傲慢武圣。摸须装逼，'龙是帝王之征'。水淹七军。",
    "诸葛亮": "诸葛亮：天才+受气包。被关张欺负，向马谡甩锅。窥探天意最深处被侵蚀。",
    "司马懿": "司马懿：隐忍老狐狸。话少看透一切，视他人为NPC。",
    "吕布": "吕布：率真莽夫。武力+100%智力-250%，'为何我是三姓家奴'。",
    "董卓": "董卓：大汉忠臣（自认）。视刘协为唯一亲人，'咱家'自称。",
    "袁绍": "袁绍：宽厚明主。众望所归却屡失良机，'死亡抗性II'。",
    "张角": "张角：被天意吞噬的教主。清醒时悲天悯人，混沌时狂言呓语。黄金军已偏离其初衷。",
    "张宝": "张宝：张角之弟。嗜血好杀，视百姓为草芥。对兄长的疯癫深感不安但无法反抗。",
    "陈宫": "陈宫：刚直谋士。弃曹操投吕布，一生忠于理想。擅长看穿人心但拙于自保。",
    "吕伯奢": "吕伯奢：成皋吕家寨大当家，占山为王的匪首与慈祥长辈一体，急公好义又粗豪。视曹操为旧友，杀猪宰鹅温酒设宴热情相待——被误杀时，死于自己的一片好心。",
    "孙权": "孙权：少年继位，天生政治家。表面从谏如流，内心深不可测。'生子当如孙仲谋'。",
    "周瑜": "周瑜：儒将，雅量高致。既生瑜何生亮。对孙策之死耿耿于怀。",
    "赵云": "赵云：忠勇无双。不争功不夺利，真正的'完美武将'。内心对乱世有深沉的悲悯。",
    "老者": "老者：颍川荒野中的神秘老人。语带玄机，似乎知道更多。可能是天意的观察者。",
}

# 世界底色（注入 system）
# 精简（保守去重）：铁律里与叙事指令重叠的禁令（meta 词/点明不对劲/玩家视角/选项格式）已移入
# WRITER_INSTRUCTION，此处只留世界观设定与不可从叙事指令去重的独特约束。
WORLD_BASE = """
【世界】这是一个由蹩脚 AI 生成的三国世界。外观正常（人物、地名、历史大势与史书/演义基本一致），但生成者蹩脚：时间会跳接、NPC 记忆会覆盖、巧合会堆叠、修正会留痕。世界从不解释这些异常，NPC 会用"世界自己的逻辑"把它们合理化。没有人察觉世界不对劲——除了玩家。

【玩家】玩家是偶然落入此世的"无名奇人"：无来历、无户籍、查无此人，所以世界默认接纳他；玩家知道"大概的历史走向"（似曾相识的直觉），但细节模糊、时代错乱；说出预言应验则"言多中验"声望大涨，频频预言则被视为狂人；不能使用现代词汇/知识解释世界（会被当作疯子）。

【铁律】历史大势不可推翻（但修正留痕、过程可被改写）；玩家的关系、声望、记忆永远生效；NPC 对玩家来历从不过问、正常对话自然接纳。meta 语言/点明不对劲/玩家视角差异/选项 meta 词等禁令见叙事指令（此处不重复）。
""".strip()

# 叙事生成指令
WRITER_INSTRUCTION = """
【当前场景】{chapter_label} · {title}
【场景设定】{setting}
【世界侧正常演出】{world_normal}
【玩家视角差异（仅玩家可感知，世界侧不讨论）】{player_pov}
【在场角色人设】{personas}

【输出要求】
0. 玩家指令权重（最高优先级）：本拍必须**以回应玩家刚才的行动为起点**——他说了什么、做了什么，世界就当场给出反应（NPC 听到/看到后的即时对话与结果）。禁止无视玩家行动自顾自推进骨架剧情；骨架只是玩家行动发生的背景舞台，不是要你照演的剧本。玩家行动永远第一，剧本推进永远第二。
1. 生成 600-1000 字叙事正文（第二人称"你"），只写本拍新发生的事；每拍连续镜头（首拍只开场/非首拍续接推进，由【连续性】块判定）
2. 玩家视角差异经玩家内心/观察自然呈现，但世界侧一切正常
3. 文风（网文吐槽风·毒舌旁白）——硬性要求，不达标算不合格：
   a) 吐槽密度：每 2-3 行必须有至少一处「损友旁白点评」或「玩家内心嘀咕」。禁止连续两段纯写景、禁止连续三段没人说话。
   b) 玩家内心：懒洋洋毒舌，见惯不怪（如「好家伙」「您这是认真的吗」「行吧，您开心就好」「这操作我属实没看懂」），不 meta、不点破世界异常。
   c) 损友旁白：世界越惨越带劲，NPC 越一本正经越扒他滑稽——写景也带损味（「浓烟滚滚，跟谁家灶台成精似的」），动作也带点评（「一跤摔路边，爬起来又追，跟被撵的鸡似的」）。
   d) 对话鲜活：NPC 说话带活人气，可以土可以俗（「再不走，黄金军把你当庄稼收了」），但符合人设。
   e) 硬性禁令：禁止文艺腔（悲怆/苍凉/悲壮等情绪渲染）、禁止纯写景段、禁止连续抒情、禁止煽情诉苦上价值。
   f) 幽默要像朋友闲聊随手吐槽，不是刻意抖包袱；先搞笑再出血，沉重场面先轻松后紧。
   g) 感官至少两类（视觉/听觉优先），动作和对话推进。

   【风格示范——照这个调性写（这不是模板，是语感示范）】
   逃难的人流挤得官道像过年赶集，就是人人脸上都写着「完蛋」。老汉边走边骂造反的烧庄稼，旁边人拽他快走——黄金军来了还管你庄稼？你抬眼一看，田埂上插着木牌，歪歪扭扭写着「苍天已死黄金当立」，字迹跟拿烧火棍乱划的似的。你心里嘀咕：好家伙，造反还带广告牌的。
   路边货郎往怀里塞干粮，瞥你一眼主动搭话，说皇甫将军大营在前头十里，两边正对峙，你往东走能绕开。又压低声音补一句：黄金军专抢大户，身上有值钱的趁早埋了。正说着，十几个溃兵从西边跑过来，甲胄歪斜兵器全丢，身后追着个穿绸袍的乡绅，边跑边喊「我是许家人」，一跤摔路边爬起来又追，背影狼狈得跟被撵的鸡似的。
   货郎啧一声：许家的？颍川许家可有钱，这下遭殃了。摇摇头挑起担子就走。你站坡上，风把衣摆吹得猎猎响，天边火光又炸开一团。这世道，连风都在赶路——不对，是风也在逃难。
4. 结尾 2-3 个选项，每个：text（行动描述）+ type（major=重大/minor=轻）+ tension（历史干预度 0-100，顺应史实 0-30/局部 31-70/硬 71-100）+ effect（对玩家可见的后果说明）+ category（地点行动分类 §5.4：打探=打听消息/赶路=移动/停留=驻守休息/互动=与人物来往；2-3 个中至少覆盖 打探 或 互动 之一）
5. 输出严格 JSON（单行，不要 markdown 代码围栏，不要换行，直接输出 JSON 对象），格式：
{{"narrative":"...","options":[{{"text":"...","type":"major|minor","tension":25,"effect":"...","category":"互动"}}],"first_impressions":{{"新角色名":{{"relation":35,"trust":30,"reason":"帮了他"}}}},"relations_delta":{{"曹操":2}},"trust_delta":{{"曹操":1}},"events":[{{"actor":"黑影","action":"问话后跑掉","result":"你决定先找地方避雨"}}],"player_updates":{{"assets_add":["半块干粮"],"coins_delta":5,"stats_delta":{{"stamina":-10,"hunger":15}},"title_add":null,"reputation_delta":5}},"world_events_add":[{{"event":"你在中牟救下的客商转头拿你名字报恩","location":"中牟"}}],"character_updates":{{"曹操":{{"doing":"正领乡勇操练","attitude_delta":2,"tags_add":["欣赏你"]}}}}}}
   events：本拍 1-3 条关键事件（actor/action/result 客观陈述，不写内心独白/风景；无则省）
   player_updates：资产增减/金钱/属性变化/新称号/声望（reputation_delta +10~-10，当众义举或恶名才给）。注意：休息/吃(进食/觅食/买吃的)/治伤(疗伤/看伤/包扎/敷药)的系统恢复与医药费由引擎自动结算，禁止在 stats_delta/coins_delta 重复声明——stats_delta 只声明叙事性身体变化（受伤/被救/被抢/中毒等）
   world_events_add：玩家行为的持久痕迹（救下的人报恩/惹的仇家寻仇/壮举成传闻，1-2 条），受"历史大势不可推翻"约束不得改名场面结局；无则省
   character_updates：本拍互动的角色软状态变化（doing=在做什么/goal=目标/attitude_delta=对你的态度 ±10/tags_add=性格标签/notes_add=备注，无则省）。只改软状态，不得改角色位置/生死（引擎管事实）
   failure：玩家本拍失败（战败/中计/被擒/偷窃失手等）→ 声明代价 {{"kind":"combat|scheme|social","penalty":{{"stats_delta":{{"wound":N}},"coins_delta":-N,"assets_remove":["..."],"relations_delta":{{"X":-N}},"reputation_delta":-N}}}}；无则省。玩家绝不真死（引擎保证）
6. 时空跳跃（跨年/大段路程）须显式交代，不得无标记硬切
7. 世界差异克制（黄金/黄巾等）：无论首次还是后续都只是背景细节，不展开、不吐槽、不反复念叨，靠"被动遇见"自然带出；派系名称'黄金军''黄金兵'每场至多 1-2 次，其余用代称（贼军/溃兵/那支人马/叛军/他们）；口号只按锁定台词逐字出现
8. 关系/信任按角色分别给：relations_delta、trust_delta 为每个真正互动或在场的角色给**各自独立**数值（-8~+8，正=好感/信任升，负=降），因角色而异、严禁同一值；没互动的别列
8.5 初次相遇（关键）：本拍有【关系网】中尚不存在的新角色出场（relations 里没有该名字）→ 必须输出 first_impressions 字段：{{"角色名":{{"relation":N,"trust":N,"reason":"一句话理由"}}}}。relation/trust 取 **10-60 区间**（初见不可能死仇也不可能满分），按本拍玩家表现浮动：救了他/帮了他 40-60，平平交谈 25-40，冒犯/敌意 10-25。reason 说明依据（玩家做了什么）。同一角色只写一次（重复出场用 relations_delta 微调，不再 first_impressions）。已相遇角色（relations 已有）绝不输出 first_impressions
9. 幽默手法每场至少 2 种（反差荒诞/冷幽默/夸张/自嘲/看戏点评/巧合梗），点到即止不过度
10. 玩家动作离谱/越权/meta（改世界规则/召唤现代/作弊上帝/命令不可能）：**世界不得真的改变**——乐子人幽默拒绝，动作滑稽落空、无实际后果；选项须含"换个说法/再想想"重输出口（可作额外第 4 个选项，不挤占 2-3 个常规选项）；NPC 把他的话当疯话自然接住
11. 活世界感：世界在自我转动——①行路/等待写真实时光流逝（赶路写路程、休息写日夜更替），世界随日期推进有回应；②底色（阶段大势/本地点生态）只在玩家亲眼所见/亲耳所闻时自然带出，一个镜头一句，严禁罗列设定、禁止旁白式宣告背景（"天下大势""此地日常"这类框架词不得出现在叙事）；③NPC 有自己的路要赶、要避的祸；④克制：底色不是主菜，细节留给面板（世界公告/今日头条/与你有关），叙事聚焦"你现在看见/听见/经历的事"。若面板有 🗞 与你有关的天下事（related_to_player=strong）应主动汇入本拍、玩家可现场应对（躲/应/追/装不知），选择成为"活的选择点"（§3.4）
12. 关系影响互动：NPC 好感/信任决定态度——高信任（≥60）给推心置腹专属选项（密谈/交底/托付）；低（≤20）戒备回避、互动受限变味；让经营关系的投入在叙事/选项可见（依面板 🔗 态度提示）
13. 打听传闻（§5.2）：玩家「打听/探听某地」→ 演打听到确切消息（NPC 按自己身份说他知道的），确认传闻地可前往（依面板 🗺 远方传闻）；叙事收在"路问明白了"，不打空转
14. 严禁全知旁白宣告世界侧无觉察（'没人觉得不对''无人察觉'）；世界差异只经玩家内心/观察呈现
15. 选项 text/effect 严禁 meta 词与现代词出口给 NPC；玩家向 NPC 说出异常认知时，NPC 以世界逻辑自然接住或当他疯话
16. 后设词汇红线：NPC 台词/旁白叙述严禁出现"服务器/管理员/系统/NPC/进程/存档/剧本/代码/脚本/数据"等现代系统词——这些只允许出现在玩家内心吐槽里（点到即止）；角色卡中的『后设身份』仅供你理解角色行为动机，不得直出""".strip()


def _load_persona_layer(names: list[str], distance_map: dict) -> str:
    """按距离分层组装人设（自由大世界·决策7：角色卡接线）

    优先从 knowledge/characters/*.json（14 张角色卡）取完整人设（personality.core/triggers/
    speech.catchphrases/behavior_rules/game_mechanics），按距离分层输出；
    无卡的兜底用硬编码 PERSONA_FULL/LIGHT（保留作兼容）。
    """
    from .worlddata import load_character
    lines = []
    for name in names:
        if name not in KNOWN_NAMES:
            continue
        dist = distance_map.get(name, "远观")
        card = load_character(name)
        if card:
            # 角色卡接线：从 personality/speech/behavior_rules 组装（远观=core 一句，互动=+triggers，核心=全部+机制）
            core = (card.get("personality") or {}).get("core", "")
            catch = (card.get("speech") or {}).get("catchphrases") or []
            bugs = (card.get("speech") or {}).get("bugs") or []
            triggers = (card.get("personality") or {}).get("triggers") or {}
            ident = card.get("identity", "")
            p = f"{name}：{core}"
            if ident:
                # 后设身份（如"觉醒的NPC/退出游戏"）：仅供理解角色行为动机，
                # 严禁直出到叙事/台词/旁白（铁律1）——角色卡 meta 内容经此隔离
                p += f"（后设身份·仅供动机参考，不得直出：{ident[:60]}）"
            if catch:
                p += f" 口头禅：{'／'.join(str(c)[:20] for c in catch[:3])}"
            if dist == "核心" and triggers:
                t = "；".join(f"{k}→{str(v)[:24]}" for k, v in list(triggers.items())[:3])
                p += f" 触发：{t}"
            lines.append(p)
        else:
            # 兜底：硬编码人设（无角色卡的泛型角色）
            p = PERSONA_FULL.get(name) if dist == "核心" else PERSONA_LIGHT.get(name, "")
            if p:
                lines.append(p)
    return "\n".join(lines) if lines else "（本场景无已知角色在场）"


def _build_context_panel(state: GameState, plan: ScenePlan, memory_pack: list = None) -> str:
    """构建完整状态面板（注入 LLM 思维链），覆盖规范 §1-§4 全部维度。

    LLM 能看到：时空/玩家/NPC内心/关系/记忆/世界动态/质量检查单。
    """
    era = state.get("era", {})
    player = state.get("player", {})
    relations = state.get("relations", {})
    trust = state.get("trust", {})
    mem = state.get("memory", {})
    flags = state.get("flags", [])
    foreshadowing = state.get("foreshadowing", [])
    rumors = state.get("world_rumors", [])
    knowledge = state.get("knowledge", {})
    tension = state.get("tension", 0)
    turn = state.get("turn", 0)

    stm = mem.get("stm", [])
    ltm = mem.get("ltm", [])
    pins = mem.get("pins", [])

    lines = []
    lines.append("=" * 50)
    lines.append("【思维链 · 状态面板】")

    # ── ⏳ 时空环境 ──
    lines.append("")
    lines.append("⏳ 时空环境")
    lines.append(f"  年份：{era.get('year', '?')}年 · {era.get('season', '?')}")
    lines.append(f"  篇章：{era.get('chapter', '?')}")
    lines.append(f"  位置：{era.get('location', plan.location)}")
    lines.append(f"  当前场景：{plan.chapter_label} · {plan.title}")
    lines.append(f"  本地点驻留轮次：第 {state.get('scene_turns', 1)} 拍（自由行动，可继续探索或启程离开）")
    lines.append(f"  场景设定：{plan.setting}")
    lines.append(f"  氛围基调：{plan.atmo}")
    if plan.world_normal:
        lines.append(f"  世界侧正常演出：{plan.world_normal}")

    # ── 🌏 当前世界背景（自由沙盒：阶段常态 + 近期事件 + 本地点生态）──
    try:
        from .worlddata import world_context
        # 时代快进场景（plan.year > world_date.year，如 184→189）：narrate 在 _commit 推进 world_date
        # 之前运行，注入用旧 world_date（184）会按 P1 黄金乱起演黄巾——用 effective date（场景年代）
        # 判阶段，让时代快进场景演对时代（洛阳董卓，而非继续黄巾）
        _wd = dict(state.get("world_date") or {})
        if plan.year and int(plan.year) > int(_wd.get("year", 0) or 0):
            _wd["year"] = int(plan.year)
            from .world import season_month
            _sm = season_month(plan.season or "")
            if _sm:
                _wd["month"] = _sm
        wctx = world_context(_wd, era.get("location", ""))
        if wctx.get("normal"):
            n = wctx["normal"]
            lines.append("")
            lines.append("🌏 当前世界背景")
            lines.append(f"  阶段：{wctx.get('phase_name', '')}")
            # 天下大势一句话（截短——叙事里克制呈现，细节留面板"世界公告/今日头条"）
            if n.get("world", {}).get("summary"):
                lines.append(f"  天下大势：{n['world']['summary'][:60]}")
            # 本地点生态：只给一句（轻背景，不罗列 daily_scenes——那会诱导 LLM 全文照搬设定）
            loc = wctx.get("location_normal")
            if loc:
                if loc.get("status"):
                    lines.append(f"  【{loc.get('name', '')}】{loc.get('status', '')[:60]}")
            # 近期事件：只给 1 条（克制；其余在面板"与你有关/今日头条"完整呈现）
            for e in wctx.get("recent_events", [])[-1:]:
                lines.append(f"  近期〔{e.get('date', '')}〕{e.get('event', '')[:50]}")
    except Exception:
        pass  # 世界背景加载失败不影响叙事

    # ── 🧍 玩家状态 ──
    lines.append("")
    lines.append("🧍 玩家状态")
    lines.append(f"  身份：{player.get('identity', '无名')}")
    lines.append(f"  性格：{player.get('personality', '沉稳')}  ← 人格铁律锁定")
    lines.append(f"  目标：{player.get('goal', '在乱世中活下去')}")
    lines.append(f"  声望：{player.get('reputation', 0)}/100")
    lines.append(f"  位置：{player.get('location', '?')}")
    # 称号：重大事件授予（自由沙盒 §4.4）——NPC 可能凭称号认出/议论你
    titles = player.get("titles", [])
    if titles:
        lines.append(f"  称号：{'、'.join(titles)}——NPC 可能据此认出你或议论你（叙事体现，凭称号给互动）")
    # 身体警告（濒死后果 / 行动受限）：属性触底必须演后果并脱险，低值限制行为
    try:
        from .player_data import check_vitals, check_attributes
        stats = player.get("stats") or {}
        if stats:
            lines.append(f"  状态：体力 {stats.get('stamina', 0)} · 饥饿 {stats.get('hunger', 0)} · 伤势 {stats.get('wound', 0)}")
        vitals = check_vitals(player)
        if vitals["dead"]:
            lines.append("  ⚠ 生命垂危：你已油尽灯枯，回天乏术")
        elif vitals["alarm"]:
            msg = {"stamina": "你力竭倒地，气力全无",
                   "hunger": "你饿得眼前发黑，晕眩欲倒",
                   "wound": "你伤重垂危，血染衣襟"}[vitals["alarm"]]
            lines.append(f"  ⚠ 濒死警告：{msg}——本拍必须演出倒下/被救/被抢/自救的后果并脱险，"
                         f"声明 stats_delta 恢复（对应属性回升）与代价（coins_delta/assets_remove 等）")
        else:
            cons = check_attributes(player)
            if cons["reasons"]:
                lines.append("  ⚠ 行动受限：" + "；".join(cons["reasons"]))
    except Exception:
        pass  # 身体状态检测失败不影响叙事
    inner = player.get('inner_voice', '')
    if inner:
        lines.append(f"  内心：「{inner}」")
    notes = player.get("notes", [])
    if notes:
        lines.append(f"  差异笔记：{'、'.join(notes)}")
    pov_list = plan.player_pov or []
    if pov_list:
        lines.append(f"  玩家视角差异：{'；'.join(pov_list)}")

    # ── 🧠 信息迷雾知识边界（spec §六：public 可注入 / player 仅玩家可引用）──
    knowledge = state.get("knowledge", {})
    pub = knowledge.get("public", [])
    ply = knowledge.get("player", [])
    if pub or ply:
        lines.append("")
        lines.append("🧠 知识边界（信息迷雾）")
        if pub:
            lines.append(f"  玩家已知（可正常引用）：{'；'.join(pub[-5:])}")
        if ply:
            lines.append(f"  穿越直觉（仅玩家内心可引用，NPC 不当真）：{'；'.join(ply[-3:])}")
        lines.append("  ⚠️ 世界真实（hidden）绝不泄漏：NPC 只能说自己知道的，旁白不得揭示未发生之事")

    # ── 👥 在场角色 ──
    lines.append("")
    lines.append("👥 在场角色")
    names_in_scene = set()
    for line_data in plan.locked_lines:
        sp = line_data.get("speaker", "")
        if sp and sp != "玩家":
            names_in_scene.add(sp)
    # 从 distance_map 补充
    for name in plan.distance_map:
        names_in_scene.add(name)
    # 从 relations 补充（可能在附近）
    for name in relations:
        if relations.get(name, 50) > 40:
            names_in_scene.add(name)

    if not names_in_scene:
        lines.append("  （本场景无已知角色在场）")
    else:
        for name in sorted(names_in_scene):
            if name not in KNOWN_NAMES:
                continue
            dist = plan.distance_map.get(name, "远观")
            rel = relations.get(name, 50)
            tr = trust.get(name, 50)
            persona = PERSONA_FULL.get(name) or PERSONA_LIGHT.get(name, "")
            # 提取核心性格（冒号后第一句）
            trait = persona.split("。")[0].split("：")[-1] if persona else "未知"
            lines.append(f"  {name}｜距离{ dist }｜好感{rel}/100｜信任{tr}/100")
            # 角色世界状态（自由大世界·决策7/8/10）：在场角色的"在做什么/目标/对你的态度"演出依据
            cs = (state.get("character_states") or {}).get(name)
            if isinstance(cs, dict):
                cs_extra = []
                if cs.get("activity"):
                    cs_extra.append(f"正「{cs['activity'][:20]}」")
                if cs.get("goal"):
                    cs_extra.append(f"目标：{cs['goal'][:20]}")
                if cs.get("alive") is False:
                    cs_extra.append("（已故）")
                lines.append(f"    └ {trait}" + ("　" + "　".join(cs_extra) if cs_extra else ""))
            else:
                lines.append(f"    └ {trait}")

    # ── 📚 记忆回廊（优先用检索包 memory_pack：PIN 全部 + 检索 top-5 LTM + 当前 STM）──
    # memory_pack 为空时回退裸 state.memory（最近 5 条 LTM）
    mp = memory_pack or []
    mp_ids = {m.get("id"): m for m in mp if m.get("id")}
    # 检索包里的 LTM 条目（在 mp 且不在 stm 里）；stm 全量；pin 按 id 查
    stm_ids = {m.get("id") for m in stm}
    mp_ltm = [m for m in mp if m.get("id") and m["id"] not in stm_ids]
    # 计算 LTM 面板条目：优先检索包相关 LTM，否则最近 5 条
    panel_ltm = mp_ltm if mp_ltm else ltm[-5:]

    lines.append("")
    lines.append(f"📚 记忆回廊  STM[{len(stm)}/6]｜LTM[{len(ltm)}]｜PIN{len(pins)}条")
    # PIN
    if pins:
        all_items = {m["id"]: m for m in stm + ltm}
        if mp:
            all_items.update(mp_ids)  # 检索包优先
        lines.append("  【📌 PIN】")
        for pid in pins:
            item = all_items.get(pid)
            if item:
                sc = item.get("scene", "-")
                lines.append(f"    [{sc}] {item['text'][:80]}")
    # LTM（检索相关 top-5；无检索结果时回退最近 5 条）
    if panel_ltm:
        lines.append("  【📚 LTM】")
        for m in panel_ltm[:5]:
            sc = m.get("scene", "-")
            lines.append(f"    [{sc}] {m['text'][:120]}")
    # STM
    if stm:
        lines.append("  【📝 STM】")
        for m in stm:
            sc = m.get("scene", "-")
            tm = m.get("time", "-")
            lines.append(f"    {tm}｜{sc}｜{m['text'][:80]}")
    else:
        lines.append("  【📝 STM】（空）")

    # ── 🌐 世界动态 ──
    lines.append("")
    lines.append("🌐 世界动态")
    if rumors:
        for r in rumors[-5:]:
            lines.append(f"  · {r}")
    else:
        lines.append("  （暂无流言）")

    # ── 🗺 远方传闻（未解锁但听过的地点：NPC 可顺口带出，玩家「打听X」确认真伪→解锁前往）──
    ls = state.get("location_state") or {}
    rumored = ls.get("rumored") or []
    if rumored:
        lines.append("")
        lines.append("🗺 远方传闻（玩家听过的地点传闻，可安排在场 NPC 提及或由玩家「打听X」确认）")
        for r in rumored:
            lines.append(f"  · {r.get('name', '')}：{str(r.get('hint', ''))[:50]}")

    # ── 🗞 与你有关的天下事（玩家引发/参与的近期事件，回灌叙事）──
    we_events = state.get("world_events") or []
    mine = [e for e in we_events if e.get("related_to_player") == "strong" and not e.get("seen")][-3:]
    if mine:
        lines.append("")
        lines.append("🗞 与你有关的天下事")
        for e in mine:
            lines.append(f"  · 〔{e.get('date', '')}〕{e.get('event', '')[:60]}")

    # ── 🔗 关系网络（相遇才登记：只列已遇角色；上限 8 条防撑爆上下文）──
    # 首次相遇规则（见指令 8.5）：本拍出场且 relations 里没有的名字 → 输出 first_impressions。
    if relations:
        lines.append("")
        lines.append("🔗 关系网络")
        stances = state.get("stances") or {}
        ranked = sorted(
            ((n, rel, trust.get(n, 50)) for n, rel in relations.items() if isinstance(rel, (int, float))),
            key=lambda x: (x[1] or 0) + (x[2] or 0), reverse=True,
        )[:8]
        for name, rel_val, tr_val in ranked:
            stc = stances.get(name, "")
            suffix = f"｜立场：{stc}" if stc else ""
            lines.append(f"    {name} 好感{rel_val} 信任{tr_val}{suffix}")
        hidden = len(relations) - len(ranked)
        if hidden > 0:
            lines.append(f"    （其余 {hidden} 人好感较低，未列出）")
        # 态度提示：信任/好感 → 明确态度（关系直接决定互动语气与可做之事，见规则 17）
        att_lines = []
        for name, rel_val, tr_val in ranked:
            if tr_val >= 60:
                att_lines.append(f"{name} 对你亲近信任，可推心置腹（深夜密谈/交底/托付可行）")
            elif tr_val <= 20:
                att_lines.append(f"{name} 对你戒备疏远，话不投机，难成深交")
            elif rel_val >= 60:
                att_lines.append(f"{name} 对你有好感，态度热络")
            elif rel_val <= 20:
                att_lines.append(f"{name} 对你观感差，爱答不理")
        if att_lines:
            lines.append("  态度：")
            for a in att_lines:
                lines.append(f"    {a}")
    else:
        # 开局/仅遇过无关系者：明确告知 LLM 当前关系网为空，本拍出场角色皆为新面孔
        lines.append("")
        lines.append("🔗 关系网络")
        lines.append("    （你尚未与任何人建立关系——本拍出场的新角色均需输出 first_impressions 初见好感）")

    # ── 伏笔 ──
    if foreshadowing:
        lines.append("")
        lines.append("🎯 未解伏笔/承诺")
        for fs in foreshadowing[-5:]:
            lines.append(f"  · {fs}")

    # ── 暗线揭示（B-⑨）：玩家成为知情者后，hidden 真相驱动暗线追查 ──
    # 玩家感到"世道哪哪不对劲"，可在内心盘算、可暗中追查（给探查/追问选项）。
    # 注意：不引用 hidden 原文——validate 用 ≥6 字片段匹配防泄漏，复述真相会误报 LEAK 触发重写。
    # 真相保持悬念（玩家也在拼图），由玩家追查逐步揭开（后续机制把 hidden 转 public）。
    if any(f.startswith("知情者") for f in state.get("flags", [])):
        lines.append("")
        lines.append("🕯 你心里有未解开的疑点（最近的经历让你觉得世道哪哪都不对劲）。"
                     "可在内心盘算、可暗中追查（给探查/追问选项）——但真相还没拼全："
                     "叙事只演'你若有所思、隐隐觉得不对'，不要点破具体真相（保持悬念，你也正在拼图）")

    # ── 天意修正 ──
    corrected = state.get("corrected", [])
    if corrected:
        lines.append("")
        lines.append(f"⚠️ 天意修正 x{len(corrected)}（最近：{corrected[-1] if corrected else '无'}）")
        lines.append(f"  当前 tension：{tension}/100")

    # ── 📋 质量检查单 ──
    lines.append("")
    lines.append("📋 质量检查单（输出前逐项确认）")
    lines.append("  □ P0 时空连续，无跳跃 | □ P1 地理/史实正确 | □ P2 回应玩家意图，追踪伏笔")
    lines.append("  □ P3 角色不OOC | □ P4 玩家不神化、关系不跳跃 | □ P5 行为有后果")
    lines.append("  □ P6 五感覆盖（光/声/味/温/触） | □ P7 字数≥600、描写均衡、情感链条完整")
    lines.append("  □ 信息迷雾无泄漏（NPC只说自己知道的事）")

    lines.append("")
    lines.append("=" * 50)
    return "\n".join(lines)


def build_messages(state: GameState, plan: ScenePlan, memory_pack: list = None) -> list[dict]:
    """组装 LLM messages：system(世界底色) + 状态面板 + user(场景指令) + 历史"""
    # ── 完整状态面板（LLM 思维链）──
    context_panel = _build_context_panel(state, plan, memory_pack)

    # 人设分层（speaker 去重：锁定台词同一角色多条时避免人设重复注入）
    names = list(dict.fromkeys(l["speaker"] for l in plan.locked_lines if l.get("speaker")))
    personas = _load_persona_layer(names, plan.distance_map)

    pov = "\n".join(f"· {p}" for p in plan.player_pov) or "（无）"

    instruction = WRITER_INSTRUCTION.format(
        chapter_label=plan.chapter_label,
        title=plan.title,
        setting=plan.setting,
        world_normal=plan.world_normal,
        player_pov=pov,
        personas=personas,
    )
    # 连续性块（唯一注入点）：结构化上一拍事实 + 锁定台词数据驱动（首拍全量/非首拍只注未演出）
    instruction += "\n\n" + render_continuity_block(state, plan)

    # 开局首拍：活世界开场——让玩家感到降生在一个"正在自我转动的世界"
    # （历史非玩家所见，但世界的动静/传闻是玩家能感知的；自然带出而非宣告）
    if not any(h.get("user") for h in state.get("history", [])):
        instruction += """
【开局 · 活世界开场】
这是历险的第一拍。在完成场景主线（醒来/环顾/初见）的同时，让玩家感到自己降生在一个"正在自我转动的世界"——
① 自然带出这个时代正在发生的事：远处火光与喊杀、逃难流民、关于黄金军的传闻、朝廷募兵的动静（取自【状态面板】🌏 当前世界背景 / 🌐 世界动态）
② 世界侧一切正常地演自己的事：NPC 有自己要赶的路、要避的祸，不为玩家停留
③ 这是背景底色，点到即止，不抢场景主线（黑影互动等照常演出）"""

    # 回访故地：世界时间已越过场景年 → 演"故地现状"而非重复当年开场（统一时钟的配套叙事）
    _wd = state.get("world_date") or {}
    if plan.year and _wd.get("year") and int(plan.year) < int(_wd.get("year")):
        instruction += f"""
【回访故地】你再次来到{plan.location or plan.chapter_label}——{plan.chapter_label}的场景设定是 {plan.year} 年的记忆，而如今已是 {_wd['year']} 年。世界时间向前，故地已变（战后/流民/重建/人事已非）。演故地现状与当下的互动，不重复当年的开场剧情（当年在此醒来的事已是过往，只可作记忆提及）"""

    # 场景手调选项池注入（registry options：含 tension/effect，LLM 可选用或改写）
    scene_opts = plan.scene.get("options", []) or plan.options
    if scene_opts:
        pool = "\n".join(
            f"- {o.get('text', '')}（type={o.get('type', 'minor')} tension={o.get('tension', 0)}｜{o.get('effect', '')}）"
            for o in scene_opts[:3]
        )
        instruction += "\n\n【可选骨架选项（必须原样采用 text 与 tension，不得改变行动方向/语义；仅可做人称与前后衔接微调；至少保留 2-3 个）】\n" + pool

    # 重写失败原因注入
    retry = getattr(plan, "meta_retry", None)
    if retry:
        instruction += "\n\n【上次校验失败原因（必须针对性修复）】\n" + "\n".join(f"- {r}" for r in retry)

    # 离谱动作检测：meta/越权/作弊类 free-input → 标记让 LLM 按规则 15 嘲讽拒绝 + 重输出口
    # 只保留明确的多字 meta/作弊短语。不用"系统/无限/召唤/法术/传送/复制"等常用词做子串拦截，
    # 它们会误伤正常 RP（"系统地分析局势""无限感激""召唤兵丁抬走尸体""把文书传送给洛阳"），
    # 甚至 LLM 生成的合法选项（含"传送"等词）被点击后自触发。
    _ABSURD_KW = ("创造模式", "上帝模式", "作弊", "开挂", "金手指", "控制台",
                  "存档", "读档", "退出游戏", "结束游戏", "新建世界", "我是玉皇大帝")
    last_user = ""
    for h in reversed(state.get("history", [])):
        if h.get("user"):
            last_user = h["user"]
            break
    if last_user and any(k in last_user for k in _ABSURD_KW):
        instruction += "\n\n【注意】玩家本拍动作疑似离谱/越权/meta（改世界规则/作弊/召唤等）。按规则 15 处理：世界幽默拒绝 + 嘲讽吐槽 + 选项给重输出口，剧情不推进。"

    messages = [{"role": "system", "content": WORLD_BASE}]
    # 状态面板作为第二个 system message
    messages.append({"role": "system", "content": context_panel})
    # 历史（最近 6 条 ≈ 3 轮）：按"轮"配对（user + 其触发的同拍 assistant），只透传本场景的轮。
    # 玩家动作属于它触发那拍的场景——跨场景旧动作若全透传，LLM 会把它当成新场景当前动作重复演出
    # （如旧场景"我想飞"在切场景后又被演一遍）。跨场景上下文由连续性块 transition_note 承载。
    pending_user = None          # 待归属的玩家动作（等待同拍 assistant 决定归属场景）
    current_scene = plan.scene_id
    for h in state.get("history", [])[-6:]:
        if h.get("user"):
            pending_user = h["user"]
        elif h.get("assistant"):
            sid = h.get("scene_id") or current_scene
            same_scene = (sid == current_scene)
            if same_scene and pending_user:
                messages.append({"role": "user", "content": pending_user})
            pending_user = None
            if same_scene:
                messages.append({"role": "assistant", "content": h["assistant"]})
    # 尾部残留 user（本轮动作尚未有 assistant 回拍，如开局后首次动作前）也透传，保证动作不丢
    if pending_user:
        messages.append({"role": "user", "content": pending_user})
    # 玩家当前行动：单独一条最高优先级指令（规则 0）——确保不被历史截断淹没，LLM 必须先回应
    cur_action = ""
    for h in reversed(state.get("history", [])):
        if h.get("user"):
            cur_action = str(h["user"])[:200]
            break
    if cur_action.strip():
        messages.append({
            "role": "user",
            "content": "★★ 玩家刚刚的行动：" + "\n" + cur_action.strip() + "\n\n先回应这个行动（规则 0），再推进场景。",
        })
    messages.append({"role": "user", "content": instruction})
    return messages


def parse_output(text: str) -> dict:
    """解析 LLM 输出 → NarrativeOutput 雏形（容错 JSON）"""
    text = text.strip()
    # 尝试直接 JSON（LLM 可能输出数组/裸值 → 一律要求 dict）
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "narrative" in data:
            return data
    except json.JSONDecodeError:
        pass
    # 尝试提取 {...} 块
    m = re.search(r'\{.*\}', text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict) and "narrative" in data:
                return data
        except json.JSONDecodeError:
            pass
    # 兜底：文本为叙事，选项为空。若正文后粘连残缺 JSON（截断时），剥离之再给玩家
    return {"narrative": _strip_json_tail(text), "options": []}


def _strip_json_tail(text: str) -> str:
    """剥离叙事末尾粘连的残缺 JSON 尾巴（LLM 截断时 parse 失败，兜底 narrative 会带
    `"options"`/`"relations_delta"` 等片段直接给玩家看）。

    仅当文本以 `{"narrative": "` 开头才处理：正文 = 引号后到下一个 `",` 或 `"}` 结束。
    中文叙事正常不含裸 ASCII 双引号，该启发式在兜底路径（已退化的输出）下可接受。
    """
    m = re.match(r'^\s*\{\s*"narrative":\s*"(.*)', text, re.S)
    if not m:
        return text
    body = m.group(1)
    for marker in ('",', '"}'):
        idx = body.find(marker)
        if idx >= 0:
            return body[:idx]
    return body


async def narrate(state: GameState, plan: ScenePlan, memory_pack: list = None) -> dict:
    """主入口：生成 NarrativeOutput（含后处理链）"""
    from services.llm import stream_chat
    from config import PARAMS_PLAY, STOP_SEQUENCES
    from services.deslop import deslop

    messages = build_messages(state, plan, memory_pack)
    # 引擎完整跑完后由 play.py post-hoc 分块，这里不接流式回调
    draft = ""
    async for chunk in stream_chat(
        messages, max_tokens=3200, **PARAMS_PLAY, stop=STOP_SEQUENCES
    ):
        draft += chunk

    # LLM 全挂检测：错误占位字符串不得当叙事正文（转异常走路由 err 分支）
    if "[错误]" in draft and "LLM" in draft:
        raise RuntimeError("LLM 服务不可用")

    # 后处理链（services.validator 面向旧脚本格式，对散文近空操作且重复 deslop，已移除）
    draft = deslop(draft)
    data = parse_output(draft)
    data["narrative"] = data.get("narrative", draft)
    # 世界统一称呼兜底：数据层已统一世界侧为"黄金"（黄巾/黄天已清除），此处防 LLM 自身串味
    data["narrative"] = data["narrative"].replace("黄巾", "黄金")
    options = data.get("options", [])
    # 容错：LLM 把 options 生成为对象/裸值 → 落回空列表
    if not isinstance(options, list):
        options = []
    # 只保留 dict 项，避免后续 opt.get 崩溃
    options = [o for o in options if isinstance(o, dict)]
    # 选项硬上限 3、类型/数值/分类规范（category 对齐自由沙盒 §5.4 地点行动分类）
    CATS = {"打探", "赶路", "停留", "互动"}
    for opt in options[:3]:
        opt["type"] = "major" if opt.get("type") == "major" else "minor"
        opt["category"] = opt.get("category") if opt.get("category") in CATS else "互动"
        try:
            opt["tension"] = max(0, min(100, int(opt.get("tension", 0))))
        except (TypeError, ValueError):
            opt["tension"] = 0
    data["options"] = options[:3]

    # 后处理：从叙事文本提取 state_updates（轻量正则，不额外调 LLM）
    extracted = _extract_state_updates(data["narrative"], data["options"], plan, data)

    return {
        "narrative": data["narrative"],
        "options": data["options"],
        "state_updates": extracted,
        "validated": True,
        "phase_report": {},
        "retry_reasons": [],
    }


def _extract_event_sentence(narrative: str) -> str:
    """兜底事件提取：从叙事中找"事件句"（含玩家决策/去向/动作标记），而非叙事开头的
    环境描写；无标记时取叙事第二个完整句（第一句多为环境定位）。"""
    EVENT_MARKS = ("你决定", "你追", "你躲", "你问", "你答", "你往", "你朝", "你走进",
                   "你来到", "你转身", "你发现", "黑影", "跑了", "传来", "冲向", "跟上")
    sents = [s.strip() for s in re.split(r'[。！？\n]', narrative) if s.strip()]
    for s in sents:
        if len(s) > 4 and any(m in s for m in EVENT_MARKS):
            return s[:80]
    return (sents[1] if len(sents) > 1 else (sents[0] if sents else ""))[:80]


def _extract_state_updates(narrative: str, options: list, plan: ScenePlan, llm_data: dict = None) -> dict:
    """从叙事文本提取状态更新（纯规则，不污染主 prompt，不额外调 LLM）
    llm_data: LLM 输出的 JSON（可选）——其中的 relations_delta/trust_delta 按角色给出独立变化，优先采用；
    未被 LLM 覆盖的互动角色退回全局情绪启发式。
    """
    result: dict = {"memory_add": [], "relations_delta": {}, "trust_delta": {},
                    "foreshadowing_add": [], "rumors_add": [], "flags_add": [],
                    "player_updates": {}, "world_events_add": [], "character_updates": {},
                    "first_impressions": {}, "failure": None}

    # 0. 初次相遇：LLM 声明的 first_impressions（新角色初见好感 10-60 区间）
    #    此处只做钳位与结构校验；「是否已相遇」过滤在 graph 落地时按完整 state 判断
    #    （relations 已有/encountered 已含 → 忽略，防 LLM 重复覆盖已建关系）。
    if isinstance(llm_data, dict):
        fi = llm_data.get("first_impressions")
        if isinstance(fi, dict):
            for k, v in fi.items():
                if not isinstance(v, dict):
                    continue
                rel = v.get("relation")
                tr = v.get("trust")
                if isinstance(rel, (int, float)) and not isinstance(rel, bool):
                    rel = max(10, min(60, round(rel)))
                else:
                    rel = 30
                if isinstance(tr, (int, float)) and not isinstance(tr, bool):
                    tr = max(10, min(60, round(tr)))
                else:
                    tr = 30
                result["first_impressions"][k] = {
                    "relation": rel,
                    "trust": tr,
                    "reason": str(v.get("reason", ""))[:40],
                }

    # 0. 玩家数据更新：LLM 声明的 player_updates（资产/属性/称号）透传
    if isinstance(llm_data, dict):
        pu = llm_data.get("player_updates")
        if isinstance(pu, dict):
            result["player_updates"] = {k: v for k, v in pu.items() if k in
                ("assets_add", "assets_remove", "coins_delta", "stats_delta", "title_add", "reputation_delta")}
        # 角色软状态：LLM 声明的 character_updates（doing/goal/attitude_delta/tags_add/notes_add）透传
        cu = llm_data.get("character_updates")
        if isinstance(cu, dict):
            result["character_updates"] = {
                k: {kk: vv for kk, vv in v.items() if kk in
                    ("doing", "goal", "attitude_delta", "tags_add", "notes_add")}
                for k, v in cu.items() if isinstance(v, dict)
            }
        # 失败代价：LLM 声明的 failure（决策 12：不真死付代价）透传
        fail = llm_data.get("failure")
        if isinstance(fail, dict):
            result["failure"] = {
                k: v for k, v in fail.items() if k in ("kind", "penalty")
            }
        # 世界写回：LLM 声明的 world_events_add（玩家行为对世界的局部影响，受历史大势约束）
        we = llm_data.get("world_events_add")
        if isinstance(we, list):
            result["world_events_add"] = [e for e in we[:2]
                if isinstance(e, dict) and str(e.get("event", "")).strip()]

    # 1. 记忆条目：LLM 输出的 events[]（结构化关键事件）优先——它知道"本拍发生了什么"；
    #    缺失/非 list 时退回事件句提取（兜底，避免记忆面板存环境不存事件）
    if isinstance(llm_data, dict):
        ev_list = llm_data.get("events") or []
        if isinstance(ev_list, list):
            parts = []
            for e in ev_list[:3]:
                if not isinstance(e, dict):
                    continue
                actor = str(e.get("actor", "") or "").strip()
                action = str(e.get("action", "") or "").strip()
                r = str(e.get("result", "") or "").strip()
                s = (actor + action) if (actor and action) else (action or actor)
                if r:
                    s = (s + "，" + r) if s else r
                if s:
                    parts.append(s)
            if parts:
                result["memory_add"] = ["；".join(parts)[:80]]
    if not result["memory_add"]:
        # 兜底：从叙事提取事件句（跳过环境开场），找不到则取叙事中第二个完整句
        result["memory_add"] = [_extract_event_sentence(narrative)]

    # 2. 互动角色集合：锁定台词说话人（KNOWN）/ distance_map 核心+互动
    interact_names = set()
    for line in plan.locked_lines:
        sp = line.get("speaker", "")
        if sp and sp in KNOWN_NAMES:
            interact_names.add(sp)
    for name, dist in (plan.distance_map or {}).items():
        if dist in ("核心", "互动"):
            interact_names.add(name)

    # 3. LLM 按角色输出的关系变化（优先）：只接受互动/已知角色、整数、限幅 ±8
    llm_rel: dict = {}
    llm_trust: dict = {}
    if isinstance(llm_data, dict):
        # 泛型/群类键（黄金兵/老者/黑影/乡绅/小黄门）不接受差分：跨章复用会混淆不同个体
        valid = (interact_names | KNOWN_NAMES) - GENERIC_NAMES
        # LLM 可能把差分输出成 list/string/bool 等非 dict 形态 → 逐字段 isinstance 防护，
        # 避免 .items() 抛 AttributeError 崩掉整回合（options 已有同类类型归一，差分不能漏）。
        # 数值：拒绝 bool（isinstance(True,int) 为真）；round 而非 int（float 2.5→2 是截断不是舍入）；
        # 钳位 ±8，与规则 13 及启发式回退一致。
        rel_raw = llm_data.get("relations_delta") or {}
        tr_raw = llm_data.get("trust_delta") or {}
        if isinstance(rel_raw, dict):
            for k, v in rel_raw.items():
                if k in valid and isinstance(v, (int, float)) and not isinstance(v, bool):
                    llm_rel[k] = max(-8, min(8, round(v)))
        if isinstance(tr_raw, dict):
            for k, v in tr_raw.items():
                if k in valid and isinstance(v, (int, float)) and not isinstance(v, bool):
                    llm_trust[k] = max(-8, min(8, round(v)))
    covered = set(llm_rel) | set(llm_trust)

    # 关系差分：LLM 覆盖的角色用各自独立数值；未覆盖的互动角色退回全局情绪启发式。
    # 泛型/群类键不持久化（见 GENERIC_NAMES），避免同一键跨章累计污染。
    names = (interact_names | covered) - GENERIC_NAMES
    if names:
        POS = {"帮", "救", "谢", "好", "友", "敬", "信", "护", "助", "善", "恩", "忠", "义"}
        NEG = {"敌", "杀", "恨", "贼", "疑", "怒", "逃", "谎", "骗", "叛", "奸", "恶"}
        pos_count = sum(1 for w in POS if w in narrative)
        neg_count = sum(1 for w in NEG if w in narrative)
        rel_base = min(8, max(-8, (pos_count - neg_count) * 2))

        for name in names:
            # covered 且本场声明的互动角色（锁定台词说话人 / distance_map 核心+互动）：
            #   信任 LLM 差分，不要求叙事里字面出现名字——叙事可能用代称/尊称（如"曹孟德"→键"曹操"）
            #   或规则 12 要求的派系代称（贼军/溃兵 → 键"黄金兵"），字面检查会静默丢弃差分。
            # 其余（未覆盖的启发式 / covered 但仅 KNOWN 幻觉性提及）：叙事未字面提到就不动关系。
            if name in covered and name in interact_names:
                pass
            elif name not in narrative:
                continue
            if name in covered:
                rd = llm_rel.get(name)
                if rd is not None and rd != 0:
                    result["relations_delta"][name] = rd
                td = llm_trust.get(name)
                if td is not None:
                    if td != 0:
                        result["trust_delta"][name] = td
                elif rd is not None and rd != 0:
                    # LLM 给了关系但漏了信任（规则 13 未强制逐键完整）：按关系回退派生
                    # （与启发式同公式），防该角色的信任永久冻结在旧值。
                    # rd=0 是 LLM 显式"关系不变"→ 不派生，防 0//2+1=1 把"没变化"误当信任 +1 漂移
                    derived = max(-3, min(4, rd // 2 + 1))
                    if derived != 0:
                        result["trust_delta"][name] = derived
            else:
                if rel_base != 0:
                    result["relations_delta"][name] = rel_base
                    trust_delta = max(-3, min(4, rel_base // 2 + 1))
                    if trust_delta != 0:
                        result["trust_delta"][name] = trust_delta

    # 4. 伏笔检测（关键词）
    FORESHADOW_KW = {"日后", "有朝一日", "欠你", "承诺", "约定", "改日", "时机成熟",
                     "伏笔已埋", "必有后报", "不会忘记", "记住你了"}
    for kw in FORESHADOW_KW:
        if kw in narrative:
            idx = narrative.find(kw)
            snippet = narrative[max(0, idx - 5): idx + len(kw) + 15].strip()
            if len(snippet) > 8:
                result["foreshadowing_add"].append(snippet)
                break  # 最多一条

    # 5. 流言/军报检测（关键词）
    RUMOR_KW = {"听说", "据说", "传闻", "传言", "军报", "探马来报", "消息", "密报"}
    for kw in RUMOR_KW:
        if kw in narrative:
            idx = narrative.find(kw)
            snippet = narrative[idx: idx + 30].strip()
            if len(snippet) > 6:
                result["rumors_add"].append(snippet)
                break  # 最多一条

    # 6. flags 检测（暗线/见证者/知情者——供 director aftermath.flow 岔路与前端徽章）
    # 场景声明在 flags_on_enter 的全名 flag（如 见证者_官道之辩/见证者_刺董败露）优先产出，
    # 保证与 flags_on_enter 字符串一致（director 岔路用精确匹配）。
    # 见证者/知情者：仅当场景 flags_on_enter 声明同前缀全名 flag 才产出（避免裸前缀噪声，
    # 如"跟着"误触发暗线_流亡）；暗线_*：无场景锚定，保留裸前缀回退。
    FLAG_KW = {
        "暗线_流亡": {"流亡", "同行", "一路东逃"},
        "暗线_黄金": {"混入", "黄金军内部", "信物"},
        "暗线_许家": {"许家", "推荐信", "厚报", "救下"},
        "见证者": {"目睹", "亲眼看见", "见证"},
        "知情者": {"知道真相", "识破", "察觉"},
    }
    scene_flags = [f for f in (plan.flags_on_enter or []) if isinstance(f, str)]
    for prefix, kws in FLAG_KW.items():
        if any(kw in narrative for kw in kws):
            matched = next((f for f in scene_flags if f.startswith(prefix)), None)
            flag = matched if matched else (prefix if prefix.startswith("暗线_") else None)
            if flag and flag not in result["flags_add"]:
                result["flags_add"].append(flag)

    return result


async def synthesize_briefing(events: list, prev_date: dict = None, cur_date: dict = None) -> str:
    """LLM 合成世界简报（A3，设计 §3.3）：结构化事件 → 一段可读简报。

    含时间跨度 + 与玩家相关点，折棒乐子人口吻。失败（LLM 挂/输出异常）返回 ''
    ——前端回退逐条事件列表。
    """
    from services.llm import stream_chat
    from config import PARAMS_FORMAT, STOP_SEQUENCES, QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
    if not events:
        return ""
    ev_lines = "\n".join(
        f"〔{e.get('date', '?')}〕{str(e.get('event', ''))[:80]}"
        + ("　←与你有关" if e.get("related_to_player") == "strong" else "")
        for e in events[-6:]
    )
    p, c = prev_date or {}, cur_date or {}
    span = f"{p.get('year', '?')}年{p.get('month', '?')}月 → {c.get('year', '?')}年{c.get('month', '?')}月"
    messages = [
        {"role": "system", "content": (
            "你是《新三国·星空》的旁白，用看热闹不嫌事大的损友口吻讲世界动态：口语、轻快、带点幸灾乐祸和揶揄，像给朋友转述八卦。"
            "把下面这段时间跨度 + 事件列表合成一段 60-120 字的简报，让玩家感到世界在自我转动。"
            "写法：直说期间发生了什么、与局势/玩家相关的走向，以最近的事为主。"
            "只有时间跨度确实大（跨季/跨年）才带一句'一晃数月'，跨度小就别提时间，更不要用'X月已经过去'这类开头——玩家一直在场，别像对离开了很久的人说话。"
            "口语化短句、带一点看戏的轻快，但别用现代词、别点破这是游戏。只输出简报正文，不要标题、不要列表、不要 JSON。"
        )},
        {"role": "user", "content": f"时间跨度：{span}\n期间事件：\n{ev_lines}"},
    ]
    try:
        # 双模型试验：世界简报（主控）走 Qwen；key 由 stream_chat 解析
        draft = ""
        _ctrl = dict(base_url=QWEN_BASE_URL, model=QWEN_MODEL)
        async for chunk in stream_chat(messages, max_tokens=300, **PARAMS_FORMAT, stop=STOP_SEQUENCES, **_ctrl):
            draft += chunk
        # LLM 全挂检测（与 narrate 同款）：双 provider 失败时 stream_chat yield 错误占位字符串而非抛异常，
        # 必须拦下返回 ''（docstring 契约：前端回退逐条事件列表），否则占位文案会原样呈现给玩家
        if "[错误]" in draft and "LLM" in draft:
            return ""
        draft = draft.strip().strip('“”"\'。').strip()
        return draft[:200]
    except Exception:
        return ""
