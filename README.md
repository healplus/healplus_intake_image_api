# API HealPlus de qualidade de imagem e avaliação de feridas FHIR R4

A API recebe avaliações clínicas com fotografias JPEG, valida a integridade das
imagens e cria uma `Task` para análise técnica assíncrona. Um worker separado
consome a fila persistida no banco e publica resultados `Observation`, com
métricas, limiares, motivos de ressalva ou rejeição e orientações em português.

O algoritmo v0 é experimental. Mede nitidez, exposição e resolução; ainda não
detecta cartão de escala ou cor, não calibra cores, não mede ITA e não valida
condições clínicas de captura. Esses critérios aparecem como não avaliados.
Uma imagem sem falhas nos critérios implementados recebe ressalva por causa
dessas limitações. Os limiares servem à demonstração com dados sintéticos e
precisam de validação com a equipe clínica antes de orientar atendimento.

## Executar localmente

Requer Python 3.12+, [uv](https://docs.astral.sh/uv/) e PostgreSQL. Os testes usam
SQLite em memória. No PowerShell:

```powershell
uv sync --all-groups
Copy-Item .env.example .env
```

Preencha `DATABASE_URL`, `POSTGRES_PASSWORD` e `API_CLIENT_TOKENS` no `.env`.
Gere uma senha e um token próprios; o token deve ter pelo menos 32 caracteres.
`API_CLIENT_TOKENS` é um objeto JSON que associa cada cliente ao seu segredo:

```dotenv
API_CLIENT_TOKENS={"cliente-demonstracao":"SUBSTITUA_POR_UM_SEGREDO_ALEATORIO_COM_32_OU_MAIS_CARACTERES"}
```

Uma forma de gerar cada segredo é `uv run python -c "import secrets;
print(secrets.token_urlsafe(32))"`. A URL do banco deve usar a mesma senha
configurada no Compose; caracteres reservados precisam de codificação na URL.
O PostgreSQL fica publicado apenas em loopback no ambiente de desenvolvimento.

```powershell
docker compose up -d --wait
uv run alembic upgrade head
uv run fastapi dev src/healplus_intake_image_api/main.py
```

Em outro terminal, com o mesmo `.env`, execute o worker:

```powershell
uv run python -m healplus_intake_image_api.worker
# Para consumir no máximo uma tarefa e encerrar:
uv run python -m healplus_intake_image_api.worker --once
```

A API fica em `http://127.0.0.1:8000`; o Swagger fica em `/docs`. A submissão
somente persiste a tarefa: o worker deve estar ativo para a análise terminar.
A migração deve ser aplicada antes de iniciar qualquer processo da versão nova.
Faça backup e revise a migração antes de atualizar um banco existente.
Os pacotes anteriores ficam segregados sob um proprietário reservado
`__legacy__:<id>`; atribuir seus proprietários exige uma revisão explícita.
O prefixo reservado não pode ser usado em `API_CLIENT_TOKENS`.

## Autenticação e limites

Toda operação clínica exige `Authorization: Bearer <token>`. Leituras de
`Patient`, `Practitioner`, `Encounter`, `Condition`, `Media`, `Bundle`,
`Observation`, `Device`, `Provenance` e `Task` são restritas ao cliente que
submeteu a avaliação. Um identificador de outro cliente responde `404`.
Sem credenciais configuradas, a API recusa operações clínicas com `503`.
Os recursos de conformidade são públicos.

Os tokens são credenciais provisionadas para desenvolvimento e homologação.
A API não implementa emissão OAuth 2.0 nem SMART Backend Services. Configure
TLS no proxy/servidor e `REQUIRE_HTTPS=true` na implantação; rotação de tokens,
rate limiting distribuído e integração com um provedor de identidade continuam
necessários para produção. Não publique dados reais antes de concluir a
validação clínica e a avaliação de privacidade do ambiente.

| Variável | Padrão | Uso |
|---|---|---|
| `DATABASE_URL` | obrigatório | Conexão SQLAlchemy; PostgreSQL em implantação. |
| `FHIR_BASE_URL` | `http://127.0.0.1:8000/api/fhir/r4` | URL pública da API usada nos `Bundle.entry.fullUrl`; configure a URL real na implantação. |
| `API_CLIENT_TOKENS` | `{}` | JSON `cliente: segredo`, com segredos únicos de no mínimo 32 caracteres. |
| `REQUIRE_HTTPS` | `false` | Exige HTTPS nas operações clínicas; HTTP local é destinado ao desenvolvimento. |
| `MAX_REQUEST_BYTES` | `33554432` | Limite do corpo completo, incluindo Base64; também aplicado a envio em chunks. |
| `ANALYSIS_TIMEOUT_SECONDS` | `120` | Prazo técnico da Task; não é SLA clínico acordado. |
| `ANALYSIS_MAX_ATTEMPTS` | `3` | Número máximo de tentativas do worker. |
| `ANALYSIS_RETRY_BASE_SECONDS` | `2` | Base do recuo exponencial para falhas transitórias. |
| `ANALYSIS_LEASE_SECONDS` | `60` | Prazo de posse da tarefa antes de recuperação por outro worker. |
| `WORKER_POLL_SECONDS` | `1.0` | Intervalo do worker quando não há tarefa elegível. |

## Contrato de entrada

```http
POST /api/fhir/r4/$avaliar-feridas
Authorization: Bearer <token>
Content-Type: application/fhir+json
Accept: application/fhir+json
Prefer: respond-async
```

Envie `Parameters` com exatamente um parâmetro `bundle`, cujo recurso é um
`Bundle.type=collection`. O Bundle contém um `Patient`, um `Practitioner`, um
`Encounter`, uma `Condition` de ferida, um `Provenance`, pelo menos um `Media`
e as observações clínicas obrigatórias: `dimensoes-ferida`, `tecido-ferida`,
`sinais-infeccao-ferida`, `exsudato-ferida`, `bordas-ferida`, `pele-perilesional`
e `qualidade-captura-imagem`. Cada fotografia exige sua própria observação
humana de qualidade em `derivedFrom`. Dispositivos podem ser incluídos e
referenciados por `Media.device`.

`Bundle.identifier.system` e `.value` são obrigatórios. Reenvie exatamente o
mesmo conteúdo com o mesmo identificador após uma falha de rede:

- Primeira submissão: `202`, nova Task e `Content-Location`.
- Mesmo cliente, identificador e conteúdo: `200`, mesma Task, sem duplicação.
- Mesmo cliente e identificador, conteúdo divergente: `409 OperationOutcome`.

O servidor atribui UUIDs ao Bundle e a cada recurso; IDs locais são opcionais e
não são chaves globais. Use as referências retornadas pelo servidor nas
consultas. As referências internas são reescritas para os IDs persistidos e os
`fullUrl` usam a base REST configurada, permitindo resolução dentro do Bundle.
Essa regra segue a [resolução de referências no FHIR R4](https://hl7.org/fhir/R4/bundle.html#references).

Cada `Media` requer `width`, `height`, `content.size` e `content.hash`. O hash
é SHA-1 dos bytes JPEG, codificado em Base64, conforme `Attachment.hash` do
FHIR R4; não é uma assinatura digital. Dimensões, tamanho e hash são conferidos
contra os bytes recebidos. Os pixels devem estar na orientação final, com
EXIF de orientação ausente ou igual a 1, perfil ICC sRGB RGB válido e sem GPS,
nome do proprietário ou número de série no EXIF. A imagem precisa ser um JPEG
completo e decodificável; a extensão e o `Content-Type` não substituem essa
verificação. Limites por imagem: 10 MiB, 8192 pixels por lado e 24 milhões de
pixels. O limite do corpo inclui todas as fotos e a expansão Base64.

Codificações `https://healplus.com.br/fhir/CodeSystem/*` precisam de
`Coding.version`. Perfis HealPlus declarados em `meta.profile` precisam da
versão canônica, por exemplo `.../HealPlusImagemClinica|1.1.0`.
`Device.version` usa uma lista de objetos `type`/`value` do FHIR R4.
Capture sem recomprimir sucessivamente a fotografia; o servidor não consegue
provar quantas recompressões ocorreram antes do envio.

## Exemplo reproduzível com dados sintéticos

O gerador cria o contexto clínico sintético, marca os recursos com `HTEST` e
produz um JPEG sRGB real com tamanho, hash e dimensões corretos. A imagem é um
padrão geométrico, sem fotografia de paciente; não é material para validação
clínica nem para treino de segmentação.

```powershell
uv run python examples/build_payload.py --output synthetic-payload.json
$env:HEALPLUS_TOKEN = '<token configurado no .env>'
curl.exe -X POST 'http://127.0.0.1:8000/api/fhir/r4/$avaliar-feridas' -H "Authorization: Bearer $env:HEALPLUS_TOKEN" -H 'Content-Type: application/fhir+json' -H 'Accept: application/fhir+json' --data-binary '@synthetic-payload.json'
```

Guarde e reenvie o mesmo arquivo para testar idempotência. Uma nova execução do
gerador cria novos instantes, referências e identificador de negócio.
O exemplo antigo com `data=/9j/4AAQ` foi removido: aqueles bytes não formam
uma fotografia JPEG e agora são rejeitados.

## Consulta da Task e resultados

Consulte a URL de `Content-Location` com o mesmo token. Estados do worker:
`accepted` → `in-progress` → `completed` ou `failed`. A rejeição técnica da
fotografia termina em `completed`; o veredito fica em `Task.businessStatus`.
`failed` significa falha da execução, com `statusReason` codificado.

`Task.input` identifica as fotografias. `Task.output.valueReference` aponta
para cada `Observation` de resultado. O resultado tem `focus=Media`,
`status=preliminary`, métricas e respectivos `component.referenceRange`,
critérios não calculados com `dataAbsentReason`, motivos e orientações de
recaptura. Um `Device` registrado pelo servidor identifica o algoritmo e suas
versões. O `Provenance` vincula resultado, origem e protocolo. Não há pesos de
rede neural neste algoritmo; o hash identifica o artefato efetivamente usado.

As leituras suportam `ETag`, `Last-Modified`, `If-None-Match`,
`If-Modified-Since` e `304`. Respeite `Retry-After` enquanto a análise estiver
pendente. O worker usa tentativas limitadas, recuo exponencial e prazo da Task
em `restriction.period`; tarefas interrompidas podem ser retomadas após a lease.
Submissões e leituras clínicas produzem `AuditEvent` interno, sem cópia da
imagem nem dos tokens no registro de auditoria.

O corpo JPEG é persistido uma única vez no armazenamento de imagens. Os JSONs
persistidos de Bundle e entradas não repetem Base64; as respostas FHIR de
leitura são reconstruídas com os bytes da imagem.

## Conformidade e documentação

- `GET /api/fhir/r4/metadata`: capacidades e versão `0.2.0` do software.
- `GET /api/fhir/r4/OperationDefinition/avaliar-feridas`: contrato da operação.
- `GET /api/fhir/r4/StructureDefinition/{id}`: perfis clínicos e de resultado,
  versão `1.1.0`.
- `GET /api/fhir/r4/CodeSystem/{id}` e `ValueSet/{id}`: terminologia técnica
  experimental, com definições dos códigos e bindings da saída.

O [mapeamento clínico](FHIR_CLINICAL_REQUIREMENTS_MAPPING.md) descreve as
relações FHIR. O [registro das 42 lacunas](docs/implementation-gaps.md) separa
as correções implementadas, parciais e pendentes. Não há exportação para
pesquisa, consentimento secundário, conjunto rotulado, adjudicação ou detecção
de cartão de referência nesta versão. Os perfis publicados são diferenciais;
a suíte não substitui validação com o validador oficial HL7 nem validação
clínica externa.

O [guia da implementação e operação](docs/quality-pipeline.md) detalha a
arquitetura, os cálculos, o ciclo da fila, a auditoria e a atualização do banco.
O [histórico da versão 0.2.0](CHANGELOG.md) reúne as mudanças e os ajustes
exigidos dos clientes. Os comandos e resultados efetivamente executados estão
no [registro de validação](docs/validation-2026-11-17.md).

## Testes

```powershell
uv run pytest -q
```

A suíte cobre o contrato FHIR, imagens reais geradas em memória, falhas de
integridade e privacidade, idempotência, isolamento de clientes, limites,
auditoria, ciclo da Task e falhas do worker. Os testes usam banco SQLite
isolado. Para validar migrações, restauração de dados legados, ausência de
divergência de schema e concorrência no PostgreSQL 16, execute também:

```powershell
uv run python scripts/verify_postgres.py
```

Esse comando exige Docker ativo, cria um banco descartável separado e remove
somente o container criado e verificado pelo próprio script. Ele não usa o
Compose nem o banco configurado no `.env`.
