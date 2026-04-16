import axios from 'axios'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
    headers: { 'Content-Type': 'application/json' },
    withCredentials: true
})

api.interceptors.request.use(config => {
    if (config.data instanceof FormData) {
        delete config.headers['Content-Type']
    }

    const token = localStorage.getItem('staff_token')
    if (token && !config.headers['X-Customer-Token']) {
        config.headers.Authorization = `Bearer ${token}`
    }

    const localCsrf = localStorage.getItem('csrf_token')
    const cookies = document.cookie.split('; ')
    const csrfCookie = cookies.find(row =>
        row.trim().startsWith('csrf_access_token=') ||
        row.trim().startsWith('csrf_token=')
    )

    if (localCsrf) {
        config.headers['X-CSRF-Token'] = localCsrf
    } else if (csrfCookie) {
        config.headers['X-CSRF-Token'] = csrfCookie.split('=')[1]
    }

    return config
}, error => {
    return Promise.reject(error)
})

export default api