import os
import streamlit as st
import requests
import io
import pandas as pd
import re

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="WA Blast Dashboard", layout="centered")

st.title("WA Blast Dashboard")

# No login required for Streamlit dashboard — public access

st.sidebar.markdown("---")
st.sidebar.subheader("WAHA QR")

def fetch_status():
    try:
        response = requests.get(f"{BACKEND_URL}/waha/status", timeout=20)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {
            "status": "error",
            "raw_status": "unknown",
            "connected": False,
            "message": str(exc),
        }

def fetch_qr(restart: bool = False):
    try:
        response = requests.get(
            f"{BACKEND_URL}/waha/qr",
            params={"restart": "true" if restart else "false"},
            timeout=45,
        )
    except Exception as exc:
        return None, f"Gagal menghubungi backend proxy: {exc}"

    if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
        return response.content, None

    try:
        payload = response.json()
        message = payload.get("message", response.text)
    except Exception:
        message = response.text

    return None, message


session_status = fetch_status()
raw_status = str(session_status.get("raw_status", "unknown")).lower()
display_status = str(session_status.get("status", "unknown")).lower()
is_connected = bool(session_status.get("connected"))
is_session_started = raw_status in {"starting", "scan_qr_code", "working", "connected"}

show_start_button = not is_session_started
show_logout_button = is_session_started
show_refresh_qr_button = not is_connected

start_session_btn = False
logout_session_btn = False
refresh_qr = False

if show_start_button:
    start_session_btn = st.sidebar.button("Start Session", key="start_session")

if show_logout_button:
    logout_session_btn = st.sidebar.button("Logout Session", key="logout_session")

if show_refresh_qr_button:
    refresh_qr = st.sidebar.button("Refresh QR", key="refresh_qr_1")

if start_session_btn:
    try:
        res = requests.post(f"{BACKEND_URL}/api/sessions/start", timeout=30)
        if res.status_code in (200, 201):
            st.sidebar.success("Permintaan start session terkirim.")
            st.rerun()
        else:
            try:
                payload = res.json()
            except Exception:
                payload = res.text
            st.sidebar.error(f"Gagal start session: {res.status_code} {payload}")
    except Exception as exc:
        st.sidebar.error(f"Error start session: {exc}")

if logout_session_btn:
    try:
        res = requests.post(f"{BACKEND_URL}/api/sessions/logout", timeout=30)
        if res.status_code in (200, 201):
            st.sidebar.success("Session berhasil logout.")
            st.rerun()
        else:
            try:
                payload = res.json()
            except Exception:
                payload = res.text
            st.sidebar.error(f"Gagal logout session: {res.status_code} {payload}")
    except Exception as exc:
        st.sidebar.error(f"Error logout session: {exc}")

if is_connected:
    st.sidebar.success(f"Status: {display_status}")
    if session_status.get("me"):
        me = session_status["me"]
        st.sidebar.caption(f"Terhubung sebagai {me.get('pushName') or me.get('id')}")
else:
    st.sidebar.warning(f"Status: {display_status} ({raw_status})")

qr_bytes, qr_error = (None, None)
if not is_connected:
    qr_bytes, qr_error = fetch_qr(restart=refresh_qr)

if qr_bytes and not is_connected:
    st.sidebar.image(io.BytesIO(qr_bytes))
elif not is_connected:
    st.sidebar.info(qr_error or "QR tidak ditemukan. Pastikan WAHA_PRINT_QR aktif dan WAHA berjalan.")


