# Pipeline de qualidade de imagem HealPlus

Este documento descreve o contrato e a operação da API 0.2.0, com perfis FHIR R4
1.1.0 e algoritmo técnico demonstrativo 0.1.0. Ele acompanha a implementação
das lacunas prioritárias identificadas no relatório técnico. A situação dos 42
itens está em [implementation-gaps.md](implementation-gaps.md); o guia inicial
está no [README](../README.md).

A API valida a submissão, preserva as fotografias recebidas e cria uma tarefa
persistente. Um processo separado calcula métricas técnicas e publica um
resultado por fotografia. Os limiares são de engenharia e ainda não foram
validados para decisão clínica. O resultado não avalia a ferida, não diagnostica,
não infere dor e não define conduta. A versão atual não pode emitir aceite sem
ressalva: critérios essenciais de escala, cor e captura continuam não avaliados.

## Organização do código e fluxo de execução

| Módulo | Responsabilidade |
|---|---|
| [main.py](../src/healplus_intake_image_api/main.py) | Aplicação FastAPI, limite do corpo antes do parser JSON e respostas de erro OperationOutcome. |
| [routes/avaliacao_ferida.py](../src/healplus_intake_image_api/api/routes/avaliacao_ferida.py) | Submissão, negociação HTTP, status 202/200 e leituras condicionais autenticadas. |
| [schemas/avaliacao_ferida.py](../src/healplus_intake_image_api/schemas/avaliacao_ferida.py) | Envelope Parameters, recursos clínicos, cardinalidades e regras de referência entre recursos. |
| [schemas/fhir.py](../src/healplus_intake_image_api/schemas/fhir.py) | Primitivas FHIR, versões de Coding/Meta e conferência de Attachment. |
| [core/image_validation.py](../src/healplus_intake_image_api/core/image_validation.py) | JPEG, limites, orientação, EXIF sensível e ICC sRGB. |
| [services/avaliacao_ferida.py](../src/healplus_intake_image_api/services/avaliacao_ferida.py) | Hash da requisição, idempotência, tradução de falhas e leituras por cliente. |
| [repositories/avaliacao_ferida.py](../src/healplus_intake_image_api/repositories/avaliacao_ferida.py) | UUIDs, reescrita de referências, persistência transacional e reconstrução dos JSONs de leitura. |
| [core/security.py](../src/healplus_intake_image_api/core/security.py) e [core/audit.py](../src/healplus_intake_image_api/core/audit.py) | Autenticação por cliente, auditoria de acesso e evento de criação atômico com o intake. |
| [services/quality.py](../src/healplus_intake_image_api/services/quality.py) | Seleção e reivindicação da fila, métricas, resultados, tentativas e recuperação. |
| [worker.py](../src/healplus_intake_image_api/worker.py) | Processo de consumo contínuo ou de uma passagem da fila. |
| [routes/conformance.py](../src/healplus_intake_image_api/api/routes/conformance.py) | CapabilityStatement, OperationDefinition, perfis e terminologia técnica publicados. |

O percurso de uma avaliação é o seguinte:

1. O middleware recebe o corpo com limite de bytes, inclusive quando não há
   `Content-Length`. A rota autentica o cliente antes da validação do payload.
2. Pydantic valida o envelope e o Bundle, decodifica cada JPEG e confere seus
   metadados declarados. A aplicação verifica o contexto clínico e as referências.
3. O serviço calcula um fingerprint da representação validada e consulta a
   chave de idempotência do cliente.
4. Em uma submissão nova, o repositório atribui UUIDs, reescreve as referências
   e grava Bundle, entradas, fotografias, Task e um AuditEvent de criação na
   mesma transação. A resposta é `202` com `Task.status=accepted`.
5. O worker consulta o banco e reivindica uma tarefa elegível com atualização
   condicional. A análise ocorre fora da transação de reivindicação.
6. O worker grava as Observations, o Device e os Provenances junto da mudança
   para `completed`, em uma transação única. O cliente encontra os resultados
   em `Task.output` e os consulta com o mesmo token da submissão.

Não há fila externa ou BackgroundTasks como mecanismo de durabilidade. A fila
é a tabela `tarefas_analise`; sem um worker em execução, a API continua aceitando
avaliações, mas o processamento não avança.

## Contrato de entrada e mudanças de compatibilidade

```http
POST /api/fhir/r4/$avaliar-feridas
Authorization: Bearer <token-do-cliente>
Content-Type: application/fhir+json
Accept: application/fhir+json
Prefer: respond-async
```

