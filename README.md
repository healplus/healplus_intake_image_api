# HealPlus Image Intake API

API responsável pela recepção de imagens clínicas que serão posteriormente analisadas pelo **Core do HealPlus**.

Aplicação Core do HealPlus:

https://github.com/healplus/healplus

---

## 1. Visão geral

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

# 2. Principais endpoints

## 2.1. Intake de imagens para análise

Recebe uma ou várias imagens clínicas para processamento.

### Endpoint

```http
POST /api/v1/analyses
Content-Type: application/fhir+json
```

### Response

A API deve responder imediatamente após aceitar as imagens, sem aguardar a conclusão da análise.

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
```

```json
{
  "analysisId": "a7f31c4e-8e3d-4b6d-9a12-123456789abc",
  "status": "accepted",
  "statusUrl": "/api/v1/analyses/a7f31c4e-8e3d-4b6d-9a12-123456789abc"
}
```

### Payload FHIR

O payload utiliza um `Bundle` contendo um ou vários recursos `Media`.

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Media",
        "id": "media-001",
        "status": "completed",
        "type": {
          "coding": [
            {
              "system": "http://terminology.hl7.org/CodeSystem/media-type",
              "code": "image"
            }
          ]
        },
        "subject": {
          "reference": "Patient/12345"
        },
        "encounter": {
          "reference": "Encounter/67890"
        },
        "createdDateTime": "2026-09-21T10:15:00Z",
        "content": {
          "contentType": "image/jpeg",
          "data": "/9j/4AAQSkZJRgABAQAAAQABAAD/..."
        }
      }
    },
    {
      "resource": {
        "resourceType": "Media",
        "id": "media-002",
        "status": "completed",
        "type": {
          "coding": [
            {
              "system": "http://terminology.hl7.org/CodeSystem/media-type",
              "code": "image"
            }
          ]
        },
        "subject": {
          "reference": "Patient/12345"
        },
        "encounter": {
          "reference": "Encounter/67890"
        },
        "createdDateTime": "2026-09-21T10:16:00Z",
        "content": {
          "contentType": "image/jpeg",
          "data": "/9j/4AAQSkZJRgABAQAAAQABAAD/..."
        }
      }
    }
  ]
}
```

### Estrutura do lote

```text
Bundle
│
├── Media 001
│   └── JPEG Base64
│
└── Media 002
    └── JPEG Base64
```

---

## 2.2. Consulta do status da análise

Permite consultar o estado atual de uma análise.

### Endpoint

```http
GET /api/v1/analyses/{analysisId}
```

### Estados da análise

A análise pode assumir os seguintes estados:

```text
ACCEPTED
QUEUED
PROCESSING
COMPLETED
FAILED
```

### Exemplo de resposta

```json
{
  "analysisId": "a7f31c4e-8e3d-4b6d-9a12-123456789abc",
  "status": "PROCESSING"
}
```

---

## 2.3. Consulta do resultado da análise

Permite consultar o resultado de uma análise concluída.

### Endpoint

```http
GET /api/v1/analyses/{analysisId}/result
```

O resultado deverá estar disponível após o processamento da análise.

---

# 3. Integrações via Webhook

A API possui dois fluxos de notificação por webhook.

## 3.1. Webhook para o HealPlus Core

Sempre que uma nova imagem for recebida e aceita pela API (`ACCEPTED`), o **HealPlus Core** deve ser notificado.

O webhook deverá fornecer os dados necessários para que o Core identifique a análise, a imagem e o contexto clínico associado.

### Fluxo

```text
Sistema cliente
      │
      │ POST /api/v1/analyses
      ▼
Image Intake API
      │
      │ 202 Accepted
      ▼
      │
      └──────────────► Webhook
                         │
                         ▼
                    HealPlus Core
                         │
                         ▼
                  Análise da imagem
```

Os dados enviados ao Core devem permitir identificar, quando aplicável:

- `analysisId`
- Identificador da imagem (`Media.id`)
- Paciente (`Patient`)
- Atendimento (`Encounter`)
- Data/hora da captura
- Demais informações necessárias para processamento

---

## 3.2. Webhook para o sistema cliente

Além do endpoint de consulta:

```http
GET /api/v1/analyses/{analysisId}/result
```

a API deverá permitir a configuração de um **webhook de resultado**.

Quando a análise for concluída, a API deverá notificar o sistema que originalmente enviou as imagens.

### Fluxo

```text
Sistema cliente
      │
      │ Envia imagens
      ▼
Image Intake API
      │
      │ Processamento assíncrono
      ▼
HealPlus Core
      │
      │ Resultado
      ▼
Image Intake API
      │
      │ Webhook
      ▼
Sistema cliente
```

O webhook deve permitir que o sistema cliente receba a notificação de conclusão sem precisar realizar consultas periódicas ao endpoint de resultado.

