# Mapeamento FHIR R4 dos requisitos clínicos de entrada

**Fonte:** Quadro 1 de `requisitos_clinicos_v1.0.html`  
**Escopo:** contrato de intake de avaliações clínicas de feridas da API HealPlus.  
**Versão normativa:** FHIR R4 4.0.1.

## 1. Decisões de interoperabilidade

O recurso clínico principal é `Condition`: uma instância representa **uma
ferida**. `Encounter` registra o contexto assistencial em que a avaliação foi
realizada; não substitui a ferida e não deve ser usado como seu identificador.
`Observation` representa medições e constatações pontuais da avaliação;
`Media` representa a fotografia clínica.

O payload de uma operação FHIR usa `Parameters`, recurso não persistido
destinado exclusivamente à passagem de parâmetros de operação. Seu parâmetro
`bundle` contém um `Bundle.type = collection`, que agrupa recursos independentes
e referenciais. O Bundle **não** é uma transação REST.

Fontes normativas:

- [Parameters R4](https://hl7.org/fhir/R4/parameters.html)
- [Bundle R4](https://hl7.org/fhir/R4/bundle.html)
- [Encounter R4](https://hl7.org/fhir/R4/encounter.html)
- [Condition R4](https://hl7.org/fhir/R4/condition.html)
- [Observation R4](https://hl7.org/fhir/R4/observation.html)
- [Media R4](https://hl7.org/fhir/R4/media.html)
- [Provenance R4](https://hl7.org/fhir/R4/provenance.html)

## 2. Modelo de relacionamento

```text
Parameters
└── Bundle (collection)
    ├── Patient
    ├── Practitioner
    ├── Encounter ────────── subject ───────► Patient
    ├── Device ───────────── usado por ─────► Observation assistiva
    ├── Condition (ferida) ─ subject ───────► Patient
    │                         encounter ────► Encounter
    ├── Media ────────────── subject ───────► Patient
    │                         encounter ────► Encounter
    ├── Observation (*) ──── subject ───────► Patient
    │                         encounter ────► Encounter
    │                         focus ────────► Condition (ferida)
    │                         derivedFrom ──► Media
    └── Provenance ───────── target ────────► recursos do Bundle
                              agent.who ────► Practitioner
```

Em FHIR R4, `Media` não possui uma referência nativa para `Condition`.
A associação entre fotografia e ferida é garantida por:

1. `Media.subject` e `Media.encounter` iguais aos da avaliação;
2. `Media.bodySite` compatível com `Condition.bodySite`; e
3. `Observation.focus` referenciando a ferida e `Observation.derivedFrom`
   referenciando a fotografia utilizada.

Referências entre entradas do Bundle usam `urn:uuid:<uuid>` em
`Bundle.entry.fullUrl`. Cada `fullUrl` deve ser único, conforme a regra R4
`bdl-7`.

## 3. Matriz de rastreabilidade do Quadro 1

| ID | Informação clínica | Recurso FHIR R4 | Regra HealPlus |
|---|---|---|---|
| RC01a | Identificação do paciente | `Patient.identifier`, referência em `subject` | Um único paciente por Bundle. É obrigatório um identificador mínimo; nome, endereço e demais dados identificáveis não são necessários. |
| RC02a | Histórico relevante | `Condition` | A ferida é uma `Condition` distinta; comorbidades relevantes são `Condition` separados. Data de início, estado clínico e contexto são registrados no recurso. |
| RC03a | Localização anatômica | `Condition.bodySite` | Um `CodeableConcept` anatômico é obrigatório. |
| RC04a | Tipo de ferida | `Condition.code`, `Condition.category` | O tipo é informado pelo profissional e nunca inferido da fotografia. |
| RC05a | Dimensões | `Observation` | Comprimento e largura são obrigatórios; profundidade é obrigatória quando mensurável. Valores usam `Quantity` e UCUM. |
| RC06a | Tecido predominante | `Observation` | Registra tecido predominante, percentuais por tecido e percentual não classificado. |
| RC07a | Sinais de infecção | `Observation` | Registra sinais observados; não produz diagnóstico de infecção. |
| RC08a | Exsudato | `Observation` | Registra presença, quantidade e aspecto informado pelo profissional. |
| RC09a | Dor | `Observation` | Opcional, conforme o Quadro 1. Não pode ser inferida a partir de imagem. |
| RC10a | Bordas | `Observation` | Registra as características observadas nas bordas. |
| RC11a | Pele ao redor | `Observation` | Registra as condições observadas na pele perilesional. |
| RC12a | Imagens padronizadas | `Media` e `Observation` | `Media` contém a imagem; uma `Observation` complementar registra a qualidade e a ROI da captura. |

## 4. Perfis HealPlus e atributos

Os perfis devem ser publicados como `StructureDefinition`, com URL canônica
`https://healplus.com.br/fhir/StructureDefinition/<nome-do-perfil>`. A coluna
**Card.** é a cardinalidade imposta pelo perfil, não necessariamente a
cardinalidade do recurso base.

Os perfis definidos são `HealPlusSubmitWoundAssessmentParameters`,
`HealPlusWoundAssessmentBundle`, `HealPlusPatient`, `HealPlusWoundEncounter`,
`HealPlusWound`, `HealPlusMedia`, `HealPlusAnalysisDevice`,
`HealPlusAssessmentProvenance`, `HealPlusWoundDimensions`,
`HealPlusWoundTissue`, `HealPlusWoundInfectionSigns`,
`HealPlusWoundExudate`, `HealPlusWoundPain`, `HealPlusWoundEdges`,
`HealPlusPeriwoundSkin` e `HealPlusImageCaptureQuality`.

### 4.1 Envelope da operação

| Perfil e elemento | Tipo de dado R4 | Card. | Restrição HealPlus |
|---|---|---:|---|
| `HealPlusSubmitWoundAssessmentParameters.resourceType` | `code` | 1..1 | Fixo em `Parameters`. |
| `.parameter` | `BackboneElement` | 1..1 | Exatamente um parâmetro. |
| `.parameter.name` | `code` | 1..1 | Fixo em `bundle`. |
| `.parameter.resource` | `Resource` | 1..1 | Deve ser `Bundle` no perfil `HealPlusWoundAssessmentBundle`. Não pode coexistir com `value[x]` ou `part`. |
| `HealPlusWoundAssessmentBundle.resourceType` | `code` | 1..1 | Fixo em `Bundle`. |
| `.id` | `id` | 1..1 | Identificador FHIR do pacote submetido. |
| `.type` | `code` | 1..1 | Fixo em `collection`. |
| `.timestamp` | `instant` | 1..1 | Momento de montagem do Bundle. |
| `.entry` | `BackboneElement` | 1..* | Contém todos os recursos da avaliação. |
| `.entry.fullUrl` | `uri` | 1..1 | `urn:uuid:<uuid>` único no Bundle. |
| `.entry.resource` | `Resource` | 1..1 | Recurso permitido pela seção 5. `entry.request` e `entry.response` são proibidos em `collection`. |

### 4.2 Contexto clínico e rastreabilidade

| Perfil e elemento | Tipo de dado R4 | Card. | Restrição HealPlus |
|---|---|---:|---|
| `HealPlusPatient.identifier` | `Identifier` | 1..* | Um identificador pseudonimizado ou institucional do paciente. |
| `HealPlusPatient.identifier.system` | `uri` | 1..1 | Sistema emissor do identificador. |
| `HealPlusPatient.identifier.value` | `string` | 1..1 | Valor do identificador. |
| `HealPlusWoundEncounter.status` | `code` | 1..1 | Estado R4 do atendimento, por exemplo `finished`. |
| `.class` | `Coding` | 1..1 | Classe assistencial, por exemplo `AMB`. |
| `.subject` | `Reference(Patient)` | 1..1 | Mesmo paciente do Bundle. |
| `.period.start` | `dateTime` | 1..1 | Início do atendimento. |
| `.period.end` | `dateTime` | 0..1 | Fim, se conhecido. |
| `.participant.individual` | `Reference(Practitioner\|PractitionerRole\|RelatedPerson)` | 1..* | Profissional ou participante responsável. |
| `HealPlusWound.subject` | `Reference(Patient)` | 1..1 | Mesmo paciente do Bundle. |
| `.encounter` | `Reference(Encounter)` | 1..1 | Atendimento da avaliação; somente pode ser omitido em captura remota sem atendimento identificável. |
| `.clinicalStatus` | `CodeableConcept` | 1..1 | Estado clínico da ferida, por exemplo `active`. |
| `.verificationStatus` | `CodeableConcept` | 1..1 | Estado de confirmação, por exemplo `confirmed`. |
| `.category` | `CodeableConcept` | 1..* | Categoria local versionada `wound`. |
| `.code` | `CodeableConcept` | 1..1 | Tipo de ferida informado pelo profissional. |
| `.bodySite` | `CodeableConcept` | 1..* | Localização anatômica codificada. |
| `.onset[x]` | `dateTime` | 0..1 | No perfil, quando informado, usa `onsetDateTime`. |
| `.recordedDate` | `dateTime` | 1..1 | Data de registro da condição. |
| `.recorder` | `Reference(Practitioner\|PractitionerRole\|Patient\|RelatedPerson)` | 1..1 | Autor do registro da ferida. |
| `.note` | `Annotation` | 0..* | Contexto relevante; `text` é `markdown`, `author[x]` e `time` devem ser preenchidos quando disponíveis. |
| `HealPlusMedia.status` | `code` | 1..1 | Fixo em `completed` para fotografia pronta. |
| `.type` | `CodeableConcept` | 1..1 | Deve incluir `media-type#image`. |
| `.subject` | `Reference(Patient)` | 1..1 | Mesmo paciente do Bundle. |
| `.encounter` | `Reference(Encounter)` | 1..1 | Mesmo Encounter da avaliação, exceto na captura remota permitida pelo perfil. |
| `.created[x]` | `dateTime` | 1..1 | No perfil, usa `createdDateTime`. |
| `.operator` | `Reference(Practitioner\|PractitionerRole\|Organization\|CareTeam\|Patient\|Device\|RelatedPerson)` | 1..1 | Responsável pela captura. |
| `.bodySite` | `CodeableConcept` | 1..1 | Compatível com a localização da ferida. |
| `.content` | `Attachment` | 1..1 | Conteúdo da fotografia. |
| `.content.contentType` | `code` | 1..1 | Fixo em `image/jpeg`. |
| `.content.data` | `base64Binary` | 1..1 | JPEG em Base64. A API não aceita URL externa neste perfil. |
| `.content.hash` | `base64Binary` | 0..1 | Hash da imagem quando disponibilizado pelo cliente. |
| `HealPlusAnalysisDevice.status` | `code` | 1..1 | Estado do dispositivo; `active` para modelo disponível. |
| `.manufacturer` | `string` | 1..1 | Responsável pelo dispositivo ou modelo. |
| `.deviceName.name` | `string` | 1..1 | Nome do dispositivo ou modelo. |
| `.deviceName.type` | `code` | 1..1 | Fixo em `user-friendly-name`. |
| `.version` | `string` | 1..1 | Versão reprodutível do modelo ou dispositivo. |
| `HealPlusAssessmentProvenance.target` | `Reference(Any)` | 1..* | Recursos de entrada produzidos na mesma atividade. |
| `.recorded` | `instant` | 1..1 | Momento em que a atividade foi registrada. |
| `.activity` | `CodeableConcept` | 1..1 | Atividade local versionada `clinical-data-capture`. |
| `.agent` | `BackboneElement` | 1..* | Agente que participou da atividade. |
| `.agent.type` | `CodeableConcept` | 1..1 | Papel, por exemplo `author`. |
| `.agent.who` | `Reference(Practitioner\|PractitionerRole\|Organization\|Patient\|RelatedPerson\|Device)` ou `uri` | 1..1 | Agente responsável. |

### 4.3 Base comum das observações

Os oito perfis de `Observation` da seção 4.4 compartilham os elementos abaixo.

| Elemento | Tipo de dado R4 | Card. | Restrição HealPlus |
|---|---|---:|---|
| `resourceType` | `code` | 1..1 | Fixo em `Observation`. |
| `status` | `code` | 1..1 | `final` para registro validado pelo profissional; `preliminary` somente antes da revisão. |
| `category` | `CodeableConcept` | 1..* | Deve incluir `observation-category#exam`. |
| `code` | `CodeableConcept` | 1..1 | Código local HealPlus que identifica o tipo da observação. |
| `subject` | `Reference(Patient)` | 1..1 | Mesmo paciente do Bundle. |
| `encounter` | `Reference(Encounter)` | 1..1 | Mesmo atendimento da avaliação, com a exceção de captura remota definida no perfil. |
| `focus` | `Reference(Condition)` | 1..1 | A `Condition` que representa a ferida. |
| `effective[x]` | `dateTime` | 1..1 | No perfil, usa `effectiveDateTime`: instante clínico da avaliação. |
| `issued` | `instant` | 1..1 | Instante de emissão do registro. |
| `performer` | `Reference(Practitioner\|PractitionerRole\|Organization\|CareTeam\|Patient\|RelatedPerson)` | 1..* | Responsável pela observação. |
| `bodySite` | `CodeableConcept` | 1..1 | Compatível com `Condition.bodySite`. |
| `method` | `CodeableConcept` | 0..1 | Método aplicado, como avaliação visual, medição manual ou análise assistiva. |
| `device` | `Reference(Device\|DeviceMetric)` | 0..1 | Obrigatório se o resultado foi gerado por dispositivo ou modelo computacional. |
| `derivedFrom` | `Reference(Observation\|QuestionnaireResponse\|MolecularSequence\|DocumentReference\|ImagingStudy\|Media)` | 0..* | Referência ao `Media` somente quando a foto contribuiu para o resultado. |
| `note` | `Annotation` | 0..* | Observação contextual do profissional; não substitui elemento estruturado. |
| `component` | `BackboneElement` | 0..* | Componentes específicos da seção 4.4. |
| `component.code` | `CodeableConcept` | 1..1 | Código do componente. |
| `component.value[x]` | `Quantity`, `CodeableConcept`, `boolean` ou `integer` | 0..1 | Tipo definido para cada componente. |
| `component.dataAbsentReason` | `CodeableConcept` | 0..1 | Obrigatório quando um componente clínico aplicável não tiver valor. |

### 4.4 Componentes dos perfis de `Observation`

Todos os códigos abaixo pertencem ao `CodeSystem` versionado
`https://healplus.com.br/fhir/CodeSystem/wound-assessment`. O conjunto final de
valores deve ser validado pela equipe clínica antes da implementação.

| Perfil | `Observation.code` | Atributos adicionais e tipo de dado |
|---|---|---|
| `HealPlusWoundDimensions` | `wound-dimensions` | `component[length]`, `component[width]`, `component[depth]` e `component[area]`: `Quantity`. Comprimento e largura usam UCUM `cm`; profundidade usa `cm`; área usa `cm2`. Profundidade não mensurável usa `dataAbsentReason`. |
| `HealPlusWoundTissue` | `wound-tissue` | `valueCodeableConcept`: tecido predominante. Componentes `granulation-percent`, `necrosis-percent`, `slough-percent`, `epithelialization-percent` e `unclassified-percent`: `Quantity` em `%`. Para análise computacional, exige `method`, `device` e extensão `analysis-confidence` (`decimal`, 0 a 1). |
| `HealPlusWoundInfectionSigns` | `wound-infection-signs` | Componentes `odor`, `erythema`, `warmth`, `increased-pain`, `secretion`, `visual-worsening` e `edema`: `boolean`. Estes valores são achados e não um diagnóstico. |
| `HealPlusWoundExudate` | `wound-exudate` | Componentes `present`: `boolean`; `amount`, `appearance`, `color` e `consistency`: `CodeableConcept`; `odor-assessed`: `boolean`. |
| `HealPlusWoundPain` | `wound-pain` | Opcional. `valueInteger`: intensidade; `method`: escala utilizada; `note`: origem do dado, relato do paciente ou observação profissional. |
| `HealPlusWoundEdges` | `wound-edges` | Componentes `maceration`, `undermining`, `epithelialization`, `hyperkeratosis` e `irregularity`: `boolean`. |
| `HealPlusPeriwoundSkin` | `periwound-skin` | Componentes `erythema`, `edema`, `maceration`, `dryness`, `scaling` e `irritation`: `boolean`; `affected-distance`: `Quantity` em `cm`. |
| `HealPlusImageCaptureQuality` | `image-capture-quality` | Componentes `focus`, `lighting`, `framing`, `distance-standardized` e `repeatable`: `CodeableConcept`; `scale-present` e `privacy-reviewed`: `boolean`. `derivedFrom` é obrigatório e referencia um `Media`. A extensão `wound-roi-geometry` usa `valueString` com GeoJSON da ROI. |

As extensões necessárias são:

| Extensão | Contexto | Tipo R4 | Uso |
|---|---|---|---|
| `https://healplus.com.br/fhir/StructureDefinition/analysis-confidence` | `Observation` | `decimal` | Confiança do modelo, limitada pelo perfil ao intervalo de 0 a 1. |
| `https://healplus.com.br/fhir/StructureDefinition/wound-roi-geometry` | `Observation` | `string` | Geometria da ROI serializada como GeoJSON; obrigatória apenas quando houver ROI. |

## 5. Validações entre recursos

1. O Bundle deve conter exatamente um `Patient`, uma `Condition` de ferida e ao
   menos um `Media`.
2. `Encounter`, `Practitioner` e `Provenance` são obrigatórios para a avaliação
   presencial. Na captura remota, `Encounter` pode ser omitido somente se o
   perfil declarar o modo remoto e `Provenance` identificar a origem.
3. Todo `Observation.subject` deve referenciar o Patient; todo
   `Observation.focus` deve referenciar a Condition; todo
   `Observation.encounter`, quando presente, deve referenciar o mesmo Encounter.
4. A data da fotografia (`Media.createdDateTime`) e a data clínica
   (`Observation.effectiveDateTime`) são independentes e ambas devem ser
   preservadas.
5. `Observation.derivedFrom` somente pode referenciar um `Media` do mesmo
   paciente, atendimento e localização anatômica compatível.
6. A composição tecidual não classificada deve estar presente sempre que a
   soma dos demais percentuais for inferior a 100%.
7. Resultados assistivos não podem inferir dor, diagnosticar infecção, definir
   conduta, prescrever tratamento ou estagiar automaticamente a lesão.

## 6. Payload completo de exemplo

O payload abaixo representa uma avaliação presencial. Ele contém todos os
requisitos RC01a–RC12a e inclui RC09a (dor), embora seja opcional. Os códigos
HealPlus são ilustrativos e precisam ser formalizados nos `ValueSet` e
`CodeSystem` publicados.

```json
{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "bundle",
      "resource": {
        "resourceType": "Bundle",
        "id": "assessment-20261019-001",
        "type": "collection",
        "timestamp": "2026-10-19T22:10:00Z",
        "entry": [
          {
            "fullUrl": "urn:uuid:patient-001",
            "resource": {
              "resourceType": "Patient",
              "id": "patient-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-patient"
                ]
              },
              "identifier": [
                {
                  "system": "https://healplus.com.br/fhir/NamingSystem/patient",
                  "value": "PSEUD-00001"
                }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:practitioner-001",
            "resource": {
              "resourceType": "Practitioner",
              "id": "practitioner-001",
              "identifier": [
                {
                  "system": "https://healplus.com.br/fhir/NamingSystem/professional",
                  "value": "PROF-00001"
                }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:device-001",
            "resource": {
              "resourceType": "Device",
              "id": "device-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-analysis-device"
                ]
              },
              "status": "active",
              "manufacturer": "HealPlus",
              "deviceName": [
                {
                  "name": "HealPlus tissue segmentation",
                  "type": "user-friendly-name"
                }
              ],
              "version": "1.0.0"
            }
          },
          {
            "fullUrl": "urn:uuid:encounter-001",
            "resource": {
              "resourceType": "Encounter",
              "id": "encounter-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-wound-encounter"
                ]
              },
              "status": "finished",
              "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "ambulatory"
              },
              "subject": {
                "reference": "urn:uuid:patient-001"
              },
              "period": {
                "start": "2026-10-19T21:50:00Z",
                "end": "2026-10-19T22:10:00Z"
              },
              "participant": [
                {
                  "individual": {
                    "reference": "urn:uuid:practitioner-001"
                  }
                }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:wound-001",
            "resource": {
              "resourceType": "Condition",
              "id": "wound-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-wound"
                ]
              },
              "clinicalStatus": {
                "coding": [
                  {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active"
                  }
                ]
              },
              "verificationStatus": {
                "coding": [
                  {
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed"
                  }
                ]
              },
              "category": [
                {
                  "coding": [
                    {
                      "system": "https://healplus.com.br/fhir/CodeSystem/condition-category",
                      "code": "wound"
                    }
                  ]
                }
              ],
              "code": {
                "coding": [
                  {
                    "system": "https://healplus.com.br/fhir/CodeSystem/wound-type",
                    "code": "venous-ulcer",
                    "display": "Venous ulcer"
                  }
                ]
              },
              "subject": {
                "reference": "urn:uuid:patient-001"
              },
              "encounter": {
                "reference": "urn:uuid:encounter-001"
              },
              "onsetDateTime": "2026-08-01",
              "recordedDate": "2026-10-19T22:00:00Z",
              "recorder": {
                "reference": "urn:uuid:practitioner-001"
              },
              "bodySite": [
                {
                  "coding": [
                    {
                      "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site",
                      "code": "left-medial-malleolus",
                      "display": "Left medial malleolus"
                    }
                  ]
                }
              ],
              "note": [
                {
                  "authorReference": {
                    "reference": "urn:uuid:practitioner-001"
                  },
                  "time": "2026-10-19T22:00:00Z",
                  "text": "Recorrência relatada; sem alteração de conduta neste intake."
                }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:media-001",
            "resource": {
              "resourceType": "Media",
              "id": "media-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-media"
                ]
              },
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
                "reference": "urn:uuid:patient-001"
              },
              "encounter": {
                "reference": "urn:uuid:encounter-001"
              },
              "createdDateTime": "2026-10-19T21:55:00Z",
              "operator": {
                "reference": "urn:uuid:practitioner-001"
              },
              "bodySite": {
                "coding": [
                  {
                    "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site",
                    "code": "left-medial-malleolus"
                  }
                ]
              },
              "content": {
                "contentType": "image/jpeg",
                "data": "/9j/4AAQ"
              }
            }
          },
          {
            "fullUrl": "urn:uuid:obs-dimensions-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-dimensions-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-wound-dimensions"
                ]
              },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-dimensions" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "method": { "text": "Manual measurement with metric scale" },
              "derivedFrom": [{ "reference": "urn:uuid:media-001" }],
              "component": [
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "length" }] }, "valueQuantity": { "value": 4.2, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "width" }] }, "valueQuantity": { "value": 2.1, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "depth" }] }, "valueQuantity": { "value": 0.3, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "area" }] }, "valueQuantity": { "value": 8.82, "unit": "cm2", "system": "http://unitsofmeasure.org", "code": "cm2" } }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-tissue-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-tissue-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-wound-tissue"] },
              "extension": [{ "url": "https://healplus.com.br/fhir/StructureDefinition/analysis-confidence", "valueDecimal": 0.91 }],
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-tissue" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "method": { "text": "Assistive image segmentation" },
              "device": { "reference": "urn:uuid:device-001" },
              "derivedFrom": [{ "reference": "urn:uuid:media-001" }],
              "valueCodeableConcept": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-tissue", "code": "granulation" }] },
              "component": [
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "granulation-percent" }] }, "valueQuantity": { "value": 65, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "necrosis-percent" }] }, "valueQuantity": { "value": 0, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "slough-percent" }] }, "valueQuantity": { "value": 20, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "epithelialization-percent" }] }, "valueQuantity": { "value": 10, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" } },
                { "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "unclassified-percent" }] }, "valueQuantity": { "value": 5, "unit": "%", "system": "http://unitsofmeasure.org", "code": "%" } }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-infection-signs-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-infection-signs-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-wound-infection-signs"] },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-infection-signs" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "component": [
                { "code": { "text": "odor" }, "valueBoolean": false },
                { "code": { "text": "erythema" }, "valueBoolean": true },
                { "code": { "text": "warmth" }, "valueBoolean": false },
                { "code": { "text": "increased-pain" }, "valueBoolean": false },
                { "code": { "text": "secretion" }, "valueBoolean": false },
                { "code": { "text": "visual-worsening" }, "valueBoolean": false },
                { "code": { "text": "edema" }, "valueBoolean": true }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-exudate-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-exudate-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-wound-exudate"] },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-exudate" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "component": [
                { "code": { "text": "present" }, "valueBoolean": true },
                { "code": { "text": "amount" }, "valueCodeableConcept": { "text": "small" } },
                { "code": { "text": "appearance" }, "valueCodeableConcept": { "text": "serous" } },
                { "code": { "text": "color" }, "valueCodeableConcept": { "text": "straw" } },
                { "code": { "text": "consistency" }, "valueCodeableConcept": { "text": "thin" } },
                { "code": { "text": "odor-assessed" }, "valueBoolean": true }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-pain-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-pain-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-wound-pain"] },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-pain" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "method": { "text": "Numeric rating scale 0 to 10" },
              "valueInteger": 3,
              "note": [{ "text": "Pain reported by the patient." }]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-edges-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-edges-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-wound-edges"] },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "wound-edges" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "component": [
                { "code": { "text": "maceration" }, "valueBoolean": false },
                { "code": { "text": "undermining" }, "valueBoolean": false },
                { "code": { "text": "epithelialization" }, "valueBoolean": true },
                { "code": { "text": "hyperkeratosis" }, "valueBoolean": false },
                { "code": { "text": "irregularity" }, "valueBoolean": false }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-periwound-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-periwound-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-periwound-skin"] },
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "periwound-skin" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T22:00:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "component": [
                { "code": { "text": "erythema" }, "valueBoolean": true },
                { "code": { "text": "edema" }, "valueBoolean": true },
                { "code": { "text": "maceration" }, "valueBoolean": false },
                { "code": { "text": "dryness" }, "valueBoolean": false },
                { "code": { "text": "scaling" }, "valueBoolean": false },
                { "code": { "text": "irritation" }, "valueBoolean": false },
                { "code": { "text": "affected-distance" }, "valueQuantity": { "value": 0.5, "unit": "cm", "system": "http://unitsofmeasure.org", "code": "cm" } }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:obs-capture-quality-001",
            "resource": {
              "resourceType": "Observation",
              "id": "obs-capture-quality-001",
              "meta": { "profile": ["https://healplus.com.br/fhir/StructureDefinition/healplus-image-capture-quality"] },
              "extension": [{ "url": "https://healplus.com.br/fhir/StructureDefinition/wound-roi-geometry", "valueString": "{\"type\":\"Polygon\",\"coordinates\":[[[10,10],[90,10],[90,90],[10,90],[10,10]]]}" }],
              "status": "final",
              "category": [{ "coding": [{ "system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "exam" }] }],
              "code": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/wound-assessment", "code": "image-capture-quality" }] },
              "subject": { "reference": "urn:uuid:patient-001" },
              "encounter": { "reference": "urn:uuid:encounter-001" },
              "focus": [{ "reference": "urn:uuid:wound-001" }],
              "effectiveDateTime": "2026-10-19T21:55:00Z",
              "issued": "2026-10-19T22:10:00Z",
              "performer": [{ "reference": "urn:uuid:practitioner-001" }],
              "bodySite": { "coding": [{ "system": "https://healplus.com.br/fhir/CodeSystem/anatomical-site", "code": "left-medial-malleolus" }] },
              "derivedFrom": [{ "reference": "urn:uuid:media-001" }],
              "component": [
                { "code": { "text": "focus" }, "valueCodeableConcept": { "text": "adequate" } },
                { "code": { "text": "lighting" }, "valueCodeableConcept": { "text": "adequate" } },
                { "code": { "text": "framing" }, "valueCodeableConcept": { "text": "complete-wound-and-periwound" } },
                { "code": { "text": "distance-standardized" }, "valueCodeableConcept": { "text": "yes" } },
                { "code": { "text": "scale-present" }, "valueBoolean": true },
                { "code": { "text": "repeatable" }, "valueCodeableConcept": { "text": "yes" } },
                { "code": { "text": "privacy-reviewed" }, "valueBoolean": true }
              ]
            }
          },
          {
            "fullUrl": "urn:uuid:provenance-001",
            "resource": {
              "resourceType": "Provenance",
              "id": "provenance-001",
              "meta": {
                "profile": [
                  "https://healplus.com.br/fhir/StructureDefinition/healplus-assessment-provenance"
                ]
              },
              "target": [
                { "reference": "urn:uuid:encounter-001" },
                { "reference": "urn:uuid:wound-001" },
                { "reference": "urn:uuid:media-001" },
                { "reference": "urn:uuid:obs-dimensions-001" },
                { "reference": "urn:uuid:obs-tissue-001" },
                { "reference": "urn:uuid:obs-infection-signs-001" },
                { "reference": "urn:uuid:obs-exudate-001" },
                { "reference": "urn:uuid:obs-pain-001" },
                { "reference": "urn:uuid:obs-edges-001" },
                { "reference": "urn:uuid:obs-periwound-001" },
                { "reference": "urn:uuid:obs-capture-quality-001" }
              ],
              "recorded": "2026-10-19T22:10:00Z",
              "activity": {
                "coding": [
                  {
                    "system": "https://healplus.com.br/fhir/CodeSystem/provenance-activity",
                    "code": "clinical-data-capture"
                  }
                ]
              },
              "agent": [
                {
                  "type": {
                    "coding": [
                      {
                        "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                        "code": "author"
                      }
                    ]
                  },
                  "who": {
                    "reference": "urn:uuid:practitioner-001"
                  }
                }
              ]
            }
          }
        ]
      }
    }
  ]
}
```

## 7. Impacto no contrato atual

O contrato atual persiste `Parameters`, `Bundle`, `Media` e `Task`. Para
implementar esta especificação, deve adicionar os perfis, validações e
persistência de `Patient`, `Encounter`, `Condition`, `Observation`,
`Practitioner` e `Provenance`, mantendo `Task` somente para o ciclo assíncrono.
Não é seguro codificar os requisitos RC01a–RC12a como extensões ad hoc em
`Media`: eles têm semântica clínica própria em FHIR R4.
