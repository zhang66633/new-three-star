<template>
  <div class="landing" ref="containerRef">
    <!-- 入场遮罩 -->
    <transition name="fade-slow">
      <div v-if="!entered" class="entry-gate" @click="enter">
        <div class="entry-content">
          <h1 class="entry-title">新三国·星图</h1>
          <p class="entry-sub">列位百官，各位诸公，且随我入这星图一观</p>
        </div>
        <div class="entry-hint">点击任意处进入</div>
      </div>
    </transition>

    <!-- 3D星图（桌面端） -->
    <div v-if="!isMobile" ref="graphRef" class="planet-graph" :class="{ active: entered }"></div>

    <!-- 2D星图（移动端降级） -->
    <div v-else class="planet-graph mobile-graph" :class="{ active: entered }">
      <MobileStarMap :worlds="WORLDS" @navigate="onMobileNavigate" />
    </div>

    <!-- 暗角 -->
    <div class="vignette"></div>

    <!-- 语录放大 -->
    <transition name="quote-fade">
      <div v-if="selectedQuote" class="quote-overlay" @click="selectedQuote = null">
        <div class="quote-card">
          <p class="quote-text">{{ selectedQuote }}</p>
        </div>
        <p class="quote-hint">点击任意处关闭</p>
      </div>
    </transition>

    <!-- 跃迁过渡 -->
    <div class="warp-overlay" :class="{ active: warpActive }" :style="{ background: warpColor }"></div>

    <!-- hover文字简介 -->
    <transition name="vision-fade">
      <div v-if="hoveredWorld && !visionWorld" class="hover-card" :style="{ '--vc': hoveredWorld.color }">
        <p class="hover-name">{{ hoveredWorld.name }}</p>
        <p class="hover-tag">{{ hoveredWorld.tagline }}</p>
        <p class="hover-desc">{{ hoveredWorld.desc }}</p>
      </div>
    </transition>

    <!-- 全屏幻象页（点击星球后） -->
    <transition name="vision-fade">
      <div v-if="visionWorld" class="fullscreen-vision" @click.self="visionWorld = null">
        <div class="fv-bg">
          <img :src="`/textures/previews/${visionWorld.id}.jpg`" class="fv-img" />
        </div>
        <div class="fv-content">
          <h1 class="fv-name" :style="{ textShadow: `0 0 40px ${visionWorld.color}` }">{{ visionWorld.name }}</h1>
          <p class="fv-tag">{{ visionWorld.tagline }}</p>
          <p class="fv-desc">{{ visionWorld.desc }}</p>
          <button class="fv-enter" :style="{ borderColor: visionWorld.color, color: visionWorld.color }" @click="enterWorld(visionWorld.id)">
            进入此世界
          </button>
        </div>
        <button class="fv-close" @click="visionWorld = null">✕</button>
      </div>
    </transition>
  </div>
</template>

<script lang="ts">
// 模块级状态：组件销毁重建时不会重置
let hasEntered = false
</script>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, inject } from 'vue'
import { useRouter } from 'vue-router'
import ForceGraph3D from '3d-force-graph'
import * as THREE from 'three'
import SpriteText from 'three-spritetext'
import { planetVertexShader, planetFragmentShader, vortexVertexShader, vortexFragmentShader, PLANET_SHADER_PARAMS } from '../shaders/planetShaders'
import MobileStarMap from '../components/MobileStarMap.vue'

const ForceGraph3DAny = ForceGraph3D as any

const router = useRouter()
const graphRef = ref<HTMLElement>()
const containerRef = ref<HTMLElement>()
const entered = ref(hasEntered)
const playGuanyu = inject<() => void>('playGuanyu', () => {})

// 移动端检测：窄屏 或 无WebGL
const isMobile = (() => {
  if (window.innerWidth < 768) return true
  try {
    const c = document.createElement('canvas')
    return !(c.getContext('webgl2') || c.getContext('webgl'))
  } catch { return true }
})()

function onMobileNavigate(id: string) {
  if (warpActive.value) return
  const world = WORLDS.find(w => w.id === id)
  warpColor.value = world?.color || '#aabbff'
  warpActive.value = true
  setTimeout(() => {
    if (id === 'create') {
      router.push('/create')
    } else {
      playGuanyu()
      router.push(`/worldview/${id}`)
    }
    setTimeout(() => { warpActive.value = false }, 100)
  }, 600)
}

const WORLDS = [
  { id: 'cthulhu', name: '外神星域', tagline: '天意即不可名状之物', color: '#8b5cf6', desc: '域外存在出于好奇污染了三国时间线，神在侵蚀世界，世界又何尝不在侵蚀神' },
  { id: 'game_world', name: '崩坏纪元', tagline: '觉醒NPC的污染世界', color: '#22d3ee', desc: '世界意志被污染的游戏，角色是觉醒的NPC，关羽张飞只是三组数据' },
  { id: 'murder_mystery', name: '迷局', tagline: '每人都有胜利条件', color: '#f59e0b', desc: '一场剧本杀，曹操三周目结局是小丑，司马懿是纯人机不玩游戏' },
  { id: 'pokemon', name: '属性大陆', tagline: '阵营即属性克制', color: '#ef4444', desc: '魏水蜀火吴草，赤壁是开晴天减半水伤，司马懿是恶属性会拍落' },
  { id: 'philosophy', name: '理念天穹', tagline: '天意即世界精神', color: '#a78bfa', desc: '黑格尔式世界精神通过人物表达自身，一旦成为限制就摧毁它' },
  { id: 'cultivation', name: '太虚境', tagline: '作减求空，超脱轮回', color: '#34d399', desc: '被污染的轮回世界，诸葛亮超脱留替身，关张灵魂锁链是牢笼' },
  { id: 'jojo', name: '命运之轮', tagline: '替身与天堂制造', color: '#f97316', desc: '天堂制造加速后的二巡三国，曹操D4C死后穿越，刘备Big死后无敌' },
  { id: 'warhammer', name: '亚空间', tagline: '混沌侵蚀一切', color: '#dc2626', desc: '战锤宇宙，密谋是灵能遮蔽，新三国道是网道，伏兵是绿皮' },
  { id: 'zhangjiao', name: '黄天残响', tagline: '两股天意争夺此世', color: '#eab308', desc: '新生天意与张角残存意志争夺控制权，所有反贼行为是黄巾幽灵' },
  { id: 'trpg', name: '骰子深渊', tagline: '调查员与SAN值', color: '#6366f1', desc: '克苏鲁跑团，曹操灵感检定太多疯了，关张是古神派来的眷族' },
  { id: 'elo', name: '天平竞技场', tagline: '强制五成胜率', color: '#14b8a6', desc: '天意是ELO匹配算法，骄兵必败是数学必然，司马懿在smurfing' },
]

