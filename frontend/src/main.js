import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/main.css'
import { brand } from './brand'
import { resolveBrand, initBrand } from './theme'

// E1：初始化品牌色阶；优先读取 window.__JTW_BRAND__ 运行期覆盖（运维不用重新构建）
initBrand(resolveBrand(brand))

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
