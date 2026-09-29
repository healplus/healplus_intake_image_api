# HealPlus Image Intake API

API responsável pela recepção de imagens clínicas que serão posteriormente analisadas pelo **Core do HealPlus**.

**Aplicação Core do HealPlus:** https://github.com/healplus/healplus

---

## 📋 Índice

1. [Visão Geral](#1-visão-geral)
2. [Estado Atual do Projeto](#2-estado-atual-do-projeto)
3. [Arquitetura](#3-arquitetura)
4. [Como Rodar](#4-como-rodar)
5. [Endpoints Atuais](#5-endpoints-atuais)
6. [Requisitos Funcionais (Futuro)](#6-requisitos-funcionais-futuro)
7. [Estrutura de Pastas](#7-estrutura-de-pastas)
8. [Desenvolvimento](#8-desenvolvimento)

---

## 1. Visão Geral

A API recebe imagens clínicas no padrão **HL7 FHIR R4**, utilizando o recurso `Media`.

O processamento das imagens é **assíncrono**:

1. O sistema cliente envia uma ou várias imagens.
2. A API valida e aceita a requisição.
3. A API retorna um `analysisId`.
4. As imagens são processadas de forma assíncrona.
5. O módulo Core do HealPlus é notificado para realizar a análise.
6. O cliente pode consultar o status da análise.
7. Quando disponível, o resultado pode ser consultado ou enviado através de um webhook.

---

## 2. Estado Atual do Projeto

### ✅ Implementado

- [x] **Arquitetura em 3 camadas** (Routes → Services → Repositories)
- [x] **Tratamento robusto de erros** com HTTP status codes apropriados
- [x] **Gerenciamento de sessão de banco de dados** com rollback automático
- [x] **Type hints** em todas as funções
- [x] **Docstrings** completas em services e routes
- [x] **Logging** integrado para debugging
- [x] **Endpoints básicos** para CRUD de imagens (GET, POST)

### 🔄 Em Desenvolvimento

- [ ] **FHIR Bundle Support** (múltiplas imagens por requisição)
- [ ] **Media Resource** (estrutura completa FHIR)
- [ ] **analysisId Generation** e tracking
- [ ] **Analysis Status Tracking** (ACCEPTED, QUEUED, PROCESSING, COMPLETED, FAILED)
- [ ] **Async Processing** com background tasks
- [ ] **Webhook Integration** (HealPlus Core + notificações de cliente)
- [ ] **Authentication** e credenciais de cliente
- [ ] **Test Suite** completo

---

## 3. Arquitetura

### 3.1 Padrão 3-Layer

```
┌─────────────────────────────────────────────────────────┐
│                    HTTP Request                         │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Routes (api/routes/)     - HTTP Layer                  │
│  • Endpoints HTTP                                       │
│  • Validação com Pydantic                               │
│  • Delegação para services                              │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Services (services/)      - Business Logic Layer       │
│  • Orquestração de operações                            │
│  • Try/except + error handling                          │
│  • db.rollback() em exceções                            │
│  • Logging                                              │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│  Repositories (repositories/)  - Data Access Layer      │
│  • db.query(), db.add(), db.commit()                    │
│  • Sem error handling (delegado ao service)             │
│  • Sem dependências HTTP/service                        │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│            PostgreSQL Database                          │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Responsabilidades por Camada

**Routes** (`api/routes/image.py`)
- Definem endpoints HTTP
- Validam entrada com Pydantic
- Delegam ao service
- Retornam respostas HTTP
- Status codes apropriados

**Services** (`services/image.py`)
- Orquestram lógica de negócio
- Chamam repositories
- Try/except com error handling
- Mapeiam exceções para HTTP status codes
- Fazem logging
- db.rollback() em erros

**Repositories** (`repositories/image.py`)
- Acesso puro a dados
- db.query(), db.add(), db.commit()
- Sem tratamento de erro (delegado ao service)
- Sem dependências externas

**Database** (`core/database.py`)
- Gerencia sessão de banco
- Rollback automático em exceções
- Close automático em finally

---

## 4. Como Rodar

### 4.1 Pré-requisitos

- Python ≥ 3.12
- PostgreSQL (local ou via Docker)
- `uv` package manager

### 4.2 Instalação

```bash
# Clonar repositório
git clone <repo>
cd healplus_intake_image_api

# Criar arquivo .env (copiar de .env.example se existir)
cp .env.example .env
# Editar .env com credenciais do banco de dados local

# Sincronizar dependências
uv sync
```

### 4.3 Banco de Dados

#### Opção 1: PostgreSQL Local

```bash
# Criar banco de dados
createdb healplus

# Criar tabelas (após rodar a API uma vez)
# As tabelas são criadas automaticamente pelo SQLAlchemy
```

#### Opção 2: PostgreSQL com Docker

```bash
# Rodar containers (via docker-compose)
docker-compose up -d

# Criar banco (opcional, container cria automaticamente)
```

### 4.4 Rodar a Aplicação

```bash
# Modo desenvolvimento com auto-reload
uv run fastapi dev src/healplus_intake_image_api/main.py

# Modo produção
uv run fastapi run src/healplus_intake_image_api/main.py
```

A API estará disponível em: **http://localhost:8000**

**Documentação interativa:** http://localhost:8000/docs

---

## 5. Endpoints Atuais

### 5.1 Criar Imagem

```http
POST /images/
Content-Type: application/json

{
  "name": "raio-x-torax-01"
}
```

**Respostas:**
- `201 Created` - Imagem criada com sucesso
- `409 Conflict` - Imagem com estes dados já existe
- `503 Service Unavailable` - Banco indisponível
- `500 Internal Server Error` - Erro inesperado

**Exemplo de resposta (201):**
```json
{
  "id": 1,
  "name": "raio-x-torax-01"
}
```

### 5.2 Obter Todas as Imagens

```http
GET /images/
```

**Respostas:**
- `200 OK` - Lista de imagens
- `500 Internal Server Error` - Erro inesperado

**Exemplo de resposta (200):**
```json
[
  {
    "id": 1,
    "name": "raio-x-torax-01"
  },
  {
    "id": 2,
    "name": "raio-x-torax-02"
  }
]
```

### 5.3 Obter Imagem Específica

```http
GET /images/{image_id}
```

**Respostas:**
- `200 OK` - Imagem encontrada
- `404 Not Found` - Imagem não existe
- `500 Internal Server Error` - Erro inesperado

**Exemplo de resposta (200):**
```json
{
  "id": 1,
  "name": "raio-x-torax-01"
}
```

---

## 6. Requisitos Funcionais (Futuro)

### 6.1 Padrão de Dados

Utilizar **HL7 FHIR R4** com o recurso `Media` para representar as imagens clínicas.

### 6.2 Tipos de Imagem

Inicialmente: **JPEG (image/jpeg)**

Fotografias capturadas por câmeras de celulares durante atendimento.

### 6.3 Contexto Clínico

Cada recurso `Media` deve permitir associação com:

- `Patient` - Paciente associado
- `Encounter` - Atendimento
- Data/hora da captura
- Profissional responsável
- Dispositivo utilizado

### 6.4 Upload de Imagem

Imagem enviada no payload FHIR via `Attachment`:

```json
{
  "content": {
    "contentType": "image/jpeg",
    "data": "<BASE64_DA_IMAGEM>"
  }
}
```

### 6.5 Múltiplas Imagens

Uma requisição aceita:
- Uma imagem; ou
- Múltiplas imagens em um FHIR `Bundle`

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Media",
        "id": "media-001",
        "content": { ... }
      }
    },
    {
      "resource": {
        "resourceType": "Media",
        "id": "media-002",
        "content": { ... }
      }
    }
  ]
}
```

### 6.6 Processamento Assíncrono

- API **não aguarda** conclusão da análise
- Retorna **HTTP 202 Accepted** com `analysisId`
- Processamento ocorre em background
- Core HealPlus notificado via webhook
- Cliente consulta status via endpoint

### 6.7 Status da Análise

Possíveis estados:
- `ACCEPTED` - Recebida e validada
- `QUEUED` - Aguardando processamento
- `PROCESSING` - Sendo processada
- `COMPLETED` - Análise concluída
- `FAILED` - Falha no processamento

---

## 7. Estrutura de Pastas

```
healplus_intake_image_api/
├── README.md                          # Este arquivo
├── copilot-instructions.md           # Instruções para Copilot
├── pyproject.toml                    # Dependências e configuração
├── uv.lock                           # Lock file de dependências
├── .env                              # Variáveis de ambiente (não commitar!)
├── .env.example                      # Template do .env
├── .gitignore                        # Arquivos ignorados pelo Git
├── docker/                           # Configuração Docker
│   └── Dockerfile                    # Build da aplicação
├── compose.yaml                      # Docker Compose (dev environment)
└── src/healplus_intake_image_api/
    ├── __init__.py
    ├── main.py                       # Aplicação FastAPI (entry point)
    ├── core/
    │   ├── __init__.py
    │   ├── config.py                 # Settings (environment variables)
    │   └── database.py               # SQLAlchemy + session management
    ├── api/
    │   ├── __init__.py
    │   └── routes/
    │       ├── __init__.py
    │       └── image.py              # Endpoints de imagem
    ├── models/
    │   ├── __init__.py
    │   └── image.py                  # SQLAlchemy ORM models
    ├── schemas/
    │   ├── __init__.py
    │   └── image.py                  # Pydantic schemas (request/response)
    ├── services/
    │   ├── __init__.py
    │   └── image.py                  # Business logic + error handling
    └── repositories/
        ├── __init__.py
        └── image.py                  # Data access layer
```

---

## 8. Desenvolvimento

### 8.1 Padrão de Erro Handling

Todos os serviços devem seguir este padrão:

```python
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

def create_image(db: Session, image: ImageCreate) -> Image:
    """Criar imagem com tratamento de erros."""
    try:
        return repo_create_image(db, image)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Erro de integridade: {e}")
        raise HTTPException(status_code=409, detail="Resource conflict")
    except OperationalError as e:
        db.rollback()
        logger.error(f"Erro operacional: {e}")
        raise HTTPException(status_code=503, detail="Database unavailable")
    except Exception as e:
        db.rollback()
        logger.error(f"Erro inesperado: {e}")
        raise HTTPException(status_code=500, detail="Internal error")
```

### 8.2 HTTP Status Codes

| Code | Significado | Quando Usar |
|------|-------------|------------|
| `201` | Created | Recurso criado com sucesso |
| `200` | OK | Operação bem-sucedida (GET) |
| `202` | Accepted | Requisição aceita para processamento assíncrono |
| `400` | Bad Request | Validação Pydantic falhou |
| `404` | Not Found | Recurso não existe |
| `409` | Conflict | IntegrityError (constraint violation) |
| `503` | Unavailable | OperationalError (DB down) |
| `500` | Server Error | Exceção inesperada |

### 8.3 Type Hints

Sempre usar type hints:

```python
def get_image(db: Session, image_id: int) -> Image | None:
    """Buscar imagem por ID."""
    ...
```

### 8.4 Logging

Sempre logar erros no service:

```python
import logging
logger = logging.getLogger(__name__)

logger.error(f"Database error: {e}")
logger.info(f"Image created: {image.id}")
```

### 8.5 Docstrings

Todo service e route deve ter docstring:

```python
def create_image(db: Session, image: ImageCreate) -> Image:
    """Create a new image.
    
    Args:
        db: Database session
        image: Image data
        
    Returns:
        Created image
        
    Raises:
        HTTPException: On database errors
    """
```

### 8.6 Rodando Testes

```bash
# Instalar pytest
uv pip install pytest pytest-asyncio

# Rodar testes
pytest tests/

# Com cobertura
pytest --cov=src tests/
```

### 8.7 Linting e Formatting

```bash
# Ruff (linter)
uv run ruff check src/

# Black (formatter)
uv run black src/
```

---

## 📞 Contato

**Autor:** wolley silva  
**Email:** wolleyws@gmail.com  
**GitHub:** https://github.com/healplus

---

## 📜 Licença

[Adicionar informação de licença aqui]

---

**Última atualização:** Setembro 2026  
**Versão:** 0.1.0
