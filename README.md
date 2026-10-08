# 🛡️ SERM API - Service & Economy Reputation Management

<div align="center">

![SERM API](https://img.shields.io/badge/SERM-API-blue?style=for-the-badge&logo=fastapi&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-green?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-teal?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue?style=for-the-badge&logo=postgresql&logoColor=white)

*Enterprise-grade API for reputation management and economic impact analysis of customer reviews*

[📚 Documentation](#-documentation) • [🚀 Quick Start](#-quick-start) • [🏗️ Architecture](#️-architecture) • [🔐 Multi-tenancy](#-multi-tenancy) • [📊 API Reference](#-api-reference)

</div>

---

## 🌟 Features

### 🎯 **Core Capabilities**
- **💰 Economic Impact Analysis** - Real-time LTV calculations and revenue impact assessment
- **🤖 AI-Powered Response Generation** - Automated review responses via OpenAI GPT integration
- **📊 Sentiment Analysis & Prioritization** - Smart review categorization with urgency detection
- **🔄 Multi-platform Integration** - Support for Google Maps, 2GIS, Trustpilot, and custom sources
- **📈 Advanced Analytics** - ROI tracking, conversion metrics, and financial forecasting

### 🔐 **Enterprise Security**
- **🏢 Multi-tenant Architecture** - Complete data isolation using PostgreSQL Row Level Security (RLS)
- **🔑 JWT Authentication** - RS256/JWKS support with Supabase integration
- **🛡️ Role-based Access Control** - Secure tenant isolation and permission management
- **🔒 Audit Trail** - Comprehensive logging with request tracing

### ⚡ **Modern Architecture**
- **🎯 Three-tier Design** - Clean separation: Routers → Services → Repositories
- **🧩 Dependency Injection** - Modular, testable, and maintainable codebase
- **🚨 Centralized Error Handling** - Standardized error responses with localization
- **📦 Async/Await** - High-performance async operations throughout

---

## 🏗️ Architecture

SERM API follows a **three-tier architecture** with multi-tenant security:

```mermaid
graph TD
    A[Client Request] --> B[FastAPI Router]
    B --> C[Authentication Layer]
    C --> D[Business Logic Services]
    D --> E[Repository Layer]
    E --> F[PostgreSQL with RLS]
    
    G[JWT Token] --> C
    H[OpenAI API] --> D
    I[Tenant Context] --> F
    
    subgraph "Security Layers"
    C --> J[AuthContext]
    J --> K[Tenant Session]
    K --> L[RLS Policies]
    end
```

### 📁 **Project Structure**

```
serm-api/
├── 🔐 app/auth/              # Authentication & JWT handling
├── 🧠 app/services/          # Business logic layer
│   ├── economics.py          # LTV & financial impact calculations
│   ├── llm.py               # AI response generation
│   ├── sentiment.py         # Review analysis & prioritization
│   └── review_processor.py  # Central review orchestration
├── 🗄️ app/repositories/      # Data access layer
│   ├── base.py              # Generic CRUD operations
│   ├── company.py           # Company data management
│   ├── platform.py          # Review platform handling
│   └── review.py            # Review operations & analytics
├── 🌐 app/routers/           # API endpoints
│   ├── economics.py         # Financial simulation & analysis
│   ├── reviews.py           # Review management & webhooks
│   ├── companies.py         # Company CRUD operations
│   └── platforms.py         # Platform management
├── 📊 app/models/            # SQLAlchemy data models
├── 📋 app/schemas/           # Pydantic validation schemas
├── 🔧 app/migrations/        # Database migrations & RLS setup
└── 📚 docs/                 # Architecture & deployment guides
```

---

## 🚀 Quick Start

### 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+** with asyncpg support
- **OpenAI API Key** for AI response generation
- **JWT Provider** (Supabase recommended) or custom JWKS endpoint

### ⚡ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/serm-api.git
   cd serm-api
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   # Standard migrations
   python app/migrations/run_migration.py
   
   # Multi-tenancy setup
   python app/migrations/run_multitenancy_migration.py
   ```

6. **Start the development server**
   ```bash
   python run.py
   ```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

---

## ⚙️ Configuration

### 🔧 **Environment Variables**

Create a `.env` file based on `.env.example`:

```bash
# Database Configuration
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/serm_db
TENANT_DATABASE_URL=postgresql+asyncpg://app_tenant:tenant_password@localhost:5432/serm_db
USE_TENANT_ROLE=true

# JWT Authentication
AUTH_JWT_ALGORITHM=RS256
AUTH_JWKS_URL=https://your-project.supabase.co/auth/v1/jwks

# OpenAI Integration
OPENAI_API_KEY=sk-your-openai-api-key-here
OPENAI_MODEL=gpt-4o-mini

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
SQL_ECHO=false

# SERM Configuration
DEFAULT_LOST_LEADS_COEFFICIENT=5
DEFAULT_POSITIVE_BOOST_COEFFICIENT=0.5
```

### 🗄️ **Database Setup**

1. **Create PostgreSQL database**
   ```sql
   CREATE DATABASE serm_db;
   ```

2. **Run multi-tenancy migrations**
   ```bash
   python app/migrations/run_multitenancy_migration.py
   ```

3. **Set up tenant role password**
   ```sql
   ALTER ROLE app_tenant PASSWORD 'secure_tenant_password';
   ```

4. **Configure Supabase Custom Access Token Hook**
   - Navigate to Supabase Dashboard
   - Go to Authentication → Hooks → Custom Access Token
   - Enable the hook created by migration `002_custom_access_token_hook.sql`

---

## 🔐 Multi-tenancy

SERM API implements **enterprise-grade multi-tenancy** using PostgreSQL Row Level Security (RLS):

### 🏢 **How It Works**

1. **JWT Authentication** - Extract `company_id` from JWT token
2. **Tenant Context** - Set `app.company_id` session variable
3. **RLS Policies** - Automatic data filtering at database level
4. **Complete Isolation** - Each tenant sees only their own data

### 🛡️ **Security Features**

- **Automatic Data Isolation** - No application-level filtering required
- **Secure Role Separation** - `postgres` for admin, `app_tenant` for runtime
- **Session-scoped Context** - Tenant context limited to transaction lifetime
- **Audit Trail** - All operations logged with tenant information

### 🔑 **Authentication Flow**

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API
    participant J as JWT Handler
    participant D as Database
    
    C->>A: Request + JWT Token
    A->>J: Verify Token
    J->>J: Extract company_id
    J->>A: AuthContext
    A->>D: SET app.company_id
    D->>D: Apply RLS Policies
    D->>A: Filtered Results
    A->>C: Response (tenant-isolated)
```

**👉 For detailed setup instructions, see [MULTITENANCY_GUIDE.md](MULTITENANCY_GUIDE.md)**

---

## 📊 API Reference

### 🔐 **Authentication**

All endpoints require JWT authentication:

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     https://api.serm.com/api/v1/economics/simulate
```

### 🎯 **Core Endpoints**

#### **Economic Analysis**
```http
POST /api/v1/economics/simulate
POST /api/v1/economics/process
POST /api/v1/economics/bulk-process
GET  /api/v1/economics/platform/{id}/roi
GET  /api/v1/economics/platform/{id}/risk-assessment
```

#### **Review Management**
```http
POST /api/v1/reviews/webhook
GET  /api/v1/reviews/{id}
GET  /api/v1/reviews/platform/{id}/reviews
PUT  /api/v1/reviews/{id}/status
GET  /api/v1/reviews/search
```

#### **Company Operations**
```http
GET    /api/v1/companies/
POST   /api/v1/companies/
GET    /api/v1/companies/{id}
PUT    /api/v1/companies/{id}
GET    /api/v1/companies/{id}/dashboard
```

#### **Platform Management**
```http
GET    /api/v1/platforms/
POST   /api/v1/platforms/
GET    /api/v1/platforms/{id}
PUT    /api/v1/platforms/{id}/metrics
GET    /api/v1/platforms/stats
```

### 📝 **Example Requests**

#### **Create Company**
```bash
curl -X POST "https://api.serm.com/api/v1/companies/" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tech Innovations Inc",
    "average_check": 15000.0,
    "margin_percent": 25.0,
    "cac": 3000.0,
    "base_ltv": 45000.0
  }'
```

#### **Simulate Review Impact**
```bash
curl -X POST "https://api.serm.com/api/v1/economics/simulate" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_id": "uuid-here",
    "author_name": "John Doe",
    "rating": 2,
    "text": "Poor service quality, very disappointed"
  }'