def read_uploaded_kreators(file):
    import csv
    from io import StringIO

    ext = file.name.lower().split(".")[-1]
    if ext == "csv":
        encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
        df = None

        file_bytes = None
        try:
            # Read raw bytes once
            file.seek(0)
            file_bytes = file.read()
        except Exception:
            raise ValueError("Gagal membaca file upload.")

        for encoding in encodings:
            try:
                text = file_bytes.decode(encoding)
            except Exception:
                continue

            # Try to detect dialect (delimiter, quotechar)
            try:
                sample = text[:8192]
                sniffer = csv.Sniffer()
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
                quotechar = dialect.quotechar
            except Exception:
                delimiter = ","
                quotechar = '"'

            try:
                sio = StringIO(text)
                df = pd.read_csv(
                    sio,
                    sep=delimiter,
                    quotechar=quotechar,
                    engine="python",
                    on_bad_lines="skip",
                )
                if df.shape[0] > 0:
                    break
            except Exception:
                df = None
                continue

        if df is None or df.shape[0] == 0:
            raise ValueError("Tidak bisa membaca file CSV. Cek format, encoding, atau kutipan di file.")
    else:
        # For Excel, let pandas handle different engines
        file.seek(0)
        df = pd.read_excel(file)

    df = df.fillna("")
    return df.to_dict(orient="records"), list(df.columns), len(df.index)


def extract_placeholders(template: str) -> list[str]:
    placeholders: list[str] = []
    for match in re.finditer(r"{{\s*([^}]+?)\s*}}", str(template or "")):
        name = match.group(1)
        if name:
            placeholders.append(name)
    seen = set()
    ordered: list[str] = []
    for item in placeholders:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def render_template(template: str, context: dict) -> str:
    def replacer(match):
        key = match.group(1).strip()
        value = context.get(key, "")
        return "" if value is None else str(value)

    return re.sub(r"{{\s*([^}]+?)\s*}}", replacer, str(template or ""))



st.subheader("Dynamic Blast")
st.caption("Upload CSV/XLSX → pilih kolom nomor WhatsApp → tulis template dengan placeholder {{HEADER_NAME}} → tambah additional fields jika perlu. Placeholder case-sensitive dan harus sama persis dengan header CSV.")

uploaded_file = st.file_uploader(
    "Upload data (CSV/XLSX)",
    type=["csv", "xlsx", "xls"],
    key="dynamic_upload",
)

rows: list[dict] = []
headers: list[str] = []
total_rows = 0

if uploaded_file is not None:
    try:
        rows, headers, total_rows = read_uploaded_kreators(uploaded_file)
        if total_rows <= 0:
            st.error("File terbaca tapi tidak ada baris data.")
        else:
            st.info(f"File terbaca: {total_rows} baris")
            st.write("Headers:")
            st.write(headers)
    except Exception as e:
        st.error(f"Gagal membaca file: {e}")


if "dynamic_additional_fields" not in st.session_state:
    st.session_state.dynamic_additional_fields = []


st.subheader("Recipient Selector")
if headers:
    if "NOMOR" not in headers:
        recipient_column = ""
        st.error("Header kolom nomor WhatsApp wajib bernama: NOMOR")
    else:
        recipient_column = "NOMOR"
        st.text_input("Kolom nomor WhatsApp (recipient)", value="NOMOR", disabled=True)
else:
    recipient_column = ""
    st.info("Upload file dulu untuk memilih kolom recipient.")


st.subheader("Template")
template = st.text_area(
    "Template Pesan",
    height=220,
    key="dynamic_template",
    placeholder="Contoh: Hi {{username}}\nProduk: {{product}}\nCampaign: {{campaign}}",
)


st.subheader("Additional Fields")
st.caption("Ini field global (dipakai untuk semua baris). Contoh: campaign, product, link_group, dll.")

remove_index = None
for i, item in enumerate(st.session_state.dynamic_additional_fields):
    col1, col2, col3 = st.columns([3, 4, 1])
    name = col1.text_input("Nama field", value=item.get("name", ""), key=f"dyn_field_name_{i}")
    value = col2.text_input("Value", value=item.get("value", ""), key=f"dyn_field_value_{i}")
    if col3.button("Hapus", key=f"dyn_field_remove_{i}"):
        remove_index = i
    st.session_state.dynamic_additional_fields[i] = {"name": name, "value": value}

if remove_index is not None:
    st.session_state.dynamic_additional_fields.pop(remove_index)
    st.rerun()

if st.button("Tambah Field", key="dyn_add_field"):
    st.session_state.dynamic_additional_fields.append({"name": "", "value": ""})
    st.rerun()

