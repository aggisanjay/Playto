import { useState, useEffect, useCallback } from 'react';
import { fetchMerchants, fetchMerchantBalance, fetchMerchantLedger, fetchPayouts, fetchBankAccounts } from '../api';

/**
 * Custom hook for managing merchant dashboard data.
 * Handles fetching, polling, and state management.
 */
export function useDashboard() {
  const [merchants, setMerchants] = useState([]);
  const [selectedMerchant, setSelectedMerchant] = useState(null);
  const [balance, setBalance] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [payouts, setPayouts] = useState([]);
  const [bankAccounts, setBankAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch all merchants on mount
  useEffect(() => {
    fetchMerchants()
      .then((data) => {
        setMerchants(data);
        if (data.length > 0) {
          setSelectedMerchant(data[0]);
        }
        setLoading(false);
      })
      .catch((err) => {
        setError('Failed to load merchants. Is the backend running?');
        setLoading(false);
      });
  }, []);

  // Refresh merchant data
  const refreshData = useCallback(async (merchantId) => {
    if (!merchantId) return;
    try {
      const [balanceData, ledgerData, payoutsData, bankData] = await Promise.all([
        fetchMerchantBalance(merchantId),
        fetchMerchantLedger(merchantId),
        fetchPayouts(merchantId),
        fetchBankAccounts(merchantId),
      ]);
      setBalance(balanceData);
      setLedger(ledgerData);
      setPayouts(payoutsData);
      setBankAccounts(bankData);
      setError(null);
    } catch (err) {
      setError('Failed to refresh data');
    }
  }, []);

  // Fetch data when merchant changes
  useEffect(() => {
    if (selectedMerchant) {
      refreshData(selectedMerchant.id);
    }
  }, [selectedMerchant, refreshData]);

  // Poll for updates every 3 seconds (live status updates)
  useEffect(() => {
    if (!selectedMerchant) return;
    const interval = setInterval(() => {
      refreshData(selectedMerchant.id);
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedMerchant, refreshData]);

  return {
    merchants,
    selectedMerchant,
    setSelectedMerchant,
    balance,
    ledger,
    payouts,
    bankAccounts,
    loading,
    error,
    refreshData,
  };
}