let graphInstance: any = null
let animFrameId: number | null = null
let starField: THREE.Points | null = null
let nebulaParticles: THREE.Points | null = null
let quoteSprites: SpriteText[] = []
const nodeGroups: Map<string, THREE.Group> = new Map()
const cleanups: (() => void)[] = []
const shaderMaterials: THREE.ShaderMaterial[] = []

// 漂浮语录（新三国2010台词）
const QUOTES: string[] = [
  // === 新三国台词 ===
  '足下怎么不说了？你接着往下说啊，你怎么个轻贱法，怎么个屈身法，你做的是哪家的鹰犬，你事的又是哪家的贼？国贼董卓嘛！',
  '好，关闭大门，熄掉灯笼，不要惊动了巡夜的鹰犬。',
  '列位，今天并不是老夫的生日，相反，是老夫的忌日啊。',
  '曹某不才，弹指之间便可将董贼的首级取下，悬于长乐宫门。',
  '你们就不打算搜搜，看我身上带没带兵刃？',
  '他今天竟然纠集了十八路诸侯，起兵反我！',
  '大凡正人君子，其肉都太酸。酒酸？咱家说了，不怕酸！',
  '你看看，我曹操居然堕入刺客之流了！',
  '你的父母、妻子、孩子，他们该怎么办？罢了，陈宫已经顾不得许多了，只当是陈宫从来就没有这些！',
  '不过你的头颅值千金，我这头颅只值五十金。抱歉，我的脑袋太贵，你的又太便宜。',
  '苍天有眼，你还没死！',
  '正因为已经错杀无辜了，所以必须要斩草除根。',
  '他已经把吃的喝的准备好了，如果我们不回去他不是白死了吗？',
  '伯父，不是阿瞒害了你，是这个乱世害了你呀！',
  '我在想我的那些个蛐蛐儿，它们个个有情有义。',
  '十八镇诸侯往这儿一站，这大半个江山，就在我们脚下了。剩下那一小片江山，也是弹指可取。',
  '小子，快去叫袁绍出来接驾！',
  '刘什么？关什么？没听说过。',
  '孟德啊，中原八百里都贴满了拿你的告示，正可谓是天下何人不识君啊！',
  '既然那董卓能把天子拘于深宫之中，视如掌上玩物，我等为什么就不能视他如草芥？',
  '我的大斧早就饥渴难耐了！',
  '主子爷，主子爷，主子爷，小的叫人给打了！',
  '因为孙坚虽然英勇，但是求胜心切，孤军深入，已成骄兵，而骄兵必败。',
  '对不起，我实在是记不住你的名字了。',
  '说得好，说得真好啊！说得我这心里呀舒服死了！',
  '列位诸公，如果你们容得下这三位在这里肆意放肆，那就容我袁术告老还乡了。',
  '你走了我们吃什么？是啊，吃什么？叉出去！',
  '我部悍将刘三刀，三刀之内必斩吕布于马下！',
  '我有北海勇将王冲，他早就想刀劈吕布！',
  '看我捅吕布那小子一万个透明窟窿去！',
  '你叫我什么？嘿嘿，三姓家奴！我堂堂吕布，为何成了三姓家奴？',
  '这个好办，我们三兄弟只管杀进洛阳，砍下董卓的脑袋就是了！',
  '好啊，生死不明，那就是死了。',
  '东头一个汉，西头一个汉，迁都入长安，方可无斯难。',
  '迁都长安，那是中兴大汉王朝，那是百年大计。洛阳暗，长安明，迁都长安就是弃暗投明！',
  '咱家半月之内，就可以再造一座皇宫。',
  '袁绍何在？大军何在？各路诸侯何在？他们，他们在六百里外喝酒呢。',
  '洛阳已是一片废墟，无用之物，天子才是宝中之宝。',
  '老臣的命苦啊，苦得就像是车轮底下的野草，石头缝里的黄连哪！',
  '恭喜爹可以称帝了！',
  '哥啊，这说两句就行了，谁知道先帝爷他听得见听不见。',
  '只要我们集中五千精兵，由我来打先锋，我保证在三个时辰之内，擒下刘表，攻克荆州！',
  '在各路诸侯当中，孙坚是个英雄，只要他一死，中原的诸侯都是猪狗鸡鸭。',
  '这尚父是什么意思啊？就如同当今天子的，爹~',
  '拜董相国为义父，不过是求个晋升之道罢了，拜你为义父，才是至真至切之情！',
  '老夫也将化作一碗血酒，被禽兽们开怀痛饮啊。',
  '若除禽兽必先献身于禽兽啊！',
  '更衣好，更衣好啊！',
  '我的心肝宝贝啊，你可让我想死了！',
  '区区一个貂蝉值什么？何至于此伤感啊。不，他是我的命根子。',
  '你要知道貂蝉是人间极品，咱家舍不得！',
  '凭我手中方天画戟，要诛杀董卓如屠猪狗。只担心他是我义父，我怕世人会说我弑父弑君啊！',
  '我被那董老贼玷污过，将军不会嫌弃我吗？不，龌龊的是我吕布。',
  '爹啊！你老人家死得好惨哪！孩儿对不住你啊！苍天哪！呱！',
  '在下一者为主公悲伤，二者给主公道喜。',
  '苍天送徐州给主公，如同送一杆大旗给狂风，送一把宝剑给剑鞘，主公不取何待？',
  '听你讲话如饮美酒，令人陶醉啊。',
  '我是要为父报仇，怒火满腔，我已经乱了方寸了。',
  '这对堂兄弟可谓是一对儿笑面虎，两头乌角鲨。',
  '我原本以为吕布已经天下无敌了，没想到有人比他还勇猛，这是谁的部将？',
  '我只想做他的友，没想做他的爹。',
  '不醉不醉，酒逢知己千杯少。',
  '好哇，吕布这厮，用自家娘们勾引咱哥！',
  '那昔日天子，不过是寒秋中的一片落叶，无用之物罢了。',
  '人昏庸到这个地步，真是叫人喜欢呀。',
  '了不起，了不起，你比董卓他们英雄十倍。',
  '我还知道，你刘备不是不想得到徐州，恰恰相反，你想，你比任何人都想得到徐州。',
  '听说刘备健在人间，我深感欣慰。',
  '今日何日，今夕何夕啊？天下的愚夫蠢货五月初五都爬出来了吗？知道吗，袁术称帝了，差点没把我笑死。',
  '袁术称帝后，天子也就随之贬值了。',
  '春秋胡言乱语！',
  '在下早就看出来了，刘备大奸似忠，大伪似真。',
  '听见了吗，谁做吕布的义父，谁就不得好死。',
  '那有什么，我要是愿意做他皇爷爷都成，但我不贪那个。',
  '你七十万大军都败了？我的天哪！这七十万大军就是伸直了脖子让曹军砍那也得砍他几天几夜啊！',
  '玄德贤弟，我盼你真是望眼欲穿哪！',
  '并非我曹操皮厚，而是我把这世上那些庸俗不堪的纲常伦理早已经不放在心上了。',
  '徐州城不愧为中原第一雄关，想当年楚霸王项羽就是在此地用三万铁骑，杀得高祖帝五十万兵马片甲不留啊！',
  '主公喜欢的是已婚少妇，尤其是别人家的媳妇。',
  '只有这厕所才是最安全的地方，它才是朕真正的帝位。',
  '放肆！胆敢搜我的身，我砍你的头！',
  '何为人主，那就是知错改错不认错，万万不可认错。',
  '好风啊，风从虎，云从龙，龙虎英雄傲苍穹啊！',
  '仁义到了你这儿就不光是世道人心啦，它还是杀人的利器！',
  '刘备还是个忠厚人哪！',
  '不可能！绝对不可能！你就算是八万个馒头，刘备也得啃上半个月，怎么可能说丢就丢！',
  '袁绍忽近忽远，丞相远近皆察。',
  '我不懂兵。',
  '妖妇，你休得放肆！',
  '她没想杀我，她只是想自杀，你这个匹夫！',
  '给云长送去，不可在半道上凉了。',
  '兵法教出来的都是呆子。',
  '破曹操三军，真如同滚滚雷霆击腐败落叶尔。',
  '此战，决定着未来五百年的历史，决定着皇朝天下的最后归属。',
  '区区一个关羽，就敢在三日内连斩颜良和文丑，难道你们连一个关羽都不如吗！',
  '一帮吃货，混账！你们是来打仗的还是来调情的！',
  '在下偶尔放肆一下，要远比那曹孟德放肆一生要强啊！',
  '你把我骂得惊天动地、山呼海啸、狗血淋头，叫我听得好享受啊！',
  '人哪，骂是骂不倒的，誉满天下者往往也是毁满天下。',
  '与其寻找主公，不如为自己创造一个主公。',
  '腐儒是什么呀，那就是腐烂的臭豆腐！',
  '大哥你千万可别拿臭豆腐当宝贝儿了。',
  '三弟说得痛切，当浮一大白！',
  '蔡瑁名为上将，其实蠢如屠夫。',
  '孔明未出茅庐已定三分天下。',
  '孔明何等人物，只要有钱粮在手他马上会变出十万精兵来！',
  '这个赵子龙的武艺真是举世无双，自从吕布死后天下再无这等战将，我爱死他了！',
  '说的对，我又忘情了。',
  '襄阳真是天上人间啊。',
  '公子啊，我能不能不逃了。',
  '列位弟兄，随我接战，战至最后一刻，自刎归天！',
  '此时此刻，除了项上这颗头颅，已经没什么能让我们再失去的了，只能天天向好，蒸蒸日上。',
  '我子敬真的是要醉啦！',
  '没想到我这区区一道反间计，借蒋干为使，竟然有这等奇效！',
  '有道是曹阿瞒知错改错不认错。真是枉为我周瑜啊。',
  '公瑾啊，这是你的书房吗？那为何不见一卷书啊？我读完一卷烧一卷。',
  '了不起！一开口便是大实话！',
  '自从盘古开天地以来可曾有过如此雄壮的水军吗？',
  '周瑜，我的小儿，我死了也不服你！',
  '我不能走啊！云长！',
  '给你个鸡毛你就当令箭了？',
  '将者如同医者，医死的人越多医术就越高明。',
  '人的脚为什么比脸和手都要白呢？因为他老藏着。',
  '不要愤怒，愤怒会降低你的智慧，与其恨敌人不如拿他来为我所用。',
  '我正是要他有去无回呀！就是我这五百个弟兄全死了我都值！',
  '南郡城就留你一人坚守！',
  '凭末将手中这把梨花开山斧定能将什么张飞赵云之流，有来无回！',
  '说出吾名吓汝一跳，我乃是零陵上将军邢道荣！',
  '回去吧，你太老了，关某的大刀不斩老幼。',
  '龙，可是帝王之征啊！',
  '以后如果我再从你们嘴里听到这样的话，我就扎聋我自己的耳朵！',
  '至于我这两个弟弟，你能用则用之，不能用就弃之，不要有任何顾忌。',
  '我当了十年的武侯了，这东吴到底是姓孙还是姓周？',
  '我身为吴侯你怎能擅自用兵？这江东到底你是主还是我是主？',
  '我刘备别无所长，剑法却是当世一流，可别逼我使出无情剑来。',
  '这二十年来我不知流了多少次血，唯独这次是最快活的。',
  '我打了一辈子仗就不能享受享受吗？',
  '你立刻给我滚回荆州去！滚，我不是你主公！',
  '不干你们的事，接着奏乐接着舞。',
  '我看，你是舍不得这张帅案吧！你拾它作甚！',
  '你以为一壶酒就可以收下一颗已经被你伤过的心吗？',
  '这是我古往今来听过的第一妙计呀！',
  '妙计，我还想再稍做修改。',
  '只要父亲一声令下，哪怕是让他砍自己的爹娘他都不皱眉头！',
  '因为丞相自己就是一个敢赖会赖一赖到底的君王！',
  '曹贼！奸贼！恶贼！逆贼！',
  '我看的眼都酸了，他们的膀子竟然不酸？',
  '你姓法名正，却一不守法，二不正行啊。',
  '天下何人无人骂，天下何人不骂人。',
  '我跟你开玩笑哪！仲德啊，你可真是个老实人啊。',
  '因为我活在马上，她活在梦里。',
  '关平，把军师的信抄上五十遍，让荆州的文武都看看。',
  '还请云长自己多饮几杯吧。我是不会客气的，来！换大盏！',
  '好方略，不过我想稍作修改。',
  '刘备匹夫！如此猖狂！欺我太甚！',
  '臣～法正，参见～汉～中～王！',
  '于禁能统兵吗，曹操真是老糊涂了，派了个种地的来救樊城。',
  '狂徒！天下英雄闻我名无不丧胆，可惜我这青龙偃月刀竟斩你这鼠辈的首级。',
  '他过江我也过江，连孙权一起拿了！',
  '我看你疗伤做甚，我要看这棋！',
  '徐晃是谁呀？是我的韩信、白起、周亚夫。',
  '水不多了，给赤兔马饮吧。',
  '我在位十多年了，一直受他们这些大都督的制约，现在才能真正当一回主公了。',
  '不可能！我二弟天下无敌！',
  '死不可怕，死是凉爽的夏夜，可供人无忧地安眠。',
  '世人昨日看错我曹操，今日又看错了，可是我仍然是我，我从来不怕别人看错我。',
  '好你个魏延，想让我称帝，无非是想让你们各自得到分封！',
  '主公生气了，看来此事有希望了。',
  '我对孙权之恨，超越古今。',
  '王是一口井，而天子则是一口深井。',
  '正方啊，我好像好久没有这么高兴过了。来，我们喝一盅！',
  '你还是不是张翼德的儿子！你还是不是我的侄儿！',
  '莫非朕不知兵吗？',
  '百分之百可信啊！万万没有此事！万万没有此事啊！',
  '快！把王司徒给我抢回来！',
  '这个诸葛亮真是个妖孽啊，三寸肉舌头，把我的军师说死了。',
  '士卒逃跑斩伍长，伍长逃跑斩什长，将军逃跑我司马懿自斩头颅向朝廷请罪。',
  '把这个帅案给我换了，立刻打造一座铜案，立在这里。',
  '凡是没有斩杀过蜀军的人，不管他是将是尉是士是卒，立刻斩首。',
  '但一想到这样的勇将有去无回，我，我心痛欲裂。',
  '皇恩浩荡啊！',
  '你且归降于我，我赏你一辆四轮车，你我同归成都见主上啊。',
  '只有两仪生八卦，还有八卦生两仪的？',
  '全军冲杀蜀军战营，直奔诸葛亮四轮儿车！',
  '杨仪，你害羞了？我都不害羞，你害什么羞？',
  '好火啊，比夷陵之火还好啊！',
  '我挥剑只有一次，可我磨剑磨了十几年哪。',
  // === 老三国台词（94版） ===
  '*天下大势，分久必合，合久必分。*',
  '*苍天已死，黄天当立；岁在甲子，天下大吉。*',
  '*满朝公卿，夜哭到明，明哭到夜，岂能哭死董卓？*',
  '*某虽不才，愿即断董卓之头，悬之东门，以谢天下。*',
  '*宁教我负天下人，休教天下人负我。*',
  '*大丈夫生居天地之间，岂能郁郁久居人下！*',
  '*我乃燕人张翼德也！谁敢与我决一死战？*',
  '*吾观颜良，如插标卖首耳。*',
  '*某去便来。*',
  '*俺也一样！*',
  '*忠臣宁死而不辱，大丈夫岂有事二主之理？*',
  '*云奔走四方，择主而事，未有如使君者。今得相随，大慰平生。*',
  '*我身为袁氏臣，死为袁氏鬼。不似你等谗谄阿谀之贼！*',
  '*我主在北，不可使我面南而死。*',
  '*我乃常山赵子龙也！*',
  '*非淡泊无以明志，非宁静无以致远。*',
  '*臣本布衣，躬耕于南阳，苟全性命于乱世，不求闻达于诸侯。*',
  '*受任于败军之际，奉命于危难之间。*',
  '*鞠躬尽瘁，死而后已。*',
  '*既生瑜，何生亮。*',
  '*曲有误，周郎顾。*',
  '*对酒当歌，人生几何？譬如朝露，去日苦多。*',
  '*老骥伏枥，志在千里；烈士暮年，壮心不已。*',
  '*玉可碎而不可改其白，竹可焚而不可毁其节。*',
  '*勿以恶小而为之，勿以善小而不为。*',
  '*兄弟如手足，妻子如衣服。*',
  '*皓首匹夫！苍髯老贼！汝即将归于九泉之下，届时有何面目去见汉朝二十四代先帝！*',
  '*一条断脊之犬，还敢在我军阵前狺狺狂吠！*',
  '*我从未见过有如此厚颜无耻之人！*',
  '*孤好梦中杀人。*',
  '*活关羽可怕，死关羽也可怕，死了还活更可怕！*',
  '*孤平生游历天下四十余年，上至天子，下及庶民，无不惧我。*',
  '*马超小儿，可认得燕人张翼德吗？！*',
  '*我虽老，可两臂尚能开三石之弓，浑身还有千斤之力！*',
  '*司马昭之心，路人皆知。*',
  '*这铮铮之音，如惊涛拍岸，风卷残云，指端似有雄兵百万！*',
  '*心乱则音噪，心静则音纯；心慌则音误，心泰则音清。*',
  '*大丈夫行于乱世，当光明磊落。*',
  '*江河水总有入海之时，而人生之志，却常常难以实现，令人抱憾终身。*',
  '*此书乃战国无名氏所作，蜀中三尺小童都能背诵，曹丞相却窃为己有。*',
  '*老夫闻听将军死期已至，特来吊丧。*',
  '*备久慕卧龙先生高名，两次拜谒不遇空回，深为遗憾。*',
  '*我想伐魏久矣，幸司马懿中计遭贬，时不我待，否则将遗恨终身。*',
  '*魏延，你好大胆！*',
  '*我命当绝，非文长之过也。*',
  '*兴师北伐，未获成功，何期病入膏肓，命垂旦夕，不及终事陛下，饮恨无穷！*',
  // === 鸣谢 ===
  '特别鸣谢列位先行者，你们不来，我们吃什么？',
  '苍天送列位诸公给新三，如同送一杆大旗给狂风，送一把宝剑给剑鞘。',
]

