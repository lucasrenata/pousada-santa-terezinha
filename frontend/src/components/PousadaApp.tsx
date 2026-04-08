
import React, { useState } from 'react';
import { Bed, Package, Home, Settings, Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { Link, useNavigate } from 'react-router-dom';
import { Dashboard } from '@/components/Dashboard';

export default function PousadaApp() {
  const [isOpen, setIsOpen] = useState(false);
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home, path: '/' },
    { id: 'rooms', label: 'Quartos', icon: Bed, path: '/quartos' },
    { id: 'inventory', label: 'Estoque', icon: Package, path: '/estoque' },
    { id: 'revenue', label: 'Receitas', icon: Settings, path: '/receitas' },
  ];

  const navigate = useNavigate();

  const handleNavigate = (view) => {
    const item = navItems.find(n => n.id === view) || navItems[0];
    navigate(item.path);
  };

  const NavigationItems = ({ onItemClick }: { onItemClick?: () => void }) => (
    <>
      {navItems.map((item) => {
        const IconComponent = item.icon;
        return (
          <Link key={item.id} to={item.path} onClick={onItemClick}>
            <Button
              variant="ghost"
              size="sm"
              className="w-full justify-start space-x-2 transition-all md:w-auto"
            >
              <IconComponent className="h-4 w-4" />
              <span>{item.label}</span>
            </Button>
          </Link>
        );
      })}
    </>
  );

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 w-full border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="rounded-lg bg-gradient-primary p-2">
                <Bed className="h-6 w-6 text-white" />
              </div>
              <div className="hidden sm:block">
                <h1 className="text-xl font-bold text-foreground">
                  Pousada Santa Terezinha
                </h1>
                <p className="text-sm text-muted-foreground">
                  Sistema de Gestão
                </p>
              </div>
              <div className="sm:hidden">
                <h1 className="text-lg font-bold text-foreground">Pousada</h1>
                <p className="text-xs text-muted-foreground">Sistema</p>
              </div>
            </div>
            
            {/* Desktop Navigation */}
            <nav className="hidden md:flex items-center space-x-2">
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
      <main className="container mx-auto px-4 py-4 sm:py-6">
        <div className="animate-fade-in">
          <Dashboard onNavigate={handleNavigate} />
        </div>
      </main>
    </div>
  );
}