---

# 4. Configurações da API

## 4.1. Configuração do webhook de resultado

A API deverá disponibilizar uma configuração para que cada sistema cliente possa informar o endpoint que receberá as notificações de resultado.

### Exemplo conceitual

```json
{
  "webhookUrl": "https://cliente.example.com/webhooks/analysis-result"
}
```

---

# 5. Autenticação e credenciais de integração

## 5.1. Geração de Client ID e Secret

A API deverá disponibilizar um endpoint para geração das credenciais utilizadas pelos sistemas clientes na integração.

O endpoint deverá gerar:

- `client_id`
- `client_secret`

Essas credenciais serão utilizadas pelo sistema cliente para autenticar as requisições de envio de imagens.

### Exemplo conceitual de resposta

```json
{
  "client_id": "client-123456",
  "client_secret": "xxxxxxxxxxxxxxxxxxxxxxxx"
}
```

> O mecanismo de autenticação e o formato definitivo dos tokens deverão ser definidos na especificação de segurança da API.

---

# 6. Requisitos obrigatórios da API de Intake

## 6.1. Padrão de dados

Utilizar **HL7 FHIR R4**, utilizando o recurso `Media` para representar as imagens clínicas.

---

## 6.2. Tipo de imagem

Inicialmente, a API deverá aceitar:

```text
JPEG (image/jpeg)
```

As imagens serão fotografias capturadas por câmeras de celulares durante o atendimento ao paciente.

---

## 6.3. Contexto clínico

Cada recurso `Media` deverá permitir associação com o contexto clínico da imagem.

Quando aplicável, deverá ser possível informar:

- `Patient`
- `Encounter`
- Data/hora da captura
- Profissional responsável
- Dispositivo utilizado

---

## 6.4. Upload da imagem

Inicialmente, a imagem deverá ser enviada diretamente no payload FHIR através de `Attachment`.

```json
{
  "content": {
    "contentType": "image/jpeg",
    "data": "<BASE64_DA_IMAGEM>"
  }
}
```

Onde:

- `contentType` identifica o formato da imagem.
- `data` contém a imagem codificada em Base64.

---

## 6.5. Suporte a múltiplas imagens

Uma única requisição deverá permitir o envio de:

- Uma imagem; ou
- Múltiplas imagens.

Para múltiplas imagens, deverá ser utilizado um FHIR `Bundle` contendo múltiplos recursos `Media`.

```text
Bundle
│
├── Media
│   └── JPEG Base64
│
├── Media
│   └── JPEG Base64
│
└── Media
    └── JPEG Base64
```

---

## 6.6. Processamento assíncrono

O processamento das imagens deverá ser assíncrono.

A API **não deve manter a requisição HTTP aberta aguardando a conclusão da análise**.

O fluxo esperado é:

```text
1. Cliente envia imagens
          │
          ▼
2. API valida e aceita
          │
          ▼
3. API retorna HTTP 202
          │
          ▼
4. API gera analysisId
          │
          ▼
5. Processamento assíncrono
          │
          ▼
6. HealPlus Core realiza análise
          │
          ▼
7. Resultado armazenado
          │
          ├──► Webhook para cliente
          │
          └──► GET /api/v1/analyses/{analysisId}/result
```

---

# 7. Resumo dos endpoints

| Método | Endpoint | Finalidade |
|---|---|---|
| `POST` | `/api/v1/analyses` | Receber uma ou várias imagens para análise |
| `GET` | `/api/v1/analyses/{analysisId}` | Consultar o status da análise |
| `GET` | `/api/v1/analyses/{analysisId}/result` | Consultar o resultado da análise |
| `POST` | `Webhook do HealPlus Core` | Notificar o Core sobre novas imagens |
| `POST` | `Webhook do cliente` | Notificar o cliente sobre o resultado |
| `POST` | `Endpoint de credenciais` | Gerar `client_id` e `client_secret` |

---

# 8. Tecnologias e padrões

A API deverá utilizar inicialmente:

- **HL7 FHIR R4**
- **FHIR Media**
- **FHIR Bundle**
- **JPEG**
- **Base64**
- **Fast API**
- **Processamento assíncrono**
- **Webhooks**
- **PostgreSQL**

## 9. Arquitetura

- ** Exemplo: Cadastro e listagem de imagens **

                         HTTP
                          │
                          ▼
                ┌─────────────────┐
                │     Router      │
                │   api/routes    │
                └────────┬────────┘
                         │
                    ImageCreate
                         │
                         ▼
                ┌─────────────────┐
                │     Service     │
                │    use case     │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │   Repository    │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ SQLAlchemy Model│
                │      Image      │
                └────────┬────────┘
                         │
                         ▼
                    PostgreSQL