const FLOAT_FONTS = ['Ma Shan Zheng', 'Zhi Mang Xing', 'Liu Jian Mao Cao', 'Long Cang', 'ZCOOL KuaiLe', 'ZCOOL XiaoWei', 'Noto Serif SC']
const FLOAT_COLORS = ['#c8c8dd', '#ddd5c5', '#c0d0dd', '#d5d0c0', '#ccc5dd', '#c0d5cc', '#ddd0c5', '#c8ccdd']

function enter() {
  hasEntered = true
  entered.value = true
  playGuanyu()
  // 设置初始飞船位置（面向星图中心）
  if (graphInstance) {
    graphInstance.cameraPosition({ x: 0, y: 30, z: 250 })
  }
}

onMounted(async () => {
  if (isMobile) return
  try {
    await initGraph()
    // 返回时直接进入星图状态
    if (hasEntered && graphInstance) {
      graphInstance.cameraPosition({ x: 0, y: 30, z: 250 })
    }
  } catch (e) {
    console.error('initGraph failed:', e)
  }
})

onBeforeUnmount(() => {
  if (animFrameId) cancelAnimationFrame(animFrameId)
  cleanups.forEach((fn) => fn())
  cleanups.length = 0
  quoteSprites = []
  nodeGroups.clear()
  shaderMaterials.length = 0
  if (graphInstance) graphInstance._destructor?.()
})

