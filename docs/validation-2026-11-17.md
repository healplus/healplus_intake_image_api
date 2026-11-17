# Validação local da API de qualidade de imagem

Em 17 de novembro de 2026, a implementação da API 0.2.0 passou em 87 testes
automatizados e nos sete cenários de integração do roteiro PostgreSQL. A
compilação dos módulos Python e a verificação de espaços do diff também
terminaram sem erros. Este registro descreve a execução local com dados
sintéticos; não constitui validação clínica, certificação FHIR ou homologação
de produção.

## Ambiente executado

| Componente | Versão ou configuração observada |
|---|---|
| Sistema e shell | Windows, PowerShell |
| Interpretador | Python 3.14.3, ambiente virtual `.venv` do projeto |
| FastAPI | 0.141.1 |
| SQLAlchemy | 2.1.1 |
| Pillow | 13.0.0 |
| Alembic | 1.20.0 |
| pytest | 9.1.1 |
| psycopg | 3.3.6 |
| Banco dos testes pytest | SQLite isolado, em memória ou arquivo temporário conforme o teste |
| Docker Engine | 29.8.2, containers Linux via Docker Desktop |
| Banco de integração | Imagem `postgres:16-alpine`, container descartável exclusivo |

O PostgreSQL de integração usou porta dinâmica publicada somente em
`127.0.0.1` e dados em `tmpfs`. A senha foi gerada em memória e incluiu
caracteres reservados, codificados na URL, para exercitar também a leitura da
conexão pelo Alembic. Nenhuma credencial foi incluída neste registro.

## Comandos e resultados

Os comandos abaixo foram executados a partir da raiz do repositório. O valor
de `DATABASE_URL` mostrado refere-se exclusivamente aos testes SQLite; o
roteiro PostgreSQL cria e usa sua própria conexão temporária.

```powershell
$env:DATABASE_URL = 'sqlite://'
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src migrations scripts examples
.\.venv\Scripts\python.exe scripts\verify_postgres.py
git diff --check
```

| Verificação | Resultado observado |
|---|---|
| pytest | `87 passed, 1 warning`; código de saída 0 |
| compileall | Código de saída 0 nos diretórios `src`, `migrations`, `scripts` e `examples` |
| Roteiro PostgreSQL | Sete cenários aprovados; código de saída 0 |
| `git diff --check` | Código de saída 0; nenhuma falha de espaços ou marcadores de conflito |

O aviso de pytest é uma depreciação da integração `httpx` com
`starlette.testclient`, emitida por uma dependência. A suíte concluiu com
sucesso; a atualização desse cliente de testes deve ser acompanhada nas
próximas atualizações de dependências. O Git também informou a conversão
configurada de LF para CRLF em alguns arquivos, sem reprovar o diff.

## Cenários executados no PostgreSQL

O roteiro aplicou a revisão inicial `20261021_01`, inseriu um snapshot legado
sintético e aplicou a revisão `20261116_02`. Depois executou a reversão para a
revisão inicial e uma nova atualização até `head`.

| Cenário | Evidência verificada |
|---|---|
| Migração e armazenamento único | `Attachment.data` removido dos JSONs de Bundle, entrada e imagem; Base64 preservado na coluna única de conteúdo |
| Quarentena dos registros legados | Proprietário reservado `__legacy__:<id>`; cliente comum sem acesso; prefixo reservado recusado na configuração de clientes |
| Restauração no downgrade | Base64 restaurado nos três JSONs utilizados pelo código anterior |
| Novo upgrade após downgrade | Revisões reaplicadas com sucesso ao mesmo snapshot de teste |
| Correspondência entre modelos e esquema | `alembic check` sem operações novas detectadas |
| Concorrência | Dois POSTs idênticos retornaram 202 e 200 com a mesma Task; dois workers sobre a mesma Task resultaram em uma única execução |
| Fluxo HTTP completo | Intake aceito, replay idempotente, execução do worker, Task `completed`, leitura da Observation de saída e bloqueio de leitura do Media legado |

O roteiro não utilizou o Compose nem um banco existente. O container criado
foi removido pelo próprio script após conferir seu ID e nome. A consulta final
ao Docker não mostrou containers de teste em execução.

## Cobertura e limites

A suíte verifica o contrato de entrada, JPEG e ICC reais gerados em memória,
dimensões, integridade, orientação e EXIF sensível, além de idempotência,
identidades atribuídas pelo servidor, isolamento entre clientes, auditoria,
limites de corpo e respostas condicionais. No worker, verifica métricas
técnicas, resultados por fotografia, agregação do pior veredito, proveniência,
tentativas, prazo, recuperação de lease e proteção contra conclusão por um
worker que perdeu a posse da tarefa.

As imagens são sintéticas. Não foram realizados ensaios com pacientes,
avaliação por especialistas, validação de limiares clínicos, validação com o
validador oficial HL7, integração com um servidor FHIR externo ou teste de uma
implantação de produção. Os testes também não comprovam captura em aparelhos
reais, desempenho sob carga, operação de TLS ou integração OAuth 2.0/SMART.

O algoritmo v0 continua sem detectar referência física, calibrar cores,
calcular ITA ou avaliar clinicamente a fotografia. Esses critérios são
declarados como não calculados e impedem aceite irrestrito. Os itens parciais e
pendentes permanecem descritos no
[registro das 42 lacunas](implementation-gaps.md).
