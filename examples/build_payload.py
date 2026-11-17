"""Generate a synthetic FHIR intake request without patient data.

Run with the project's Python environment; the output contains an actual JPEG
and is suitable for exercising the API contract, not for clinical validation.
"""

import argparse
import base64
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageCms, ImageDraw


FHIR = "https://healplus.com.br/fhir"
VERSION = "1.1.0"


def concept(system: str, code: str) -> dict:
    """Build a Coding with a terminology version for local systems."""
    coding = {"system": system, "code": code}
    if system.startswith(FHIR + "/CodeSystem/"):
        coding["version"] = VERSION
    return {"coding": [coding]}


def build_payload(identifier: str | None = None) -> dict:
    """Create one synthetic assessment with a generated sRGB JPEG."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    names = ["patient", "practitioner", "encounter", "wound", "capture", "media", "provenance"]
    refs = {name: f"urn:uuid:{uuid4()}" for name in names}
    entries: list[dict] = []
    test_label = [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActReason", "code": "HTEST"}]

    def add(name: str, resource: dict, profile: str | None = None) -> None:
        meta = {"security": test_label}
        if profile:
            meta["profile"] = [f"{FHIR}/StructureDefinition/{profile}|{VERSION}"]
        entries.append({"fullUrl": refs[name], "resource": {
            **resource, "id": name + "-local", "meta": meta,
        }})

    patient = {"reference": refs["patient"]}
    encounter = {"reference": refs["encounter"]}
    professional = {"reference": refs["practitioner"]}
    location = concept(FHIR + "/CodeSystem/localizacao-anatomica", "maleolo-medial-esquerdo")
    add("patient", {"resourceType": "Patient", "identifier": [{
        "system": "urn:healplus:synthetic:patient", "value": "synthetic-001",
    }]}, "HealPlusPaciente")
    add("practitioner", {"resourceType": "Practitioner", "identifier": [{
        "system": "urn:healplus:synthetic:practitioner", "value": "synthetic-professional-001",
    }]}, "HealPlusProfissional")
    add("encounter", {
        "resourceType": "Encounter", "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
        "subject": patient, "period": {"start": now},
        "participant": [{"individual": professional}],
    }, "HealPlusAtendimentoAvaliacaoFerida")
    add("wound", {
        "resourceType": "Condition",
        "clinicalStatus": concept("http://terminology.hl7.org/CodeSystem/condition-clinical", "active"),
        "verificationStatus": concept("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed"),
        "category": [concept(FHIR + "/CodeSystem/categoria-condicao", "ferida")],
        "code": concept(FHIR + "/CodeSystem/tipo-ferida", "ulcera-venosa"),
        "subject": patient, "encounter": encounter, "recordedDate": now,
        "recorder": professional, "bodySite": [location],
    }, "HealPlusFerida")
    add("capture", {
        "resourceType": "Device", "status": "active", "manufacturer": "HealPlus Exemplo",
        "modelNumber": "gerador-sintetico", "deviceName": [{
            "name": "Gerador de imagem sintética", "type": "model-name",
        }],
        "version": [{"type": {"text": "aplicativo"}, "value": "0.2.0"}],
    })

    image = Image.new("RGB", (640, 640), (135, 135, 135))
    draw = ImageDraw.Draw(image)
    for y in range(0, 640, 32):
        for x in range(0, 640, 32):
            draw.rectangle((x, y, x + 31, y + 31), fill=(90, 90, 90) if (x + y) // 32 % 2 else (180, 180, 180))
    draw.text((15, 15), "HEALPLUS SYNTHETIC TEST IMAGE", fill=(20, 20, 20))
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="JPEG", quality=95,
               icc_profile=ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes())
    jpeg = image_bytes.getvalue()
    add("media", {
        "resourceType": "Media", "status": "completed",
        "type": concept("http://terminology.hl7.org/CodeSystem/media-type", "image"),
        "subject": patient, "encounter": encounter, "createdDateTime": now,
        "operator": professional, "bodySite": location, "device": {"reference": refs["capture"]},
        "width": 640, "height": 640,
        "content": {"contentType": "image/jpeg", "data": base64.b64encode(jpeg).decode(),
                    "size": len(jpeg), "hash": base64.b64encode(hashlib.sha1(jpeg).digest()).decode()},
    }, "HealPlusImagemClinica")

    observations = {
        "dimensoes-ferida": "HealPlusDimensoesFerida", "tecido-ferida": "HealPlusTecidoFerida",
        "sinais-infeccao-ferida": "HealPlusSinaisInfeccaoFerida", "exsudato-ferida": "HealPlusExsudatoFerida",
        "bordas-ferida": "HealPlusBordasFerida", "pele-perilesional": "HealPlusPelePerilesional",
        "qualidade-captura-imagem": "HealPlusQualidadeCapturaImagem",
    }
    for code, profile in observations.items():
        refs[code] = f"urn:uuid:{uuid4()}"
        add(code, {
            "resourceType": "Observation", "status": "final",
            "category": [concept("http://terminology.hl7.org/CodeSystem/observation-category", "exam")],
            "code": concept(FHIR + "/CodeSystem/avaliacao-ferida", code),
            "subject": patient, "encounter": encounter, "focus": [{"reference": refs["wound"]}],
            "effectiveDateTime": now, "issued": now, "performer": [professional],
            "bodySite": location, "derivedFrom": [{"reference": refs["media"]}],
            "note": [{"text": "Registro sintético para teste do contrato; sem observação clínica real."}],
        }, profile)
    add("provenance", {
        "resourceType": "Provenance", "target": [{"reference": entry["fullUrl"]} for entry in entries],
        "recorded": now, "activity": concept(FHIR + "/CodeSystem/atividade-proveniencia", "captura-dados-clinicos"),
        "agent": [{"type": concept("http://terminology.hl7.org/CodeSystem/provenance-participant-type", "author"),
                   "who": professional}],
    }, "HealPlusProvenienciaAvaliacao")
    return {
        "resourceType": "Parameters", "parameter": [{"name": "bundle", "resource": {
            "resourceType": "Bundle", "id": "assessment-local", "type": "collection",
            "identifier": {"system": "urn:healplus:synthetic:assessment", "value": identifier or str(uuid4())},
            "meta": {"profile": [f"{FHIR}/StructureDefinition/HealPlusAvaliacaoFerida|{VERSION}"],
                     "source": "urn:healplus:synthetic-generator:0.2.0", "security": test_label},
            "timestamp": now, "entry": entries,
        }}],
    }


def main() -> None:
    """Write a JSON request to disk for curl or another HTTP client."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("synthetic-payload.json"))
    parser.add_argument("--identifier", help="Business identifier; reuse the generated file for retries.")
    args = parser.parse_args()
    args.output.write_text(json.dumps(build_payload(args.identifier), ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
