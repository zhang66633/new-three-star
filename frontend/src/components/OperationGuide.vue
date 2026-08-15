<template>
  <!-- 操作引导（首次进入游戏显示）：讲解视角前进/选项/自由行动/菜单/存档 -->
  <div class="ops-guide">
    <div class="ops-card">
      <h2 class="ops-title">行 事 之 道</h2>
      <p class="ops-sub">几个简单操作，助你行走这方错乱的三国</p>
      <div class="ops-list">
        <div class="ops-item">
          <span class="ops-key">📖 视角前进</span>
          <span class="ops-desc">剧情自动流入；输入框留空直接发送即「继续前行」，视角随世道推进</span>
        </div>
        <div class="ops-item">
          <span class="ops-key">🗞 抉择选项</span>
          <span class="ops-desc">银色选项在剧情落定后浮现，点击即选——每一个都改变走向</span>
        </div>
        <div class="ops-item">
          <span class="ops-key">✍️ 自由行动</span>
          <span class="ops-desc">在输入框写下任何想做的事——「放走曹操」「去洛阳」「打听许攸」，天意都会回应</span>
        </div>
        <div class="ops-item">
          <span class="ops-key">🧭 菜单</span>
          <span class="ops-desc">右下打开 地图 / 档案 / 在场 / 天下事 / 关系网，随时查看自身处境</span>
        </div>
        <div class="ops-item">
          <span class="ops-key">💾 自动存档</span>
          <span class="ops-desc">每拍自动落盘，可随时回到星图，下次接着来</span>
        </div>
        <div class="ops-item">
          <span class="ops-key">🕯 暗线伏笔</span>
          <span class="ops-desc">乱世藏着未尽的伏笔——留意叙事中的暗示，自由行动或可抓住</span>
        </div>
      </div>
      <button class="ops-begin" @click="dismiss">懂了，开始行路</button>
    </div>
  </div>
</template>

<script setup lang="ts">
// OperationGuide —— 首次进入游戏的操作引导（localStorage 记一次，之后不再打扰）
const SEEN_KEY = 'sg3d_ops_guide_seen'

const emit = defineEmits<{ (e: 'close'): void }>()

function dismiss() {
  try { localStorage.setItem(SEEN_KEY, '1') } catch { /* 隐私模式忽略 */ }
  emit('close')
}
</script>

<style scoped>
.ops-guide {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(3, 3, 6, 0.72);
  backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ops-card {
  width: min(560px, 92vw);
  max-height: 86vh;
  overflow-y: auto;
  background: rgba(10, 10, 18, 0.94);
  border: 1px solid rgba(202, 138, 4, 0.28);
  border-radius: 16px;
  padding: 26px 28px;
  box-shadow: 0 0 60px rgba(202, 138, 4, 0.12);
}
.ops-title {
  font-family: var(--font-display, 'Ma Shan Zheng', serif);
  font-size: 26px;
  text-align: center;
  letter-spacing: 6px;
  color: var(--accent-gold, #c9a24b);
  margin: 0 0 6px;
}
.ops-sub {
  text-align: center;
  font-size: 13px;
  color: var(--text-muted, rgba(200, 200, 220, 0.6));
  margin: 0 0 18px;
}
.ops-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ops-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding: 10px 14px;
  border-left: 2px solid rgba(202, 138, 4, 0.4);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}
.ops-key {
  font-size: 14px;
  font-weight: 600;
  color: #ececf2;
}
.ops-desc {
  font-size: 12.5px;
  line-height: 1.6;
  color: rgba(220, 220, 235, 0.78);
}
.ops-begin {
  margin-top: 20px;
  width: 100%;
  padding: 12px;
  border: 1px solid rgba(202, 138, 4, 0.5);
  background: rgba(202, 138, 4, 0.12);
  color: var(--accent-gold, #c9a24b);
  font-size: 15px;
  font-family: var(--font-display, 'Ma Shan Zheng', serif);
  letter-spacing: 3px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}
.ops-begin:hover {
  background: rgba(202, 138, 4, 0.22);
}
</style>