`Prefer` é opcional; quando informado, precisa incluir `respond-async`. O corpo
é `Parameters` com exatamente um parâmetro `bundle`, contendo um
`Bundle.type=collection`. Entradas usam `fullUrl=urn:uuid:<UUID>` único e não
podem conter `request` ou `response`, que pertenceriam a outros tipos de Bundle.

O Bundle contém exatamente um Patient, Practitioner, Encounter e Provenance;
pelo menos um Media; e exatamente uma Condition de categoria local `ferida`.
Condições adicionais de comorbidade são permitidas. O conjunto mínimo de códigos
de Observation é `dimensoes-ferida`, `tecido-ferida`, `sinais-infeccao-ferida`,
`exsudato-ferida`, `bordas-ferida`, `pele-perilesional` e
`qualidade-captura-imagem`, no CodeSystem HealPlus de avaliação de ferida.
Ausência de dor é permitida. Cada fotografia precisa de sua própria observação
humana de qualidade, com referência individual em `derivedFrom`.

O contrato clínico pretende manter paciente, atendimento e ferida consistentes.
A implementação confere subject/encounter de Media e Observation, referências
da Condition de ferida, participantes do Encounter, alvos de Provenance e
referências derivedFrom previstas. Para Observation, a verificação de ferida
compara somente o primeiro focus. Operador da foto, recorder da Condition e todos
os performers não são integralmente resolvidos por essa checagem. As observações
clínicas de entrada usam primeiro `focus=Condition`; a qualidade automática
criada pelo servidor usa `focus=Media`.
`Media.device` é opcional, mas, se informado, deve resolver para um Device
incluído. A observação técnica completa de metadados de câmera ainda não é
obrigatória, e a API não garante coleta de ISO, flash, distância ou ângulo.

As seguintes mudanças exigem adaptação dos clientes antigos:

| Alteração | Como adaptar |
|---|---|
| Rotas clínicas exigem Bearer | Configurar um cliente e enviar seu token na submissão e em todas as leituras. |
| `Bundle.identifier.system/value` obrigatórios | Gerar uma chave de negócio antes do primeiro POST e preservá-la nos reenvios. |
| UUIDs atribuídos pelo servidor | Usar os IDs e referências retornados; `media-001` e outros IDs locais não são mais URLs persistidas. IDs locais podem ser omitidos quando todas as referências usam fullUrl. |
| JPEG real com ICC e dados de integridade | Enviar bytes completos com dimensões, tamanho e SHA-1 corretos; o placeholder `/9j/4AAQ` é rejeitado. |
| Versão de terminologia e perfis | Informar `Coding.version` para sistemas locais e `canonical|versão` em todo perfil HealPlus declarado. |
| `Device.version` nativo de R4 | Enviar lista de objetos com `value` e tipo opcional, em vez de uma string única. |
| Uma qualidade humana por fotografia | Criar observação separada para cada Media, em vez de uma avaliação global para várias fotos. |

O schema tipa componentes clínicos sem exigir todos os componentes do protocolo,
somar percentuais de tecido até 100 ou conferir compatibilidade de bodySite entre
todos os recursos. Também não obriga Bundle.timestamp. Regras clínicas mais
estritas precisam de outro incremento; presença de um código obrigatório não
prova completude ou validade clínica das medidas e classificações.

O servidor preserva elementos FHIR adicionais aceitos pelos schemas, mas isso
não equivale à validação integral de todos os perfis possíveis do FHIR R4. A
checagem de versões locais também percorre codificações e Meta preservados em
campos adicionais. Declarar um perfil versionado identifica o contrato alegado
pelo emissor; não substitui um validador oficial HL7 ou validação clínica externa.

### Idempotência e identidade

A chave é a combinação `(cliente_id, Bundle.identifier.system,
Bundle.identifier.value)`, protegida por restrição única no banco. O fingerprint
é SHA-256 do JSON obtido por `resource_json(bundle)`, com chaves ordenadas,
separadores compactos e UTF-8. Nulos e arrays vazios omitidos pela serialização
FHIR não entram nessa representação. Não se trata de canonicalização de
assinatura FHIR nem de comparação semântica entre avaliações clínicas.

| Situação | Resposta |
|---|---|
| Chave inédita no cliente | `202`, nova Task e `Content-Location`. |
| Mesma chave e mesmo fingerprint | `200`, Task existente no estado em que estiver, sem nova avaliação. |
| Mesma chave e conteúdo diferente | `409 OperationOutcome`, expressão `Bundle.identifier`. |
| Mesma chave usada por outro cliente | Avaliação independente, com outros UUIDs e propriedade. |

Mudar instantes, IDs locais, ordem de arrays, referências ou bytes da imagem
pode mudar o fingerprint. Após falha de rede, reenvie o mesmo arquivo gerado.
A restrição única arbitra também POSTs idênticos concorrentes; o serviço recupera
a Task vencedora após rollback da tentativa concorrente.

