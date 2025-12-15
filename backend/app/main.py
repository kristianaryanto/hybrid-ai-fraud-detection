import asyncio
import json
import os
import random
import uuid
from contextlib import asynccontextmanager

import joblib
import pandas as pd
import redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import google.generativeai as genai

# --- Konfigurasi dan Setup Awal ---
load_dotenv()

# Model dan Scaler
MODEL_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "isolation_forest.joblib")
SCALER_PATH = os.path.join(os.path.dirname(__file__), "..", "models", "scaler.joblib")
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "sample_data.csv")

ml_models = {}

# Koneksi ke Redis
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Memuat model Machine Learning...")
    try:
        ml_models["isolation_forest"] = joblib.load(MODEL_PATH)
        ml_models["scaler"] = joblib.load(SCALER_PATH)
        print("Model berhasil dimuat.")
    except FileNotFoundError:
        print("ERROR: File model tidak ditemukan. Jalankan `train_model.py` terlebih dahulu.")
    
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("WARNING: GEMINI_API_KEY tidak ditemukan. Fitur AI dinamis tidak akan berfungsi.")
        ml_models["gemini"] = None
    else:
        genai.configure(api_key=gemini_api_key)
        ml_models["gemini"] = genai.GenerativeModel('gemini-1.5-flash')
        print("Gemini API terkonfigurasi untuk penjelasan dinamis dan SAR.")

    yield
    ml_models.clear()