additional_fields: dict[str, str] = {}
empty_names = 0
for item in st.session_state.dynamic_additional_fields:
    name = str(item.get("name", "")).strip()
    value = "" if item.get("value") is None else str(item.get("value"))
    if not name and value.strip():
        empty_names += 1
        continue
    if name:
        additional_fields[name] = value

if empty_names:
    st.warning("Ada additional field yang valuenya terisi tapi namanya kosong.")


st.subheader("Validation & Preview")
placeholders = extract_placeholders(template)

available_keys = list(headers) + list(additional_fields.keys())
missing_placeholders = [p for p in placeholders if p not in set(available_keys)]

if placeholders:
    st.write("Placeholders terdeteksi:")
    st.write(placeholders)
else:
    st.info("Belum ada placeholder {{...}} di template.")

if missing_placeholders:
    st.error(f"Placeholder tidak ditemukan di headers/additional fields: {missing_placeholders}")
    st.caption("Pastikan nama placeholder sama persis dengan header CSV (case-sensitive), atau tambah via Additional Fields.")

preview_text = ""
if rows and template.strip():
    context = {}
    context.update(rows[0])
    context.update(additional_fields)
    preview_text = render_template(template, context)

st.text_area(
    "Preview (baris pertama)",
    value=preview_text,
    height=180,
    disabled=True,
    key="dyn_preview",
)


st.subheader("Pengaturan Delay")
pre_typing_delay_min = st.number_input("Delay sebelum typing min (detik)", value=3, key="dyn_pre_typing_min")
pre_typing_delay_max = st.number_input("Delay sebelum typing max (detik)", value=11, key="dyn_pre_typing_max")
typing_duration_min = st.number_input("Durasi typing min (detik)", value=10, key="dyn_typing_min")
typing_duration_max = st.number_input("Durasi typing max (detik)", value=39, key="dyn_typing_max")
pre_send_delay_min = st.number_input("Delay sebelum kirim min (detik)", value=1, key="dyn_pre_send_min")
pre_send_delay_max = st.number_input("Delay sebelum kirim max (detik)", value=4, key="dyn_pre_send_max")
batch_size = st.number_input("Istirahat setiap berapa pesan?", value=10, key="dyn_batch_size")
batch_rest = st.number_input("Durasi istirahat batch (detik)", value=300, key="dyn_batch_rest")


can_start = True
if uploaded_file is None:
    can_start = False
if not headers:
    can_start = False
if not template.strip():
    can_start = False
if not recipient_column:
    can_start = False
if missing_placeholders:
    can_start = False

start = st.button("Mulai Dynamic Blast", key="dyn_start", disabled=not can_start)

if start:
    try:
        payload = {
            "rows": rows,
            "template": template,
            "recipient_column": recipient_column,
            "additional_fields": additional_fields,
            "pre_typing_delay_min": int(pre_typing_delay_min),
            "pre_typing_delay_max": int(pre_typing_delay_max),
            "typing_duration_min": int(typing_duration_min),
            "typing_duration_max": int(typing_duration_max),
            "pre_send_delay_min": int(pre_send_delay_min),
            "pre_send_delay_max": int(pre_send_delay_max),
            "batch_size": int(batch_size),
            "batch_rest_seconds": int(batch_rest),
        }

        res = requests.post(
            f"{BACKEND_URL}/send-blast-dynamic",
            json=payload,
            timeout=60,
        )

        if res.status_code == 200:
            payload_out = res.json()
            if payload_out.get("status") == "error":
                st.error(payload_out.get("message", "Gagal mulai dynamic blast."))
                st.json(payload_out)
            else:
                st.success(f"Dynamic blast dimulai untuk {total_rows} baris. Cek log backend untuk progress.")
                st.json(payload_out)
        else:
            st.error("Gagal mulai dynamic blast.")
            try:
                st.json(res.json())
            except Exception:
                st.text(res.text)
    except Exception as e:
        st.error(f"Terjadi error: {e}")