Na persistência, cada recurso recebe UUID e referências internas são reescritas
para `Tipo/UUID`. Os `Bundle.entry.fullUrl` retornados são URLs REST absolutas
construídas com `FHIR_BASE_URL`. Configure essa base para o endereço externo
correto; ela não é inferida do header Host da requisição. O snapshot do Bundle
submetido não recebe as entradas de resultado adicionadas depois pelo worker.

## Validação do JPEG

As regras estão em [image_validation.py](../src/healplus_intake_image_api/core/image_validation.py)
e [Attachment](../src/healplus_intake_image_api/schemas/fhir.py). A aplicação
rejeita o arquivo; ela não remove EXIF, gira pixels ou recompõe a fotografia.
Assim, os hashes continuam identificando exatamente os bytes enviados.

| Regra | Valor ou comportamento |
|---|---|
| Corpo completo da requisição | `MAX_REQUEST_BYTES`, padrão 33.554.432 bytes, equivalente a 32 MiB; inclui JSON, todas as imagens e expansão Base64. |
| Arquivo por Media | Até 10.485.760 bytes, equivalente a 10 MiB. |
| Dimensões | Até 8192 por lado e produto de até 24.000.000 pixels. |
| `width` e `height` | Inteiros estritos positivos, iguais às dimensões lidas do JPEG. |
| `content.size` | Inteiro estrito positivo, igual ao número de bytes decodificados. |
| `content.hash` | SHA-1 de 20 bytes, codificado em Base64 e comparado com os bytes recebidos. |
| Tipo e estrutura | `contentType=image/jpeg`, marcadores de início/fim completos e decodificação Pillow restrita a JPEG. PNG renomeado não é aceito. |
| Pixels | Modo RGB; imagens cinza ou CMYK não atendem a este contrato. |
| Orientação | Tag EXIF 274 ausente ou igual a 1; o cliente normaliza os pixels antes do envio. |
| ICC | Perfil embutido de até 1 MiB, parseável, RGB e correspondente a sRGB. |
| Fontes externas | `Attachment.url` não é permitido na entrada; os dados devem estar incorporados. |

A conferência de ICC não confia apenas no nome do perfil: além de exigir
descrição que contenha sRGB, transforma uma grade de 125 cores, usando valores
0, 64, 128, 192 e 255 por canal, para sRGB. Diferença superior a 3 em qualquer
canal de qualquer amostra rejeita o perfil. Essa verificação limita os espaços
aceitos; não mede a calibração da câmera nem o desvio de cor da cena.

As tags EXIF sensíveis 34853 (GPS), 315 (Artist), 37500 (MakerNote),
42032 (CameraOwnerName), 42033 (BodySerialNumber) e 42037 (LensSerialNumber)
são rejeitadas tanto no diretório principal quanto no Exif IFD consultado.
Pillow precisa conseguir carregar todos os pixels; erros de truncamento e
avisos de decompression bomb tornam a imagem inválida.

Falhas de imagem ou de perfil retornam `422 OperationOutcome` com expressão
do elemento validado. Excesso do corpo é `413` antes do parser. Remover EXIF
sensível não anonimiza o conteúdo visual: rosto, tatuagem, pulseira e textos
na fotografia ainda exigem revisão de privacidade. SHA-1 e o SHA-256 registrado
na proveniência são conferências de integridade; não são assinatura JWS nem
prova de origem em um aparelho específico.

## Algoritmo técnico demonstrativo

O algoritmo está em [quality.py](../src/healplus_intake_image_api/services/quality.py),
com `ALGORITHM_VERSION=0.1.0` e pré-processamento
`grayscale-thumbnail-512-v1`. Ele mede a fotografia inteira, sem segmentar
ferida, pele perilesional ou cartão. O JPEG original permanece intacto.

Primeiro os pixels são convertidos com Pillow para escala de cinza (`L`). Uma
miniatura preserva proporção, cabe em 512×512, usa LANCZOS e nunca amplia a
imagem. As métricas de foco e exposição usam essa miniatura; a resolução usa
as dimensões originais. Imagem cuja miniatura tenha dimensão inferior a 3
pixels não permite calcular nitidez e gera falha técnica de imagem inválida.

Para cada pixel interior da miniatura, o Laplaciano usa quatro vizinhos:

```text
L(x,y) = I(x-1,y) + I(x+1,y) + I(x,y-1) + I(x,y+1) - 4 × I(x,y)
nitidez = max(0, média(L²) - média(L)²)
exposição média = soma(I) / (N × 255)
fração escura = quantidade(I ≤ 10) / N
fração saturada = quantidade(I ≥ 245) / N
menor dimensão = min(largura original, altura original)
```

