import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import AccountGate from './components/AccountGate.jsx';
import './index.css';
import './brand.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <AccountGate><App /></AccountGate>
  </React.StrictMode>,
);
