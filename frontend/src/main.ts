import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './styles/global.css'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: () => import('./pages/LandingPage.vue') },
    { path: '/worldview/:id', name: 'explore', component: () => import('./pages/ExplorePage.vue') },
    { path: '/create', name: 'create', component: () => import('./pages/CreatePage.vue') },
    { path: '/play', name: 'play', component: () => import('./pages/TianyiPage.vue') },
  ],
})

createApp(App).use(router).mount('#app')