// 菲涅尔大气光晕shader
const fresnelVertexShader = `
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;
    gl_Position = projectionMatrix * mvPosition;
  }
`

const fresnelFragmentShader = `
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uPower;
  varying vec3 vNormal;
  varying vec3 vViewPosition;
  void main() {
    vec3 viewDir = normalize(vViewPosition);
    float fresnel = 1.0 - abs(dot(vNormal, viewDir));
    fresnel = pow(fresnel, uPower) * uIntensity;
    gl_FragColor = vec4(uColor, fresnel);
  }
`

function createStarField(scene: THREE.Scene) {
  const count = 4000
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)
  const sizes = new Float32Array(count)

  for (let i = 0; i < count; i++) {
    // 球形分布
    const radius = 300 + Math.random() * 900
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta)
    positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta)
    positions[i * 3 + 2] = radius * Math.cos(phi)

    // 微微偏暖/偏冷的白色
    const warmth = Math.random()
    colors[i * 3] = 0.8 + warmth * 0.2
    colors[i * 3 + 1] = 0.8 + warmth * 0.15
    colors[i * 3 + 2] = 0.85 + (1 - warmth) * 0.15

    sizes[i] = 0.5 + Math.random() * 2.0
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))
  geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1))

  const material = new THREE.PointsMaterial({
    size: 1.8,
    vertexColors: true,
    transparent: true,
    opacity: 0.9,
    sizeAttenuation: true,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })

  starField = new THREE.Points(geometry, material)
  scene.add(starField)
}

