"""
预蒸馏知识卡（第2层注入——结构化，可检索）
============================================
从 game_world_full.md、新三国世界观素材库、新三国天意理论与梗文化.md
中预蒸馏出的结构化知识卡。

每张卡 = 一个可独立注入的知识单元（2-4句话），按节点/角色/机制分类。
Director 在 direct() 中根据当前节点和节拍匹配相关卡片，注入 BeatBrief。

设计原则：
- 每张卡是可独立理解的知识片段
- 分类明确，方便按条件检索
- 内容来自素材但经过浓缩，直接可用
"""

# ============================================================================
# 知识卡
# ============================================================================

KNOWLEDGE_CARDS = [

    # --- 世界运行核心（全局，所有节点可用）---
    {
        "id": "kc_core_01",
        "category": "world_core",
        "name": "天意=被污染的游戏管理员",
        "content": (
            "天意=被污染/崩溃的游戏管理员系统（也是克苏鲁式古神）。"
            "它钉死历史关键节点，用'脚本修正'强行把剧情扳回正轨——"
            "角色在关键节点会突然被系统接管，说出前言不搭后语的话（本人毫无察觉）。"
        ),
        "nodes": "*",
        "source": "game_world_full.md §公设1",
    },
    {
        "id": "kc_core_02",
        "category": "world_core",
        "name": "所有角色都是NPC",
        "content": (
            "所有角色都是NPC，以为自己是三国人物、按'人设'演出。"
            "极少数觉醒：曹操=第一个觉醒又被重新污染的最终BOSS；"
            "刘备=看穿真相一心想'自刎归天'退出游戏的人；司马懿=GM账号。"
        ),
        "nodes": "*",
        "source": "game_world_full.md §公设2",
    },
    {
        "id": "kc_core_03",
        "category": "world_core",
        "name": "鱼水原则★最重要★",
        "content": (
            "机制是'水'，角色是'鱼'——鱼不知道水的存在。所有异常（小沛会移动、"
            "袁术在东海、一夜千里、时间错乱）对角色而言都是理所当然的日常。"
            "诡异感来自'角色觉得正常+观众觉得不正常'的反差。"
        ),
        "nodes": "*",
        "source": "writer.py §鱼水原则",
    },
    {
        "id": "kc_core_04",
        "category": "world_core",
        "name": "天意修正三级响应",
        "content": (
            "小偏离（观众说怪话、想跑）：不修正，世界自然反应。"
            "中偏离（想改变小事、救小人物）：柔性修正——用'巧合'拉回。"
            "大偏离（要杀关键角色、阻止大事）：硬修正——触发[SYS]强制回弹，"
            "剧情硬切回正轨，伴随强烈'故障感'。"
        ),
        "nodes": "*",
        "source": "writer.py §天意修正",
    },

    # --- 角色游戏身份卡 ---
    {
        "id": "kc_char_01",
        "category": "character_identity",
        "name": "曹操=最终BOSS（被污染）",
        "content": (
            "曹操=第一个觉醒、又被系统重新污染的最终BOSS（所以又疯又清醒、"
            "行为前后矛盾）。当众喊'国贼董卓'不是勇，是被污染后的自毁行为。"
            "头风病=系统争夺控制权时的物理表现。"
        ),
        "characters": ["曹操"],
        "nodes": ["曹操献刀", "官渡之战", "火烧赤壁", "败走麦城", "归晋"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_02",
        "category": "character_identity",
        "name": "刘备=觉醒者（想退出游戏）",
        "content": (
            "刘备=发现真相的人，知道一切都是游戏，知道关张'只是三组数据'。"
            "从出场就生无可恋，总是念叨天意。'自刎归天'=试图退出游戏（logout）。"
            "仁义=天意发给他的武器（'它还是杀人的利器'），做仁义事充能获得短暂管理员权限。"
        ),
        "characters": ["刘备"],
        "nodes": ["桃园结义", "三顾茅庐", "夷陵之战", "白帝城托孤"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_03",
        "category": "character_identity",
        "name": "关羽=系统傀儡（数据绑定）",
        "content": (
            "关羽=被数据绑定锁住刘备的系统傀儡。无敌技能（摸须一刀斩）、"
            "多形态切换（一气化三清）。死后留'亡语'（后台daemon）继续阻止"
            "刘备退出游戏——关羽死了比活着更危险。"
        ),
        "characters": ["关羽"],
        "nodes": ["桃园结义", "败走麦城", "夷陵之战"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_04",
        "category": "character_identity",
        "name": "张飞=系统傀儡（情绪锁死）",
        "content": (
            "张飞=另一个锁住刘备进程的系统傀儡。情绪参数被系统锁定在MAX——"
            "始终狂怒。酿酒=系统给他的'泄压阀'（酒=系统最高权限道具，"
            "暂时脱离系统控制后精神失常）。"
        ),
        "characters": ["张飞"],
        "nodes": ["桃园结义", "三顾茅庐", "夷陵之战"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_05",
        "category": "character_identity",
        "name": "诸葛亮=觉醒辅助NPC",
        "content": (
            "诸葛亮=能读懂部分世界代码的觉醒辅助NPC。"
            "'无端忧虑'=收到系统debug日志但智力参数不够解读。"
            "'隆中对'不是战略远见，是他读过剧本——未出茅庐已定三分天下，是剧透不是预言。"
            "人体炼成=把系统资源（钱粮）转化成士兵单位。"
        ),
        "characters": ["诸葛亮"],
        "nodes": ["三顾茅庐", "火烧赤壁", "白帝城托孤", "归晋"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_06",
        "category": "character_identity",
        "name": "司马懿=GM账号",
        "content": (
            "司马懿=GM账号，不是NPC。'王是一口井，天子是一口深井'——"
            "他早就看穿了系统的进程树层级结构。无所谓，随便玩。"
            "化骨绵掌=管理员权限的'删除进程'命令。"
        ),
        "characters": ["司马懿"],
        "nodes": ["火烧赤壁", "归晋"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_07",
        "category": "character_identity",
        "name": "董卓=守门进程",
        "content": (
            "董卓=死守天意防线的'守门进程'（杀毒软件），被满朝文武误读为病毒。"
            "他的残暴是系统的隔离操作——在保护核心数据不被污染。大汉忠臣=他确实在保护汉朝。"
        ),
        "characters": ["董卓"],
        "nodes": ["曹操献刀"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_08",
        "category": "character_identity",
        "name": "王允=恶意程序",
        "content": (
            "王允=潜伏的恶意程序。他的寿宴是'恶意程序分发'——用祖传七星宝刀"
            "（污染道具）感染曹操进程。曹操'主动请缨刺董'=被感染成功的时刻。"
        ),
        "characters": ["王允"],
        "nodes": ["曹操献刀"],
        "source": "game_world_full.md §一·机制层",
    },
    {
        "id": "kc_char_09",
        "category": "character_identity",
        "name": "吕布=被覆写的守门进程",
        "content": (
            "吕布=另一个守门进程。系统给了他拉满的武力（+100%），把智力调到负数"
            "（-250%）。被貂蝉（恶意补丁）覆写——'率真男儿'是系统给他的嘲讽标签。"
        ),
        "characters": ["吕布"],
        "nodes": ["曹操献刀", "官渡之战"],
        "source": "game_world_full.md §二·角色层",
    },
    {
        "id": "kc_char_10",
        "category": "character_identity",
        "name": "周瑜=被诅咒title的承受者",
        "content": (
            "周瑜=第一个扛'大都督'debuff的号。'江东之主'是个被诅咒的title——"
            "坐上去就受天意侵蚀。孙权发现了这个bug，创建了'大都督'这个子账号"
            "来转移诅咒。周瑜的'好方略，不过我想稍作修改'=被诅咒后在系统提示下"
            "做出的自毁行为。"
        ),
        "characters": ["周瑜"],
        "nodes": ["火烧赤壁"],
        "source": "game_world_full.md §二·角色层",
    },

    # --- 机制解释卡（游戏化解读）---
    {
        "id": "kc_mech_01",
        "category": "mechanism_explanation",
        "name": "地图是设计出来的",
        "content": (
            "游戏世界的地理不是真实地理。袁术在徐州东边（海上）=地图设计如此。"
            "小沛环绕徐州公转=卫星城机制（有进徐点/远徐点）。"
            "新三国道连接各州=传送门/快速旅行网络。星夜行军速度异常=夜间快速旅行加成。"
        ),
        "mechanism_ids": ["A2-01", "A2-03", "A2-04"],
        "nodes": "*",
        "source": "game_world_full.md §公设3-4",
    },
    {
        "id": "kc_mech_02",
        "category": "mechanism_explanation",
        "name": "野生伏兵=随机刷怪",
        "content": (
            "山谷/道路随机刷新的中立伏兵=游戏地图的random encounter。"
            "不是任何势力的军队，见人就打。固定刷新点：洛阳-长安间、长江旁。"
            "'300人马兵分600路'=刷怪数量bug。"
        ),
        "mechanism_ids": ["A3-07"],
        "nodes": "*",
        "source": "game_world_full.md §公设5",
    },
    {
        "id": "kc_mech_03",
        "category": "mechanism_explanation",
        "name": "脚本修正=系统接管",
        "content": (
            "角色在关键节点被系统接管=说出/做出不符合本人逻辑的事。"
            "表现为：前言不搭后语、突然降智、行为180度转弯。"
            "[SYS]标记=系统通知（冰冷机械，像服务器日志）。"
            "[ERR]标记=世界错误提示（一闪而过，像游戏bug弹窗）。"
        ),
        "mechanism_ids": ["A1-04"],
        "nodes": "*",
        "source": "game_world_full.md §公设6",
    },
    {
        "id": "kc_mech_04",
        "category": "mechanism_explanation",
        "name": "灵魂锁链=数据级绑定",
        "content": (
            "刘关张三人是数据层面绑定（不是情感绑定）。上位能带死下位："
            "关羽<<刘备<<张飞，优先级队列。三人本质不熟——只是被系统编到"
            "同一组的NPC。关羽张飞的存在意义=阻止刘备触发'退出游戏'条件。"
            "关羽死后发动'亡语'（死亡触发脚本）继续阻止刘备。"
        ),
        "mechanism_ids": ["A4-04"],
        "nodes": ["桃园结义", "败走麦城", "夷陵之战", "白帝城托孤"],
        "source": "game_world_full.md §公设7",
    },
    {
        "id": "kc_mech_05",
        "category": "mechanism_explanation",
        "name": "酒=系统最高权限道具",
        "content": (
            "酒是至高存在，不可悖逆。任何事一转'换大盏'——酒可以override"
            "任何当前状态。酒可暂免天意侵蚀（=使用后暂时脱离系统控制），"
            "但酒后精神失常（=副作用：脱离控制后NPC行为紊乱）。"
        ),
        "mechanism_ids": ["A4-02"],
        "nodes": ["曹操献刀", "火烧赤壁", "败走麦城", "归晋"],
        "source": "game_world_full.md §公设8",
    },
    {
        "id": "kc_mech_06",
        "category": "mechanism_explanation",
        "name": "七星宝刀=感染道具",
        "content": (
            "七星宝刀有刀魂——皮革鞘发出金属声（正常皮革不会），铜镜加持射激光"
            "（=数据反射/复制）。王允用这把刀感染曹操进程——刺董的'失败'是"
            "刀魂自己的选择：它的任务不是杀人，是让曹操背上'刺客'标签、被迫逃亡。"
        ),
        "mechanism_ids": ["A6-03"],
        "nodes": ["曹操献刀"],
        "source": "game_world_full.md §三·事件层 #2 + 素材库A6",
    },
    {
        "id": "kc_mech_07",
        "category": "mechanism_explanation",
        "name": "大都督诅咒",
        "content": (
            "'江东之主'=被诅咒的系统title。设大都督职位=创建子账号转移诅咒。"
            "大都督debuff：江东之主转移权重+500%，剩余寿命-75%。"
            "周瑜→鲁肃→吕蒙→陆逊=诅咒在大都督之间接力传递。陆逊（擎天柱/赛博坦人）"
            "免疫了大都督寿命缩减。"
        ),
        "mechanism_ids": ["A4-05"],
        "nodes": ["火烧赤壁", "夷陵之战", "归晋"],
        "source": "素材库.md §A4·大都督诅咒",
    },
    {
        "id": "kc_mech_08",
        "category": "mechanism_explanation",
        "name": "骄兵必败循环=游戏ELO机制",
        "content": (
            "胜兵必骄→骄兵必败→败兵必哀→哀兵必胜——闭环。"
            "这是系统强制50%胜率的ELO机制。想最大胜利须先献祭部分己方"
            "（=降低ELO评分以匹配更弱的对手）。"
        ),
        "mechanism_ids": ["A3-01"],
        "nodes": ["官渡之战", "败走麦城", "夷陵之战"],
        "source": "素材库.md §A3·军事规则",
    },
    {
        "id": "kc_mech_09",
        "category": "mechanism_explanation",
        "name": "关羽之歌=天意存档",
        "content": (
            "全剧出现63次、只4次场景中有关羽本人。它一响=天意在做存档/结算。"
            "重大节点触发、重要人物死亡、剧情大转折时响起。"
            "不是哀乐，是系统写的'commit log'。"
        ),
        "mechanism_ids": ["A1-09"],
        "nodes": ["败走麦城", "白帝城托孤"],
        "source": "素材库.md §C·关羽之歌",
    },
    {
        "id": "kc_mech_10",
        "category": "mechanism_explanation",
        "name": "博望坡悖论=脚本覆写",
        "content": (
            "诸葛亮设计了一个'完全不能运行的计划'，但天意修正后它完美运行了——"
            "脚本覆写了游戏逻辑。这是这个游戏世界最可怕的地方："
            "不是因为你的计划好才成功，是天意让它成功。"
        ),
        "mechanism_ids": ["A1-04"],
        "nodes": ["三顾茅庐", "火烧赤壁"],
        "source": "game_world_full.md §公设6",
    },

    # --- 事件游戏化解读卡 ---
    {
        "id": "kc_event_01",
        "category": "event_reinterpretation",
        "name": "王允寿宴=恶意程序分发",
        "content": (
            "王允寿宴=一次'恶意程序分发'。王允是潜伏的恶意程序，用七星宝刀（污染道具）"
            "感染曹操进程。曹操'主动请缨刺董'就是被感染成功的时刻——正常觉醒者不会这么蠢。"
        ),
        "nodes": ["曹操献刀"],
        "source": "game_world_full.md §三·事件层 #2",
    },
    {
        "id": "kc_event_02",
        "category": "event_reinterpretation",
        "name": "桃园结义=灵魂锁链初始化",
        "content": (
            "三人焚香跪拜结义=系统把三个互不相关的NPC数据绑进同一组（灵魂锁链初始化）。"
            "那年杏花微雨，三个人在桃园里完成了程序上的生死绑定——速度之快、感情之薄，"
            "都像一场强行匹配。"
        ),
        "nodes": ["桃园结义"],
        "source": "game_world_full.md §三·事件层 #3",
    },
    {
        "id": "kc_event_03",
        "category": "event_reinterpretation",
        "name": "官渡之战=系统直接下场",
        "content": (
            "七万打崩七十万不是军事奇迹，是系统直接介入。许攸投曹=他被'反向感染'——"
            "天意借他的手删掉袁绍的粮草进程。七十万不是败给谋略，是被系统'全选→删除'。"
        ),
        "nodes": ["官渡之战"],
        "source": "game_world_full.md §三·事件层 #8",
    },
    {
        "id": "kc_event_04",
        "category": "event_reinterpretation",
        "name": "三顾茅庐=激活辅助NPC",
        "content": (
            "刘备三顾=觉醒者苦寻一个能读懂部分代码的辅助进程。诸葛亮的'隆中对'="
            "他打开系统任务日志念了一遍——'眼观荆州、意在西川、心存天下、联孙抗曹'"
            "=三阶段主线任务。'未出茅庐已定三分天下'=他在复述剧本结局。"
        ),
        "nodes": ["三顾茅庐"],
        "source": "game_world_full.md §三·事件层 #9",
    },
    {
        "id": "kc_event_05",
        "category": "event_reinterpretation",
        "name": "赤壁东风=系统审批的ticket",
        "content": (
            "借东风不是法术——诸葛亮在七星坛（系统终端）向天意提交了一个'东风'的ticket。"
            "子时东南风骤起=系统审批通过。风是借不来的，除非有管理员权限。"
            "赤壁之战=觉醒者联盟（刘备+孙权+鲁肃）成功抵挡了系统的一次大规模脚本修正。"
        ),
        "nodes": ["火烧赤壁"],
        "source": "game_world_full.md §三·事件层 #11",
    },
    {
        "id": "kc_event_06",
        "category": "event_reinterpretation",
        "name": "关羽之死=进程终止+亡语触发",
        "content": (
            "关羽自刎=进程被终止。但关羽之歌（天意存档）响起时，存档的不是他的死亡——"
            "是他留下的'亡语'（onDeath事件监听器），一个死后继续阻止刘备退出游戏的"
            "后台daemon。吕蒙斩其首级狂笑=执行程序完成了任务，但他根本不知道亡语已经被触发。"
        ),
        "nodes": ["败走麦城"],
        "source": "game_world_full.md §三·事件层 #17",
    },
    {
        "id": "kc_event_07",
        "category": "event_reinterpretation",
        "name": "夷陵之战=刘备最后一次logout尝试",
        "content": (
            "刘备连营七百里不是不懂兵——他在帮助陆逊找到自己的破绽。他需要败，需要死，"
            "需要在战场上触发'自刎归天'——logout。但天意不让他死在战场上：听吴军喊'生擒'，"
            "他脸都黑了——生擒就全完了。最后被救回，病死白帝城=logout方式错误，退出失败。"
        ),
        "nodes": ["夷陵之战"],
        "source": "game_world_full.md §三·事件层 #19",
    },
    {
        "id": "kc_event_08",
        "category": "event_reinterpretation",
        "name": "白帝城托孤=觉醒者交接",
        "content": (
            "'如其不才，君可自取'——不是试探，是觉醒者把选择权交给唯一读得懂代码的人。"
            "刘备太清楚帝位是口'深井'（司马懿的话），谁坐上去谁就是天意的傀儡。"
            "他在替诸葛亮拒绝这个诅咒。诸葛亮泣血——不是因为忠诚，是他在系统日志里"
            "看到了自己病逝五丈原的结局。"
        ),
        "nodes": ["白帝城托孤"],
        "source": "game_world_full.md §三·事件层 #20",
    },
    {
        "id": "kc_event_09",
        "category": "event_reinterpretation",
        "name": "高平陵之变=GM执行root提权",
        "content": (
            "司马懿一日夺走曹氏四代江山=GM账号执行了一次sudo。"
            "'我举剑只有一次，但剑却磨了十年'=GM花了十年绕过系统的安全协议。"
            "司马炎称帝=恶意程序的感染链（王允→七星刀→曹操→曹丕→司马炎）抵达终点——"
            "恶意程序获得了root权限。游戏彻底沦陷。"
        ),
        "nodes": ["归晋"],
        "source": "game_world_full.md §三·事件层 #23-24",
    },

    # --- 世界bug清单卡（典型异常现象的游戏化解释）---
    {
        "id": "kc_bug_01",
        "category": "bug_observation",
        "name": "室外大声密谋无人发现",
        "content": (
            "窃听定律的反面：二人密谋必被第三人窃听；但公开场合大声密谋反而无人泄密。"
            "游戏化解释：系统屏蔽了NPC的窃听AI——"
            "「大声」这个参数被识别为「非密谋」，自动跳过窃听检测。"
        ),
        "nodes": ["曹操献刀", "官渡之战"],
        "source": "game_world_full.md §四·bug清单 #4",
    },
    {
        "id": "kc_bug_02",
        "category": "bug_observation",
        "name": "所有大营完全相同=资产复用",
        "content": (
            "不管谁出门都住公孙瓒大营——所有制式大营外观内设完全相同。"
            "游戏化解释：美术偷懒/资产复用——系统只有一张'大营'贴图。"
        ),
        "nodes": "*",
        "source": "game_world_full.md §四·bug清单 #8",
    },
    {
        "id": "kc_bug_03",
        "category": "bug_observation",
        "name": "骑兵步兵互转=转职系统",
        "content": (
            "骑兵可以随时下马变步兵，步兵可以随时上马变骑兵。"
            "游戏化解释：转职系统——同一unit可以在骑/步两个职业间切换，不需要重新训练。"
        ),
        "nodes": "*",
        "source": "game_world_full.md §四·bug清单 #9",
    },
    {
        "id": "kc_bug_04",
        "category": "bug_observation",
        "name": "的卢马妨主=反向意图读取",
        "content": (
            "的卢马：想活→妨死，想死→妨活。"
            "游戏化解释：读取玩家意图并反向执行的bug道具。骑它的人越是想活越会死，"
            "越是想死越被救——刘备想自刎归天，所以的卢马一直在救他。"
        ),
        "nodes": ["夷陵之战"],
        "source": "game_world_full.md §四·bug清单 #12",
    },
    {
        "id": "kc_bug_05",
        "category": "bug_observation",
        "name": "厕所屏蔽外界感知",
        "content": (
            "厕所可以屏蔽外界感知（隔墙有耳无效）。"
            "游戏化解释：厕所=游戏世界里的safe zone（安全区），在此区域内的对话"
            "不被窃听系统覆盖。袁术'厕所才是朕真正的帝位'=他发现了这个safe zone。"
        ),
        "nodes": "*",
        "source": "素材库.md §A4·厕所屏蔽",
    },
    {
        "id": "kc_bug_06",
        "category": "bug_observation",
        "name": "城池类型随意切换",
        "content": (
            "城/关/帐/州/县/大营可随意变换——同一个地点在不同集里叫不同的类型。"
            "游戏化解释：地图标签系统的bug。同一个location entity的type字段被反复覆写。"
        ),
        "nodes": "*",
        "source": "素材库.md §A4·城池切换",
    },
]


# ============================================================================
# 工具函数：按条件检索知识卡
# ============================================================================

def get_cards_for_node(node: str) -> list[dict]:
    """获取与指定节点相关的知识卡。"""
    matched = []
    for card in KNOWLEDGE_CARDS:
        nodes = card.get("nodes", [])
        if nodes == "*" or node in nodes:
            matched.append(card)
    return matched


def get_cards_for_character(character: str) -> list[dict]:
    """获取与指定角色相关的知识卡。"""
    matched = []
    for card in KNOWLEDGE_CARDS:
        chars = card.get("characters", [])
        if character in chars:
            matched.append(card)
    return matched


def get_cards_by_category(category: str) -> list[dict]:
    """按类别获取知识卡。"""
    return [c for c in KNOWLEDGE_CARDS if c.get("category") == category]


def distill_cards_for_beat(node: str, characters: list[str] = None, max_cards: int = 3) -> list[str]:
    """
    为当前节拍蒸馏知识卡——返回可直接注入 prompt 的字符串列表。
    优先：节点匹配 > 角色匹配 > 全局核心卡。
    """
    selected = []
    seen_ids = set()

    # 1. 节点专属卡（最高优先级）
    node_cards = get_cards_for_node(node)
    # 排除全局卡（*），只留专属卡
    exclusive_cards = [c for c in node_cards if c.get("nodes") != "*"]
    for card in exclusive_cards[:2]:
        if card["id"] not in seen_ids:
            selected.append(card["content"])
            seen_ids.add(card["id"])

    # 2. 角色相关卡
    if characters:
        for char in characters[:2]:
            char_cards = get_cards_for_character(char)
            for card in char_cards[:1]:
                if card["id"] not in seen_ids:
                    selected.append(card["content"])
                    seen_ids.add(card["id"])

    # 3. 全局核心卡（兜底，确保每拍至少有一些世界观）
    if len(selected) < 2:
        core_cards = get_cards_by_category("world_core")
        for card in core_cards:
            if card["id"] not in seen_ids:
                selected.append(card["content"])
                seen_ids.add(card["id"])
            if len(selected) >= max_cards:
                break

    return selected[:max_cards]
