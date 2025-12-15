import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import joblib
import os

# Konfigurasi
DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_data.csv')
MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'isolation_forest.joblib')
SCALER_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'scaler.joblib')

def train():
    print("Memulai training model deteksi anomali...")

    # Pastikan direktori model ada
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # 1. Muat & Pra-pemrosesan Data
    df = pd.read_csv(DATA_PATH)
    
    # Rekayasa Fitur Sederhana
    df['type_encoded'] = df['type'].astype('category').cat.codes
    df['errorBalanceOrig'] = df['newbalanceOrg'] + df['amount'] - df['oldbalanceOrg']
    df['errorBalanceDest'] = df['oldbalanceDest'] + df['amount'] - df['newbalanceDest']

    # Pilih fitur untuk model
    features = ['amount', 'oldbalanceOrg', 'newbalanceOrg', 'type_encoded', 'errorBalanceOrig', 'errorBalanceDest']
    X = df[features]

    # 2. Scaling Fitur
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    print(f"Fitur yang digunakan untuk training: {features}")

    # 3. Training Model Isolation Forest
    # contamination = 'auto' atau float kecil. Kita set ke 0.01 (1%) karena anomali jarang terjadi.
    model = IsolationForest(n_estimators=100, contamination=0.01, random_state=42)
    model.fit(X_scaled)
    print("Training model selesai.")

    # 4. Simpan model dan scaler
    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    print(f"Model disimpan di: {MODEL_PATH}")
    print(f"Scaler disimpan di: {SCALER_PATH}")

if __name__ == "__main__":
    train()