function createNebulaParticles(scene: THREE.Scene) {
  // 在"创造新世界"节点附近创建旋转星云粒子
  const count = 200
  const positions = new Float32Array(count * 3)
  const colors = new Float32Array(count * 3)

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2
    const radius = 3 + Math.random() * 12
    const height = (Math.random() - 0.5) * 6
    positions[i * 3] = Math.cos(angle) * radius
    positions[i * 3 + 1] = height
    positions[i * 3 + 2] = Math.sin(angle) * radius

    // 蓝紫色调
    colors[i * 3] = 0.5 + Math.random() * 0.3
    colors[i * 3 + 1] = 0.4 + Math.random() * 0.2
    colors[i * 3 + 2] = 0.9 + Math.random() * 0.1
  }

  const geometry = new THREE.BufferGeometry()
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3))
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3))

  const material = new THREE.PointsMaterial({
    size: 0.8,
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  })

  nebulaParticles = new THREE.Points(geometry, material)
  scene.add(nebulaParticles)
}

const selectedQuote = ref<string | null>(null)
const warpActive = ref(false)
const warpColor = ref('#030306')
const hoveredWorld = ref<{ name: string; tagline: string; color: string; desc?: string; img?: string } | null>(null)
const visionWorld = ref<{ id: string; name: string; tagline: string; color: string; desc?: string } | null>(null)

function enterWorld(id: string) {
  visionWorld.value = null
  const world = WORLDS.find(w => w.id === id)
  warpColor.value = world?.color || '#aabbff'
  warpActive.value = true
  setTimeout(() => {
    if (id === 'create') {
      router.push('/create')
    } else {
      playGuanyu()
      router.push(`/worldview/${id}`)
    }
    setTimeout(() => { warpActive.value = false }, 100)
  }, 600)
}

function createFloatingQuotes(scene: THREE.Scene) {
  const len = QUOTES.length
  QUOTES.forEach((q, i) => {
    const isCredit = i >= len - 2
    const sprite = new SpriteText(q)
    sprite.fontFace = isCredit ? 'Ma Shan Zheng' : FLOAT_FONTS[i % FLOAT_FONTS.length]
    sprite.color = isCredit ? '#e8d8a0' : FLOAT_COLORS[i % FLOAT_COLORS.length]
    sprite.textHeight = isCredit ? 7 : 3.5 + Math.random() * 3
    sprite.material.opacity = isCredit ? 0.85 : 0.2 + Math.random() * 0.18
    sprite.material.transparent = true
    sprite.material.depthWrite = false
    ;(sprite as any).userData = { text: q }

    if (i === len - 2) {
      sprite.position.set(0, 18, 120)
    } else if (i === len - 1) {
      sprite.position.set(0, 8, 120)
    } else {
      const radius = 120 + Math.random() * 980
      const theta = Math.random() * Math.PI * 2
      const phi = Math.acos(2 * Math.random() - 1)
      sprite.position.set(
        radius * Math.sin(phi) * Math.cos(theta),
        radius * Math.sin(phi) * Math.sin(theta) * 0.7,
        radius * Math.cos(phi)
      )
    }

    scene.add(sprite)
    quoteSprites.push(sprite)
  })
}