O escore global é uma combinação fixa:

```text
S_foco = min(1, nitidez / 100)
S_resolução = min(1, menor dimensão / 512)
S_exposição = max(0, 1 - max(fração escura, fração saturada))
escore = 0,55 × S_foco + 0,25 × S_exposição + 0,20 × S_resolução
```

| Critério | Limiar v0 | Efeito |
|---|---|---|
| Nitidez | `< 100` | Motivo `desfocada`; rejeição. |
| Menor dimensão original | `< 512` pixels | Motivo `baixa-resolucao`; rejeição. |
| Fração de pixels com cinza ≤ 10 | `> 0,40` | Motivo `subexposta`; rejeição. |
| Fração de pixels com cinza ≥ 245 | `> 0,40` | Motivo `superexposta`; rejeição. |
| Escore global | `< 0,55` | Rejeição; é o limiar de ressalva publicado. |
| Escore global | `0,75` | Referência de aceite publicada; não permite aceite irrestrito enquanto houver critérios não calculados. |
| Exposição média | Faixa matemática 0 a 1 | Métrica informativa, sem limiar clínico próprio de rejeição. |

Qualquer falha eliminatória ou escore abaixo de 0,55 produz `rejeitada`.
Nos demais casos o resultado é `aceita-com-ressalva`. O código `aceita` existe
no vocabulário e na ordenação dos vereditos, mas não é emitido pelo algoritmo
atual. Escore não é probabilidade de adequação clínica ou de acerto de modelo.

Os oito critérios não implementados são `referencia-escala-detectada`,
`referencia-cor-detectada`, `desvio-cor-delta-e`, `resolucao-espacial`,
`angulo-captura`, `reflexo`, `enquadramento` e `ita-pele-perilesional`. Seus
componentes usam `dataAbsentReason=unsupported`, sem valor inventado. Todo
resultado inclui o motivo `criterios-nao-avaliados` e uma orientação de revisão
humana. Não se mede concordância entre avaliadores nem disparidade por tom
de pele, e limiares demonstrativos não devem ser interpretados como validados
entre dispositivos, ambientes, tipos de ferida ou tons de pele.

## Ciclo da Task e recuperação da fila

Os campos do modelo estão em [models/avaliacao_ferida.py](../src/healplus_intake_image_api/models/avaliacao_ferida.py).
Cada Bundle novo inicia exatamente uma Task com `attempts=0` e prazo em
`deadline_at`, refletido em `Task.restriction.period.end`. O prazo é contado
da submissão, incluindo espera na fila; o padrão é 120 segundos e não é um
SLA clínico acordado.

| Estado | Significado e transição |
|---|---|
| `accepted` | Persistida e aguardando tentativa; pode ter `next_attempt_at` após falha transitória. |
| `in-progress` | Uma geração do worker reivindicou a Task, incrementou `attempts` e definiu `lease_expires_at`. |
| `completed` | Todos os resultados foram persistidos; `businessStatus` contém o pior veredito entre as fotos. |
| `failed` | Imagem inválida, prazo esgotado, limite de tentativas ou falha técnica sem oportunidade de repetição. |

O worker seleciona a Task elegível mais antiga por `criado_em`. São elegíveis
Tasks `accepted` sem agendamento futuro e Tasks `in-progress` sem lease válida.
A seleção não é um bloqueio exclusivo: uma atualização SQL condicional,
comparando estado, elegibilidade e contador de tentativas, decide quem obteve
a posse. Isso evita depender de uma fila em memória ou de um lock Python.

A tentativa incrementa `attempts` e a lease termina no menor instante entre
`agora + ANALYSIS_LEASE_SECONDS` e o prazo da Task. Não há renovação periódica
de lease durante a análise. Uma tentativa que dure além da lease pode ter seu
resultado descartado e a tarefa recuperada por outro worker; dimensione lease
e prazo para a carga e a quantidade de fotografias esperadas.

O contador de tentativas funciona também como geração de posse, ou fencing.
Para concluir, o worker precisa encontrar a mesma geração ainda em
`in-progress` e lease posterior ao término do cálculo. Se outro worker recuperou
a Task, a tentativa antiga não pode gravar seus resultados sobre a nova.
Os resultados e a transição para `completed` são atômicos: uma tentativa que
perdeu a posse não deixa saídas parciais publicadas.

Falhas transitórias agendam a próxima tentativa com:

```text
atraso = ANALYSIS_RETRY_BASE_SECONDS × 2^(attempts - 1)
```

