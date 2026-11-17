# Atendimento das lacunas da API de qualidade de imagem

Este registro relaciona as 42 lacunas do relatório técnico à implementação local
da versão 0.2.0, em 16 de novembro de 2026. A entrega prioriza integridade das
fotografias, término da análise assíncrona, resultado rastreável, idempotência e
controle de acesso. Não constitui implantação em produção nem validação clínica.

"Implementada" indica que a função descrita foi construída no código; "parcial"
identifica uma parte entregue e a parte que falta. "Pendente" identifica trabalho
fora desta implementação, inclusive decisões que exigem equipe clínica,
governança ou dados de validação. O levantamento contém 16 lacunas implementadas,
11 parcialmente atendidas e 15 pendentes. A execução da suíte está no
[registro de validação de 17 de novembro](validation-2026-11-17.md); a
[documentação da implementação](quality-pipeline.md) explica os contratos e a
operação das partes entregues.

| ID | Estado | Entrega e limite restante |
|---|---|---|
| A1 | Implementada | `Media.width/height` obrigatórios, positivos e conferidos com o JPEG; limites por lado e total de pixels. |
| A2 | Parcial | `Attachment.size/hash` obrigatórios e conferidos; SHA-1 do FHIR e SHA-256 da origem na proveniência. Não há assinatura JWS do cliente/servidor nem prova de que os bytes vieram de uma câmera específica. |
| A3 | Implementada | JPEG completo decodificado com Pillow; rejeição de bytes arbitrários, truncamento e conteúdo com formato divergente. |
| A4 | Parcial | Regra de evitar recompressão documentada. Não é possível provar a cadeia de recompressões anteriores; estimativa de quantização JPEG ainda não implementada. |
| A5 | Parcial | ICC RGB sRGB válido obrigatório e conferido. Perfil amplo de metadados técnicos e outros espaços de cor ainda não implementados. |
| A6 | Pendente | A observação tipada de exposição/ISO/flash/distância focal depende da integração com as APIs da câmera; não há novo perfil obrigatório nesta versão. |
| A7 | Implementada | Orientação EXIF ausente ou igual a 1; dimensões declaradas precisam coincidir com os pixels recebidos. A normalização cabe ao cliente. |
| A8 | Implementada | Rejeição de EXIF com GPS, proprietário e números de série; cliente deve remover esses campos antes do envio. A inspeção visual de dados identificáveis na fotografia continua humana. |
| A9 | Parcial | `Media.device` é aceito e, se informado, precisa resolver para `Device` do Bundle; `Device.version` usa estrutura R4. Aparelho de captura e suas versões ainda não são obrigatórios. |
| A10 | Pendente | Sem medida física de distância nem método de aquisição; não se infere distância pelos pixels. |
| A11 | Pendente | Sem detector de escala, ângulo ou resolução espacial. A saída usa `dataAbsentReason=unsupported` para esses critérios. |
| A12 | Parcial | CodeSystems e ValueSets experimentais da saída técnica publicados com definições. Vocabulário e definição operacional do julgamento humano continuam dependentes da equipe clínica. |
| A13 | Parcial | Uma observação humana de qualidade por fotografia, com referência individual em `derivedFrom`. A observação técnica de metadados por foto ainda não é obrigatória. |
| A14 | Pendente | Não foi definido protocolo clínico de vistas nem ValueSet obrigatório para `Media.view`. |
| A15 | Implementada | Base64 persistido em uma única coluna por fotografia; JSONs de Bundle/entradas sem duplicá-lo; reidratação na leitura. Limite de corpo antes do parsing, inclusive envio em chunks. |
| B1 | Pendente | Sem detecção de referência colorimétrica nem cálculo de delta E calibrado. Não se afirma que uma foto passou por esses critérios. |
| B2 | Pendente | ITA não é calculado; falta ROI válida, protocolo e avaliação ética/de privacidade para estratificação. |
| B3 | Pendente | Sem base validada para comparar taxas de rejeição por estrato. Limiares v0 únicos, demonstrativos e sem aplicação por tom de pele. |
| B4 | Pendente | RIPD e governança dos dados derivados não são substituídos por código; não se cria dado sensível derivado de tom de pele nesta versão. |
| C1 | Implementada | `Observation` técnica por imagem, com veredito, escore, métricas, limiares, critérios não calculados, motivos e orientações. Resultado experimental, sem certificação clínica. |
| C2 | Implementada | `Task.code/input/output/businessStatus/executionPeriod/restriction.period` e links de leitura dos resultados. |
| C3 | Implementada | `focus=Condition` permanece nas observações clínicas de entrada; os resultados criados pelo servidor usam `focus=Media`. |
| C4 | Implementada | Gerador de resultado usa critérios técnicos fechados; perfil publica binding required e nota assistiva fixa. Não há rota de escrita livre de resultados pelo cliente. |
| D1 | Implementada | Worker separado com fila no banco; `accepted → in-progress → completed/failed`; rejeitar fotografia conclui a execução com veredito `rejeitada`. |
| D2 | Implementada | UUIDs do servidor; idempotência por cliente, `Bundle.identifier.system/value` e hash canônico da requisição; mesmo conteúdo retorna 200 e divergência retorna 409. |
| D3 | Pendente | Operação `Task/{id}/$reenviar-imagem`, encadeamento `partOf` e proveniência de revisão ainda não implementados. Nova avaliação pode ser submetida com outro identificador sem sobrescrever a anterior. |
| D4 | Parcial | Polling condicional mantido; prazo técnico configurável da Task. Subscription e pré-checagem no aparelho não implementadas; SLA durante atendimento exige acordo clínico. |
| D5 | Implementada | Tentativas limitadas, recuo exponencial, lease recuperável e prazo; falhas e timeout geram códigos técnicos, sem dados sensíveis de exceção na Task. |
| D6 | Pendente | Esta API não executa segmentação; não foi alterado o fluxo externo que pode ter gerado uma análise assistiva antes da submissão. A integração deve tratar qualidade como pré-condição. |
| E1 | Implementada | `Coding.version` obrigatório para CodeSystems HealPlus na entrada tipada; códigos gerados pelo servidor também carregam versão. |
| E2 | Parcial | Perfis publicados têm `StructureDefinition.version=1.1.0`; referências e `meta.profile` fornecido são versionados. Não se exige `meta.profile` em todo recurso enviado. |
| E3 | Implementada | Algoritmo v0 registrado pelo servidor como Device com versões de algoritmo, pré-processamento, limiares, Pillow e API, hashes reais de código e limiares e DeviceDefinition contido. O algoritmo não tem pesos de rede neural. |
| E4 | Parcial | Provenance de cada análise e versão real da API em metadata. `Bundle.meta.source` do aplicativo é preservado, mas não é obrigatório nem autenticado como versão de software do aparelho. |
| E5 | Implementada | Métricas implementadas carregam `component.referenceRange`; limiares experimentais fixos e identificados no Device e protocolo. Critério não calculado não recebe métrica inventada. |
| F1 | Pendente | Sem ingestão/anotação espacial de máscaras PNG, contornos ou referência segmentada. Exige processo de rotulagem e dados. |
| F2 | Pendente | Sem protocolo de avaliadores independentes, adjudicação ou mensuração de concordância. |
| F3 | Pendente | Sem Consent para uso secundário; não autoriza treino/pesquisa com as imagens recebidas. |
| F4 | Pendente | Sem exportação de datasets e Groups de treino/validação/teste por paciente. |
| F5 | Pendente | Sem pipeline de exportação com deslocamento de datas, remoção de texto livre e revisão visual. UUIDs e rejeição de EXIF sensível não equivalem à anonimização de imagens de saúde. |
| G1 | Parcial | Bearer provisionado, negação por padrão, UUIDs e leitura escopada ao cliente. OAuth 2.0/SMART, identidades profissionais e gestão centralizada de credenciais continuam pendentes. |
| G2 | Implementada | AuditEvent interno para submissões e leituras clínicas, com cliente, ação, destino e resultado; não registra token nem corpo clínico. Retenção e acesso operacional ao log exigem política do ambiente. |
| G3 | Parcial | Senha do Compose por variável, porta local e limite de corpo. TLS depende da implantação; rate limiting distribuído, cofre e dimensionamento do gateway ainda precisam ser configurados. |

