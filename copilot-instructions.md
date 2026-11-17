# Guia de desenvolvimento da API HealPlus

Este repositório implementa intake clínico de avaliações de feridas e análise
técnica experimental de fotografias em um subconjunto declarado do FHIR R4
4.0.1. A versão da API é `0.2.0`; os perfis publicados usam `1.1.0`. Preserve o
contrato clínico e a distinção entre qualidade da fotografia e avaliação da
ferida ao alterar o código.

O [README](README.md) é a referência operacional. O
[mapeamento clínico](FHIR_CLINICAL_REQUIREMENTS_MAPPING.md) explica as relações
FHIR e separa a implementação do desenho futuro. O
[registro de lacunas](docs/implementation-gaps.md) informa o que está
implementado, parcial ou pendente; uma proposta nesse documento não é uma
funcionalidade disponível.

## Estrutura atual

```text
src/healplus_intake_image_api/
  main.py                         FastAPI, limites de corpo e erros FHIR
  worker.py                       Processo separado que consome a fila no banco
  api/routes/
    avaliacao_ferida.py            Operação de intake e leituras clínicas
    conformance.py                Capacidades, operação, perfis e terminologia
  core/
    config.py                     Settings carregadas do ambiente e de .env
    database.py                   Base SQLAlchemy, engine, sessões e get_db
    fhir.py                       Negociação, respostas e leitura condicional
    image_validation.py           Decodificação JPEG, ICC, EXIF e limites
    security.py                   Bearer, autorização de entrada e auditoria HTTP
    audit.py                      Evento de submissão na transação de criação
  models/avaliacao_ferida.py       Tabelas de intake, imagens, Tasks e auditoria
  repositories/avaliacao_ferida.py Persistência, IDs, referências e reidratação
  schemas/
    fhir.py                       Tipos básicos e serialização FHIR
    avaliacao_ferida.py            Parameters, Bundle e invariantes de entrada
    task.py                       Contrato Task e códigos de estado R4
  services/
    avaliacao_ferida.py            Idempotência, leitura por cliente e erros
    quality.py                    Métricas v0, recursos de saída e fila durável
migrations/                       Revisões Alembic
examples/build_payload.py         Payload e JPEG sintéticos reproduzíveis
scripts/verify_postgres.py         Verificação isolada em PostgreSQL 16 via Docker
tests/                            Contrato, imagem, segurança, conformidade e worker
```

Use Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy, Alembic, psycopg e Pillow.
As dependências e seus limites ficam em `pyproject.toml`; mantenha `uv.lock`
consistente quando houver mudança de dependências.

## Preparar e executar

No PowerShell, a partir da raiz do repositório:

```powershell
uv sync --all-groups
Copy-Item .env.example .env
```

Preencha o `.env` antes de subir o banco. `DATABASE_URL` e
`POSTGRES_PASSWORD` precisam usar a mesma senha, com os caracteres reservados
codificados na URL de conexão. Configure `API_CLIENT_TOKENS` como JSON
`cliente: segredo`; use um segredo aleatório e diferente por cliente, com pelo
menos 32 caracteres. Não salve credenciais em código, exemplos ou logs.
`API_CLIENT_TOKENS={}` mantém as operações clínicas fechadas com `503`.

```powershell
docker compose up -d --wait
uv run alembic upgrade head
uv run fastapi dev src/healplus_intake_image_api/main.py
```

Em outro terminal com a mesma configuração:

```powershell
uv run python -m healplus_intake_image_api.worker
# Executa uma passagem, consumindo no máximo uma tarefa:
uv run python -m healplus_intake_image_api.worker --once
```

A API local fica em `http://127.0.0.1:8000`, com Swagger em `/docs`.
O POST persiste uma Task; iniciar somente a API não executa a análise.
O processamento usa um worker independente e fila persistida, sem
`BackgroundTasks` como mecanismo de entrega.

Configure `FHIR_BASE_URL` com a base REST pública real na implantação. Essa
configuração determina os `Bundle.entry.fullUrl` retornados; não derive a base
de um cabeçalho `Host` fornecido pelo cliente. TLS e confiança no proxy devem
ser configurados no ambiente. `REQUIRE_HTTPS=true` exige HTTPS nas operações
clínicas, mas não instala certificados nem um proxy TLS.

