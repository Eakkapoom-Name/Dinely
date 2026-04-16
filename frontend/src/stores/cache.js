import { defineStore } from 'pinia'
import { ref } from 'vue'

const CACHE_TTL = 30000 // 30 seconds

export const useCacheStore = defineStore('cache', () => {
  // Admin data caches
  const tables = ref(null)
  const menuItems = ref(null)
  const categories = ref(null)
  const categoriesRaw = ref(null)
  const currencySymbol = ref(null)
  const users = ref(null)
  const settings = ref(null)
  const businessStats = ref(null)
  const itemPerformance = ref(null)

  // Customer data caches
  const customerMenus = ref(null)
  const customerCategories = ref(null)
  const customerSettings = ref(null)
  const customerCartItems = ref(null)
  const customerOrderItems = ref(null)

  // Timestamps for TTL tracking
  const _timestamps = ref({})

  const _cacheMap = () => ({
    tables, menuItems, categories, categoriesRaw,
    currencySymbol, users, settings,
    businessStats, itemPerformance,
    customerMenus, customerCategories, customerSettings,
    customerCartItems, customerOrderItems
  })

  function set(key, value) {
    const map = _cacheMap()
    if (map[key]) {
      map[key].value = value
      _timestamps.value[key] = Date.now()
    }
  }

  function get(key) {
    const map = _cacheMap()
    return map[key]?.value ?? null
  }

  function isFresh(key) {
    const ts = _timestamps.value[key]
    if (!ts) return false
    return (Date.now() - ts) < CACHE_TTL
  }

  function invalidate(...keys) {
    const map = _cacheMap()
    for (const key of keys) {
      if (map[key]) {
        map[key].value = null
        delete _timestamps.value[key]
      }
    }
  }

  function invalidateAll() {
    tables.value = null
    menuItems.value = null
    categories.value = null
    categoriesRaw.value = null
    currencySymbol.value = null
    users.value = null
    settings.value = null
    businessStats.value = null
    itemPerformance.value = null
    customerMenus.value = null
    customerCategories.value = null
    customerSettings.value = null
    customerCartItems.value = null
    customerOrderItems.value = null
    _timestamps.value = {}
  }

  return {
    tables, menuItems, categories, categoriesRaw,
    currencySymbol, users, settings,
    businessStats, itemPerformance,
    customerMenus, customerCategories, customerSettings,
    customerCartItems, customerOrderItems,
    set, get, isFresh, invalidate, invalidateAll
  }
})
