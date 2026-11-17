# Histórico de mudanças

## 0.2.0 — 17 de novembro de 2026

Esta versão transforma o intake em uma fila persistida de análise técnica de
imagem, com resultados consultáveis e acesso restrito por cliente. A análise
é experimental e não representa validação clínica ou implantação em produção.

### Mudanças que exigem adaptação dos clientes

- As operações clínicas exigem token Bearer provisionado em `API_CLIENT_TOKENS`.
  Sem clientes configurados, respondem `503`; credenciais ausentes ou inválidas
  respondem `401`. Recursos de outro cliente respondem `404`.
- `Bundle.identifier.system/value` passam a ser obrigatórios. Reenvios do mesmo
  conteúdo reutilizam a Task com `200`; conteúdo diferente para a mesma chave
  retorna `409`. A chave é isolada por cliente autenticado.
- Cada imagem exige JPEG completo, ICC sRGB válido, `Media.width/height`,
  `Attachment.size` e `Attachment.hash` SHA-1 em Base64, conferidos contra os
  bytes recebidos. Orientação não normalizada e EXIF sensível são rejeitados.
- Cada fotografia exige uma observação humana de qualidade própria, vinculada
  por `derivedFrom`. Códigos HealPlus exigem `Coding.version`; perfis HealPlus
  declarados exigem URL canônica com versão. `Device.version` usa a lista nativa
  de objetos do FHIR R4.
- IDs de entrada são opcionais e servem à resolução local. O servidor atribui
  novos UUIDs e reescreve as referências. As consultas devem usar os IDs
  retornados. `FHIR_BASE_URL` determina as URLs completas do Bundle persistido.

### Análise assíncrona e resultado

- Worker separado em `python -m healplus_intake_image_api.worker`, com fila no
  banco, reivindicação atômica, lease, recuperação de trabalho interrompido,
  tentativas limitadas, recuo exponencial e prazo técnico configurável.
- Ciclo `accepted → in-progress → completed/failed`. Uma foto rejeitada conclui
  a execução em `completed`; falhas técnicas terminam em `failed`.
- Uma `Observation` por imagem contém veredito, escore, métricas, limiares,
  motivos codificados e orientações em português. `Task.input/output`,
  `businessStatus`, `executionPeriod` e `restriction.period` ligam o fluxo.
- Nitidez, exposição e resolução são medidas pelo algoritmo v0. Escala, cor
  calibrada, reflexo, ângulo, enquadramento e ITA permanecem não calculados.
  Esses critérios recebem `dataAbsentReason=unsupported`; nenhum resultado
  recebe aceite irrestrito.
- `Device` do algoritmo é gerenciado pelo servidor, com versões e hashes reais
  do código e dos limiares. `Provenance` registra origem, SHA-256 da imagem e
  protocolo. O algoritmo não usa pesos de rede neural nem assinatura JWS.

### Segurança, persistência e conformidade

- Leituras clínicas isoladas por cliente, tokens comparados sem registrar os
  segredos, opção de exigir HTTPS e respostas clínicas com `private, no-store`.
- `AuditEvent` interno para submissões e leituras, inclusive respostas `304`
  e recusas processadas nas rotas. A criação da Task e seu evento de criação
  são atômicos. Uma falha na auditoria de leitura impede a entrega dos dados.
- Corpo limitado antes do parsing, inclusive em envio por chunks. Limites de
  bytes, dimensões e pixels são aplicados às imagens. Recusas `413` no
  middleware não geram o evento de rota e devem ser acompanhadas pelo gateway.
- Base64 persistido uma única vez por foto; os JSONs armazenados não duplicam
  seu conteúdo. Respostas Media e Bundle são reconstituídas na leitura.
- Migração `20261116_02` adiciona isolamento por cliente, chave de idempotência,
  estado do worker e auditoria. Legados são segregados sob `__legacy__:<id>`
  até uma atribuição de propriedade revisada. O downgrade restaura as cópias
  JSON da implementação anterior.
- Senha fixa removida do Compose; PostgreSQL de desenvolvimento publicado em
  loopback. Perfis e terminologia técnica publicados na versão `1.1.0` e
  CapabilityStatement atualizado para software `0.2.0`.
- Polling com ETag preservado, com precedência de `If-None-Match` e tratamento
  conservador de `If-Modified-Since` para mudanças rápidas de Task.

### Documentação e verificação

- [Guia da implementação e operação](docs/quality-pipeline.md),
  [matriz das 42 lacunas](docs/implementation-gaps.md),
  [registro de validação](docs/validation-2026-11-17.md) e README atualizados.
- Gerador `examples/build_payload.py` cria contexto e JPEG sintéticos,
  identificados como teste, sem dados de pacientes.
- Testes automatizados de contrato, validação, autenticação, auditoria,
  isolamento, idempotência e worker. Roteiro PostgreSQL opt-in verifica
  migrações, dados legados, rollback, concorrência e fluxo até o resultado em
  container descartável separado do banco de uso.

### Limites que permanecem

OAuth 2.0/SMART, recaptura por operação dedicada, detecção e calibração de cartão,
validação clínica dos limiares, governança de pesquisa e dados rotulados
continuam pendentes. A matriz das lacunas registra os limites de cada entrega.
