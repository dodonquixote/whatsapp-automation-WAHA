import os
import time
import random
import math
import re
import requests
from typing import Any, Dict, List
from fastapi import FastAPI, BackgroundTasks, Response, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

app = FastAPI()

# Serve frontend static files under /static and expose index at /
try:
    # mount static assets at /static so API routes are not shadowed
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

    @app.get("/", include_in_schema=False)
    def serve_index():
        index_path = os.path.join("frontend", "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path, media_type="text/html")
        return {"status": "backend running"}
except Exception:
    # If frontend folder missing in the runtime image, ignore silently
    pass

WAHA_URL = os.getenv("WAHA_URL", "http://localhost:3000")
WAHA_SESSION = os.getenv("WAHA_SESSION", "default")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "")


def _waha_headers():
    headers = {}
    if WAHA_API_KEY:
        headers["x-api-key"] = WAHA_API_KEY
        headers["Authorization"] = f"Bearer {WAHA_API_KEY}"
    return headers


def fetch_waha_qr(restart: bool = False, attempts: int = 20, retry_delay_seconds: float = 1.5):
    headers = _waha_headers()
    session_url = f"{WAHA_URL}/api/{WAHA_SESSION}/auth/qr"

    if restart:
        requests.post(
            f"{WAHA_URL}/api/sessions/{WAHA_SESSION}/restart",
            headers=headers,
            timeout=30,
        )

    last_error = None
    for _ in range(max(1, attempts)):
        response = requests.get(session_url, headers=headers, timeout=30)
        content_type = response.headers.get("content-type", "")

        if response.status_code == 200 and content_type.startswith("image/"):
            return response.content

        parsed_payload = None
        try:
            parsed_payload = response.json()
        except Exception:
            parsed_payload = None

        last_error = {
            "status_code": response.status_code,
            "response": parsed_payload if parsed_payload is not None else response.text,
        }

        # WAHA may return 422 while the session is still starting and QR is not ready yet.
        if response.status_code == 422 and isinstance(parsed_payload, dict):
            status = str(parsed_payload.get("status", "")).upper()
            expected = parsed_payload.get("expected") or []
            if status == "STARTING" and "SCAN_QR_CODE" in expected:
                time.sleep(retry_delay_seconds)
                continue

        if response.status_code not in (404, 422):
            break

        time.sleep(retry_delay_seconds)

    if isinstance(last_error, dict):
        error_body = last_error.get("response")
        if isinstance(error_body, dict):
            status = str(error_body.get("status", "")).upper()
            expected = error_body.get("expected") or []
            if status == "STARTING" and "SCAN_QR_CODE" in expected:
                raise RuntimeError("Session masih STARTING. Tunggu beberapa detik lalu refresh QR.")

    raise RuntimeError(f"QR tidak tersedia: {last_error}")


