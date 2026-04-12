import { useState, useEffect, type ChangeEvent } from 'react';
import api from '../services/api';
import { Save, Settings as SettingsIcon, AlertCircle, ListChecks, Copy } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { useToast } from '../hooks/use-toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import BusinessRulesTab from '../components/BusinessRulesTab';

interface Setting {
  key: string;
  value: string;
  description: string | null;
}

export default function Settings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();
  const tenantId = localStorage.getItem('tenant_id') || '0';
  const publicAgentUrl = `${window.location.origin}/${tenantId}/atendimento`;

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(publicAgentUrl);
      toast({ title: "Link copiado para a área de transferência!" });
    } catch (err) {
      toast({ title: "Erro ao copiar o link", variant: "destructive" });
    }
  };

  const loadSettings = async () => {
    try {
      const response = await api.get('/settings/');
      setSettings(response.data);
    } catch (error) {
      console.error('Erro ao carregar configurações:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleUpdateSetting = async (key: string, value: string, description: string | null) => {
    setSaving(true);
    try {
      await api.post('/settings/', { key, value, description });
      toast({
        title: "Sucesso",
        description: "Configuração atualizada!",
      });
      await loadSettings();
    } catch (error) {
      toast({
        title: "Erro",
        description: "Falha ao salvar configuração.",
        variant: "destructive"
      });
    } finally {
      setSaving(false);
    }
  };

  const getSettingValue = (key: string) => {
    const setting = settings.find(s => s.key === key);
    if (!setting) {
      if (key === 'pousada_pricing_model') return 'per_person';
      if (key === 'pousada_rate_child_percentage') return '50';
      if (key === 'pousada_rate_infant_fixed') return '25';
      if (key === 'pousada_name') return 'Pousada System';
    }
    return setting?.value || '';
  };

  const setLocalValue = (key: string, value: string) => {
    setSettings(prev => {
      const exists = prev.some(s => s.key === key);
      if (exists) {
        return prev.map(s => s.key === key ? { ...s, value } : s);
      }
      return [...prev, { key, value, description: null }];
    });
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Carregando configurações...</div>;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <SettingsIcon className="w-8 h-8 text-blue-600" />
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Configurações</h1>
          <p className="text-slate-500">Gerencie valores padrões, regras de preços e informações da pousada.</p>
        </div>
      </div>

      <Tabs defaultValue="general" className="w-full">
        <TabsList className="grid w-full grid-cols-2 bg-slate-100 p-1 rounded-xl mb-6">
          <TabsTrigger value="general" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm py-2">
            <SettingsIcon className="w-4 h-4 mr-2" /> Geral
          </TabsTrigger>
          <TabsTrigger value="rules" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm py-2">
            <ListChecks className="w-4 h-4 mr-2" /> Regras de Negócio
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-sm border-slate-200">
              <CardHeader>
                <CardTitle>Regras de Precificação</CardTitle>
                <CardDescription>Valores utilizados no cálculo automático de reservas.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Meia Diária (7-12 anos) - % do Valor Base</label>
                  <div className="flex gap-2">
                    <Input 
                      type="number" 
                      value={getSettingValue('pousada_rate_child_percentage') || '50'} 
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_rate_child_percentage', e.target.value)}
                    />
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_rate_child_percentage', getSettingValue('pousada_rate_child_percentage'), 'Porcentagem cobrada para crianças de 7 a 12 anos')}
                      disabled={saving}
                    >
                      <Save className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Taxa Fixa (0-6 anos) - R$</label>
                  <div className="flex gap-2">
                    <Input 
                      type="number" 
                      value={getSettingValue('pousada_rate_infant_fixed') || '25'} 
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_rate_infant_fixed', e.target.value)}
                    />
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_rate_infant_fixed', getSettingValue('pousada_rate_infant_fixed'), 'Valor fixo diário para crianças até 6 anos')}
                      disabled={saving}
                    >
                      <Save className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Modelo de Cobrança (Diárias)</label>
                    <div className="flex gap-2">
                      <select 
                        className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        value={getSettingValue('pousada_pricing_model') || 'per_person'} 
                        onChange={(e) => setLocalValue('pousada_pricing_model', e.target.value)}
                      >
                        <option value="per_person">Por Pessoa (Soma diárias individuais)</option>
                        <option value="per_room">Por Quarto (Valor fixo por unidade)</option>
                      </select>
                      <Button 
                        onClick={() => handleUpdateSetting('pousada_pricing_model', getSettingValue('pousada_pricing_model'), 'Modelo de cálculo: por pessoa ou por quarto')}
                        disabled={saving}
                      >
                        <Save className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="shadow-sm border-slate-200">
              <CardHeader>
                <CardTitle>Informações Gerais</CardTitle>
                <CardDescription>Dados públicos da pousada.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Nome da Pousada</label>
                  <div className="flex gap-2">
                    <Input 
                      value={getSettingValue('pousada_name') || 'Pousada System'} 
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_name', e.target.value)}
                    />
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_name', getSettingValue('pousada_name'), 'Nome oficial da propriedade')}
                      disabled={saving}
                    >
                      <Save className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Telefone de Contato</label>
                  <div className="flex gap-2">
                    <Input 
                      value={getSettingValue('pousada_phone') || ''} 
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_phone', e.target.value)}
                    />
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_phone', getSettingValue('pousada_phone'), 'Telefone visível para clientes')}
                      disabled={saving}
                    >
                      <Save className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="pt-4 border-t border-slate-100">
                  <div className="space-y-2">
                    <label className="text-sm font-medium">Link de Atendimento (Hóspedes)</label>
                    <div className="flex gap-2">
                      <Input 
                        readOnly 
                        value={publicAgentUrl} 
                        className="bg-slate-50 text-slate-500 cursor-not-allowed font-mono text-xs"
                      />
                      <Button 
                        onClick={copyToClipboard}
                        type="button"
                        variant="secondary"
                        className="flex gap-2 bg-slate-100 hover:bg-slate-200 text-slate-700"
                        title="Copiar link"
                      >
                        <Copy className="w-4 h-4" /> Copiar
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="rules">
          <BusinessRulesTab />
        </TabsContent>
      </Tabs>

      <Card className="bg-blue-50 border-blue-100 border shadow-none">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-700">
            <strong>Dica:</strong> Estas configurações afetam os cálculos de novas reservas no Dashboard e no motor de precificação do backend.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
