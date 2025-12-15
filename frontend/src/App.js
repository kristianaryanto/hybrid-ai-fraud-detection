import React, { useState, useEffect, useCallback } from 'react';
// Impor ikon dari react-icons
import {
  FiShield, FiList, FiAlertTriangle, FiCreditCard, FiSend, FiArrowDown, FiDollarSign, FiEdit, FiPlay, FiPause, FiX
} from 'react-icons/fi';
import './App.css';
import { FaGithub } from 'react-icons/fa'; // Import ikon

const API_URL = process.env.REACT_APP_API_URL || 'http://188.166.197.4:8088';

// Komponen helper untuk memilih ikon berdasarkan tipe transaksi
const TransactionTypeIcon = ({ type }) => {
  const iconMap = {
    PAYMENT: <FiCreditCard />,
    TRANSFER: <FiSend />,
    CASH_IN: <FiArrowDown />,
    CASH_OUT: <FiDollarSign />,
    DEBIT: <FiCreditCard />,
    default: <FiDollarSign />,
  };
  return <div className="transaction-icon">{(iconMap[type] || iconMap.default)}</div>;
};

function App() {
  const [liveTransactions, setLiveTransactions] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);
  const [sarDraft, setSarDraft] = useState('');
  const [isLoadingSar, setIsLoadingSar] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused) return;

    const eventSource = new EventSource(`${API_URL}/stream`);
    eventSource.onmessage = (event) => {
      const transaction = JSON.parse(event.data);
      setLiveTransactions(prev => [transaction, ...prev].slice(0, 50));
      if (transaction.is_anomaly) {
        setAnomalies(prev => [transaction, ...prev]);
      }
    };
    eventSource.onerror = (err) => {
      console.error("EventSource failed:", err);
      eventSource.close();
    };
    return () => eventSource.close();
  }, [isPaused]);

  const handleGenerateSar = useCallback(async (anomaly) => {
    setSelectedAnomaly(anomaly);
    setIsLoadingSar(true);
    setSarDraft('');
    try {
      const response = await fetch(`${API_URL}/generate-sar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transaction: anomaly }),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setSarDraft(data.sar_draft);
    } catch (error) {
      console.error("Failed to generate SAR:", error);
      setSarDraft(`Gagal membuat draf SAR: ${error.message}\n\nPastikan backend berjalan dan GEMINI_API_KEY sudah benar.`);
    } finally {
      setIsLoadingSar(false);
    }
  }, []);

  const formatCurrency = (amount) => new Intl.NumberFormat('id-ID', {
    style: 'currency', currency: 'IDR', minimumFractionDigits: 2,
  }).format(amount);

  return (
    <div className="App">
      <header className="app-header">
        {/* Bagian Logo */}
        <div className="app-logo">
          <FiShield className="icon" />
          <h1>Jaga Dana</h1>
        </div>

        {/* Bagian Navigasi */}
        <div className="nav-links">
          <a href="#home">Home</a>
          <a href="#about">About</a>
          <a href="https://github.com" target="_blank" rel="noopener noreferrer">
            <FaGithub size={24} />
          </a>
        </div>
      </header>
      <main className="container">
        <div className="main-content">
          <div className="panel">
            <div className="panel-header">
              <h2><FiList /> Aliran Transaksi Langsung</h2>
              <button onClick={() => setIsPaused(!isPaused)}>
                {isPaused ? <FiPlay /> : <FiPause />}
                {isPaused ? ' Lanjutkan' : ' Jeda'}
              </button>
            </div>
            <div className="transaction-list">
              {liveTransactions.length === 0 && !isPaused && <div className="placeholder">Menunggu data transaksi...</div>}
              {liveTransactions.map(tx => (
                <div key={tx.id} className={`transaction-item ${tx.is_anomaly ? 'anomaly' : ''}`}>
                  <TransactionTypeIcon type={tx.type} />
                  <div className="transaction-details">
                    <p className="transaction-info">{tx.type}</p>
                    <p className="transaction-meta">ke: {tx.nameDest}</p>
                  </div>
                  <p className="transaction-amount">{formatCurrency(tx.amount)}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2><FiAlertTriangle /> Anomali Terdeteksi</h2>
            </div>
            <div className="transaction-list">
              {anomalies.length === 0 ? <p className="placeholder">Belum ada anomali terdeteksi.</p> :
                anomalies.map(tx => (
                  <div key={tx.id} className="anomaly-item">
                    <div className="anomaly-header">
                      <p>{tx.type} - {formatCurrency(tx.amount)}</p>
                      <span>Skor: {tx.anomaly_score.toFixed(4)}</span>
                    </div>
                    <p className="explanation">{tx.explanation}</p>
                    <button onClick={() => handleGenerateSar(tx)} disabled={isLoadingSar && selectedAnomaly?.id === tx.id}>
                      {isLoadingSar && selectedAnomaly?.id === tx.id ? 'Memproses...' : <><FiEdit /> Buat Draf SAR</>}
                    </button>
                  </div>
                ))}
            </div>
          </div>
        </div>
        
        {selectedAnomaly && (
          <div className="sar-panel panel">
            <div className="panel-header">
                <h2>Draf Laporan Aktivitas Mencurigakan (SAR)</h2>
                <button className="close-sar" onClick={() => setSelectedAnomaly(null)}><FiX/></button>
            </div>
             {isLoadingSar ? 
                <div className="spinner-container"><div className="spinner"></div></div> : 
                <textarea value={sarDraft} readOnly placeholder="Draf narasi SAR akan muncul di sini..." />
             }
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