def fetch_waha_session_status():
    response = requests.get(
        f"{WAHA_URL}/api/sessions/{WAHA_SESSION}",
        headers=_waha_headers(),
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    raw_status = str(payload.get("status", "")).upper()

    if raw_status in {"WORKING", "CONNECTED"}:
        display_status = "connected"
        connected = True
    elif raw_status in {"STARTING", "SCAN_QR_CODE"}:
        display_status = "connecting"
        connected = False
    elif raw_status:
        display_status = raw_status.lower()
        connected = False
    else:
        display_status = "unknown"
        connected = False

    return {
        "session": payload.get("name", WAHA_SESSION),
        "status": display_status,
        "raw_status": raw_status or "unknown",
        "connected": connected,
        "me": payload.get("me"),
        "engine": payload.get("engine"),
    }


class BlastRequest(BaseModel):
    numbers: List[str]
    message: str
    min_delay: int = 20
    max_delay: int = 45
    batch_size: int = 20
    batch_rest_seconds: int = 300


class CsvBlastRequest(BaseModel):
    kreators: List[Dict[str, Any]]
    templates: List[str]
    campaign: str = ""
    produk: str = ""
    komisi: str = ""
    sow: str = ""
    link_affiliate: str = ""
    link_group: str = ""
    pre_typing_delay_min: int = 3
    pre_typing_delay_max: int = 11
    typing_duration_min: int = 10
    typing_duration_max: int = 39
    pre_send_delay_min: int = 1
    pre_send_delay_max: int = 4
    batch_size: int = 10
    batch_rest_seconds: int = 300
    skip_sent: bool = True


class OutreachBlastRequest(BaseModel):
    kreators: List[Dict[str, Any]]
    message: str
    pre_typing_delay_min: int = 3
    pre_typing_delay_max: int = 11
    typing_duration_min: int = 10
    typing_duration_max: int = 39
    pre_send_delay_min: int = 1
    pre_send_delay_max: int = 4
    batch_size: int = 10
    batch_rest_seconds: int = 300


class DynamicBlastRequest(BaseModel):
    rows: List[Dict[str, Any]]
    template: str
    recipient_column: str
    additional_fields: Dict[str, Any] = Field(default_factory=dict)
    pre_typing_delay_min: int = 3
    pre_typing_delay_max: int = 11
    typing_duration_min: int = 10
    typing_duration_max: int = 39
    pre_send_delay_min: int = 1
    pre_send_delay_max: int = 4
    batch_size: int = 10
    batch_rest_seconds: int = 300


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    return str(value).strip()


def _normalize_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", _safe_text(key).lower()).strip("_")


def _pick_value(normalized_row: Dict[str, Any], aliases: List[str]) -> str:
    for alias in aliases:
        if alias in normalized_row:
            value = _safe_text(normalized_row[alias])
            if value:
                return value
    return ""


def _map_kreator_row(row: Dict[str, Any]) -> Dict[str, str]:
    normalized_row = {_normalize_key(k): v for k, v in row.items()}

    username = _pick_value(normalized_row, ["username", "userame", "user_name"])
    no = _pick_value(normalized_row, ["no", "nomor", "no_hp", "nomor_hp", "phone"])
    whatsapp = _pick_value(normalized_row, ["whatsapp", "wa", "wa_number", "whatsapp_number"])
    nama_penerima = _pick_value(normalized_row, ["nama_penerima", "nama", "name"])
    alamat = _pick_value(normalized_row, ["alamat", "address"])
    status = _pick_value(normalized_row, ["status"])

    selected_number = whatsapp or no
    chat_id = ""
    if selected_number:
        normalized_number = normalize_number(selected_number)
        chat_id = f"{normalized_number}@c.us"

    return {
        "username": username,
        "no": no,
        "whatsapp": whatsapp,
        "nama_penerima": nama_penerima,
        "alamat": alamat,
        "status": status,
        "chatId": chat_id,
    }


def _render_template(template: str, data: Dict[str, str]) -> str:
    def replacer(match):
        key = match.group(1)
        return data.get(key, "")

    return re.sub(r"{{(\w+)}}", replacer, template)


def extract_placeholders(template: str) -> List[str]:
    """Extract placeholders in the form {{VARIABLE}} (case-sensitive)."""
    placeholders: List[str] = []
    for match in re.finditer(r"{{\s*([^}]+?)\s*}}", _safe_text(template)):
        name = match.group(1)
        if name:
            placeholders.append(name)
    # Preserve order, unique
    seen = set()
    ordered: List[str] = []
    for item in placeholders:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def merge_context(csv_row: Dict[str, Any], additional_fields: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {}
    context.update(csv_row or {})
    context.update(additional_fields or {})
    return context


def validate_placeholders(placeholders: List[str], context_keys: List[str]) -> List[str]:
    key_set = set(context_keys)
    return [p for p in placeholders if p not in key_set]


def render_template_dynamic(template: str, context: Dict[str, Any]) -> str:
    def replacer(match):
        key = match.group(1).strip()
        value = context.get(key, "")
        return _safe_text(value)

    return re.sub(r"{{\s*([^}]+?)\s*}}", replacer, _safe_text(template))


def get_csv_headers(rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []
    # Prefer first row's key order; add any missing keys from later rows
    headers: List[str] = list(rows[0].keys())
    seen = set(headers)
    for row in rows[1:]:
        for k in row.keys():
            if k not in seen:
                headers.append(k)
                seen.add(k)
    return headers


def normalize_number(number: str) -> str:
    number = re.sub(r"\D+", "", number.strip())
    if number.startswith("0"):
        number = "62" + number[1:]
    elif not number.startswith("62") and number:
        number = "62" + number
    return number


def send_message(number: str, message: str):
    phone = normalize_number(number)
    chat_id = f"{phone}@c.us"

    return send_chat_message(chat_id, message, phone)


def send_chat_message(chat_id: str, message: str, phone_display: str = ""):
    phone = phone_display or chat_id.replace("@c.us", "")

    payload = {
        "chatId": chat_id,
        "text": message,
        "session": WAHA_SESSION
    }

    response = requests.post(
        f"{WAHA_URL}/api/sendText",
        json=payload,
        headers=_waha_headers(),
        timeout=30
    )

    return {
        "number": phone,
        "status_code": response.status_code,
        "response": response.text
    }


def _is_success_status(status_code: int) -> bool:
    return 200 <= int(status_code) < 300


def process_blast(data: BlastRequest):
    results = []

    for index, number in enumerate(data.numbers, start=1):
        try:
            result = send_message(number, data.message)
            results.append(result)
            print(f"[SENT] {number} => {result['status_code']}")

        except Exception as e:
            print(f"[ERROR] {number} => {str(e)}")

        if index % data.batch_size == 0:
            print(f"[BATCH REST] Sleep {data.batch_rest_seconds} seconds")
            time.sleep(data.batch_rest_seconds)
        else:
            delay = random.randint(data.min_delay, data.max_delay)
            print(f"[SMART DELAY] Sleep {delay} seconds")
            time.sleep(delay)


def process_csv_blast(data: CsvBlastRequest):
    templates = [t.strip() for t in data.templates if _safe_text(t)]
    if not templates:
        print("[ERROR] Tidak ada template valid")
        return

    sent_count = 0

    for index, raw_row in enumerate(data.kreators, start=1):
        mapped = _map_kreator_row(raw_row)

        if data.skip_sent and mapped["status"].lower() == "sent":
            print(f"[SKIP] baris={index} alasan=status_sent")
            continue

        if not mapped["chatId"]:
            print(f"[SKIP] baris={index} alasan=nomor_kosong")
            continue

        template_text = random.choice(templates)
        template_data = {
            "username": mapped["username"],
            "campaign": _safe_text(data.campaign),
            "tes": _safe_text(data.campaign),
            "product": _safe_text(data.produk),
            "komisi": _safe_text(data.komisi),
            "sow": _safe_text(data.sow),
            "link_affiliate": _safe_text(data.link_affiliate),
            "namapenerima": mapped["nama_penerima"],
            "no": mapped["no"] or mapped["whatsapp"],
            "kontak": mapped["no"] or mapped["whatsapp"],
            "alamat": mapped["alamat"],
            "nama": mapped["nama_penerima"],
            "link_grup": _safe_text(data.link_group),
            "link_group": _safe_text(data.link_group),
        }
        rendered_message = _render_template(template_text, template_data)

        pre_typing_delay = random.randint(data.pre_typing_delay_min, data.pre_typing_delay_max)
        print(f"[WAIT BEFORE TYPING] {pre_typing_delay}s | {mapped['chatId']}")
        time.sleep(pre_typing_delay)

        typing_delay = random.randint(data.typing_duration_min, data.typing_duration_max)
        print(f"[WAIT TYPING] {typing_delay}s | {mapped['chatId']}")
        time.sleep(typing_delay)

        pre_send_delay = random.randint(data.pre_send_delay_min, data.pre_send_delay_max)
        print(f"[WAIT BEFORE SEND] {pre_send_delay}s | {mapped['chatId']}")
        time.sleep(pre_send_delay)

        try:
            result = send_chat_message(mapped["chatId"], rendered_message)
            sent_count += 1
            print(f"[SENT] {mapped['chatId']} => {result['status_code']}")
        except Exception as e:
            print(f"[ERROR] {mapped['chatId']} => {str(e)}")

        if data.batch_size > 0 and sent_count > 0 and sent_count % data.batch_size == 0:
            print(f"[BATCH REST] Sleep {data.batch_rest_seconds} seconds")
            time.sleep(data.batch_rest_seconds)


def process_outreach_blast(data: OutreachBlastRequest):
    """Process outreach blast for creator recruitment."""
    sent_count = 0
    
    for index, raw_row in enumerate(data.kreators, start=1):
        # Extract key fields: username, whatsapp, contact
        username = _safe_text(raw_row.get("username", ""))
        whatsapp = _safe_text(raw_row.get("whatsapp", ""))
        contact = _safe_text(raw_row.get("contact", ""))
        
        selected_number = whatsapp or contact
        if not selected_number:
            print(f"[SKIP] baris={index} alasan=nomor_kosong")
            continue
        
        normalized_number = normalize_number(selected_number)
        chat_id = f"{normalized_number}@c.us"
        
        # Render template with username
        template_data = {
            "username": username,
        }
        rendered_message = _render_template(data.message, template_data)
        
        pre_typing_delay = random.randint(data.pre_typing_delay_min, data.pre_typing_delay_max)
        print(f"[WAIT BEFORE TYPING] {pre_typing_delay}s | {chat_id}")
        time.sleep(pre_typing_delay)
        
        typing_delay = random.randint(data.typing_duration_min, data.typing_duration_max)
        print(f"[WAIT TYPING] {typing_delay}s | {chat_id}")
        time.sleep(typing_delay)
        
        pre_send_delay = random.randint(data.pre_send_delay_min, data.pre_send_delay_max)
        print(f"[WAIT BEFORE SEND] {pre_send_delay}s | {chat_id}")
        time.sleep(pre_send_delay)
        
        try:
            result = send_chat_message(chat_id, rendered_message)
            sent_count += 1
            print(f"[SENT] {chat_id} => {result['status_code']}")
        except Exception as e:
            print(f"[ERROR] {chat_id} => {str(e)}")
        
        if data.batch_size > 0 and sent_count > 0 and sent_count % data.batch_size == 0:
            print(f"[BATCH REST] Sleep {data.batch_rest_seconds} seconds")
            time.sleep(data.batch_rest_seconds)


def process_dynamic_blast(data: DynamicBlastRequest):
    template = _safe_text(data.template)
    if not template:
        print("[ERROR] Template kosong")
        return {
            "status": "error",
            "message": "Template kosong",
            "total_rows": 0,
            "recipient_column": _safe_text(data.recipient_column),
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }

    rows = data.rows or []
    if not rows:
        print("[ERROR] Tidak ada rows")
        return {
            "status": "error",
            "message": "Tidak ada rows",
            "total_rows": 0,
            "recipient_column": _safe_text(data.recipient_column),
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }

    recipient_column = _safe_text(data.recipient_column)
    if not recipient_column:
        print("[ERROR] recipient_column kosong")
        return {
            "status": "error",
            "message": "recipient_column kosong",
            "total_rows": len(rows),
            "recipient_column": recipient_column,
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }

    placeholders = extract_placeholders(template)
    headers = get_csv_headers(rows)
    context_keys = headers + list((data.additional_fields or {}).keys())
    missing = validate_placeholders(placeholders, context_keys)
    if missing:
        print(f"[ERROR] Missing placeholders: {missing}")
        return {
            "status": "error",
            "message": "Missing placeholders",
            "missing_placeholders": missing,
            "available_keys": context_keys,
            "total_rows": len(rows),
            "recipient_column": recipient_column,
            "sent_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
        }

    sent_count = 0
    failed_count = 0
    skipped_count = 0
    failed_items: List[Dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        selected_number = _safe_text(row.get(recipient_column))
        if not selected_number:
            print(f"[SKIP] baris={index} alasan=recipient_kosong kolom={recipient_column}")
            skipped_count += 1
            continue

        normalized_number = normalize_number(selected_number)
        chat_id = f"{normalized_number}@c.us"

        context = merge_context(row, data.additional_fields)
        rendered_message = render_template_dynamic(template, context)

        pre_typing_delay = random.randint(data.pre_typing_delay_min, data.pre_typing_delay_max)
        print(f"[WAIT BEFORE TYPING] {pre_typing_delay}s | {chat_id}")
        time.sleep(pre_typing_delay)

        typing_delay = random.randint(data.typing_duration_min, data.typing_duration_max)
        print(f"[WAIT TYPING] {typing_delay}s | {chat_id}")
        time.sleep(typing_delay)

        pre_send_delay = random.randint(data.pre_send_delay_min, data.pre_send_delay_max)
        print(f"[WAIT BEFORE SEND] {pre_send_delay}s | {chat_id}")
        time.sleep(pre_send_delay)

        try:
            result = send_chat_message(chat_id, rendered_message)
            if _is_success_status(result.get("status_code", 0)):
                sent_count += 1
                print(f"[SENT] {chat_id} => {result['status_code']}")
            else:
                failed_count += 1
                failed_items.append({
                    "row": index,
                    "chatId": chat_id,
                    "status_code": result.get("status_code"),
                    "response": result.get("response"),
                })
                print(f"[FAILED] {chat_id} => {result['status_code']}")
        except Exception as exc:
            failed_count += 1
            failed_items.append({
                "row": index,
                "chatId": chat_id,
                "error": str(exc),
            })
            print(f"[ERROR] {chat_id} => {str(exc)}")

        if data.batch_size > 0 and sent_count > 0 and sent_count % data.batch_size == 0:
            print(f"[BATCH REST] Sleep {data.batch_rest_seconds} seconds")
            time.sleep(data.batch_rest_seconds)

    return {
        "status": "blast_completed",
        "message": "Blast selesai",
        "total_rows": len(rows),
        "recipient_column": recipient_column,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "failed_items": failed_items,
    }


@app.get("/")
def health_check():
    return {"status": "backend running"}


@app.post("/send-blast")
def send_blast(data: BlastRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_blast, data)
    return {
        "status": "blast_started",
        "total_numbers": len(data.numbers),
        "note": "Process berjalan di background. Cek log Docker untuk progress."
    }


@app.post("/send-blast-csv")
def send_blast_csv(data: CsvBlastRequest, background_tasks: BackgroundTasks):
    templates = [t.strip() for t in data.templates if _safe_text(t)]
    if not templates:
        return {"status": "error", "message": "Template wajib diisi minimal 1"}

    background_tasks.add_task(process_csv_blast, data)
    return {
        "status": "blast_started",
        "total_rows": len(data.kreators),
        "total_templates": len(templates),
        "note": "Proses CSV blast berjalan di background. Cek log untuk progress."
    }


@app.post("/send-outreach-blast")
def send_outreach_blast(data: OutreachBlastRequest, background_tasks: BackgroundTasks):
    if not data.message:
        return {"status": "error", "message": "Message wajib diisi"}

    background_tasks.add_task(process_outreach_blast, data)
    return {
        "status": "outreach_blast_started",
        "total_rows": len(data.kreators),
        "note": "Proses outreach blast berjalan di background. Cek log untuk progress."
    }


@app.post("/send-blast-dynamic")
def send_blast_dynamic(data: DynamicBlastRequest):
    if not _safe_text(data.template):
        return {"status": "error", "message": "Template wajib diisi"}
    if not data.rows:
        return {"status": "error", "message": "Rows kosong"}
    if not _safe_text(data.recipient_column):
        return {"status": "error", "message": "recipient_column wajib diisi"}

    headers = get_csv_headers(data.rows)
    selected_column = _safe_text(data.recipient_column)
    matched_column = next((header for header in headers if header.lower() == selected_column.lower()), "")
    if not matched_column:
        return {
            "status": "error",
            "message": "Kolom recipient tidak ditemukan di data",
            "available_headers": headers,
            "recipient_column": data.recipient_column,
        }

    data.recipient_column = matched_column

    placeholders = extract_placeholders(data.template)
    context_keys = headers + list((data.additional_fields or {}).keys())
    missing = validate_placeholders(placeholders, context_keys)
    if missing:
        return {
            "status": "error",
            "message": "Missing placeholders",
            "missing_placeholders": missing,
            "available_keys": context_keys,
        }

    preview_context = merge_context(data.rows[0], data.additional_fields)
    preview = render_template_dynamic(data.template, preview_context)

    summary = process_dynamic_blast(data)
    summary.update({
        "placeholders": placeholders,
        "preview": preview,
    })
    return summary


@app.post("/webhook")
def webhook(payload: dict):
    print("[WEBHOOK RECEIVED]", payload)

    event = payload.get("event")
    data = payload.get("payload", {})

    if event == "message":
        from_number = data.get("from")
        message_text = data.get("body", "")

        if from_number and message_text:
            auto_reply = "Halo, terima kasih sudah membalas. Tim kami akan segera follow up ya."

            try:
                requests.post(
                    f"{WAHA_URL}/api/sendText",
                    json={
                        "chatId": from_number,
                        "text": auto_reply,
                        "session": WAHA_SESSION
                    },
                    headers=_waha_headers(),
                    timeout=30
                )
            except Exception:
                pass

    return {"status": "received"}


@app.get("/waha/qr")
def get_waha_qr(restart: bool = Query(False)):
    try:
        # If the session is already connected, avoid requesting a new QR
        status = fetch_waha_session_status()
        if status.get("connected"):
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "message": "Session already connected; QR not required",
                    "session": WAHA_SESSION,
                    "connected": True,
                },
            )

        qr_bytes = fetch_waha_qr(restart=restart)
        return Response(content=qr_bytes, media_type="image/png")
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "session": WAHA_SESSION,
            "waha_url": WAHA_URL,
        }


@app.get("/waha/status")
def get_waha_status():
    try:
        return fetch_waha_session_status()
    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "session": WAHA_SESSION,
            "waha_url": WAHA_URL,
            "connected": False,
        }


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    favicon_path = os.path.join("frontend", "favicon.ico")
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path, media_type="image/x-icon")
    return Response(status_code=204)