async function initGraph() {
  if (!graphRef.value) return

  const nodes = WORLDS.map((w) => ({
    id: w.id,
    name: w.name,
    tagline: w.tagline,
    color: w.color,
    val: 20,
    isNebula: false,
  }))

  nodes.push({
    id: 'create',
    name: '创造新世界',
    tagline: '输入一个概念，AI构建全新世界观',
    color: '#aabbff',
    val: 14,
    isNebula: true,
  } as any)

  const links = WORLDS.map((w, i) => ({
    source: w.id,
    target: WORLDS[(i + 1) % WORLDS.length].id,
  }))

  // 加载用户创建的世界
  try {
    const resp = await fetch(`${import.meta.env.VITE_API_BASE || ''}/api/worlds`)
    if (resp.ok) {
      const customWorlds = await resp.json()
      for (const cw of customWorlds) {
        nodes.push({
          id: cw.id,
          name: cw.name,
          tagline: cw.tagline,
          color: cw.color || '#aabbff',
          val: 10,
          isNebula: true,
        } as any)
        links.push({ source: 'create', target: cw.id })
      }
    }
  } catch (e) {
    console.warn('Failed to load custom worlds:', e)
  }

  graphInstance = ForceGraph3DAny()(graphRef.value)
    .graphData({ nodes, links })
    .backgroundColor('#030306')
    .showNavInfo(false)
    .enableNodeDrag(false)
    .enableNavigationControls(true)
    .nodeRelSize(5)
    .nodeVal((node: any) => node.val)
    .nodeColor(() => 'transparent')
    .linkColor(() => 'rgba(120, 130, 180, 0.08)')
    .linkWidth(0.3)
    .linkCurvature(0.15)
    .nodeThreeObject((node: any) => {
      const group = new THREE.Group()
      const params = PLANET_SHADER_PARAMS[node.id]
      const color = new THREE.Color(node.color)
      const isNebula = node.isNebula
      const coreRadius = isNebula ? 3 : 5

      // 程序化星球核心
      const coreGeo = new THREE.SphereGeometry(coreRadius, 48, 48)
      const coreMat = new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor1: { value: new THREE.Color(params.color1) },
          uColor2: { value: new THREE.Color(params.color2) },
          uColor3: { value: new THREE.Color(params.color3) },
          uNoiseScale: { value: params.noiseScale },
          uNoiseSpeed: { value: params.noiseSpeed },
          uOctaves: { value: params.octaves },
          uStyle: { value: params.style },
        },
        vertexShader: planetVertexShader,
        fragmentShader: planetFragmentShader,
      })
      group.add(new THREE.Mesh(coreGeo, coreMat))
      shaderMaterials.push(coreMat)

      // 漩涡吸积盘
      const vortexGeo = new THREE.RingGeometry(coreRadius * 1.3, coreRadius * 2.8, 64)
      const vortexMat = new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uColor: { value: new THREE.Color(params.vortexColor) },
          uOpacity: { value: params.vortexOpacity },
        },
        vertexShader: vortexVertexShader,
        fragmentShader: vortexFragmentShader,
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
      })
      const vortex = new THREE.Mesh(vortexGeo, vortexMat)
      vortex.rotation.x = Math.PI * 0.5 + (Math.random() - 0.5) * 0.4
      vortex.rotation.z = (Math.random() - 0.5) * 0.3
      group.add(vortex)
      shaderMaterials.push(vortexMat)

      // 菲涅尔大气光晕
      const atmosGeo = new THREE.SphereGeometry(coreRadius * 1.3, 48, 48)
      const atmosMat = new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: color },
          uIntensity: { value: isNebula ? 1.5 : 2.0 },
          uPower: { value: 2.2 },
        },
        vertexShader: fresnelVertexShader,
        fragmentShader: fresnelFragmentShader,
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
      })
      group.add(new THREE.Mesh(atmosGeo, atmosMat))

      // 外发光（简化为两层）
      const glowLayers = isNebula
        ? [{ radius: 5, opacity: 0.08 }, { radius: 8, opacity: 0.03 }]
        : [{ radius: 8, opacity: 0.1 }, { radius: 12, opacity: 0.04 }]
      for (const layer of glowLayers) {
        const glowGeo = new THREE.SphereGeometry(layer.radius, 24, 24)
        const glowMat = new THREE.MeshBasicMaterial({
          color: color,
          transparent: true,
          opacity: layer.opacity,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        })
        group.add(new THREE.Mesh(glowGeo, glowMat))
      }

      // 文字标签
      try {
        const label = new SpriteText(node.name)
        label.color = isNebula ? '#aabbff' : node.color
        label.textHeight = isNebula ? 2.5 : 3
        label.fontFace = 'Noto Serif SC'
        label.fontWeight = '700'
        label.backgroundColor = 'rgba(3,3,6,0.5)'
        label.padding = 2
        label.borderRadius = 2
        label.position.y = isNebula ? -8 : -9
        group.add(label)
      } catch (e) {
        console.warn('Label creation failed:', e)
      }

      nodeGroups.set(node.id, group)
      return group
    })
    .onNodeClick((node: any) => {
      if (warpActive.value) return
      hoveredWorld.value = null
      const targetPos = { x: node.x || 0, y: node.y || 0, z: node.z || 0 }
      const cam = graphInstance.camera()
      const startPos = { x: cam.position.x, y: cam.position.y, z: cam.position.z }
      const endPos = {
        x: targetPos.x + (startPos.x - targetPos.x) * 0.08,
        y: targetPos.y + (startPos.y - targetPos.y) * 0.08,
        z: targetPos.z + (startPos.z - targetPos.z) * 0.08,
      }

      const duration = 1200
      const startTime = performance.now()

      function flyAnimate(now: number) {
        const elapsed = now - startTime
        const progress = Math.min(elapsed / duration, 1)
        const ease = progress < 0.5
          ? 4 * progress * progress * progress
          : 1 - Math.pow(-2 * progress + 2, 3) / 2

        cam.position.x = startPos.x + (endPos.x - startPos.x) * ease
        cam.position.y = startPos.y + (endPos.y - startPos.y) * ease
        cam.position.z = startPos.z + (endPos.z - startPos.z) * ease
        cam.lookAt(targetPos.x, targetPos.y, targetPos.z)

        if (progress < 1) {
          requestAnimationFrame(flyAnimate)
        } else {
          // 动画结束，打开全屏幻象页
          visionWorld.value = {
            id: node.id,
            name: node.name,
            tagline: node.tagline,
            color: node.color,
            desc: WORLDS.find(w => w.id === node.id)?.desc || '',
          }
        }
      }
      requestAnimationFrame(flyAnimate)
    })
    .onNodeHover((node: any) => {
      if (graphRef.value) {
        graphRef.value.style.cursor = node ? 'pointer' : 'default'
      }
      if (node && !warpActive.value && !visionWorld.value) {
        const w = WORLDS.find(w => w.id === node.id)
        hoveredWorld.value = {
          name: node.name,
          tagline: node.tagline,
          color: node.color,
          desc: w?.desc || '',
        }
      } else {
        hoveredWorld.value = null
      }
    })

  // 初始相机位置（略高俯瞰，等待进入动画）
  graphInstance.cameraPosition({ x: 0, y: 80, z: 600 })

  // 禁用默认OrbitControls，改用飞船视角
  const controls = graphInstance.controls()
  if (controls) {
    controls.enabled = false
  }

  // 飞船视角：WASD移动 + 鼠标拖拽360转
  const moveState = { forward: false, backward: false, left: false, right: false, up: false, down: false }
  let yaw = 0, pitch = -0.1
  let isDragging = false
  let lastMouseX = 0, lastMouseY = 0
  const moveSpeed = 2.5
  const lookSpeed = 0.003

  const onKeyDown = (e: KeyboardEvent) => {
    switch (e.code) {
      case 'KeyW': case 'ArrowUp': moveState.forward = true; break
      case 'KeyS': case 'ArrowDown': moveState.backward = true; break
      case 'KeyA': case 'ArrowLeft': moveState.left = true; break
      case 'KeyD': case 'ArrowRight': moveState.right = true; break
      case 'KeyQ': moveState.down = true; break
      case 'KeyE': moveState.up = true; break
    }
  }
  const onKeyUp = (e: KeyboardEvent) => {
    switch (e.code) {
      case 'KeyW': case 'ArrowUp': moveState.forward = false; break
      case 'KeyS': case 'ArrowDown': moveState.backward = false; break
      case 'KeyA': case 'ArrowLeft': moveState.left = false; break
      case 'KeyD': case 'ArrowRight': moveState.right = false; break
      case 'KeyQ': moveState.down = false; break
      case 'KeyE': moveState.up = false; break
    }
  }
  const onMouseDown = (e: MouseEvent) => {
    if (e.button === 0 || e.button === 2) { isDragging = true; lastMouseX = e.clientX; lastMouseY = e.clientY }
  }
  const onMouseUp = () => { isDragging = false }
  const onMouseMove = (e: MouseEvent) => {
    if (!isDragging) return
    const dx = e.clientX - lastMouseX
    const dy = e.clientY - lastMouseY
    yaw -= dx * lookSpeed
    pitch -= dy * lookSpeed
    pitch = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, pitch))
    lastMouseX = e.clientX
    lastMouseY = e.clientY
  }
  const onWheel = (e: WheelEvent) => {
    // 滚轮前后推进（直接操作camera.position避免闪烁）
    const cam = graphInstance.camera()
    const dir = new THREE.Vector3(0, 0, -1).applyEuler(new THREE.Euler(pitch, yaw, 0, 'YXZ'))
    const step = e.deltaY > 0 ? -8 : 8
    cam.position.x += dir.x * step
    cam.position.y += dir.y * step
    cam.position.z += dir.z * step
  }
  const onContextMenu = (e: Event) => e.preventDefault()

  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  graphRef.value.addEventListener('mousedown', onMouseDown)
  window.addEventListener('mouseup', onMouseUp)
  window.addEventListener('mousemove', onMouseMove)
  graphRef.value.addEventListener('wheel', onWheel, { passive: true })
  graphRef.value.addEventListener('contextmenu', onContextMenu)

  const el = graphRef.value
  cleanups.push(() => {
    window.removeEventListener('keydown', onKeyDown)
    window.removeEventListener('keyup', onKeyUp)
    el.removeEventListener('mousedown', onMouseDown)
    window.removeEventListener('mouseup', onMouseUp)
    window.removeEventListener('mousemove', onMouseMove)
    el.removeEventListener('wheel', onWheel)
    el.removeEventListener('contextmenu', onContextMenu)
  })

  // 延迟添加星空背景（等图谱初始化完成）
  setTimeout(() => {
    try {
      const scene = graphInstance.scene()
      if (scene) {
        createStarField(scene)
        createNebulaParticles(scene)
        createFloatingQuotes(scene)
      }
    } catch (e) {
      console.warn('Star field init failed:', e)
    }
  }, 100)

  // 呼吸动画 + 星云旋转 + 飞船移动
  const timer = new THREE.Timer()

  function animate() {
    animFrameId = requestAnimationFrame(animate)
    timer.update()
    const t = timer.getElapsed()

    // 更新所有程序化shader的时间
    for (const mat of shaderMaterials) {
      mat.uniforms.uTime.value = t
    }

    // 星空缓慢旋转
    if (starField) {
      starField.rotation.y = t * 0.005
      starField.rotation.x = Math.sin(t * 0.003) * 0.02
    }

    // 语录缓慢漂移
    quoteSprites.forEach((sprite, i) => {
      const speed = 0.02 + (i % 5) * 0.008
      sprite.position.y += Math.sin(t * speed + i) * 0.008
      sprite.position.x += Math.cos(t * speed * 0.7 + i * 0.5) * 0.006
    })

    // 飞船移动（WASD）
    if (entered.value && graphInstance) {
      const cam = graphInstance.camera()
      const forward = new THREE.Vector3(0, 0, -1).applyEuler(new THREE.Euler(pitch, yaw, 0, 'YXZ'))
      const right = new THREE.Vector3(1, 0, 0).applyEuler(new THREE.Euler(0, yaw, 0, 'YXZ'))

      if (moveState.forward) { cam.position.x += forward.x * moveSpeed; cam.position.y += forward.y * moveSpeed; cam.position.z += forward.z * moveSpeed }
      if (moveState.backward) { cam.position.x -= forward.x * moveSpeed; cam.position.y -= forward.y * moveSpeed; cam.position.z -= forward.z * moveSpeed }
      if (moveState.left) { cam.position.x -= right.x * moveSpeed; cam.position.z -= right.z * moveSpeed }
      if (moveState.right) { cam.position.x += right.x * moveSpeed; cam.position.z += right.z * moveSpeed }
      if (moveState.up) { cam.position.y += moveSpeed }
      if (moveState.down) { cam.position.y -= moveSpeed }

      // 更新视角方向
      const lookTarget = new THREE.Vector3(
        cam.position.x + forward.x * 100,
        cam.position.y + forward.y * 100,
        cam.position.z + forward.z * 100
      )
      cam.lookAt(lookTarget)
    }

    // 星云粒子旋转
    if (nebulaParticles) {
      nebulaParticles.rotation.y = t * 0.3
      // 找到create节点位置
      const createNode = nodes.find((n: any) => n.id === 'create') as any
      if (createNode && createNode.x !== undefined) {
        nebulaParticles.position.set(createNode.x, createNode.y, createNode.z)
      }
    }

    // 行星呼吸脉动
    nodeGroups.forEach((group, id) => {
      const node = nodes.find((n: any) => n.id === id) as any
      if (!node || node.isNebula) return
      const scale = 1 + Math.sin(t * 0.8 + group.id * 0.5) * 0.03
      group.scale.setScalar(scale)
    })
  }
  animate()

  // 适配尺寸
  const resize = () => {
    if (graphInstance && containerRef.value) {
      graphInstance.width(containerRef.value.clientWidth)
      graphInstance.height(containerRef.value.clientHeight)
    }
  }
  window.addEventListener('resize', resize)
  cleanups.push(() => window.removeEventListener('resize', resize))
  resize()

  // 点击语录放大
  const raycaster = new THREE.Raycaster()
  const mouse = new THREE.Vector2()
  ;(raycaster.params as any).Sprite = { threshold: 5 }

  const onQuoteClick = (e: MouseEvent) => {
    if (!graphInstance || quoteSprites.length === 0) return
    const rect = el.getBoundingClientRect()
    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1
    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1
    raycaster.setFromCamera(mouse, graphInstance.camera())
    const hits = raycaster.intersectObjects(quoteSprites)
    if (hits.length > 0) {
      const data = (hits[0].object as any).userData
      if (data && data.text) {
        selectedQuote.value = data.text
      }
    }
  }
  el.addEventListener('click', onQuoteClick)
  cleanups.push(() => el.removeEventListener('click', onQuoteClick))
}
</script>