Com os padrões, os atrasos após a primeira e a segunda falha são 2 e 4 segundos;
o total máximo é de três tentativas. A repetição só é agendada se houver tentativa
disponível e o próximo instante for anterior ao prazo. O estado retorna a
`accepted`, com `statusReason=falha-tecnica`. Exceções arbitrárias não são
copiadas para o recurso FHIR.

`imagem-invalida` é falha terminal, sem repetição. `tempo-esgotado` identifica
prazo ultrapassado e `limite-tentativas` identifica esgotamento do contador.
Uma falha transitória sem janela suficiente para novo retry pode terminar em
`failed/falha-tecnica` antes do prazo. O timeout é verificado pelo worker,
antes e depois do cálculo; não interrompe à força uma chamada de biblioteca
travada. Um worker precisa estar ativo para persistir a expiração ou recuperar
a lease. Reiniciar o processo não apaga a fila.

`executionPeriod.start` marca a primeira análise e é preservado nos retries;
`executionPeriod.end` aparece no estado terminal. Cada transição atualiza
`meta.versionId`, `meta.lastUpdated` e `lastModified`. Não há rota de cancelamento,
mutação livre da Task, Subscription ou operação `$reenviar-imagem` nesta versão.
Uma nova avaliação pode ser submetida com outro identificador, sem substituir
os registros anteriores ou criar automaticamente `partOf` de recaptura.

## Recursos produzidos e consulta pelo cliente

Uma Task concluída contém uma entrada `input` por Media e uma entrada `output`
por Observation. `businessStatus` resume o pior veredito usando a ordem
`aceita < aceita-com-ressalva < rejeitada`. Rejeitar uma fotografia é uma
execução concluída; não muda a Task para `failed`.

```json
{
  "resourceType": "Task",
  "status": "completed",
  "businessStatus": {"coding": [{
    "system": "https://healplus.com.br/fhir/CodeSystem/veredito-qualidade-imagem",
    "version": "1.1.0", "code": "aceita-com-ressalva"
  }]},
  "output": [{
    "type": {"text": "Resultado técnico da fotografia"},
    "valueReference": {"reference": "Observation/<uuid-do-resultado>"}
  }]
}
```

O fragmento ilustra a navegação; a resposta completa inclui os demais campos e
tipos codificados de `Task.input/output`. Consulte as referências com GET no
mesmo prefixo `/api/fhir/r4` e com o token original.

Cada `Observation` de resultado usa o perfil
`HealPlusResultadoQualidadeImagem|1.1.0`, `status=preliminary`, categoria
`imaging`, `focus` e `derivedFrom` para a fotografia, `device` para o algoritmo e
`valueCodeableConcept` para o veredito. O instante caracterizado é o de captura
em `effectiveDateTime`; `issued` marca a emissão da análise. `subject` e
`encounter` vêm da Media. Se houver uma observação de metadados de captura
reconhecida pelo worker, ela também é referenciada em `derivedFrom`.

Os valores quantitativos são arredondados a seis casas na serialização e
incluem `referenceRange` e interpretação `L`, `N` ou `H`; o escore publica as
referências 0,75 e 0,55. Há componente de integridade de arquivo, critérios
não calculados, motivos e orientações em português. As notas mantêm o caráter
assistivo e experimental. O resultado herda `meta.security` da Media quando
o rótulo estava presente. Motivos e orientações técnicas são códigos fechados
publicados nos [recursos de conformidade](../src/healplus_intake_image_api/api/routes/conformance.py).

Um `Device` de algoritmo é criado por análise da Task, compartilhado entre os
resultados daquela Task. Ele contém `DeviceDefinition` e versões tipadas de
algoritmo, SHA-256 do arquivo de código executado, pré-processamento, SHA-256
do JSON de limiares, Pillow e API. Não existem pesos de rede neural nesse
algoritmo. Manter apenas o número 0.1.0 não basta para reproduzir o resultado:
preserve também código, dependências, configuração e bytes originais.

Um `Provenance` por resultado vincula a Observation ao Device e à Media de
origem. `entity.what.identifier` registra SHA-256 dos bytes em formato
`ni:///sha-256;<base64url>`. A política é
`https://healplus.com.br/fhir/protocolo/qualidade-tecnica-demonstrativa|0.1.0`.
Não há assinatura criptográfica desses recursos ou autenticação da câmera.
O Device é identidade produzida pelo servidor; o cliente não escolhe qual
versão é declarada como executora da análise.