## Arquitetura e transações

As rotas tratam HTTP e chamam serviços. Os schemas validam os recursos e suas
relações; os serviços de intake aplicam idempotência e escopo do cliente; o
repositório persiste e reconstrói as respostas. Use `get_db()` nas rotas para
rollback em falhas e encerramento da sessão. Não compartilhe uma sessão entre
requisições ou threads.

O serviço `quality.py` também controla transações SQLAlchemy diretamente para
reivindicar tarefas e publicar resultados. Essa responsabilidade inclui lease,
contador de tentativas e atualização condicional de estado. Preserve essas
condições ao refatorar: uma execução antiga não pode sobrescrever o resultado
de outro worker, e as saídas devem ser gravadas na mesma transação da conclusão
da Task. Não substitua o controle durável por locks apenas em memória.

O evento de criação de intake é gravado na transação do Bundle e da Task.
`AuditedRoute` mantém uma sessão independente para auditar a resposta HTTP,
inclusive leituras `304`, erros de validação e recusas de autenticação. Esses
eventos representam fatos distintos. Falha da auditoria impede uma resposta
clínica de sucesso; um cliente deve poder repetir um POST cuja resposta não
chegou usando a mesma chave idempotente.

## Invariantes do contrato

- A entrada é `Parameters` com exatamente um parâmetro `bundle`, contendo
  `Bundle.type=collection`. Não é uma transação FHIR REST nem um CRUD genérico
  de imagens. A operação é `POST /api/fhir/r4/$avaliar-feridas`.
- `Condition` representa a ferida; `Encounter` representa o atendimento.
  Observações clínicas de entrada mantêm `focus=Condition`; a observação
  técnica criada pelo servidor usa `focus=Media`.
- Preserve as validações de paciente, atendimento e referências internas.
  Cada fotografia requer uma observação humana de qualidade de captura com
  uma referência individual em `derivedFrom`.
- `Bundle.identifier.system/value` é obrigatório. A chave é escopada ao cliente
  autenticado e usa uma impressão SHA-256 do JSON validado e serializado.
  Primeira submissão retorna `202`; conteúdo idêntico com a mesma chave retorna
  `200` e a mesma Task; conteúdo divergente retorna `409`. A restrição única no
  banco também arbitra submissões concorrentes.
- IDs locais são opcionais. Quando fornecidos, precisam ser válidos e únicos
  por tipo no Bundle, mas nunca se tornam chaves globais. O servidor atribui
  UUIDs a todos os recursos e reescreve referências. Preserve o suporte tanto
  a `urn:uuid` de `fullUrl` quanto a referências relativas com IDs locais.
- `Media.content` contém JPEG Base64 incorporado; `Attachment.url` de entrada
  não é aceito. `width`, `height`, `size` e `hash` são obrigatórios e conferidos
  com os bytes. O hash de Attachment é SHA-1 Base64, conforme R4, e não constitui
  assinatura nem prova de origem em um aparelho específico.
- JPEG precisa ser decodificável, RGB, com ICC sRGB válido, orientação EXIF
  ausente ou 1 e sem os campos EXIF sensíveis rejeitados pelo validador. Os
  limites atuais são 10 MiB, 8192 pixels por lado e 24 milhões de pixels.
  `MAX_REQUEST_BYTES` limita o corpo inteiro antes do parser, inclusive chunks
  e expansão Base64. Não recomprima ou normalize silenciosamente os bytes no
  servidor, pois tamanho e hashes precisam continuar identificando a origem.
- Persistir `Attachment.data` somente em `imagens_clinicas.conteudo`. Os JSONs
  de Bundle, entradas e imagem mantêm metadados; as leituras são reidratadas.
  Não reintroduza cópias Base64 nem exponha o snapshot interno sem reidratar.
- Coding de CodeSystems HealPlus requer `version`. Perfis HealPlus declarados
  usam `canonical|versão`; `StructureDefinition.url` continua sendo apenas a
  URL canônica, com versão no campo próprio. `Device.version` é uma lista de
  objetos R4. Use `resource_json()` para omitir nulos e arrays vazios na saída.

## Segurança e erros