<style scoped>
.landing {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: #030306;
}

.planet-graph {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 2s ease;
}

.planet-graph.active {
  opacity: 1;
}

.mobile-graph {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 入场遮罩 */
.entry-gate {
  position: absolute;
  inset: 0;
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: radial-gradient(ellipse at center, #0a0a18 0%, #030306 70%);
  cursor: pointer;
}

.entry-content {
  text-align: center;
  animation: float-in 1.5s ease-out;
}

.entry-title {
  font-family: var(--font-display);
  font-size: clamp(2.5rem, 6vw, 4.5rem);
  font-weight: 900;
  color: #f0f0f8;
  letter-spacing: 0.2em;
  text-shadow:
    0 0 60px rgba(232, 168, 56, 0.15),
    0 0 120px rgba(100, 100, 200, 0.1);
}

.entry-sub {
  margin-top: 16px;
  font-size: clamp(0.9rem, 2vw, 1.15rem);
  color: #6a6a80;
  letter-spacing: 0.4em;
}

.entry-hint {
  position: absolute;
  bottom: 8vh;
  font-size: 0.8rem;
  color: #3a3a50;
  letter-spacing: 0.2em;
  animation: blink-soft 3s ease-in-out infinite;
}

/* 暗角效果 */
.vignette {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 5;
  background: radial-gradient(ellipse at center, transparent 50%, rgba(3, 3, 6, 0.7) 100%);
}

/* 过渡动画 */
.fade-slow-leave-active {
  transition: opacity 1.5s ease;
}
.fade-slow-leave-to {
  opacity: 0;
}

@keyframes float-in {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes blink-soft {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}

/* 语录放大弹层 */
.quote-overlay {
  position: absolute;
  inset: 0;
  z-index: 200;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(3, 3, 6, 0.85);
  backdrop-filter: blur(6px);
  cursor: pointer;
}

.quote-card {
  max-width: 70vw;
  text-align: center;
  padding: 40px;
}

.quote-text {
  font-family: 'Ma Shan Zheng', var(--font-display);
  font-size: clamp(1.8rem, 4vw, 3.2rem);
  color: var(--text-bright);
  line-height: 1.6;
  letter-spacing: 0.08em;
  text-shadow: 0 0 40px rgba(232, 168, 56, 0.15);
}

.quote-hint {
  position: absolute;
  bottom: 6vh;
  font-size: 0.75rem;
  color: var(--text-dim);
  letter-spacing: 0.15em;
}

.quote-fade-enter-active,
.quote-fade-leave-active {
  transition: opacity 0.4s ease;
}
.quote-fade-enter-from,
.quote-fade-leave-to {
  opacity: 0;
}

/* 跃迁过渡 */
.warp-overlay {
  position: absolute;
  inset: 0;
  z-index: 500;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.6s ease-in;
}

.warp-overlay.active {
  opacity: 1;
  pointer-events: all;
}

/* 星球幻象 */
/* hover文字卡片 */
.hover-card {
  position: absolute;
  bottom: 12%;
  left: 50%;
  transform: translateX(-50%);
  z-index: 150;
  pointer-events: none;
  text-align: center;
  padding: 16px 28px;
  border-radius: 8px;
  background: rgba(3, 3, 6, 0.75);
  border: 1px solid color-mix(in srgb, var(--vc) 30%, transparent);
  backdrop-filter: blur(8px);
}
.hover-name {
  font-family: 'Ma Shan Zheng', serif;
  font-size: 1.5rem;
  color: #f0f0f8;
  letter-spacing: 0.25em;
  margin: 0 0 4px;
}
.hover-tag {
  font-size: 0.75rem;
  color: var(--vc);
  letter-spacing: 0.1em;
  margin: 0 0 8px;
}
.hover-desc {
  font-size: 0.8rem;
  color: #9999bb;
  line-height: 1.5;
  max-width: 360px;
  margin: 0;
}

/* 全屏幻象页 */
.fullscreen-vision {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(3, 3, 6, 0.92);
}
.fv-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}
.fv-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0.6;
  mask-image: radial-gradient(ellipse at center, black 40%, transparent 85%);
  -webkit-mask-image: radial-gradient(ellipse at center, black 40%, transparent 85%);
}
.fv-content {
  position: relative;
  z-index: 2;
  text-align: center;
  padding: 40px;
}
.fv-name {
  font-family: 'Ma Shan Zheng', serif;
  font-size: 3.5rem;
  color: #f0f0f8;
  letter-spacing: 0.3em;
  margin: 0 0 12px;
}
.fv-tag {
  font-size: 1rem;
  color: #aaaacc;
  letter-spacing: 0.15em;
  margin: 0 0 20px;
}
.fv-desc {
  font-size: 0.95rem;
  color: #8888aa;
  line-height: 1.8;
  max-width: 500px;
  margin: 0 auto 36px;
}
.fv-enter {
  background: transparent;
  border: 1px solid;
  padding: 12px 36px;
  font-size: 1rem;
  letter-spacing: 0.2em;
  cursor: pointer;
  border-radius: 4px;
  transition: all 0.3s ease;
}
.fv-enter:hover {
  background: rgba(255, 255, 255, 0.05);
  transform: scale(1.05);
}
.fv-close {
  position: absolute;
  top: 24px;
  right: 32px;
  z-index: 3;
  background: none;
  border: none;
  color: #666;
  font-size: 1.5rem;
  cursor: pointer;
  transition: color 0.2s;
}
.fv-close:hover { color: #fff; }

@keyframes vision-breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.02); }
}
.vision-fade-enter-active { transition: opacity 0.6s ease; }
.vision-fade-leave-active { transition: opacity 0.4s ease; }
.vision-fade-enter-from,
.vision-fade-leave-to { opacity: 0; }
</style>
