import React from 'react';
import ReactDOM from 'react-dom/client';
import './App.css'; // Kita akan gunakan App.css sebagai file style utama
import StyledApp from './App'; // Mengimpor komponen yang sudah di-style dari App.js

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <StyledApp />
  </React.StrictMode>
);