app = FastAPI(lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class SarRequest(BaseModel):
    transaction: dict

# --- Fungsi Helper ---

def preprocess_transaction(tx: pd.DataFrame):
    known_categories = ['CASH_OUT', 'PAYMENT', 'CASH_IN', 'TRANSFER', 'DEBIT']
    tx['type_encoded'] = pd.Categorical(tx['type'], categories=known_categories).codes
    tx['errorBalanceOrig'] = tx['newbalanceOrg'] + tx['amount'] - tx['oldbalanceOrg']
    tx['errorBalanceDest'] = tx['oldbalanceDest'] + tx['amount'] - tx['newbalanceDest']
    features = ['amount', 'oldbalanceOrg', 'newbalanceOrg', 'type_encoded', 'errorBalanceOrig', 'errorBalanceDest']
    return tx[features].fillna(0)

async def generate_ai_explanation(transaction_data: dict) -> str:
    gemini_model = ml_models.get("gemini")
    if not gemini_model:
        return "Model AI tidak tersedia."
    relevant_data = {
        "jenis_transaksi": transaction_data.get("type"),
        "jumlah": transaction_data.get("amount"),
        "saldo_awal_pengirim": transaction_data.get("oldbalanceOrg"),
        "saldo_akhir_pengirim": transaction_data.get("newbalanceOrg"),
    }
    prompt = f"""
Anda adalah seorang analis fraud keuangan yang sangat teliti.
Berdasarkan data transaksi berikut, berikan satu kalimat singkat dalam Bahasa Indonesia yang menjelaskan mengapa transaksi ini mencurigakan.
Fokus pada hubungan antar angka, bukan hanya menyebutkan angkanya.
Data Transaksi:
{json.dumps(relevant_data, indent=2)}
Penjelasan Singkat Anda (satu kalimat):
"""
    try:
        response = await gemini_model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Error saat memanggil Gemini untuk penjelasan: {e}")
        return "Gagal menghasilkan penjelasan AI."

def get_rule_based_explanation(tx: pd.DataFrame) -> str:
    explanations = []
    if tx['amount'].iloc[0] > 100000:
        explanations.append(f"Jumlah transaksi sangat besar.")
    if tx['errorBalanceOrig'].iloc[0] != 0:
        explanations.append("Saldo pengirim tidak konsisten.")
    if tx['type'].iloc[0] == 'TRANSFER' and tx['amount'].iloc[0] == tx['oldbalanceOrg'].iloc[0] and tx['oldbalanceOrg'].iloc[0] > 0:
        explanations.append("Transaksi mengosongkan seluruh saldo akun.")
    if not explanations:
        return "Kombinasi fitur tidak biasa."
    return ". ".join(explanations)

# --- Endpoint API ---

@app.get("/stream")
async def transaction_stream(request: Request):
    async def event_generator():
        print("Klien terhubung ke stream.")
        try:
            df = pd.read_csv(DATA_PATH)
            scaler = ml_models["scaler"]
            model = ml_models["isolation_forest"]
            for _, row in df.iterrows():
                if await request.is_disconnected():
                    print("Klien terputus dari stream.")
                    break
                tx_df = pd.DataFrame([row])
                tx_features = preprocess_transaction(tx_df)
                tx_scaled = scaler.transform(tx_features)
                score = model.decision_function(tx_scaled)[0]
                prediction = model.predict(tx_scaled)[0]
                is_anomaly = prediction == -1
                explanation = ""
                transaction_dict = row.to_dict()
                if is_anomaly:
                    try:
                        explanation = await generate_ai_explanation(transaction_dict)
                    except Exception as e:
                        print(f"Gagal mendapatkan penjelasan AI, menggunakan fallback: {e}")
                        explanation = get_rule_based_explanation(tx_df)
                result = {
                    "id": str(uuid.uuid4()),"type": str(transaction_dict["type"]),"amount": float(transaction_dict["amount"]),"oldbalanceOrg": float(transaction_dict["oldbalanceOrg"]),"newbalanceOrg": float(transaction_dict["newbalanceOrg"]),"nameDest": str(transaction_dict["nameDest"]),"anomaly_score": float(score),"is_anomaly": bool(is_anomaly),"explanation": explanation
                }
                if result["is_anomaly"]:
                    redis_client.set(f"anomaly:{result['id']}", json.dumps(result), ex=3600)
                yield {"data": json.dumps(result)}
                await asyncio.sleep(random.uniform(0.5, 2.0))
        except Exception as e:
            print(f"Error kritis dalam event generator: {e}")
        finally:
            print("Event generator selesai.")
    return EventSourceResponse(event_generator())


@app.post("/generate-sar")
async def generate_sar_draft(req: SarRequest):
    """Endpoint untuk menghasilkan draf SAR menggunakan Gemini."""
    gemini_model = ml_models.get("gemini")
    if not gemini_model:
        raise HTTPException(status_code=503, detail="Layanan AI tidak terkonfigurasi. Periksa GEMINI_API_KEY.")

    tx_data = req.transaction
    # Menambahkan tanggal dan nomor referensi unik ke data yang akan dikirim
    tx_data['tanggal_laporan'] = "27 Oktober 2023" # Contoh tanggal statis, bisa diganti dengan tanggal dinamis
    tx_data['nomor_referensi'] = str(uuid.uuid4())
    
    tx_json = json.dumps(tx_data, indent=2)

    # --- PERBAIKAN PROMPT DI SINI ---
    prompt = f"""
Anda adalah seorang analis kepatuhan keuangan profesional yang sedang menulis Laporan Aktivitas Mencurigakan (SAR) untuk dilaporkan kepada Pusat Pelaporan dan Analisis Transaksi Keuangan (PPATK) Indonesia.
Berdasarkan data transaksi dalam format JSON berikut, tuliskan narasi laporan yang jelas, formal, dan ringkas.

Struktur narasi harus mencakup:
1.  Kepada: Pusat Pelaporan dan Analisis Transaksi Keuangan (PPATK) Indonesia
2.  Tanggal: [Gunakan tanggal dari data]
3.  Nomor Referensi: [Gunakan nomor referensi dari data]
4.  Ringkasan Aktivitas: Jelaskan secara singkat apa yang terjadi.
5.  Detail Transaksi: Sebutkan detail kunci seperti jumlah, jenis transaksi, dan pihak terkait.
6.  Indikator Kecurigaan: Jelaskan MENGAPA transaksi ini mencurigakan, merujuk pada kolom 'explanation'.
7.  Rekomendasi: Sarankan tindakan selanjutnya.

PENTING: Jangan gunakan format Markdown. Hasilkan teks biasa (plain text) tanpa karakter seperti '*' atau '#'. Gunakan baris baru untuk memisahkan bagian.

Berikut adalah data transaksinya:
{tx_json}
"""
    try:
        response = await gemini_model.generate_content_async(prompt)
        
        # --- PERBAIKAN POST-PROCESSING DI SINI ---
        # Membersihkan teks dari karakter Markdown sebagai pengaman
        raw_text = response.text
        cleaned_text = raw_text.replace('**', '').replace('*', '').replace('#', '')
        
        return {"sar_draft": cleaned_text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghubungi Gemini API: {e}")

@app.get("/")
def read_root():
    return {"status": "Jaga Dana Backend is running"}

