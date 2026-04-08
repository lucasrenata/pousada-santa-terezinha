import React, { useState, useEffect, useRef } from 'react';
import { Package, Plus, Search, Edit, Trash2, AlertTriangle, ShoppingCart, BarChart3, Home, Settings, Bell, ArrowLeft, Download } from 'lucide-react';
import jsPDF from 'jspdf';
import { useRealTimeInventory, type Product, type Category, type StockMovement } from '@/hooks/useRealTimeInventory';
import { useToast } from '@/hooks/use-toast';

const InventorySystem = () => {
  const { toast } = useToast();
  const {
    categories,
    products,
    movements,
    lowStockProducts,
    totalProducts,
    totalValue,
    alertsCount,
    loading,
    error,
    createProduct,
    updateProduct,
    deleteProduct,
    createMovement
  } = useRealTimeInventory();

  // States
  const [currentView, setCurrentView] = useState('dashboard');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategory, setSelectedCategory] = useState('');
  const [showProductModal, setShowProductModal] = useState(false);
  const [showMovementModal, setShowMovementModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState<Product | null>(null);

  // Show loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Carregando sistema de estoque...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <p className="text-red-600 font-semibold">Erro ao carregar dados</p>
          <p className="text-gray-600 mt-2">{error}</p>
        </div>
      </div>
    );
  }

  // Sidebar
  const Sidebar = () => (
    <div className="w-64 bg-gray-900 text-white h-screen p-4" aria-label="Navegação lateral">
      <div className="mb-8">
        <h1 className="text-xl font-bold">Gestão de Estoque</h1>
        <p className="text-sm text-gray-400">Sistema Corporativo</p>
      </div>
      
      {/* Botão Voltar ao Painel */}
      <div className="mb-6">
        <button
          onClick={() => window.location.href = '/'}
          className="w-full flex items-center px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors text-left"
          aria-label="Voltar ao painel principal"
        >
          <ArrowLeft className="w-5 h-5 mr-3" aria-hidden />
          Voltar ao Painel
        </button>
      </div>
      
      <nav className="space-y-2" role="navigation">
        {[
          { id: 'dashboard', label: 'Dashboard', icon: Home },
          { id: 'products', label: 'Produtos', icon: Package },
          { id: 'movements', label: 'Movimentações', icon: BarChart3 },
          { id: 'alerts', label: 'Alertas', icon: Bell, badge: alertsCount },
          { id: 'shopping', label: 'Lista de Compras', icon: ShoppingCart }
        ].map(item => (
          <button
            key={item.id}
            onClick={() => setCurrentView(item.id)}
            className={`w-full flex items-center justify-between px-3 py-2 rounded-lg transition-colors text-left ${
              currentView === item.id ? 'bg-blue-600' : 'hover:bg-gray-800'
            }`}
            aria-current={currentView === item.id ? 'page' : undefined}
            aria-label={item.label}
          >
            <div className="flex items-center">
              <item.icon className="w-5 h-5 mr-3" aria-hidden />
              {item.label}
            </div>
            {item.badge && item.badge > 0 && (
              <span className="bg-red-500 text-white text-xs px-2 py-1 rounded-full">{item.badge}</span>
            )}
          </button>
        ))}
      </nav>
    </div>
  );

  // MODAL: Produto
  const ProductModal = () => {
    const modalRef = useRef<HTMLDivElement>(null);
    const [formData, setFormData] = useState({
      name: editingProduct?.name || '',
      barcode: editingProduct?.barcode || '',
      category_id: editingProduct?.category_id || '',
      current_stock: editingProduct?.current_stock || 0,
      min_stock: editingProduct?.min_stock || 0,
      cost_price: editingProduct?.cost_price || 0,
      sale_price: editingProduct?.sale_price || 0,
    });

    useEffect(() => {
      if (editingProduct) {
        setFormData({
          name: editingProduct.name,
          barcode: editingProduct.barcode || '',
          category_id: editingProduct.category_id || '',
          current_stock: editingProduct.current_stock,
          min_stock: editingProduct.min_stock,
          cost_price: editingProduct.cost_price,
          sale_price: editingProduct.sale_price,
        });
      }
    }, [editingProduct]);

    useEffect(() => {
      const handleEsc = (e: KeyboardEvent) => {
        if (e.key === "Escape") handleClose();
      };
      window.addEventListener("keydown", handleEsc);
      return () => window.removeEventListener("keydown", handleEsc);
    });

    const handleOverlayClick = (e: React.MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        handleClose();
      }
    };

    const handleClose = () => {
      setShowProductModal(false);
      setEditingProduct(null);
    };

    const handleSave = async () => {
      try {
        if (!formData.name || !formData.barcode || !formData.category_id) {
          toast({
            title: "Erro",
            description: "Preencha todos os campos obrigatórios!",
            variant: "destructive"
          });
          return;
        }
        
        if (formData.cost_price < 0 || formData.sale_price < 0 || formData.current_stock < 0 || formData.min_stock < 0) {
          toast({
            title: "Erro",
            description: "Os valores não podem ser negativos.",
            variant: "destructive"
          });
          return;
        }

        if (editingProduct) {
          await updateProduct(editingProduct.id, formData);
          toast({
            title: "Sucesso",
            description: "Produto atualizado com sucesso!"
          });
        } else {
          await createProduct(formData);
          toast({
            title: "Sucesso", 
            description: "Produto criado com sucesso!"
          });
        }
        
        handleClose();
      } catch (error) {
        toast({
          title: "Erro",
          description: "Erro ao salvar produto: " + (error as Error).message,
          variant: "destructive"
        });
      }
    };

    return (
      <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4" onMouseDown={handleOverlayClick} role="dialog" aria-modal="true">
        <div ref={modalRef} className="bg-white rounded-lg p-6 w-full max-w-md" onMouseDown={e => e.stopPropagation()}>
          <h2 className="text-xl font-bold mb-4">{editingProduct ? 'Editar Produto' : 'Novo Produto'}</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nome do Produto</label>
              <input
                type="text"
                value={formData.name}
                onChange={e => setFormData({ ...formData, name: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
                placeholder="Ex: Coca-Cola 350ml"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Código de Barras</label>
              <input
                type="text"
                value={formData.barcode}
                onChange={e => setFormData({ ...formData, barcode: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
                placeholder="7894900011517"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Categoria</label>
              <select
                value={formData.category_id}
                onChange={e => setFormData({ ...formData, category_id: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
              >
                <option value="">Selecione uma categoria</option>
                {categories.map(cat => (
                  <option key={cat.id} value={cat.id}>{cat.name}</option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Estoque Atual</label>
                <input
                  type="number"
                  min={0}
                  value={formData.current_stock}
                  onChange={e => setFormData({ ...formData, current_stock: parseInt(e.target.value) || 0 })}
                  className="w-full p-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Estoque Mínimo</label>
                <input
                  type="number"
                  min={0}
                  value={formData.min_stock}
                  onChange={e => setFormData({ ...formData, min_stock: parseInt(e.target.value) || 0 })}
                  className="w-full p-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Preço de Custo (R$)</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={formData.cost_price}
                  onChange={e => setFormData({ ...formData, cost_price: parseFloat(e.target.value) || 0 })}
                  className="w-full p-2 border border-gray-300 rounded-lg"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Preço de Venda (R$)</label>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={formData.sale_price}
                  onChange={e => setFormData({ ...formData, sale_price: parseFloat(e.target.value) || 0 })}
                  className="w-full p-2 border border-gray-300 rounded-lg"
                />
              </div>
            </div>
          </div>
          <div className="flex justify-end space-x-3 mt-6">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              aria-label="Salvar produto"
            >
              Salvar
            </button>
          </div>
        </div>
      </div>
    );
  };

  // MODAL: Movimentação
  const MovementModal = () => {
    const modalRef = useRef<HTMLDivElement>(null);
    const [formData, setFormData] = useState({
      product_id: '', 
      movement_type: 'entrada' as 'entrada' | 'saida', 
      quantity: 0, 
      notes: '',
      user_name: 'Usuário Atual'
    });

    useEffect(() => {
      const handleEsc = (e: KeyboardEvent) => { 
        if (e.key === "Escape") setShowMovementModal(false); 
      };
      window.addEventListener("keydown", handleEsc);
      return () => window.removeEventListener("keydown", handleEsc);
    });

    const handleOverlayClick = (e: React.MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(e.target as Node)) {
        setShowMovementModal(false);
      }
    };

    const handleSave = async () => {
      try {
        if (!formData.product_id || formData.quantity <= 0) {
          toast({
            title: "Erro",
            description: "Selecione um produto e informe uma quantidade válida!",
            variant: "destructive"
          });
          return;
        }

        await createMovement({
          product_id: formData.product_id,
          movement_type: formData.movement_type,
          quantity: formData.quantity,
          notes: formData.notes,
          user_name: formData.user_name
        });

        toast({
          title: "Sucesso",
          description: "Movimentação registrada com sucesso!"
        });

        setFormData({ product_id: '', movement_type: 'entrada', quantity: 0, notes: '', user_name: 'Usuário Atual' });
        setShowMovementModal(false);
      } catch (error) {
        toast({
          title: "Erro",
          description: "Erro ao registrar movimentação: " + (error as Error).message,
          variant: "destructive"
        });
      }
    };

    return (
      <div className="fixed inset-0 z-50 bg-black bg-opacity-50 flex items-center justify-center p-4" onMouseDown={handleOverlayClick} role="dialog" aria-modal="true">
        <div ref={modalRef} className="bg-white rounded-lg p-6 w-full max-w-md" onMouseDown={e => e.stopPropagation()}>
          <h2 className="text-xl font-bold mb-4">Nova Movimentação</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">Produto</label>
              <select
                value={formData.product_id}
                onChange={e => setFormData({ ...formData, product_id: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg"
                autoFocus
              >
                <option value="">Selecione um produto</option>
                {products.map(product => (
                  <option key={product.id} value={product.id}>{product.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Tipo de Movimentação</label>
              <select
                value={formData.movement_type}
                onChange={e => setFormData({ ...formData, movement_type: e.target.value as 'entrada' | 'saida' })}
                className="w-full p-2 border border-gray-300 rounded-lg"
              >
                <option value="entrada">Entrada</option>
                <option value="saida">Saída</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Quantidade</label>
              <input
                type="number"
                min={1}
                value={formData.quantity}
                onChange={e => setFormData({ ...formData, quantity: parseInt(e.target.value) || 0 })}
                className="w-full p-2 border border-gray-300 rounded-lg"
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Observações</label>
              <textarea
                value={formData.notes}
                onChange={e => setFormData({ ...formData, notes: e.target.value })}
                className="w-full p-2 border border-gray-300 rounded-lg h-20"
                placeholder="Observações sobre a movimentação..."
              />
            </div>
          </div>
          <div className="flex justify-end space-x-3 mt-6">
            <button
              onClick={() => setShowMovementModal(false)}
              className="px-4 py-2 text-gray-600 hover:text-gray-800"
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Salvar
            </button>
          </div>
        </div>
      </div>
    );
  };

  // DASHBOARD VIEW
  const DashboardView = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">Dashboard</h2>
      
      {/* Cards de resumo */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total de Produtos</p>
              <p className="text-2xl font-bold text-gray-900">{totalProducts}</p>
            </div>
            <Package className="h-8 w-8 text-blue-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Valor Total</p>
              <p className="text-2xl font-bold text-gray-900">R$ {totalValue.toFixed(2)}</p>
            </div>
            <BarChart3 className="h-8 w-8 text-green-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Alertas de Estoque</p>
              <p className="text-2xl font-bold text-red-600">{alertsCount}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-red-600" />
          </div>
        </div>
        
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Categorias</p>
              <p className="text-2xl font-bold text-gray-900">{categories.length}</p>
            </div>
            <Settings className="h-8 w-8 text-purple-600" />
          </div>
        </div>
      </div>

      {/* Produtos com estoque baixo */}
      {lowStockProducts.length > 0 && (
        <div className="bg-white rounded-lg shadow-md">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold text-gray-800 flex items-center">
              <AlertTriangle className="h-5 w-5 text-red-500 mr-2" />
              Produtos com Estoque Baixo
            </h3>
          </div>
          <div className="p-6">
            <div className="space-y-3">
              {lowStockProducts.map(product => (
                <div key={product.id} className="flex items-center justify-between p-3 bg-red-50 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900">{product.name}</p>
                    <p className="text-sm text-gray-600">{product.category?.name}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-red-600">Estoque: {product.current_stock}</p>
                    <p className="text-xs text-gray-500">Mínimo: {product.min_stock}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  // PRODUCTS VIEW
  const ProductsView = () => {
    const filteredProducts = products.filter(product => {
      const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                           (product.barcode && product.barcode.includes(searchTerm));
      const matchesCategory = !selectedCategory || product.category_id === selectedCategory;
      return matchesSearch && matchesCategory;
    });

    const handleDeleteProduct = async (id: string) => {
      if (confirm("Tem certeza que deseja excluir este produto?")) {
        try {
          await deleteProduct(id);
          toast({
            title: "Sucesso",
            description: "Produto excluído com sucesso!"
          });
        } catch (error) {
          toast({
            title: "Erro",
            description: "Erro ao excluir produto: " + (error as Error).message,
            variant: "destructive"
          });
        }
      }
    };

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-800">Produtos</h2>
          <button
            onClick={() => setShowProductModal(true)}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
          >
            <Plus className="h-4 w-4 mr-2" />
            Novo Produto
          </button>
        </div>

        {/* Filtros */}
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 h-4 w-4" />
              <input
                type="text"
                placeholder="Buscar por nome ou código de barras..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                className="w-full pl-10 p-2 border border-gray-300 rounded-lg"
              />
            </div>
            <select
              value={selectedCategory}
              onChange={e => setSelectedCategory(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-lg"
            >
              <option value="">Todas as categorias</option>
              {categories.map(cat => (
                <option key={cat.id} value={cat.id}>{cat.name}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Tabela de produtos */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Produto</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Categoria</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Estoque</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Preços</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Ações</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredProducts.map(product => (
                  <tr key={product.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div>
                        <div className="text-sm font-medium text-gray-900">{product.name}</div>
                        <div className="text-sm text-gray-500">{product.barcode}</div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                        {product.category?.name}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">
                        <span className={product.current_stock <= product.min_stock ? 'text-red-600 font-bold' : ''}>
                          {product.current_stock}
                        </span>
                        <span className="text-gray-500"> / {product.min_stock}</span>
                      </div>
                      {product.current_stock <= product.min_stock && (
                        <div className="text-xs text-red-500">Estoque baixo!</div>
                      )}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      <div>Custo: R$ {product.cost_price.toFixed(2)}</div>
                      <div>Venda: R$ {product.sale_price.toFixed(2)}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex space-x-2">
                        <button
                          onClick={() => {
                            setEditingProduct(product);
                            setShowProductModal(true);
                          }}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteProduct(product.id)}
                          className="text-red-600 hover:text-red-800"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  // MOVEMENTS VIEW
  const MovementsView = () => (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Movimentações</h2>
        <button
          onClick={() => setShowMovementModal(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 flex items-center"
        >
          <Plus className="h-4 w-4 mr-2" />
          Nova Movimentação
        </button>
      </div>

      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Produto</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Tipo</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Quantidade</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Usuário</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Observações</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {movements.map(movement => (
                <tr key={movement.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {new Date(movement.created_at).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {movement.product?.name}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                      movement.movement_type === 'entrada' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                    }`}>
                      {movement.movement_type === 'entrada' ? 'Entrada' : 'Saída'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {movement.quantity}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                    {movement.user_name}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">
                    {movement.notes}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  // ALERTS VIEW
  const AlertsView = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">Alertas de Estoque</h2>
      
      {lowStockProducts.length === 0 ? (
        <div className="bg-white rounded-lg shadow-md p-8 text-center">
          <AlertTriangle className="h-12 w-12 text-green-500 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Nenhum alerta!</h3>
          <p className="text-gray-600">Todos os produtos estão com estoque adequado.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow-md">
          <div className="p-6 border-b">
            <h3 className="text-lg font-semibold text-red-600 flex items-center">
              <AlertTriangle className="h-5 w-5 mr-2" />
              {lowStockProducts.length} produtos com estoque baixo
            </h3>
          </div>
          <div className="divide-y divide-gray-200">
            {lowStockProducts.map(product => (
              <div key={product.id} className="p-6 flex items-center justify-between">
                <div className="flex-1">
                  <h4 className="text-lg font-medium text-gray-900">{product.name}</h4>
                  <p className="text-sm text-gray-600">{product.category?.name} • {product.barcode}</p>
                  <div className="mt-2 flex items-center space-x-4">
                    <span className="text-sm text-red-600 font-medium">
                      Estoque atual: {product.current_stock}
                    </span>
                    <span className="text-sm text-gray-500">
                      Estoque mínimo: {product.min_stock}
                    </span>
                  </div>
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => {
                      setEditingProduct(product);
                      setShowProductModal(true);
                    }}
                    className="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700"
                  >
                    Editar
                  </button>
                  <button
                    onClick={() => setShowMovementModal(true)}
                    className="bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700"
                  >
                    Repor Estoque
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // SHOPPING LIST VIEW
  const ShoppingListView = () => {
    const shoppingItems = lowStockProducts.map(product => ({
      ...product,
      suggestedQuantity: Math.max(product.min_stock * 2 - product.current_stock, product.min_stock)
    }));

    const totalCost = shoppingItems.reduce((sum, item) => sum + (item.suggestedQuantity * item.cost_price), 0);

    const generatePDF = () => {
      const doc = new jsPDF();
      const currentDate = new Date().toLocaleDateString('pt-BR');
      
      // Cabeçalho
      doc.setFontSize(20);
      doc.text('Lista de Compras - Estoque', 20, 20);
      
      doc.setFontSize(12);
      doc.text(`Data: ${currentDate}`, 20, 35);
      doc.text(`Total de itens: ${shoppingItems.length}`, 20, 45);
      doc.text(`Valor estimado: R$ ${totalCost.toFixed(2)}`, 20, 55);
      
      // Linha separadora
      doc.line(20, 65, 190, 65);
      
      // Cabeçalhos da tabela
      doc.setFontSize(10);
      doc.setFont(undefined, 'bold');
      doc.text('Produto', 20, 75);
      doc.text('Categoria', 80, 75);
      doc.text('Estoque Atual', 120, 75);
      doc.text('Qtd. Sugerida', 150, 75);
      doc.text('Valor', 175, 75);
      
      // Linha dos cabeçalhos
      doc.line(20, 78, 190, 78);
      
      // Itens da lista
      doc.setFont(undefined, 'normal');
      let yPosition = 88;
      
      shoppingItems.forEach((item, index) => {
        if (yPosition > 280) { // Nova página se necessário
          doc.addPage();
          yPosition = 20;
        }
        
        // Truncar nome do produto se muito longo
        const productName = item.name.length > 25 ? item.name.substring(0, 22) + '...' : item.name;
        const categoryName = item.category?.name || 'N/A';
        const categoryShort = categoryName.length > 15 ? categoryName.substring(0, 12) + '...' : categoryName;
        
        doc.text(productName, 20, yPosition);
        doc.text(categoryShort, 80, yPosition);
        doc.text(item.current_stock.toString(), 125, yPosition);
        doc.text(item.suggestedQuantity.toString(), 155, yPosition);
        doc.text(`R$ ${(item.suggestedQuantity * item.cost_price).toFixed(2)}`, 175, yPosition);
        
        yPosition += 10;
      });
      
      // Rodapé
      const pageCount = doc.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.text(`Página ${i} de ${pageCount}`, 20, 290);
        doc.text('Sistema de Gestão de Estoque', 120, 290);
      }
      
      // Download
      doc.save(`lista-compras-${currentDate.replace(/\//g, '-')}.pdf`);
      
      toast({
        title: "Sucesso",
        description: "Lista de compras baixada com sucesso!"
      });
    };

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h2 className="text-2xl font-bold text-gray-800">Lista de Compras</h2>
          {shoppingItems.length > 0 && (
            <button
              onClick={generatePDF}
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 flex items-center"
              aria-label="Baixar lista de compras em PDF"
            >
              <Download className="h-4 w-4 mr-2" />
              Baixar PDF
            </button>
          )}
        </div>
        
        {shoppingItems.length === 0 ? (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <ShoppingCart className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Lista vazia!</h3>
            <p className="text-gray-600">Todos os produtos estão com estoque adequado.</p>
          </div>
        ) : (
          <>
            <div className="bg-white rounded-lg shadow-md p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold text-gray-900">
                  Itens para reposição ({shoppingItems.length})
                </h3>
                <div className="text-right">
                  <p className="text-sm text-gray-600">Valor total estimado:</p>
                  <p className="text-xl font-bold text-green-600">R$ {totalCost.toFixed(2)}</p>
                </div>
              </div>
              
              <div className="space-y-4">
                {shoppingItems.map(item => (
                  <div key={item.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex-1">
                      <h4 className="font-medium text-gray-900">{item.name}</h4>
                      <p className="text-sm text-gray-600">{item.category?.name}</p>
                      <p className="text-sm text-red-600">Estoque atual: {item.current_stock}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-600">Quantidade sugerida:</p>
                      <p className="text-lg font-bold text-blue-600">{item.suggestedQuantity}</p>
                      <p className="text-sm text-gray-500">
                        R$ {(item.suggestedQuantity * item.cost_price).toFixed(2)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    );
  };

  // Renderização condicional baseada na view atual
  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard': return <DashboardView />;
      case 'products': return <ProductsView />;
      case 'movements': return <MovementsView />;
      case 'alerts': return <AlertsView />;
      case 'shopping': return <ShoppingListView />;
      default: return <DashboardView />;
    }
  };

  return (
    <div className="flex h-screen bg-gray-100">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="p-8">
          {renderCurrentView()}
        </div>
      </main>
      
      {/* Modais */}
      {showProductModal && <ProductModal />}
      {showMovementModal && <MovementModal />}
    </div>
  );
};

export default InventorySystem;