```

#### **Process Review with AI Response**
```bash
curl -X POST "https://api.serm.com/api/v1/economics/process" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "platform_id": "uuid-here",
    "author_name": "Jane Smith",
    "rating": 1,
    "text": "Terrible experience, money wasted"
  }'
```

---

## 🧪 Testing & Development

### 🏥 **Health Checks**

```bash
curl https://api.serm.com/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "SERM API",
  "version": "1.0.0",
  "checks": {
    "database": true,
    "llm_service": true,
    "jwt_handler": true
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### 🧪 **Error Handler Testing**

```bash
# Test different error types
GET /api/v1/system/test-errors?error_type=404
GET /api/v1/system/test-errors?error_type=timeout
GET /api/v1/system/test-errors?error_type=llm
GET /api/v1/system/test-errors?error_type=validation
```

### 🔍 **RLS Isolation Testing**

```bash
# Run smoke tests to verify tenant isolation
python app/migrations/003_rls_smoke_test.sql
```

### 🐳 **Docker Development**

```bash
# Build and run with Docker
docker-compose up -d

# Run migrations
docker-compose exec api python app/migrations/run_multitenancy_migration.py
```

---

## 📈 Performance & Monitoring

### ⚡ **Performance Features**

- **Async/Await** throughout the application
- **Connection pooling** optimized for Supabase
- **Indexed queries** for multi-tenant performance
- **Cached dependencies** (JWT validation, LLM client)
- **Batch processing** for bulk operations

### 📊 **Monitoring**

- **Structured logging** with tenant context
- **Request tracing** with unique request IDs
- **Health check endpoints** for infrastructure monitoring
- **Error aggregation** with detailed stack traces
- **Performance metrics** for database operations

### 🔧 **Optimization Tips**

1. **Database Indexes** - Automatically created for `company_id` fields
2. **JWT Caching** - Tokens cached until expiration
3. **JWKS Caching** - Public keys cached for 1 hour
4. **Singleton Services** - Stateless services reused across requests

---

## 🚀 Deployment

### 🌩️ **Production Environment**

```bash
# Production environment variables
USE_TENANT_ROLE=true
AUTH_JWT_ALGORITHM=RS256
SQL_ECHO=false
DEBUG=false
LOG_LEVEL=WARNING

# Security settings
OPENAI_API_KEY=<production-key>
JWT_SECRET=<strong-secret>
DATABASE_URL=<production-db-url>
```

### 🔄 **CI/CD Pipeline**

```yaml
# GitHub Actions example
name: Deploy SERM API
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run migrations
        run: python app/migrations/run_multitenancy_migration.py
      - name: Deploy to production
        run: ./deploy.sh
```

### 🏗️ **Infrastructure Requirements**

- **Python 3.11+** runtime
- **PostgreSQL 15+** with RLS support
- **Redis** (optional, for caching)
- **Load balancer** for high availability
- **SSL/TLS** certificate for HTTPS

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### 🛠️ **Development Setup**

1. **Fork the repository**
2. **Create feature branch** (`git checkout -b feature/amazing-feature`)
3. **Install dev dependencies** (`pip install -r requirements-dev.txt`)
4. **Run pre-commit hooks** (`pre-commit install`)
5. **Write tests** for new features
6. **Submit pull request**

### 📏 **Code Standards**

- **Black** for code formatting
- **isort** for import sorting
- **mypy** for type checking
- **pytest** for testing
- **pre-commit** hooks for quality assurance

---

## 📚 Documentation

- **[Architecture Guide](ARCHITECTURE.md)** - Detailed system architecture
- **[Multi-tenancy Setup](MULTITENANCY_GUIDE.md)** - Complete RLS configuration
- **[API Documentation](https://api.serm.com/docs)** - Interactive Swagger UI
- **[Migration Guide](app/migrations/README.md)** - Database setup instructions

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🏆 Acknowledgments

- **FastAPI** - Modern, fast web framework for building APIs
- **SQLAlchemy** - Powerful ORM for database operations
- **Pydantic** - Data validation using Python type annotations
- **OpenAI** - GPT integration for AI-powered responses
- **Supabase** - Backend-as-a-Service with excellent auth support

---

<div align="center">

### 🌟 Star this repository if it helped you! 

**Built with ❤️ for enterprise reputation management**

[⬆ Back to Top](#️-serm-api---service--economy-reputation-management)

</div>