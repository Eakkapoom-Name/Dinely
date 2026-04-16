import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import router from './router'
import api from './api.js'

const app = createApp(App);
app.use(createPinia()); // Add Pinia
app.use(router);

api.interceptors.response.use(
    response => response,
    error => Promise.reject(error)
)

app.mount("#app");
