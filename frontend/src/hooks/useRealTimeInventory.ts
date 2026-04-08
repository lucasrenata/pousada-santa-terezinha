import { useState, useEffect } from 'react';
import { supabase } from '@/integrations/supabase/client';

export interface Category {
  id: string;
  name: string;
  description: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Product {
  id: string;
  name: string;
  barcode: string | null;
  category_id: string | null;
  current_stock: number;
  min_stock: number;
  cost_price: number;
  sale_price: number;
  created_at: string;
  updated_at: string;
  category?: Category;
}

export interface StockMovement {
  id: string;
  product_id: string;
  movement_type: 'entrada' | 'saida';
  quantity: number;
  notes: string | null;
  user_name: string | null;
  created_at: string;
  product?: Product;
}

export const useRealTimeInventory = () => {
  const [categories, setCategories] = useState<Category[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [movements, setMovements] = useState<StockMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch initial data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        
        // Fetch categories
        const { data: categoriesData, error: categoriesError } = await supabase
          .from('categories')
          .select('*')
          .eq('active', true)
          .order('name');

        if (categoriesError) throw categoriesError;
        setCategories(categoriesData || []);

        // Fetch products with categories
        const { data: productsData, error: productsError } = await supabase
          .from('products')
          .select(`
            *,
            category:categories(*)
          `)
          .order('name');

        if (productsError) throw productsError;
        setProducts(productsData || []);

        // Fetch recent movements
        const { data: movementsData, error: movementsError } = await supabase
          .from('stock_movements')
          .select(`
            *,
            product:products(*)
          `)
          .order('created_at', { ascending: false })
          .limit(100);

        if (movementsError) throw movementsError;
        setMovements((movementsData || []) as StockMovement[]);

      } catch (err) {
        console.error('Error fetching inventory data:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  // Real-time subscriptions
  useEffect(() => {
    // Categories subscription
    const categoriesChannel = supabase
      .channel('categories_changes')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'categories' 
      }, (payload) => {
        console.log('Categories change:', payload);
        
        if (payload.eventType === 'INSERT') {
          setCategories(prev => [...prev, payload.new as Category]);
        } else if (payload.eventType === 'UPDATE') {
          setCategories(prev => prev.map(cat => 
            cat.id === payload.new.id ? payload.new as Category : cat
          ));
        } else if (payload.eventType === 'DELETE') {
          setCategories(prev => prev.filter(cat => cat.id !== payload.old.id));
        }
      })
      .subscribe();

    // Products subscription
    const productsChannel = supabase
      .channel('products_changes')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'products' 
      }, async (payload) => {
        console.log('Products change:', payload);
        
        if (payload.eventType === 'INSERT' || payload.eventType === 'UPDATE') {
          // Fetch complete product data with category
          const { data: productData } = await supabase
            .from('products')
            .select(`
              *,
              category:categories(*)
            `)
            .eq('id', payload.new.id)
            .single();

          if (productData) {
            if (payload.eventType === 'INSERT') {
              setProducts(prev => [...prev, productData]);
            } else {
              setProducts(prev => prev.map(prod => 
                prod.id === payload.new.id ? productData : prod
              ));
            }
          }
        } else if (payload.eventType === 'DELETE') {
          setProducts(prev => prev.filter(prod => prod.id !== payload.old.id));
        }
      })
      .subscribe();

    // Stock movements subscription
    const movementsChannel = supabase
      .channel('stock_movements_changes')
      .on('postgres_changes', { 
        event: '*', 
        schema: 'public', 
        table: 'stock_movements' 
      }, async (payload) => {
        console.log('Stock movements change:', payload);
        
        if (payload.eventType === 'INSERT') {
          // Fetch complete movement data with product
          const { data: movementData } = await supabase
            .from('stock_movements')
            .select(`
              *,
              product:products(*)
            `)
            .eq('id', payload.new.id)
            .single();

          if (movementData) {
            setMovements(prev => [movementData as StockMovement, ...prev.slice(0, 99)]);
          }
        }
      })
      .subscribe();

    return () => {
      supabase.removeChannel(categoriesChannel);
      supabase.removeChannel(productsChannel);
      supabase.removeChannel(movementsChannel);
    };
  }, []);

  // Helper functions
  const createCategory = async (categoryData: Omit<Category, 'id' | 'created_at' | 'updated_at'>) => {
    const { data, error } = await supabase
      .from('categories')
      .insert(categoryData)
      .select()
      .single();

    if (error) throw error;
    return data;
  };

  const createProduct = async (productData: Omit<Product, 'id' | 'created_at' | 'updated_at' | 'category'>) => {
    const { data, error } = await supabase
      .from('products')
      .insert(productData)
      .select(`
        *,
        category:categories(*)
      `)
      .single();

    if (error) throw error;
    return data;
  };

  const updateProduct = async (id: string, productData: Partial<Omit<Product, 'id' | 'created_at' | 'updated_at' | 'category'>>) => {
    const { data, error } = await supabase
      .from('products')
      .update(productData)
      .eq('id', id)
      .select(`
        *,
        category:categories(*)
      `)
      .single();

    if (error) throw error;
    return data;
  };

  const deleteProduct = async (id: string) => {
    const { error } = await supabase
      .from('products')
      .delete()
      .eq('id', id);

    if (error) throw error;
  };

  const createMovement = async (movementData: Omit<StockMovement, 'id' | 'created_at' | 'product'>) => {
    const { data, error } = await supabase
      .from('stock_movements')
      .insert(movementData)
      .select(`
        *,
        product:products(*)
      `)
      .single();

    if (error) throw error;
    return data;
  };

  const lowStockProducts = products.filter(p => p.current_stock <= p.min_stock);
  const totalProducts = products.length;
  const totalValue = products.reduce((sum, p) => sum + (p.current_stock * p.cost_price), 0);
  const alertsCount = lowStockProducts.length;

  return {
    categories,
    products,
    movements,
    lowStockProducts,
    totalProducts,
    totalValue,
    alertsCount,
    loading,
    error,
    createCategory,
    createProduct,
    updateProduct,
    deleteProduct,
    createMovement
  };
};