As leituras suportam ETag fraco, Last-Modified e `304`. Prefira `If-None-Match`
para polling de Task: a data HTTP tem precisão de segundos e uma Task pode
mudar mais de uma vez nesse intervalo. `If-None-Match` tem precedência sobre
`If-Modified-Since`; o tratamento de Task preserva a precisão do instante real
para não esconder conclusão ocorrida no mesmo segundo. Enquanto estiver em
`accepted` ou `in-progress`, a resposta inclui `Retry-After: 2`.

## Autenticação, propriedade e auditoria

`API_CLIENT_TOKENS` é um objeto JSON `cliente → segredo`, validado na
inicialização. Cada segredo precisa ter no mínimo 32 caracteres e ser único.
O identificador de cliente tem até 128 caracteres; nomes iniciados por
`__legacy__` são reservados. A autenticação compara hashes SHA-256 dos tokens
com `secrets.compare_digest`. As credenciais de configuração usam `SecretStr`;
não são persistidas na trilha de auditoria.

Todas as leituras clínicas e o POST usam `Authorization: Bearer`. Ausência ou
token desconhecido produz `401`, com `WWW-Authenticate: Bearer`. Nenhum cliente
configurado produz `503`; `REQUIRE_HTTPS=true` rejeita acesso HTTP com `403`.
Em implantação com proxy, configure transporte e encaminhamento de esquema
confiáveis; a opção não instala TLS nem autoriza confiar em proxies arbitrários.

A propriedade pertence ao cliente que submeteu o pacote. As consultas unem
o recurso ao pacote e filtram `cliente_id`, inclusive Device e Provenance
gerados. Recurso inexistente ou de outro cliente responde `404`. Esta é uma
fronteira entre clientes, não uma política clínica por profissional, organização
ou finalidade. OAuth 2.0, SMART Backend Services, emissão de tokens, RBAC e
gestão centralizada de sessões não estão implementados.

Conformidade é pública: `metadata`, `OperationDefinition`, `StructureDefinition`,
`CodeSystem` e `ValueSet` não expõem fotografias ou contexto clínico. Não há
rota pública para AuditEvent. Respostas sob `/api/fhir/r4/` recebem
`Cache-Control: private, no-store` e `X-Content-Type-Options: nosniff`.

O evento `Intake persistido` é gravado na mesma transação da nova Task; se essa
gravação falhar, o intake não é confirmado. A rota também grava um evento HTTP
de acesso em sessão própria, cobrindo submissões, leituras, `304`, erros de
contrato e recusas de autenticação. É esperado haver evento de criação e evento
HTTP separados para uma submissão nova bem-sucedida.

A trilha contém cliente ou `anonymous`, ação `C/R`, instante, resultado, status
HTTP, rota parametrizada e UUIDs válidos de destino. Não contém token, query
string, imagem nem payload clínico. Se não conseguir registrar o acesso de uma
resposta bem-sucedida, a rota retorna `503` e não entrega a leitura clínica.
Uma criação já confirmada pode permanecer gravada quando falha apenas a trilha
HTTP posterior; o retry idempotente recupera sua Task.

O middleware de tamanho responde `413` antes de entrar na rota auditada;
essas rejeições não geram o AuditEvent da rota. Logs e limites do gateway
precisam cobrir essa camada. Os AuditEvents locais não têm mecanismo de
retenção, exportação ou proteção contra alteração por administradores do banco;
essas políticas pertencem à implantação.

## Armazenamento, migração e dados legados

O modelo continua preservando recursos clínicos em JSON estruturado, sem
materializar todas as tabelas clínicas propostas no mapeamento original.

| Tabela | Conteúdo relevante |
|---|---|
| `pacotes_fhir` | Snapshot do Bundle sem Base64 duplicado, proprietário, chave de negócio e fingerprint SHA-256. |
| `entradas_pacote` | Recursos de entrada e recursos de saída com tipo/ID/ordem; Media sem `content.data`. |
| `imagens_clinicas` | Metadados de Media e uma única cópia Base64 em `conteudo`. |
| `codificacoes_tipo_imagem` | Índice estruturado de Media.type.coding. |
| `tarefas_analise` | Recurso Task e estado, tentativa, agendamento, lease, prazo e código da última falha. |
| `eventos_auditoria` | AuditEvent interno de criação e de acesso. |

O código de leitura reinsere Base64 a partir de `imagens_clinicas.conteudo`.
O worker decodifica essa mesma coluna e confere tamanho/hash persistidos antes
de analisar. A leitura do Bundle devolve o snapshot da submissão, com imagens
reconstruídas, sem anexar automaticamente saídas criadas depois. Os resultados
são encontrados por Task.output e pelas rotas de recurso.