Toda operação clínica usa Bearer provisionado e consultas escopadas ao cliente
autenticado. Um recurso existente de outro cliente recebe `404`, incluindo
resultados gerados pelo worker. Não aceite um proprietário declarado no payload
como autorização. Os recursos de conformidade são públicos.

Use `FHIRRequestError` e as funções de resposta em `core/fhir.py` para preservar
`OperationOutcome`, negociação de mídia e os cabeçalhos de leitura condicional.
Validação usa `422`; autenticação ausente ou inválida usa `401`; identificador
divergente usa `409`; corpo excessivo usa `413`; indisponibilidade usa `503`.
Não devolva exceções, SQL, tokens ou conteúdo clínico em mensagens e logs.

Não registre Base64, cabeçalho Authorization, query string ou identificadores
clínicos livres nos eventos de auditoria. Preserve `Cache-Control: private,
no-store`, `ETag`, `Last-Modified` e as respostas condicionais. Bearer
provisionado não equivale a OAuth 2.0/SMART: emissão e rotação centralizada de
credenciais, identidades profissionais, rate limiting distribuído e políticas
de retenção ainda dependem de evolução e implantação.

## Worker e limites clínicos

O fluxo executado é `accepted → in-progress → completed/failed`. Falhas
transitórias podem voltar a `accepted` com próxima tentativa agendada. Prazo,
tentativas, recuo, lease e intervalo de consulta são configurados pelas
variáveis `ANALYSIS_*` e `WORKER_POLL_SECONDS` descritas no README.

Uma fotografia rejeitada é uma análise `completed`; o veredito pertence a
`Task.businessStatus` e à Observation. `failed` indica falha técnica da execução.
`Task.input` aponta para imagens; `Task.output` aponta para resultados. Preserve
o Device registrado pelo servidor, hashes reais, versões, limiares na saída,
Provenance e vínculo com os bytes efetivamente analisados.

O algoritmo v0 mede nitidez, exposição e dimensão mínima. Os limiares em
`services/quality.py` são demonstrativos, sem validação clínica. Não detecta
cartão, escala física, ferida, ângulo, reflexo ou tom de pele; critérios não
implementados aparecem com `dataAbsentReason=unsupported`. Uma imagem sem
falhas nos critérios medidos recebe `aceita-com-ressalva`, sem aceite irrestrito.
Não invente métricas, pesos de modelo ou limiares clínicos para completar a
saída. O resultado não diagnostica, não infere dor e não define conduta.

Recaptura por `Task/{id}/$reenviar-imagem`, Subscription, metadados completos de
câmera, calibração com cartão e integração de segmentação continuam pendentes.
Também não há pipeline de pesquisa com Consent, máscaras, adjudicação,
separação de datasets por paciente ou exportação anonimizada. Remoção de EXIF
e UUIDs não tornam uma fotografia clínica anônima.

## Migrações e verificação

Use Alembic para evoluir o schema, sem depender de `create_all()` em
implantação. A revisão `20261116_02` adiciona escopo do cliente, idempotência,
estado durável do worker e auditoria, e remove cópias Base64 dos snapshots.
Registros anteriores ficam segregados como `__legacy__:<id>` até atribuição de
proprietário revisada; esse prefixo é proibido em `API_CLIENT_TOKENS`. Não
reatribua registros antigos automaticamente. Revise upgrade e downgrade e
faça backup antes de migrar um banco existente.

```powershell
uv run pytest -q
# Exige Docker; usa somente um PostgreSQL 16 descartável criado pelo script:
uv run python scripts/verify_postgres.py
```

Os testes comuns usam SQLite isolado e imagens sintéticas geradas em memória.
Cubra alterações com testes de comportamento: integridade e privacidade da
imagem, referências, idempotência, isolamento, auditoria e falhas do worker.
Use a verificação PostgreSQL ao alterar schema, concorrência ou transações;
ela também confere migração de snapshot legado, downgrade/upgrade e
`alembic check`. Não use imagens ou dados reais nos fixtures.

Documente invariantes e decisões transacionais em docstrings proporcionais à
complexidade, mantenha anotações de tipos e atualize documentação quando o
contrato mudar. Não afirme que testes locais comprovam validação clínica,
conformidade FHIR integral ou uma implantação em produção.