@app.post("/api/sessions/{session}/start")
def start_waha_session(session: str):
    """Start a WAHA session by name. Forwards the start request to the WAHA server

    Returns 201 on success with WAHA response body, or forwards WAHA error status.
    """
    try:
        resp = requests.post(
            f"{WAHA_URL}/api/sessions/{session}/start",
            headers=_waha_headers(),
            timeout=30,
        )

        content_type = resp.headers.get("content-type", "application/json")

        if 200 <= resp.status_code < 300:
            return Response(content=resp.text, status_code=201, media_type=content_type)
        else:
            return Response(content=resp.text, status_code=resp.status_code, media_type=content_type)

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "session": session,
            "waha_url": WAHA_URL,
        }


@app.post("/api/sessions/start")
def start_default_waha_session():
    """Convenience endpoint to start the configured default session."""
    return start_waha_session(WAHA_SESSION)


@app.post("/api/sessions/{session}/logout")
def logout_waha_session(session: str):
    """Logout a WAHA session by name."""
    try:
        resp = requests.post(
            f"{WAHA_URL}/api/sessions/{session}/logout",
            headers=_waha_headers(),
            timeout=30,
        )

        content_type = resp.headers.get("content-type", "application/json")

        if 200 <= resp.status_code < 300:
            return Response(content=resp.text, status_code=200, media_type=content_type)
        else:
            return Response(content=resp.text, status_code=resp.status_code, media_type=content_type)

    except Exception as exc:
        return {
            "status": "error",
            "message": str(exc),
            "session": session,
            "waha_url": WAHA_URL,
        }


@app.post("/api/sessions/logout")
def logout_default_waha_session():
    """Convenience endpoint to logout the configured default session."""
    return logout_waha_session(WAHA_SESSION)
