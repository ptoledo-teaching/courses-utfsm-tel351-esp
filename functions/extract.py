"""Lectura Asistida: complete únicamente process_request y seleccione Deploy."""

import json
import logging
import os
import re
import traceback
from urllib.parse import unquote_plus

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
s3 = boto3.client("s3")
DATA_BUCKET = os.environ["DATA_BUCKET"]
REQUEST_ID = re.compile(r"[0-9a-f]{32}")
ERROR_MESSAGES = {
    "NO_TEXT": "No se reconoció texto en la imagen.",
    "TEXT_TOO_LONG": "El texto supera el límite permitido para esta etapa.",
    "LANGUAGE_NOT_DETECTED": "No fue posible determinar el idioma con confianza suficiente.",
    "PROCESSING_ERROR": "No fue posible completar el procesamiento. Revise los logs de la función.",
}


class ProcessingError(Exception):
    """Error esperado que puede mostrarse en el sitio sin detalles internos."""

    def __init__(self, code):
        if code not in ERROR_MESSAGES:
            raise ValueError("Código de error desconocido")
        self.code = code
        super().__init__(code)


def save_json(bucket_name, key, document):
    """Guarda un documento JSON en UTF-8, conservando los caracteres del texto."""
    s3.put_object(
        Bucket=bucket_name,
        Key=key,
        Body=json.dumps(document, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def load_json(bucket_name, key, request_id):
    response = s3.get_object(Bucket=bucket_name, Key=key)
    body = response["Body"]
    try:
        raw = body.read(65537)
    finally:
        body.close()
    if len(raw) > 65536:
        raise ValueError("El documento de entrada supera el tamaño admitido")
    document = json.loads(raw.decode("utf-8"))
    if not isinstance(document, dict) or document.get("requestId") != request_id:
        raise ValueError("El documento no corresponde a la solicitud")
    return document


def require_text(document, field, limit):
    text = document.get(field)
    if not isinstance(text, str) or not text.strip():
        raise ValueError("El documento no contiene el texto requerido")
    if len(text) > limit:
        raise ProcessingError("TEXT_TOO_LONG")
    return text


def request_from_record(record):
    """Ignora eventos ajenos a esta etapa; nunca procesa buckets arbitrarios."""
    if not isinstance(record, dict) or record.get("eventSource") != "aws:s3":
        return None
    if not str(record.get("eventName", "")).startswith("ObjectCreated:"):
        return None
    details = record.get("s3", {})
    if not isinstance(details, dict):
        return None
    bucket = details.get("bucket", {})
    object_data = details.get("object", {})
    if not isinstance(bucket, dict) or not isinstance(object_data, dict):
        return None
    bucket_name = bucket.get("name")
    encoded_key = object_data.get("key", "")
    if not isinstance(encoded_key, str):
        return None
    key = unquote_plus(encoded_key)
    if bucket_name != DATA_BUCKET or not key.startswith(INPUT_PREFIX) or not key.endswith(INPUT_SUFFIX):
        return None
    request_id = key[len(INPUT_PREFIX):-len(INPUT_SUFFIX)]
    if not REQUEST_ID.fullmatch(request_id):
        return None
    return request_id, bucket_name, key


def error_location(error):
    # Solo archivos, líneas y nombres de función; no valores ni código fuente.
    return " > ".join(
        f"{os.path.basename(frame.filename)}:{frame.lineno}:{frame.name}"
        for frame in traceback.extract_tb(error.__traceback__)
    )


def lambda_handler(event, context):
    if not isinstance(event, dict):
        raise ValueError("La función espera una notificación S3")
    if event.get("Event") == "s3:TestEvent":
        return {"processed": 0, "failed": 0, "ignored": 0}
    records = event.get("Records")
    if not isinstance(records, list):
        raise ValueError("La función espera una notificación S3 con Records")
    counts = {"processed": 0, "failed": 0, "ignored": 0}
    unsaved_errors = 0
    for record in records:
        request = request_from_record(record)
        if request is None:
            counts["ignored"] += 1
            continue
        request_id, bucket_name, key = request
        logger.info("requestId=%s stage=%s status=started", request_id, STAGE)
        try:
            run_request(request_id, bucket_name, key)
            counts["processed"] += 1
            logger.info("requestId=%s stage=%s status=completed", request_id, STAGE)
            continue
        except ProcessingError as error:
            code = error.code
            error_type = type(error).__name__
            service_code = "-"
            location = "-"
        except Exception as error:
            service_code = error.response.get("Error", {}).get("Code", "-") if isinstance(error, ClientError) else "-"
            code = "LANGUAGE_NOT_DETECTED" if STAGE == "translate" and service_code == "DetectedLanguageLowConfidenceException" else "PROCESSING_ERROR"
            error_type = type(error).__name__
            location = error_location(error)
        counts["failed"] += 1
        logger.error("requestId=%s stage=%s error=%s errorType=%s serviceCode=%s location=%s", request_id, STAGE, code, error_type, service_code, location)
        try:
            save_json(bucket_name, f"errors/{request_id}.json", {
                "requestId": request_id,
                "stage": STAGE,
                "code": code,
                "message": ERROR_MESSAGES[code],
            })
        except Exception as error:
            unsaved_errors += 1
            logger.error("requestId=%s stage=%s status=error_not_saved errorType=%s location=%s", request_id, STAGE, type(error).__name__, error_location(error))
    if unsaved_errors:
        raise RuntimeError("No fue posible registrar uno o más errores; revise los permisos y CloudWatch Logs")
    return counts


STAGE = "extract"
INPUT_PREFIX = "uploads/"
INPUT_SUFFIX = ".jpg"
rekognition = boto3.client("rekognition")


def process_request(request_id, bucket_name, image_key):
    # TODO: invoque detect_text con Image.S3Object, usando bucket_name e image_key.
    # Seleccione las detecciones LINE y una sus textos con saltos de línea, respetando el orden recibido. No incorpore también las detecciones WORD.
    # Si el texto queda vacío, utilice raise ProcessingError("NO_TEXT").
    # Si supera 1000 caracteres, utilice raise ProcessingError("TEXT_TOO_LONG").
    # Construya el documento con requestId y sourceText; utilice save_json para guardarlo en extracted/<requestId>.json, dentro de bucket_name.
    raise NotImplementedError("Complete la extracción de texto y el almacenamiento del resultado")


def run_request(request_id, bucket_name, key):
    process_request(request_id, bucket_name, key)
