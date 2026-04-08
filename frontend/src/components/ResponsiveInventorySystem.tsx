import React, { useState } from 'react';
import { useRealTimeInventory } from '@/hooks/useRealTimeInventory';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { toast } from '@/hooks/use-toast';
import {
  Package,
  Plus,
  Minus,
  ShoppingCart,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  Download,
  Menu,
  Search,
  Filter,
  Edit,
  Trash2
} from 'lucide-react';
import jsPDF from 'jspdf';

export default function ResponsiveInventorySystem() {
  const {
    products,
    categories,
    movements,
    lowStockProducts,
    totalProducts,
    totalValue,
    alertsCount,
    loading,
    createProduct,
    updateProduct,
    deleteProduct,
    createMovement
  } = useRealTimeInventory();

  const [activeTab, setActiveTab] = useState('dashboard');
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCategory, setFilterCategory] = useState('all');
  const [isAddProductOpen, setIsAddProductOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [newProduct, setNewProduct] = useState({
    name: '',
    barcode: '',
    category_id: '',
    sale_price: '',
    min_stock: '',
    current_stock: ''
  });

  const stats = {
    totalProducts,
    totalValue,
    lowStockItems: lowStockProducts.length,
    recentMovements: movements.length
  };

  const filteredProducts = products.filter(product => {
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesCategory = filterCategory === 'all' || product.category_id === filterCategory;
    return matchesSearch && matchesCategory;
  });

  const handleAddProduct = async () => {
    try {
      await createProduct({
        name: newProduct.name,
        barcode: newProduct.barcode || null,
        category_id: newProduct.category_id,
        sale_price: parseFloat(newProduct.sale_price),
        cost_price: parseFloat(newProduct.sale_price), // Using sale_price as cost_price for simplicity
        min_stock: parseInt(newProduct.min_stock),
        current_stock: parseInt(newProduct.current_stock)
      });
      setNewProduct({ name: '', barcode: '', category_id: '', sale_price: '', min_stock: '', current_stock: '' });
      setIsAddProductOpen(false);
      toast({ title: 'Produto adicionado com sucesso!' });
    } catch (error) {
      toast({ title: 'Erro ao adicionar produto', variant: 'destructive' });
    }
  };

  const generatePDF = () => {
    const doc = new jsPDF();
    const shoppingList = lowStockProducts; // Using lowStockProducts as shopping list
    
    doc.setFontSize(16);
    doc.text('Lista de Compras - Pousada Santa Terezinha', 20, 20);
    
    doc.setFontSize(12);
    doc.text(`Data: ${new Date().toLocaleDateString('pt-BR')}`, 20, 35);
    
    let yPosition = 50;
    let totalValue = 0;
    
    shoppingList.forEach((item, index) => {
      const category = categories.find(c => c.id === item.category_id);
      const suggestedQuantity = item.min_stock - item.current_stock + 5; // Suggested quantity calculation
      const itemValue = item.sale_price * suggestedQuantity;
      totalValue += itemValue;
      
      doc.text(`${index + 1}. ${item.name}`, 20, yPosition);
      doc.text(`Categoria: ${category?.name || 'N/A'}`, 30, yPosition + 10);
      doc.text(`Estoque atual: ${item.current_stock}`, 30, yPosition + 20);
      doc.text(`Qtd. sugerida: ${suggestedQuantity}`, 30, yPosition + 30);
      doc.text(`Valor: R$ ${itemValue.toFixed(2)}`, 30, yPosition + 40);
      
      yPosition += 55;
      
      if (yPosition > 250) {
        doc.addPage();
        yPosition = 20;
      }
    });
    
    doc.text(`Total estimado: R$ ${totalValue.toFixed(2)}`, 20, yPosition + 10);
    doc.save('lista-compras.pdf');
  };

  const MobileMenu = () => (
    <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Menu className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="w-[300px]">
        <nav className="flex flex-col space-y-4 mt-8">
          <Button
            variant={activeTab === 'dashboard' ? 'default' : 'ghost'}
            onClick={() => { setActiveTab('dashboard'); setIsMobileMenuOpen(false); }}
            className="justify-start"
          >
            <TrendingUp className="h-4 w-4 mr-2" />
            Dashboard
          </Button>
          <Button
            variant={activeTab === 'products' ? 'default' : 'ghost'}
            onClick={() => { setActiveTab('products'); setIsMobileMenuOpen(false); }}
            className="justify-start"
          >
            <Package className="h-4 w-4 mr-2" />
            Produtos
          </Button>
          <Button
            variant={activeTab === 'movements' ? 'default' : 'ghost'}
            onClick={() => { setActiveTab('movements'); setIsMobileMenuOpen(false); }}
            className="justify-start"
          >
            <TrendingDown className="h-4 w-4 mr-2" />
            Movimentações
          </Button>
          <Button
            variant={activeTab === 'shopping' ? 'default' : 'ghost'}
            onClick={() => { setActiveTab('shopping'); setIsMobileMenuOpen(false); }}
            className="justify-start"
          >
            <ShoppingCart className="h-4 w-4 mr-2" />
            Lista de Compras
          </Button>
        </nav>
      </SheetContent>
    </Sheet>
  );

  const StatsCards = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Produtos</CardTitle>
          <Package className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.totalProducts}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Valor Total</CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">R$ {stats.totalValue.toFixed(2)}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Estoque Baixo</CardTitle>
          <AlertTriangle className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.lowStockItems}</div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Movimentações</CardTitle>
          <TrendingDown className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{stats.recentMovements}</div>
        </CardContent>
      </Card>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center space-x-4">
          <MobileMenu />
          <h1 className="text-2xl sm:text-3xl font-bold">Sistema de Estoque</h1>
        </div>
        
        <Dialog open={isAddProductOpen} onOpenChange={setIsAddProductOpen}>
          <DialogTrigger asChild>
            <Button className="hidden sm:flex">
              <Plus className="h-4 w-4 mr-2" />
              Adicionar Produto
            </Button>
          </DialogTrigger>
          <DialogTrigger asChild>
            <Button size="icon" className="sm:hidden">
              <Plus className="h-4 w-4" />
            </Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Adicionar Produto</DialogTitle>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="name">Nome</Label>
                <Input
                  id="name"
                  value={newProduct.name}
                  onChange={(e) => setNewProduct({...newProduct, name: e.target.value})}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="barcode">Código de Barras</Label>
                <Input
                  id="barcode"
                  value={newProduct.barcode}
                  onChange={(e) => setNewProduct({...newProduct, barcode: e.target.value})}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="category">Categoria</Label>
                <Select value={newProduct.category_id} onValueChange={(value) => setNewProduct({...newProduct, category_id: value})}>
                  <SelectTrigger>
                    <SelectValue placeholder="Selecione uma categoria" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="grid gap-2">
                  <Label htmlFor="sale_price">Preço</Label>
                  <Input
                    id="sale_price"
                    type="number"
                    step="0.01"
                    value={newProduct.sale_price}
                    onChange={(e) => setNewProduct({...newProduct, sale_price: e.target.value})}
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="min_stock">Estoque Min.</Label>
                  <Input
                    id="min_stock"
                    type="number"
                    value={newProduct.min_stock}
                    onChange={(e) => setNewProduct({...newProduct, min_stock: e.target.value})}
                  />
                </div>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="current_stock">Estoque Atual</Label>
                <Input
                  id="current_stock"
                  type="number"
                  value={newProduct.current_stock}
                  onChange={(e) => setNewProduct({...newProduct, current_stock: e.target.value})}
                />
              </div>
              <Button onClick={handleAddProduct} className="w-full">
                Adicionar Produto
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {/* Desktop Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="hidden md:block">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="dashboard">Dashboard</TabsTrigger>
          <TabsTrigger value="products">Produtos</TabsTrigger>
          <TabsTrigger value="movements">Movimentações</TabsTrigger>
          <TabsTrigger value="shopping">Lista de Compras</TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" className="mt-6">
          <StatsCards />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Produtos com Estoque Baixo</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {lowStockProducts.map((product) => (
                      <div key={product.id} className="flex justify-between items-center p-2 border rounded">
                        <div>
                          <p className="font-medium">{product.name}</p>
                          <p className="text-sm text-muted-foreground">Estoque: {product.current_stock}</p>
                        </div>
                        <Badge variant="destructive">Baixo</Badge>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Movimentações Recentes</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {movements.slice(0, 10).map((movement) => (
                      <div key={movement.id} className="flex justify-between items-center p-2 border rounded">
                        <div>
                          <p className="font-medium">{movement.product?.name}</p>
                          <p className="text-sm text-muted-foreground">
                            {movement.movement_type === 'entrada' ? 'Entrada' : 'Saída'} de {movement.quantity}
                          </p>
                        </div>
                        <Badge variant={movement.movement_type === 'entrada' ? 'default' : 'secondary'}>
                          {movement.movement_type === 'entrada' ? '+' : '-'}{movement.quantity}
                        </Badge>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="products" className="mt-6">
          <div className="flex flex-col sm:flex-row gap-4 mb-6">
            <div className="flex-1">
              <Input
                placeholder="Buscar produtos..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full"
              />
            </div>
            <Select value={filterCategory} onValueChange={setFilterCategory}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <SelectValue placeholder="Filtrar por categoria" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Todas as categorias</SelectItem>
                {categories.map((category) => (
                  <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="hidden lg:block">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nome</TableHead>
                  <TableHead>Categoria</TableHead>
                  <TableHead>Preço</TableHead>
                  <TableHead>Estoque</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Ações</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredProducts.map((product) => {
                  const category = categories.find(c => c.id === product.category_id);
                  return (
                    <TableRow key={product.id}>
                      <TableCell className="font-medium">{product.name}</TableCell>
                      <TableCell>{category?.name}</TableCell>
                      <TableCell>R$ {product.sale_price.toFixed(2)}</TableCell>
                      <TableCell>{product.current_stock}</TableCell>
                      <TableCell>
                        <Badge variant={product.current_stock <= product.min_stock ? 'destructive' : 'default'}>
                          {product.current_stock <= product.min_stock ? 'Baixo' : 'OK'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex space-x-2">
                          <Button size="sm" variant="outline">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button size="sm" variant="outline">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </div>

          <div className="lg:hidden">
            <ScrollArea className="h-[60vh]">
              <div className="space-y-4">
                {filteredProducts.map((product) => {
                  const category = categories.find(c => c.id === product.category_id);
                  return (
                    <Card key={product.id}>
                      <CardHeader>
                        <div className="flex justify-between items-start">
                          <div>
                            <CardTitle className="text-lg">{product.name}</CardTitle>
                            <p className="text-sm text-muted-foreground">{category?.name}</p>
                          </div>
                          <Badge variant={product.current_stock <= product.min_stock ? 'destructive' : 'default'}>
                            {product.current_stock <= product.min_stock ? 'Baixo' : 'OK'}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="font-medium">Preço</p>
                            <p>R$ {product.sale_price.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="font-medium">Estoque</p>
                            <p>{product.current_stock}</p>
                          </div>
                        </div>
                        <div className="flex justify-end space-x-2 mt-4">
                          <Button size="sm" variant="outline">
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button size="sm" variant="outline">
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </ScrollArea>
          </div>
        </TabsContent>

        <TabsContent value="movements" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Movimentações de Estoque</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-2">
                  {movements.map((movement) => (
                    <div key={movement.id} className="flex justify-between items-center p-3 border rounded">
                      <div>
                        <p className="font-medium">{movement.product?.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {movement.movement_type === 'entrada' ? 'Entrada' : 'Saída'} de {movement.quantity}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {new Date(movement.created_at).toLocaleString('pt-BR')}
                        </p>
                      </div>
                      <Badge variant={movement.movement_type === 'entrada' ? 'default' : 'secondary'}>
                        {movement.movement_type === 'entrada' ? '+' : '-'}{movement.quantity}
                      </Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="shopping" className="mt-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold">Lista de Compras</h2>
            <Button onClick={generatePDF} className="hidden sm:flex">
              <Download className="h-4 w-4 mr-2" />
              Baixar PDF
            </Button>
            <Button size="icon" onClick={generatePDF} className="sm:hidden">
              <Download className="h-4 w-4" />
            </Button>
          </div>
          <Card>
            <CardHeader>
              <CardTitle>Produtos com Estoque Baixo</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-3">
                  {lowStockProducts.map((product) => {
                    const category = categories.find(c => c.id === product.category_id);
                    const suggestedQuantity = product.min_stock - product.current_stock + 5;
                    return (
                      <div key={product.id} className="flex justify-between items-center p-3 border rounded">
                        <div>
                          <p className="font-medium">{product.name}</p>
                          <p className="text-sm text-muted-foreground">{category?.name}</p>
                          <p className="text-sm">Estoque atual: {product.current_stock}</p>
                          <p className="text-sm">Quantidade sugerida: {suggestedQuantity}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium">R$ {product.sale_price.toFixed(2)}</p>
                          <p className="text-sm text-muted-foreground">
                            Total: R$ {(product.sale_price * suggestedQuantity).toFixed(2)}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Mobile Content */}
      <div className="md:hidden">
        <StatsCards />
        {activeTab === 'dashboard' && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Produtos com Estoque Baixo</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-2">
                    {lowStockProducts.map((product) => (
                      <div key={product.id} className="flex justify-between items-center p-2 border rounded">
                        <div>
                          <p className="font-medium">{product.name}</p>
                          <p className="text-sm text-muted-foreground">Estoque: {product.current_stock}</p>
                        </div>
                        <Badge variant="destructive">Baixo</Badge>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        )}
        {activeTab === 'products' && (
          <div className="space-y-4">
            <div className="flex flex-col gap-4">
              <Input
                placeholder="Buscar produtos..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              <Select value={filterCategory} onValueChange={setFilterCategory}>
                <SelectTrigger>
                  <SelectValue placeholder="Filtrar por categoria" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Todas as categorias</SelectItem>
                  {categories.map((category) => (
                    <SelectItem key={category.id} value={category.id}>{category.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <ScrollArea className="h-[60vh]">
              <div className="space-y-4">
                {filteredProducts.map((product) => {
                  const category = categories.find(c => c.id === product.category_id);
                  return (
                    <Card key={product.id}>
                      <CardHeader>
                        <div className="flex justify-between items-start">
                          <div>
                            <CardTitle className="text-lg">{product.name}</CardTitle>
                            <p className="text-sm text-muted-foreground">{category?.name}</p>
                          </div>
                          <Badge variant={product.current_stock <= product.min_stock ? 'destructive' : 'default'}>
                            {product.current_stock <= product.min_stock ? 'Baixo' : 'OK'}
                          </Badge>
                        </div>
                      </CardHeader>
                      <CardContent>
                        <div className="grid grid-cols-2 gap-4 text-sm">
                          <div>
                            <p className="font-medium">Preço</p>
                            <p>R$ {product.sale_price.toFixed(2)}</p>
                          </div>
                          <div>
                            <p className="font-medium">Estoque</p>
                            <p>{product.current_stock}</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </ScrollArea>
          </div>
        )}
        {activeTab === 'movements' && (
          <Card>
            <CardHeader>
              <CardTitle>Movimentações Recentes</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-2">
                  {movements.map((movement) => (
                    <div key={movement.id} className="flex justify-between items-center p-2 border rounded">
                      <div>
                        <p className="font-medium">{movement.product?.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {movement.movement_type === 'entrada' ? 'Entrada' : 'Saída'} de {movement.quantity}
                        </p>
                      </div>
                      <Badge variant={movement.movement_type === 'entrada' ? 'default' : 'secondary'}>
                        {movement.movement_type === 'entrada' ? '+' : '-'}{movement.quantity}
                      </Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        )}
        {activeTab === 'shopping' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold">Lista de Compras</h2>
              <Button size="icon" onClick={generatePDF}>
                <Download className="h-4 w-4" />
              </Button>
            </div>
            <Card>
              <CardContent className="pt-6">
                <ScrollArea className="h-[400px]">
                  <div className="space-y-3">
                    {lowStockProducts.map((product) => {
                      const category = categories.find(c => c.id === product.category_id);
                      const suggestedQuantity = product.min_stock - product.current_stock + 5;
                      return (
                        <div key={product.id} className="p-3 border rounded">
                          <div className="flex justify-between items-start mb-2">
                            <p className="font-medium">{product.name}</p>
                            <p className="font-medium">R$ {product.sale_price.toFixed(2)}</p>
                          </div>
                          <p className="text-sm text-muted-foreground">{category?.name}</p>
                          <p className="text-sm">Estoque atual: {product.current_stock}</p>
                          <p className="text-sm">Quantidade sugerida: {suggestedQuantity}</p>
                          <p className="text-sm font-medium mt-2">
                            Total: R$ {(product.sale_price * suggestedQuantity).toFixed(2)}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
