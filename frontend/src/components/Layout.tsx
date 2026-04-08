
import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Bed, Users, Package, Home, DollarSign, Settings, Menu, Calendar } from 'lucide-react';

interface LayoutProps {
  children: React.ReactNode;
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  
  const navItems = [
    { key: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
    { key: 'rooms', label: 'Quartos', icon: Bed, path: '/quartos' },
    { key: 'reservations', label: 'Reservas', icon: Calendar, path: '/reservas' },
    { key: 'inventory', label: 'Estoque', icon: Package, path: '/estoque' },
    { key: 'revenue', label: 'Receitas', icon: DollarSign, path: '/receitas' },
  ];

  const NavigationItems = ({ onItemClick }: { onItemClick?: () => void }) => (
    <>
      {navItems.map(item => (
        <Link key={item.key} to={item.path} onClick={onItemClick}>
          <Button
            variant={location.pathname === item.path ? "default" : "ghost"}
            className="w-full justify-start space-x-2 md:w-auto"
          >
            <item.icon className="h-4 w-4" />
            <span>{item.label}</span>
          </Button>
        </Link>
      ))}
    </>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-border">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="bg-primary text-primary-foreground p-2 rounded-lg">
                <Bed className="h-5 w-5" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-xl font-bold text-foreground">Pousada Santa Terezinha</h1>
                <p className="text-sm text-muted-foreground">Sistema de Gestão</p>
              </div>
              <div className="sm:hidden">
                <h1 className="text-lg font-bold text-foreground">Pousada</h1>
                <p className="text-xs text-muted-foreground">Sistema</p>
              </div>
            </div>
            
            {/* Desktop Navigation */}
            <nav className="hidden md:flex space-x-2">
              <NavigationItems />
            </nav>

            {/* Mobile Menu */}
            <Sheet open={isOpen} onOpenChange={setIsOpen}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" className="md:hidden">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-[300px] sm:w-[400px]">
                <nav className="flex flex-col space-y-4 mt-8">
                  <NavigationItems onItemClick={() => setIsOpen(false)} />
                </nav>
              </SheetContent>
            </Sheet>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-4 sm:py-6 lg:py-8">
        {children}
      </main>
    </div>
  );
}