## Verificação e uso da demonstração

Os testes de validação geram fotografias sintéticas em memória para conferir
JPEG/ICC, dimensões, hashes, orientação e EXIF. A suíte do worker distingue uma
imagem nítida de sua versão desfocada, verifica resultados e proveniência,
tentativas, timeout, recuperação de lease e proteção contra conclusão tardia de
um worker anterior. A suíte HTTP verifica o contrato, idempotência, isolamento,
auditoria e limites. O gerador `examples/build_payload.py` mantém um exemplo
reproduzível sem dados reais.

Uma imagem nítida e bem exposta recebe `aceita-com-ressalva`: escala, cor,
ângulo, reflexo, enquadramento e ITA não são analisados pelo algoritmo v0.
Uma imagem desfocada pode receber `rejeitada` e a Task termina em `completed`.
Falha técnica não é confundida com rejeição: a Task termina em `failed` após as
tentativas ou o prazo. Sem worker em execução, a fila não avança.

A validação local também passou em PostgreSQL 16 descartável: migração com
snapshot legado, armazenamento único da imagem, segregação dos registros sem
proprietário, restauração em downgrade, novo upgrade e `alembic check` sem
divergência. Foram exercitados intake, replay, worker, leitura de saída e
submissões e workers concorrentes. O roteiro reproduzível está em
`scripts/verify_postgres.py`.

A auditoria da rota inclui submissões inválidas e recusas de autenticação que
chegam ao seu handler. Recusas de tamanho `413`, feitas antes pelo middleware,
não geram `AuditEvent` da rota; precisam de registro no gateway. O evento de
criação é gravado na mesma transação da avaliação. Em leituras bem-sucedidas,
uma falha ao persistir a auditoria faz a API responder `503` sem liberar o
conteúdo clínico.

## Próximas decisões que alteram o contrato

O próximo incremento depende de definir protocolo de captura e cartão de
referência, requisitos do aparelho e dos metadados, conjunto de imagens de
validação revisado por profissionais e critérios eliminatórios. A partir dessas
decisões será possível implementar detecção e calibração, validar limiares e
fechar a recaptura sem reenviar toda a avaliação. A autorização de uso de dados
reais e de pesquisa requer decisões próprias de governança e implantação.

Referências do contrato: [Media R4](https://hl7.org/fhir/R4/media.html),
[Attachment R4](https://hl7.org/fhir/R4/datatypes.html#Attachment),
[Observation R4](https://hl7.org/fhir/R4/observation.html),
[Task R4](https://hl7.org/fhir/R4/task.html),
[Device R4](https://hl7.org/fhir/R4/device.html) e
[Provenance R4](https://hl7.org/fhir/R4/provenance.html).
