# ระบบสั่งอาหาร (Food Ordering System)

## Team: (25cs212g10) TaskFailedSuccessfully
### Project: 4 ระบบสั่งอาหาร
**Group ID:** 25cs212g10
**Mentor:** พี่ดร.โสภณ (66)

---

### Tech Stack:
- **Frontend:** Vue 3, Vite, Vue Router, Pinia, Tailwind CSS, Axios, vue-cookies, jwt-decode
- **Backend:** FastAPI, SQLAlchemy (Async), Alembic, Pydantic v2, Gunicorn, Uvicorn
- **Database:** PostgreSQL (Supabase / Local Docker)
- **Authentication:** JWT (python-jose, PyJWT), Google OAuth 2.0 (Authlib), LINE Login, CSRF Protection
- **Deployment:** Vercel (Serverless), Docker Compose (Local Development)
- **Other:** QR Code Generation (qrcode), Supabase Storage (Image Upload), Pillow (Image Processing), HTTPX

### Members:

#### 1. ยุวดี สุดใจ
- **Student ID:** 660510721
- **GitHub ID:** [Mfei66](https://github.com/mfei66)
- **Role:** Frontend

#### 2. เอกภูมิ ม้าเพ็ง
- **Student ID:** 670510686
- **GitHub ID:** [Eakkapoom-Name](https://github.com/Eakkapoom-Name)
- **Role:** Fullstack

#### 3. คมภณ บุรุษศรี
- **Student ID:** 670510691
- **GitHub ID:** [jayenzf](https://github.com/jayenzf)
- **Role:** Fullstack

#### 4. จักรินทร์ หายโศก
- **Student ID:** 670510693
- **GitHub ID:** [petezaboyyy](https://github.com/petezaboyyy)
- **Role:** Backend

#### 5. ณัฐณิชา สมเป้า
- **Student ID:** 670510705
- **GitHub ID:** [Fi11Ter](https://github.com/Fi11Ter)
- **Role:** Frontend

---

## System Architecture

The application is composed of three primary services orchestrated via Docker Compose:

*   **Frontend**: A Single Page Application (SPA) built with Vue 3 and Vite. It serves the user interface and communicates with the backend via RESTful API calls. All API requests are prefixed with `/api` and proxied through Vite in development or routed via `vercel.json` in production.
*   **Backend**: A Python-based REST API built with FastAPI. It handles data persistence, business logic, authentication (JWT + Google OAuth + LINE Login), and CSRF protection via custom middleware.
*   **Database**: PostgreSQL for relational data storage. Supports two modes:
    *   **Local**: A Dockerized PostgreSQL 13 Alpine container (activated with `--profile with-db`).
    *   **Remote**: Supabase managed PostgreSQL (set `USE_SUPABASE=true` in `.env`).

## Project Structure

```
├── .env.example                  # Environment variable template
├── .dockerignore                 # Docker ignore rules
├── .gitignore                    # Git ignore rules
├── docker-compose.yml            # Docker Compose orchestration (fastapi, frontend, db services)
├── vercel.json                   # Vercel deployment configuration (routes & builds)
├── run.sh                        # Local startup script (auto-detects Supabase vs local DB)
├── package.json                  # Root package.json (Vercel build script)
├── README.md                     # This file
│
├── design/                       # Design assets
│   ├── db/
│   │   └── db.png                # Database schema diagram
│   └── ui/
│       ├── v0/                   # Initial UI mockups
│       │   ├── customers_home_page.png
│       │   ├── customers_in_cart_page.png
│       │   ├── customers_menu_page.png
│       │   ├── customers_order_page.png
│       │   ├── staff_checkout_page.png
│       │   ├── staff_kitchen_page.png
│       │   ├── staff_login_page.jpg
│       │   ├── staff_menu_page.png
│       │   └── staff_table_page.png
│       └── v1/                   # Revised UI mockups
│           ├── admin_dashboard.png
│           ├── admin_menu_edit.png
│           ├── admin_menu_management.png
│           ├── admin_table_edit.png
│           ├── admin_table_management.png
│           ├── admin_user_management1.png
│           ├── admin_user_management2.png
│           ├── Cashier_Checkout.png
│           ├── Cashier_Table_management.png
│           ├── Customers_Discription.png
│           ├── Customers_Home.png
│           ├── Customers_In_Cart.png
│           ├── Customers_Ordered.png
│           ├── KDS_dashboard.png
│           ├── KDS_menu_management.png
│           └── Login.png
│
├── img/                          # Documentation images
│   ├── supabase_connect.png
│   ├── supabase_overview.png
│   ├── supabase_pooler.png
│   └── supabase_schema.png
│
├── fastapi/                      # Backend application
│   ├── Dockerfile                # Backend Docker image
│   ├── main.py                   # Application entry point (registers all routers)
│   ├── requirements.txt          # Python dependencies
│   ├── gunicorn.config.py        # Gunicorn server configuration
│   ├── uvicorn_starter.sh        # Uvicorn startup script
│   ├── alembic.ini               # Alembic configuration
│   ├── alembic/                  # Database migrations
│   │   ├── env.py                # Alembic environment setup
│   │   ├── script.py.mako        # Migration template
│   │   ├── README
│   │   └── versions/
│   │       ├── 001_add_stores_and_store_id.py
│   │       └── 002_add_order_number.py
│   ├── app/                      # Core application package
│   │   ├── __init__.py           # FastAPI app factory, CORS & CSRF middleware
│   │   ├── config.py             # Settings (pydantic-settings, reads .env)
│   │   ├── db.py                 # Async SQLAlchemy engine & session
│   │   ├── env_detector.py       # Detects Docker vs Vercel environment
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── authuser.py       # Auth user model
│   │   │   └── database_models.py # All DB models (Store, Staff, MenuItems, Orders, etc.)
│   │   ├── routers/
│   │   │   ├── auth.py           # Authentication (Google OAuth, LINE Login, JWT, QR login)
│   │   │   ├── cart_items.py     # Customer cart CRUD
│   │   │   ├── categories.py     # Menu categories
│   │   │   ├── customers.py      # Customer sessions
│   │   │   ├── daily_business_stats.py   # Daily revenue & order statistics
│   │   │   ├── daily_item_performance.py # Per-item daily sales analytics
│   │   │   ├── debug.py          # Debug/testing endpoints
│   │   │   ├── menu_items.py     # Menu item CRUD (with add-ons, image upload)
│   │   │   ├── order_items.py    # Individual order item management
│   │   │   ├── orders.py         # Order lifecycle (create, status updates, payment)
│   │   │   ├── restaurant_setting.py # Restaurant settings (name, hours, tax, service charge)
│   │   │   ├── staff.py          # Staff management (roles, accounts)
│   │   │   └── tables.py         # Table CRUD & QR code generation
│   │   ├── schemas/
│   │   │   ├── auth.py           # Auth request/response schemas
│   │   │   └── schemas.py        # Pydantic schemas for all models
│   │   └── utilities/
│   │       ├── auth.py           # JWT token creation & validation helpers
│   │       ├── qr_code.py        # QR code generation utility
│   │       ├── security.py       # Password hashing (bcrypt)
│   │       ├── timezone.py       # Bangkok timezone helper
│   │       └── upload.py         # Image upload to Supabase Storage
│   └── static/
│       ├── qr_codes/             # Generated QR code images
│       └── uploads/              # Uploaded menu item images
│
└── frontend/                     # Frontend application
    ├── Dockerfile                # Frontend Docker image
    ├── package.json              # Node dependencies & scripts
    ├── bun.lock                  # Bun lockfile
    ├── index.html                # SPA entry HTML
    ├── vite.config.js            # Vite config (dev proxy to backend)
    ├── tailwind.config.js        # Tailwind CSS configuration
    ├── postcss.config.js         # PostCSS configuration
    ├── start_vue.sh              # Frontend startup script
    ├── README.md                 # Vue scaffolding readme
    ├── public/
    │   └── vite.svg              # Default Vite favicon
    └── src/
        ├── main.js               # Vue app bootstrap (Pinia, Router, Cookies)
        ├── App.vue               # Root Vue component
        ├── style.css             # Global styles (Tailwind directives)
        ├── api.js                # Legacy API client
        ├── assets/               # Static assets (icons, images, CSS)
        │   ├── arrow_button.png
        │   ├── back_button.png
        │   ├── bill_icon.png
        │   ├── cart_icon.png
        │   ├── cashier.png
        │   ├── default_img.png
        │   ├── n_b.png
        │   ├── p_g.png
        │   ├── p_w.png
        │   ├── temp.css
        │   └── vue.svg
        ├── components/
        │   └── __init__.vue      # Placeholder component
        ├── router/
        │   └── index.js          # Vue Router configuration (all routes)
        ├── services/
        │   └── api.js            # Axios API client (with CSRF interceptor)
        ├── stores/
        │   ├── cache.js          # Pinia cache store
        │   ├── customer.js       # Customer session store (cart, table, orders)
        │   └── staff.js          # Staff session store (auth, role)
        └── views/
            ├── customer/                 # Customer-facing pages (mobile-optimized)
            │   ├── homePage.vue          # Menu browsing home page
            │   ├── menu.vue             # Menu item detail & add-ons selection
            │   ├── cart.vue             # Shopping cart
            │   └── order.vue            # Order tracking
            └── staff/                    # Staff-facing pages
                ├── login.vue             # Staff login (Google OAuth / LINE Login)
                ├── loginsuccess.vue      # OAuth callback handler
                ├── register.vue          # Staff registration
                ├── roleselect.vue        # Role selection (Admin/Kitchen/Cashier)
                ├── setup.vue             # Initial store setup
                ├── layout.vue            # Staff main layout with sidebar navigation
                ├── Chashier/             # Cashier module
                │   ├── table.vue         # Table status overview
                │   └── checkout.vue      # Payment processing
                ├── KDS/                  # Kitchen Display System module
                │   ├── layout.vue        # KDS layout with navigation
                │   ├── kitchen.vue       # Active order queue
                │   ├── Inventory.vue     # Menu inventory management
                │   └── history.vue       # Completed order history
                └── adminPage/            # Admin module
                    ├── menumanage/
                    │   ├── menuManager.vue   # Menu item list
                    │   ├── AddMenu.vue       # Add new menu item
                    │   └── EditMenu.vue      # Edit menu item
                    ├── tablemanage/
                    │   ├── tableManager.vue  # Table list & QR codes
                    │   ├── AddTable.vue      # Add new table
                    │   └── EditTable.vue     # Edit table
                    ├── usermanage/
                    │   ├── users.vue         # Staff user list
                    │   ├── AddUser.vue       # Add staff user
                    │   └── EditUser.vue      # Edit staff user
                    ├── settingpage/
                    │   └── setting.vue       # Restaurant settings
                    └── statistics/
                        └── statistics.vue    # Business analytics dashboard
```

## Local Development Setup

The project runs in a containerized environment using Docker Compose.

### 1. Environment Configuration

Copy the example configuration file and update the values with your credentials.

```bash
cp .env.example .env
```

### 2. Service Initialization

Execute the initialization script to start the services. The script automatically detects the database configuration from `.env`.

```bash
./run.sh
```

**Database Modes:**
*   **Local**: Uses a local PostgreSQL 13 container (default when `USE_SUPABASE` is not set).
*   **Remote**: Set `USE_SUPABASE=true` in `.env` to connect to a managed Supabase instance.

### 3. Access Points

*   **Frontend**: `http://localhost:8080`
*   **Backend API**: `http://localhost:56733`
*   **API Documentation (Swagger)**: `http://localhost:56733/api/docs` (Direct) or `http://localhost:8080/api/docs` (Proxied)

## Deployment (Vercel)

The application is configured for deployment on the Vercel platform. The `vercel.json` routes `/api/*` requests to the FastAPI backend and serves the Vue SPA for all other paths.

1.  **Install Vercel CLI**:
    ```bash
    npm i -g vercel
    ```

2.  **Deploy**:
    ```bash
    vercel --prod
    ```

### Configuration Requirements

Set the following environment variables in the Vercel Project Dashboard:

*   `SUPABASE_DB_URL`: Connection string for the production database.
*   `SUPABASE_PROJECT_URL` / `SUPABASE_API_KEY`: Supabase project credentials (for image storage).
*   `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`: Google OAuth credentials.
*   `LINE_APP_ID` / `LINE_APP_SECRET`: LINE Login credentials.
*   `SECRET_KEY` / `JWT_SECRET_KEY`: Cryptographic signing keys.
*   `APP_ENV`: Set to `production`.
*   `VITE_API_BASE_URL`: Set to `https://<your-project>.vercel.app/api`.
*   `FRONTEND_LOGIN_SUCCESS_URI`: Set to `https://<your-project>.vercel.app/login-success`.
*   `GOOGLE_OAUTH_REDIRECT_URI`: Set to `https://<your-project>.vercel.app/api/google/auth`.
*   `LINE_OAUTH_REDIRECT_URI`: Set to `https://<your-project>.vercel.app/api/line/auth`.

Build settings are overridden by `vercel.json` and do not require manual configuration.

## Authentication

Authentication is implemented using JSON Web Tokens (JWT) and OAuth 2.0 with CSRF protection middleware.

*   **Staff Authentication**: Google OAuth 2.0 or LINE Login. Supports three roles: **Admin**, **Kitchen**, and **Cashier**. Staff JWT is stored in a `jwt` cookie.
*   **Customer Authentication**: QR code-based session. Customers scan a table-specific QR code which creates a JWT session stored in a `jwt_customer` cookie. No login required.
*   **CSRF Protection**: All mutating requests (POST, PUT, PATCH, DELETE) require an `X-CSRF-Token` header that matches the token embedded in the JWT payload.

### OAuth Redirect URIs

*   **Google OAuth**:
    *   Local: `http://localhost:8080/api/google/auth`
    *   Production: `https://<your-project>.vercel.app/api/google/auth`
*   **LINE Login**:
    *   Local: `http://localhost:8080/api/line/auth`
    *   Production: `https://<your-project>.vercel.app/api/line/auth`

## API Endpoints

The backend exposes the following router groups (all prefixed with `/api`):

| Router | Description |
|---|---|
| Auth | Google OAuth, LINE Login, JWT login, QR customer login, logout |
| Restaurant Settings | Store name, open/close hours, tax %, service charge % |
| Menu Items | CRUD for menu items with add-ons (JSONB), image upload, recommended items |
| Categories | Menu categories management |
| Staff | Staff account & role management |
| Cart Items | Customer cart operations (add, update, remove) |
| Customers | Customer session management |
| Tables | Table CRUD, status management, QR code generation |
| Orders | Order lifecycle (create, status transitions, payment) |
| Order Items | Individual order item status management (PREPARING → FINISHED) |
| Daily Item Performance | Per-item sales analytics |
| Daily Business Stats | Daily revenue, order count, and business statistics |
| Debug | Debug/testing utilities (excluded from CSRF validation) |

## Dependency Management

Dependencies are managed separately for each service:

*   **Frontend**: `npm install` (within `frontend/` directory)
*   **Backend**: `pip install -r requirements.txt` (within `fastapi/` directory)

## Notes

- The system supports **multi-store architecture** where each staff account is scoped to their own store.
- Table status follows a state machine: **FREE → PENDING → PREPARING → WAITING_FOR_PAYMENT → FREE**.
- Kitchen Display System (KDS) allows kitchen staff to manage order items with **PREPARING → FINISHED** status flow.
- Cashier can view table statuses, process payments, and manage the order lifecycle.
- Customer-facing pages are **mobile-optimized** with QR code entry for table sessions.
- Menu items support **add-ons** stored as JSONB (key-value pairs of addon name → price).
- The admin dashboard includes **business analytics** with daily revenue and per-item performance tracking.
- Restaurant settings allow configuring **tax percentage** and **service charge percentage** per store.
- The debug mode (`DEBUG_MODE=true` in `.env`) enables a debugger button on the login page for development.
