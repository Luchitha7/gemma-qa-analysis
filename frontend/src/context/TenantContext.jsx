import React, { createContext, useContext, useState, useEffect } from 'react';

const API_BASE = 'http://localhost:8000';
const TenantContext = createContext();

export function TenantProvider({ children }) {
  const [tenants, setTenants] = useState([]);
  const [selectedTenant, setSelectedTenant] = useState('S-NET');
  const [loadingTenants, setLoadingTenants] = useState(false);

  const fetchTenants = async () => {
    setLoadingTenants(true);
    try {
      const res = await fetch(`${API_BASE}/api/tenants`);
      const data = await res.json();
      setTenants(data);
      if (data.length > 0 && !selectedTenant) {
        setSelectedTenant(data[0].id);
      }
    } catch (e) {
      console.error('Failed to fetch tenants:', e);
    } finally {
      setLoadingTenants(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  return (
    <TenantContext.Provider value={{
      tenants,
      selectedTenant,
      setSelectedTenant,
      fetchTenants,
      loadingTenants,
      API_BASE
    }}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  return useContext(TenantContext);
}
