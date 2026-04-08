import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Rooms from './pages/Rooms';
import NewBooking from './pages/NewBooking';
import Reservations from './pages/Reservations';
import BookingSummary from './pages/BookingSummary';
import Inventory from './pages/Inventory';
import Finance from './pages/Finance';
import Payments from './pages/Payments';
import MainLayout from './components/MainLayout';
import PublicBooking from './pages/PublicBooking';
import ServicePanel from './pages/ServicePanel';
import Settings from './pages/Settings';
import AdminUsers from './pages/AdminUsers';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Rota Pública (Sem Layout) */}
        <Route path="/" element={<Login />} />
        <Route path="/public/book" element={<PublicBooking />} />
        <Route path="/service" element={<ServicePanel />} />

        {/* Rotas Privadas (Com Layout "ParcerIA") */}
        <Route element={<MainLayout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/rooms" element={<Rooms />} />
          <Route path="/bookings" element={<Reservations />} />
          <Route path="/bookings/new" element={<NewBooking />} />
          <Route path="/bookings/summary" element={<BookingSummary />} />
          <Route path="/inventory" element={<Inventory />} />
          <Route path="/finance" element={<Finance />} />
          <Route path="/payments" element={<Payments />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="/admin/users" element={<AdminUsers />} />
        </Route>

        {/* Redireciona qualquer rota doida para o login */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
export default App;
