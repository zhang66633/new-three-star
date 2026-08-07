<template>
  <div class="archive-page">
    <button class="back-btn" @click="goBack">←</button>

    <!-- 加载 -->
    <div v-if="loading" class="archive-loading">
      <span class="gold-dot"></span>
      <span>正在展开档案……</span>
    </div>

    <!-- 档案内容 -->
    <div v-else-if="archive" class="archive-content">
      <!-- 封面 -->
      <header class="archive-cover">
        <h1 class="archive-name">{{ archive.name }}</h1>
        <p class="archive-tagline">{{ archive.tagline }}</p>
        <div class="goldline"></div>
      </header>

      <!-- 核心隐喻 -->
      <section class="archive-section">
        <h2 class="section-title">核心隐喻</h2>
        <p class="section-text">{{ archive.core_metaphor }}</p>
      </section>

      <!-- 天意解读 -->
      <section v-if="archive.tianyi_interpretation" class="archive-section">
        <h2 class="section-title">天意解读</h2>
        <p class="section-text">{{ archive.tianyi_interpretation }}</p>
      </section>

      <!-- 关键设定 -->
      <section v-if="archive.key_points?.length" class="archive-section">
        <h2 class="section-title">关键设定</h2>
        <ul class="key-points">
          <li v-for="(kp, i) in archive.key_points" :key="i" class="key-point">{{ kp }}</li>
        </ul>
      </section>

      <!-- 角色定位 -->
      <section v-if="archive.character_roles && Object.keys(archive.character_roles).length" class="archive-section">
        <h2 class="section-title">角色定位</h2>
        <div class="role-list">
          <div v-for="(desc, name) in archive.character_roles" :key="name" class="role-card">
            <span class="role-name">{{ name }}</span>
            <span class="role-desc">{{ desc }}</span>
          </div>
        </div>
      </section>

      <!-- 适用场景 -->
      <section v-if="archive.suitable_scenes?.length" class="archive-section">
        <h2 class="section-title">适合解读的场景</h2>
        <div class="scene-tags">
          <span v-for="(s, i) in archive.suitable_scenes" :key="i" class="scene-tag">{{ s }}</span>
        </div>
      </section>

      <!-- 关键词 -->
      <section v-if="archive.keywords?.length" class="archive-section">
        <h2 class="section-title">关键词</h2>
        <div class="scene-tags">
          <span v-for="(k, i) in archive.keywords" :key="i" class="scene-tag kw">{{ k }}</span>
        </div>
      </section>
    </div>

    <!-- 未找到 -->
    <div v-else class="archive-missing">
      <p>档案不存在。</p>
      <button class="back-star-btn" @click="goBack">返回星图</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const API_BASE = import.meta.env.VITE_API_BASE || ''

const loading = ref(true)
const archive = ref<Record<string, any> | null>(null)

onMounted(async () => {
  try {
    const id = route.params.id as string
    const resp = await fetch(`${API_BASE}/api/archive/${encodeURIComponent(id)}`)
    if (resp.ok) {
      archive.value = await resp.json()
    }
  } catch (e) {
    console.error('档案加载失败:', e)
  } finally {
    loading.value = false
  }
})

function goBack() {
  router.push('/')
}
</script>

<style scoped>
.archive-page {
  width: 100%;
  height: 100%;
  background: radial-gradient(ellipse at 50% 30%, #0f0f23 0%, #020203 75%);
  overflow-y: auto;
  position: relative;
  padding: 60px 12% 80px;
}

.back-btn {
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 50;
  background: rgba(15, 15, 35, 0.6);
  border: 1px solid rgba(202, 138, 4, 0.3);
  color: #ca8a04;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s ease;
}
.back-btn:hover {
  background: rgba(202, 138, 4, 0.15);
  border-color: rgba(202, 138, 4, 0.7);
}

.archive-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: 12px;
  color: rgba(148, 163, 184, 0.7);
  letter-spacing: 0.3em;
  font-size: 0.85rem;
}
.gold-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #ca8a04;
  box-shadow: 0 0 10px rgba(202, 138, 4, 0.8);
  animation: gold-pulse 1.2s ease-in-out infinite;
}
@keyframes gold-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1.2); }
}

.archive-cover {
  text-align: center;
  margin-bottom: 40px;
}
.archive-name {
  font-family: var(--font-display);
  font-size: clamp(2rem, 5vw, 3rem);
  font-weight: 900;
  letter-spacing: 0.3em;
  background: linear-gradient(180deg, #ffffff 0%, #e2d8b0 45%, #ca8a04 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}
.archive-tagline {
  margin-top: 12px;
  font-size: 1rem;
  letter-spacing: 0.2em;
  color: rgba(202, 138, 4, 0.7);
}
.goldline {
  width: 200px;
  height: 1px;
  margin: 24px auto 0;
  background: linear-gradient(90deg, transparent, rgba(202, 138, 4, 0.7), transparent);
}

.archive-section {
  margin-bottom: 36px;
}
.section-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.3em;
  color: #ca8a04;
  margin-bottom: 14px;
}
.section-text {
  font-size: 1rem;
  line-height: 2;
  color: rgba(248, 250, 252, 0.9);
  text-align: justify;
}
.key-points {
  list-style: none;
  padding: 0;
}
.key-point {
  padding: 10px 0 10px 16px;
  border-left: 2px solid rgba(202, 138, 4, 0.3);
  margin-bottom: 8px;
  font-size: 0.95rem;
  line-height: 1.8;
  color: rgba(248, 250, 252, 0.85);
}
.role-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.role-card {
  display: flex;
  gap: 12px;
  align-items: baseline;
  padding: 10px 14px;
  background: rgba(15, 15, 35, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
}
.role-name {
  color: #e8a838;
  font-weight: 700;
  flex-shrink: 0;
  min-width: 70px;
}
.role-desc {
  font-size: 0.9rem;
  color: rgba(248, 250, 252, 0.8);
  line-height: 1.7;
}
.scene-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.scene-tag {
  padding: 5px 12px;
  border: 1px solid rgba(202, 138, 4, 0.3);
  border-radius: 20px;
  font-size: 0.8rem;
  color: rgba(232, 168, 56, 0.9);
}
.scene-tag.kw {
  border-color: rgba(148, 163, 184, 0.25);
  color: rgba(148, 163, 184, 0.8);
}

.archive-missing {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  color: rgba(148, 163, 184, 0.6);
}
.back-star-btn {
  background: rgba(202, 138, 4, 0.15);
  border: 1px solid rgba(202, 138, 4, 0.5);
  color: #ca8a04;
  border-radius: 20px;
  padding: 8px 20px;
  cursor: pointer;
  font-family: var(--font-body);
}
</style>
