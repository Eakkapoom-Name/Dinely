import { createRouter, createWebHistory } from 'vue-router'

// Customer view
import homePage from '../views/customer/homePage.vue'
import cart from '../views/customer/cart.vue'
import order from '../views/customer/order.vue'
import menu from '../views/customer/menu.vue'

// Staff views
import layout from '../views/staff/layout.vue'
import checkout from '../views/staff/Chashier/checkout.vue'
import tableManager from '../views/staff/adminPage/tablemanage/tableManager.vue'
import menuManager from '../views/staff/adminPage/menumanage/menuManager.vue'
import kitchen from '../views/staff/KDS/kitchen.vue'
import setting from '../views/staff/adminPage/settingpage/setting.vue'
import users from '../views/staff/adminPage/usermanage/users.vue'
import EditMenu from '../views/staff/adminPage/menumanage/EditMenu.vue'
import AddMenu from '../views/staff/adminPage/menumanage/AddMenu.vue'
import AddUser from '../views/staff/adminPage/usermanage/AddUser.vue'
import EditUser from '../views/staff/adminPage/usermanage/EditUser.vue'
import AddTable from '../views/staff/adminPage/tablemanage/AddTable.vue'
import EditTable from '../views/staff/adminPage/tablemanage/EditTable.vue'
import History from '../views/staff/KDS/history.vue'
import kdslayout from '../views/staff/KDS/layout.vue'
import Inventory from '../views/staff/KDS/Inventory.vue'
import statistics from '../views/staff/adminPage/statistics/statistics.vue'
import table from '../views/staff/Chashier/table.vue'
import setup from '../views/staff/setup.vue'
import login from '../views/staff/login.vue'
import roleselect from '../views/staff/roleselect.vue'
import loginsuccess from '../views/staff/loginsuccess.vue'
import register from '../views/staff/register.vue'
import api from '../api.js'

const routes = [
    // Customer routes
    { path: '/', redirect: '/staff/login' },
    { path: '/customer', name: 'customer-home', component: homePage },
    { path: '/customer/cart', name: 'customer-cart', component: cart },
    { path: '/customer/order', name: 'customer-order', component: order},
    { path: '/customer/menu', name: 'customer-menu', component: menu},
    { path: '/customer/:pathMatch(.*)*', redirect: '/customer' },

    // Auth routes
    { path: '/staff/setup', name: 'setup', component: setup },
    { path: '/staff/login', name: 'login', component: login },
    { path: '/staff/role-select', name: 'role-select', component: roleselect },
    { path: '/staff/register', name: 'register', component: register },
    { path: '/login-success', name: 'login-success', component: loginsuccess },
    { path: '/login', redirect: '/staff/login' },

    // Staff routes
    {
        path: '/staff',
        component: layout,
        children: [
            { path: '', redirect: '/staff/menu' },
            { path: 'tables', name: 'staff-tables',
                component: tableManager,
                children: [
                    { path: 'addTable', name: 'staff-tables-addTable', component: AddTable },
                    { path: ':id/edit', name: 'staff-tables-edit', component: EditTable },]},

            { path: 'menu', name: 'staff-menu',
                component: menuManager,
                children: [
                    { path: 'addMenu', name: 'staff-menu-addMenu', component: AddMenu },
                    { path: ':id/edit', name: 'staff-menu-edit', component: EditMenu },]},
            { path: 'users', name: 'staff-users',
                component: users,
                children: [
                    { path: 'addUser', name: 'staff-user-addUser', component: AddUser },
                    { path: ':id/edit', name: 'staff-user-edit', component: EditUser },]},
            { path: 'settings', name: 'staff-settings', component: setting },
            { path: 'statistics', name: 'staff-statistics', component: statistics },]},
    { path: '/checkout/:table_id', name: 'checkout', component: checkout },
    { path: '/table', name: 'staff-table', component: table },
    {   path: '/kitchen',
        component: kdslayout,
        children: [
            { path: '', name: 'staff-kitchen', component: kitchen },
            { path: 'history', name: 'staff-kitchen-history', component: History },
            { path: 'inventory', name: 'staff-kitchen-inventory', component: Inventory }
        ]
    },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

const roleRedirect = {
  admin: '/staff/menu',
  cashier: '/table',
  kitchen: '/kitchen'
}
const roleAllowed = {
  admin: null,
  cashier: ['/table', '/checkout'],
  kitchen: ['/kitchen']
}

// Routes that don't require authentication
const publicStaffRoutes = ['setup', 'login', 'login-success', 'register']

// Cache debug mode status
let debugModeCache = null

async function isDebugMode() {
  if (debugModeCache !== null) return debugModeCache
  try {
    const res = await api.get('/debug/config')
    debugModeCache = res.data.debug_mode
  } catch {
    debugModeCache = false
  }
  return debugModeCache
}

router.beforeEach(async (to, from, next) => {
  const token = localStorage.getItem('staff_token')
  const role = localStorage.getItem('role')

  const isStaffRoute = to.path.startsWith('/staff') ||
    to.path.startsWith('/kitchen') ||
    to.path.startsWith('/table') ||
    to.path.startsWith('/checkout')

  // Allow all non-staff routes (customer, login-success, etc.)
  if (!isStaffRoute && to.name !== 'login-success' && to.name !== 'register') return next()

  // Always allow public routes
  if (publicStaffRoutes.includes(to.name)) return next()

  // role-select: accessible via Google SSO or debug mode
  if (to.name === 'role-select') {
    const hasGoogleJwt = !!localStorage.getItem('google_jwt')
    const debug = await isDebugMode()
    if (!hasGoogleJwt && !debug) return next({ name: 'login' })
    return next()
  }

  // Cashier/Kitchen role-based access
  if (role === 'cashier' || role === 'kitchen') {
    const allowed = roleAllowed[role] || []
    const canAccess = allowed.some(p => to.path.startsWith(p))
    if (!canAccess) return next(roleRedirect[role])
    return next()
  }

  // No auth — redirect to login
  if (!token || !role) return next({ name: 'login' })

  // Admin — allow all
  if (role === 'admin') return next()

  return next({ name: 'login' })
})

export default router
