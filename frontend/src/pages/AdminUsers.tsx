import { useState, useEffect } from 'react';
import api from '../services/api';
import { UserPlus, Trash2, Shield, User, Edit2 } from 'lucide-react';

interface UserData {
  id: number;
  username: string;
  full_name?: string;
  email?: string;
  role: string;
}

export default function AdminUsers() {
  const [users, setUsers] = useState<UserData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingUserId, setEditingUserId] = useState<number | null>(null);
  const [newUser, setNewUser] = useState({ username: '', full_name: '', email: '', password: '', role: 'recepcionista' });
  const [passwordError, setPasswordError] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await api.get('/admin/users');
      setUsers(response.data);
    } catch (err) {
      console.error('Erro ao buscar usuários', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validação de senha forte (na edição, a senha pode ser vazia se não for alterar)
    if (!editingUserId || newUser.password) {
      const passRegex = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}$/;
      if (!passRegex.test(newUser.password)) {
        setPasswordError('A senha deve ter no mínimo 8 caracteres, com Maiúscula, Minúscula, Número e Especial (!@#$).');
        return;
      }
    }
    setPasswordError('');

    try {
      if (editingUserId) {
        // Remove username if editing, usually we don't change username
        const { username, ...updateData } = newUser;
        await api.put(`/admin/users/${editingUserId}`, updateData);
      } else {
        await api.post('/admin/users', newUser);
      }
      setShowModal(false);
      setEditingUserId(null);
      setNewUser({ username: '', full_name: '', email: '', password: '', role: 'recepcionista' });
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao salvar usuário');
    }
  };

  const openForm = (user?: UserData) => {
    if (user) {
      setEditingUserId(user.id);
      setNewUser({
        username: user.username,
        full_name: user.full_name || '',
        email: user.email || '',
        password: '',
        role: user.role
      });
    } else {
      setEditingUserId(null);
      setNewUser({ username: '', full_name: '', email: '', password: '', role: 'recepcionista' });
    }
    setPasswordError('');
    setShowModal(true);
  };

  const handleDeleteUser = async (id: number) => {
    if (!confirm('Deseja realmente remover este acesso?')) return;
    try {
      await api.delete(`/admin/users/${id}`);
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Erro ao deletar');
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Carregando usuários...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Gestão de Acessos</h1>
          <p className="text-slate-500 text-sm">Controle quem pode acessar o sistema e seus níveis de permissão.</p>
        </div>
        <button 
          onClick={() => openForm()}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg font-medium hover:bg-blue-700 flex items-center gap-2 transition"
        >
          <UserPlus size={18} />
          Novo Usuário
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <table className="w-full text-left">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Usuário</th>
              <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Contato</th>
              <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider">Nível de Acesso</th>
              <th className="px-6 py-4 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200">
            {users.map((user) => (
              <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="bg-slate-100 p-2 rounded-full text-slate-500">
                      <User size={18} />
                    </div>
                    <div className="flex flex-col">
                      <span className="font-semibold text-slate-700">{user.full_name || 'Não informado'}</span>
                      <span className="text-xs text-slate-400">@{user.username}</span>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className="text-sm text-slate-600">{user.email || '-'}</span>
                </td>
                <td className="px-6 py-4">
                  <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium capitalize 
                    ${user.role === 'admin' ? 'bg-purple-100 text-purple-700' : 
                      user.role === 'recepcionista' ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-700'}`}>
                    {user.role}
                  </span>
                </td>
                <td className="px-6 py-4 text-right flex justify-end gap-3">
                  {user.username !== 'admin' && (
                    <button 
                      onClick={() => openForm(user)}
                      className="text-blue-500 hover:text-blue-700 transition"
                      title="Editar usuário"
                    >
                      <Edit2 size={18} />
                    </button>
                  )}
                  {user.username !== 'admin' && (
                    <button 
                      onClick={() => handleDeleteUser(user.id)}
                      className="text-red-400 hover:text-red-600 transition"
                      title="Excluir usuário"
                    >
                      <Trash2 size={18} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* MODAL DE CRIAÇÃO */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] backdrop-blur-sm">
          <div className="bg-white p-6 rounded-2xl shadow-2xl w-full max-w-md mx-4 transform transition-all">
            <div className="flex items-center gap-3 mb-6">
              <div className="bg-blue-100 text-blue-600 p-2 rounded-lg">
                <Shield size={24} />
              </div>
              <h2 className="text-xl font-bold text-slate-800">
                {editingUserId ? 'Editar Acesso' : 'Novo Acesso System'}
              </h2>
            </div>
            
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Nome Completo</label>
                <input 
                  required
                  className="w-full border rounded-xl px-4 py-2 focus:ring-2 ring-blue-500 outline-none border-slate-200"
                  placeholder="ex: João Silva"
                  value={newUser.full_name}
                  onChange={(e) => setNewUser({...newUser, full_name: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">E-mail Corporativo</label>
                <input 
                  type="email"
                  required
                  className="w-full border rounded-xl px-4 py-2 focus:ring-2 ring-blue-500 outline-none border-slate-200"
                  placeholder="ex: joao@pousada.com"
                  value={newUser.email}
                  onChange={(e) => setNewUser({...newUser, email: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Login (Username)</label>
                <input 
                  autoFocus={!editingUserId}
                  required
                  disabled={editingUserId !== null}
                  className="w-full border rounded-xl px-4 py-2 focus:ring-2 ring-blue-500 outline-none border-slate-200 disabled:bg-slate-100 disabled:text-slate-500"
                  placeholder="ex: joao.silva"
                  value={newUser.username}
                  onChange={(e) => setNewUser({...newUser, username: e.target.value})}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Senha Segura {editingUserId && <span className="font-normal text-slate-500">(Deixe em branco para manter a atual)</span>}
                </label>
                <input 
                  type="password"
                  required={!editingUserId}
                  className="w-full border rounded-xl px-4 py-2 focus:ring-2 ring-blue-500 outline-none border-slate-200"
                  placeholder="••••••••"
                  value={newUser.password}
                  onChange={(e) => {
                    setNewUser({...newUser, password: e.target.value});
                    setPasswordError('');
                  }}
                />
                {passwordError && (
                  <p className="mt-2 text-xs text-red-500 font-semibold">{passwordError}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Nível de Acesso (Rule)</label>
                <select 
                  className="w-full border rounded-xl px-4 py-2 focus:ring-2 ring-blue-500 outline-none border-slate-200"
                  value={newUser.role}
                  onChange={(e) => setNewUser({...newUser, role: e.target.value})}
                >
                  <option value="recepcionista">Recepcionista</option>
                  <option value="manutencao">Manutenção (Apenas Quarto Status)</option>
                  <option value="faxina">Faxina / Limpeza (Apenas Quarto Status)</option>
                  <option value="admin">Administrador (Total)</option>
                </select>
              </div>

              <div className="flex gap-3 pt-4">
                <button 
                  type="button" 
                  onClick={() => setShowModal(false)}
                  className="flex-1 bg-slate-100 text-slate-600 py-2.5 rounded-xl font-semibold hover:bg-slate-200 transition"
                >
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="flex-1 bg-blue-600 text-white py-2.5 rounded-xl font-semibold hover:bg-blue-700 transition"
                >
                  {editingUserId ? 'Salvar Edição' : 'Criar Acesso'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