A revisão Alembic
[20261116_02](../migrations/versions/20261116_02_quality_pipeline.py) sucede
`20261021_01`. Ela adiciona propriedade e fingerprint ao pacote, restrição
única de idempotência, campos duráveis do worker e tabela de auditoria. Também
remove as cópias de `content.data` dos JSONs de Bundle, entradas e imagem,
preservando a coluna `conteudo` como fonte única.

Pacotes existentes recebem proprietário `__legacy__:<identificador-do-pacote>`.
O prefixo não pode ser configurado como cliente autenticado. Isso impede que
um token novo ganhe acesso automático a fotografias antigas sem revisão da
propriedade. A migração não converte imagens antigas para o novo perfil,
recalcula fingerprint de submissão nem atribui um dono clínico real.

Essa quarentena é de propriedade e acesso: o seletor atual da fila não exclui
Tasks legadas por proprietário. Antes de iniciar workers em um banco existente,
revise o estado dessas tarefas. Uma Task antiga pendente pode ser processada,
falhar por imagem inválida ou expirar conforme o prazo calculado a partir da
criação. Não há operação pública de transferência de propriedade ou de liberação
de legado. Uma atribuição futura precisa de processo revisado e evidência de dono.

O downgrade restaura Base64 nos JSONs para compatibilidade com o código anterior
e remove as novas colunas e a tabela de auditoria. Isso perde os metadados de
propriedade, execução e auditoria introduzidos pela revisão; não restaura por si
só a política de segurança da versão nova. Faça backup e planeje rollback junto
da versão da aplicação. A migração percorre os JSONs existentes em memória;
avalie volume, duração e janela de manutenção antes de aplicá-la a uma base grande.

## Configuração e execução operacional

As variáveis são lidas por [Settings](../src/healplus_intake_image_api/core/config.py)
do ambiente e do `.env`; campos de Compose adicionais são ignorados pela
aplicação. Não publique `.env` com segredos no repositório.

| Variável | Padrão | Efeito |
|---|---|---|
| `DATABASE_URL` | Obrigatória | Banco usado pela API e pelo worker. |
| `FHIR_BASE_URL` | `http://127.0.0.1:8000/api/fhir/r4` | Base REST absoluta dos fullUrl persistidos; sem credenciais, query ou fragmento. |
| `API_CLIENT_TOKENS` | `{}` | Credenciais provisionadas; vazio mantém recursos clínicos fechados. |
| `REQUIRE_HTTPS` | `false` | Exige esquema HTTPS na rota clínica quando habilitado. |
| `MAX_REQUEST_BYTES` | `33554432` | Limite total de corpo; mínimo configurável de 1024 bytes. |
| `ANALYSIS_TIMEOUT_SECONDS` | `120` | Prazo desde a submissão; mínimo 1 segundo. |
| `ANALYSIS_MAX_ATTEMPTS` | `3` | Tentativas totais, entre 1 e 20. |
| `ANALYSIS_RETRY_BASE_SECONDS` | `2` | Base positiva do recuo exponencial. |
| `ANALYSIS_LEASE_SECONDS` | `60` | Posse por tentativa, limitada ao prazo; mínimo 1 segundo. |
| `WORKER_POLL_SECONDS` | `1.0` | Pausa positiva quando não houve trabalho elegível. |
| `POSTGRES_PASSWORD` | Sem segredo padrão utilizável | Variável consumida pelo Compose, que publica o PostgreSQL somente em loopback. |

Para preparar um ambiente local, instale dependências, copie o exemplo e
preencha senha do banco, URL correspondente e credenciais próprias:

```powershell
uv sync --all-groups
Copy-Item .env.example .env
# Edite .env antes dos próximos comandos.
docker compose up -d --wait
uv run alembic upgrade head
uv run alembic current
uv run fastapi dev src/healplus_intake_image_api/main.py
```

Inicie o worker em outro terminal com o mesmo ambiente:

```powershell
uv run python -m healplus_intake_image_api.worker
# Ou processe no máximo uma tarefa elegível:
uv run python -m healplus_intake_image_api.worker --once
```

`--once` encerra normalmente tanto quando processa uma tarefa quanto quando não
há trabalho. Portanto, código de saída zero não prova que uma Task específica
foi concluída: consulte o recurso. Erro externo da fila com `--once` é propagado;
no modo contínuo, a indisponibilidade é registrada e o processo tenta novamente.
O processo pode ser encerrado com interrupção de teclado; use um supervisor
adequado na implantação. Não use o servidor de desenvolvimento como serviço
de produção.

O gerador [examples/build_payload.py](../examples/build_payload.py) produz um
Parameters completo com imagem geométrica RGB sRGB, hash/tamanho corretos e
rótulo HTEST em recursos sintéticos:

```powershell
uv run python examples/build_payload.py --output synthetic-payload.json
```

Use o arquivo para o POST descrito no README e preserve-o para o teste de replay.
Uma nova execução do gerador muda identificador, referências e instantes; isso
representa nova submissão, não o retry idempotente da anterior. O gerador não
produz fotografia clínica nem material de treino.

## Observabilidade e diagnóstico

Não há endpoint de métricas, dashboard de fila ou alerta automático. O estado
operacional pode ser observado por polling das próprias Tasks, consultas
administrativas restritas ao banco e logs do processo worker. Os logs registram
eventos genéricos de conclusão/falha e extras de Task/tentativa para um handler
estruturado; o formatter padrão não garante exibir todos os extras. Não ative
logging de headers, payloads, URLs de banco ou imagens como forma de diagnóstico.

Consultas PostgreSQL de leitura, sem expor imagem ou contexto clínico:

```sql
SELECT estado, count(*) AS quantidade, min(criado_em) AS mais_antiga
FROM tarefas_analise
GROUP BY estado;

SELECT last_error, count(*) AS quantidade
FROM tarefas_analise
WHERE estado = 'failed'
GROUP BY last_error;

SELECT count(*) AS leases_expiradas
FROM tarefas_analise
WHERE estado = 'in-progress' AND lease_expires_at <= now();
```

| Sintoma | Verificação |
|---|---|
| Task permanece `accepted` | Worker está ativo e usa o mesmo DATABASE_URL? Há `next_attempt_at` futuro? A Task já venceu e aguarda passagem do worker? |
| `in-progress` após queda do processo | Aguarde expiração da lease e passagem de outro worker; verifique banco acessível. Não zere manualmente attempts para ocultar falhas. |
| `failed/tempo-esgotado` | Compare espera da fila, tempo de cálculo e prazo; ajuste capacidade e limites conforme dados medidos. |
| `failed/limite-tentativas` | Verifique falhas técnicas repetidas no worker e disponibilidade do banco; a Task não repetirá indefinidamente. |
| `failed/imagem-invalida` | Pode haver registro legado ou corrupção/divergência no conteúdo persistido; novas entradas já passam pela validação de JPEG. |
| POST retorna `409` após regenerar payload | A chave de negócio foi preservada mas o conteúdo mudou; reenvie o arquivo original ou use nova chave para nova avaliação. |
| Recurso retorna `404` | Confira UUID retornado e cliente autenticado; a API não distingue externamente ID inexistente de propriedade de outro cliente. |
| Operações clínicas retornam `503` | Verifique credenciais configuradas, banco e escrita de auditoria; não abra rotas para contornar a falha. |
| Imagem aparentemente boa tem ressalva | Comportamento esperado do v0 por critérios não implementados, não uma falha da fila. |

Para impedir crescimento silencioso, a implantação deve monitorar idade da fila,
falhas por motivo, expiração de leases, tempo até estado terminal, tamanho do
armazenamento e gravação de auditoria. Essa instrumentação e seus alertas ainda
precisam ser conectados à infraestrutura operacional.

## Verificação e limites da evidência

```powershell
uv run pytest -q
# Integração PostgreSQL em container descartável próprio:
uv run python scripts/verify_postgres.py
```

A suíte cobre contrato HTTP/FHIR, JPEG real, ICC, EXIF, limites com chunks,
idempotência, isolamento, auditoria e falhas de sua transação, navegação de
referências, métricas, múltiplas fotografias, retry, prazo, lease e fencing.
Os testes estão em [tests](../tests), especialmente
[test_image_validation.py](../tests/test_image_validation.py),
[test_quality_worker.py](../tests/test_quality_worker.py),
[test_worker_integration.py](../tests/test_worker_integration.py) e
[test_request_limits_and_audit_failures.py](../tests/test_request_limits_and_audit_failures.py).

O [roteiro PostgreSQL](../scripts/verify_postgres.py) cria container próprio com
nome aleatório e dados temporários, aplica migrações sobre snapshot legado,
verifica armazenamento único/quarentena, restauração em downgrade, novo upgrade,
`alembic check`, HTTP, replay e concorrência de submissões/workers. Ele não usa
o banco do Compose existente e remove somente o container cuja identidade
confere ao final. Requer Docker funcionando e acesso à imagem PostgreSQL 16.

Esses testes não demonstram operação clínica, TLS de produção, disponibilidade
externa, integração com câmera real, conformidade integral do FHIR ou adequação
LGPD do ambiente. A próxima etapa depende de protocolo de captura e referência
física definidos, dados revisados por profissionais, validação dos limiares e
decisões de segurança/governança descritas na matriz das lacunas.
