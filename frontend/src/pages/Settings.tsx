import { useState, useEffect, type ChangeEvent } from 'react';
import api from '../services/api';
import { Save, Settings as SettingsIcon, AlertCircle, ListChecks, Copy, CreditCard, Lock, CheckCircle2, Globe } from 'lucide-react';
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
  const [mpConfig, setMpConfig] = useState({
    accessToken: '',
    publicKey: '',
    manualPixKey: '',
    hasToken: false
  });
  const [testingMp, setTestingMp] = useState(false);
  const [savingManual, setSavingManual] = useState(false);
  const [isValidated, setIsValidated] = useState(false);
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

  const loadMpConfig = async () => {
    try {
      const resp = await api.get('/payments/config');
      setMpConfig(prev => ({
        ...prev,
        publicKey: resp.data.mp_public_key,
        manualPixKey: resp.data.manual_pix_key,
        hasToken: resp.data.has_token
      }));
    } catch (error) {
      console.error('Erro ao carregar MP config:', error);
    }
  };

  useEffect(() => {
    loadSettings();
    loadMpConfig();
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

  const handleTestAndSaveMp = async () => {
    if (!mpConfig.accessToken && !mpConfig.hasToken) {
      toast({ 
        title: "Campo Vazio", 
        description: "Por favor, insira o seu Access Token para configurar.", 
        variant: "destructive" 
      });
      return;
    }
    
    setTestingMp(true);
    try {
      // 1. Validar via API
      const testResp = await api.post('/payments/test-config', { token: mpConfig.accessToken });
      
      if (!testResp.data.valid) {
        toast({ 
          title: "Falha na Conexão", 
          description: testResp.data.message || "As credenciais não são válidas.", 
          variant: "destructive" 
        });
        return;
      }

      // 2. Salvar configurações MP
      await api.post('/payments/config', {
        mp_access_token: mpConfig.accessToken,
        mp_public_key: mpConfig.publicKey,
        manual_pix_key: mpConfig.manualPixKey // Mantém a chave atual ao salvar MP
      });

      if (mpConfig.accessToken) {
        toast({ 
          title: "Configuração Atualizada!", 
          description: "Suas novas credenciais foram salvas e validadas.",
        });
        setMpConfig(prev => ({ ...prev, accessToken: '' }));
      } else {
        toast({ 
          title: "Conexão Ativa!", 
          description: "A credencial salva está funcionando corretamente.",
        });
      }
      
      setIsValidated(true);
      setTimeout(() => setIsValidated(false), 5000);
      loadMpConfig();
    } catch (error) {
      toast({ 
        title: "Erro de Conexão", 
        description: "Não foi possível validar as credenciais.", 
        variant: "destructive" 
      });
    } finally {
      setTestingMp(false);
    }
  };

  const handleSaveManualPix = async () => {
    if (!mpConfig.manualPixKey) {
      toast({ 
        title: "Atenção", 
        description: "Por favor, insira uma chave PIX válida.", 
        variant: "destructive" 
      });
      return;
    }
    
    setSavingManual(true);
    try {
      await api.post('/payments/config-manual', {
        manual_pix_key: mpConfig.manualPixKey
      });
      toast({ 
        title: "PIX Manual Salvo!", 
        description: "Sua chave de fallback foi atualizada com sucesso.",
      });
      loadMpConfig();
    } catch (error) {
      toast({ 
        title: "Erro ao Salvar", 
        description: "Não foi possível salvar a chave PIX manual.", 
        variant: "destructive" 
      });
    } finally {
      setSavingManual(false);
    }
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
        <TabsList className="grid w-full grid-cols-3 bg-slate-100 p-1 rounded-xl mb-6">
          <TabsTrigger value="general" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm py-2">
            <SettingsIcon className="w-4 h-4 mr-2" /> Geral
          </TabsTrigger>
          <TabsTrigger value="rules" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm py-2">
            <ListChecks className="w-4 h-4 mr-2" /> Regras de Negócio
          </TabsTrigger>
          <TabsTrigger value="mercadopago" className="rounded-lg data-[state=active]:bg-white data-[state=active]:shadow-sm py-2">
            <CreditCard className="w-4 h-4 mr-2" /> Mercado Pago
          </TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-md border-slate-200 overflow-hidden">
              <div className="h-2 bg-gradient-to-r from-blue-600 to-cyan-500" />
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <ListChecks className="w-5 h-5 text-blue-600" /> Regras de Precificação
                </CardTitle>
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

            <Card className="shadow-md border-slate-200 overflow-hidden">
              <div className="h-2 bg-gradient-to-r from-indigo-500 to-purple-500" />
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <SettingsIcon className="w-5 h-5 text-indigo-600" /> Informações Gerais
                </CardTitle>
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

                <div className="space-y-2">
                  <label className="text-sm font-medium">Nome da IA de Atendimento (Persona)</label>
                  <div className="flex gap-2">
                    <Input 
                      placeholder="Ex: Ana, Maria, Recepcionista Virtual"
                      value={getSettingValue('ai_receptionist_name') || 'Ana'} 
                      onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('ai_receptionist_name', e.target.value)}
                    />
                    <Button 
                      onClick={() => handleUpdateSetting('ai_receptionist_name', getSettingValue('ai_receptionist_name'), 'Nome que a IA usará para se apresentar aos hóspedes')}
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

        <TabsContent value="mercadopago" className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="shadow-md border-slate-200 overflow-hidden">
              <div className="h-2 bg-gradient-to-r from-blue-600 to-blue-800" />
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                       <Lock className="w-5 h-5 text-blue-600" /> Credenciais MP
                    </CardTitle>
                    <CardDescription>Configure suas chaves oficiais para habilitar pagamentos.</CardDescription>
                  </div>
                  {mpConfig.hasToken && (
                    <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 rounded-full text-xs font-semibold border border-emerald-100 italic animate-pulse">
                      <CheckCircle2 className="w-3.5 h-3.5" /> ATIVO
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-medium">Access Token</label>
                    {isValidated && (
                      <span className="text-[10px] font-bold text-emerald-600 flex items-center gap-0.5 animate-bounce">
                        <CheckCircle2 size={12} /> VALIDADO!
                      </span>
                    )}
                  </div>
                  <div className="relative">
                    <Input 
                      type="password"
                      placeholder={mpConfig.hasToken ? "••••••••••••••••••••••••••••" : "APP_USR-..."}
                      value={mpConfig.accessToken}
                      onChange={(e) => {setMpConfig({...mpConfig, accessToken: e.target.value}); setIsValidated(false);}}
                    />
                    <Lock className="absolute right-3 top-2.5 w-4 h-4 text-slate-300" />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">Public Key</label>
                  <Input 
                    placeholder="APP_USR-..."
                    value={mpConfig.publicKey}
                    onChange={(e) => setMpConfig({...mpConfig, publicKey: e.target.value})}
                  />
                </div>

                <div className="pt-2">
                  <Button 
                    onClick={handleTestAndSaveMp}
                    disabled={testingMp}
                    className="w-full bg-blue-600 hover:bg-blue-700"
                  >
                    {testingMp ? "Validando..." : <><Save className="w-4 h-4 mr-2" /> Testar e Salvar</>}
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="shadow-md border-slate-200 overflow-hidden">
                <div className="h-2 bg-gradient-to-r from-blue-400 to-indigo-500" />
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <CreditCard size={18} className="text-blue-500" /> Chave PIX Manual (Fallback)
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Input 
                      placeholder="Sua chave PIX da pousada"
                      value={mpConfig.manualPixKey}
                      onChange={(e) => setMpConfig({...mpConfig, manualPixKey: e.target.value})}
                    />
                  </div>
                  <Button 
                    onClick={handleSaveManualPix}
                    disabled={savingManual}
                    variant="secondary"
                    className="w-full bg-slate-100 hover:bg-slate-200 text-slate-900 border"
                  >
                    {savingManual ? "Salvando..." : <><Save className="w-4 h-4 mr-2" /> Salvar Chave Manual</>}
                  </Button>
                </CardContent>
              </Card>
              <Card className="shadow-md border-slate-200 overflow-hidden">
                <div className="h-1.5 bg-slate-400" />
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Globe size={16} className="text-slate-500" /> Webhook de Notificações
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex gap-2">
                    <Input 
                      readOnly 
                      value="https://hotelaria.parceriacomia.com.br/api/payments/webhook" 
                      className="bg-slate-50 text-xs font-mono"
                    />
                    <Button 
                      variant="outline"
                      onClick={() => {
                        navigator.clipboard.writeText("https://hotelaria.parceriacomia.com.br/api/payments/webhook");
                        toast({ title: "Copiado!" });
                      }}
                      size="icon"
                    >
                      <Copy size={14} />
                    </Button>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-relaxed italic">
                    Use este link no campo "URL de Notificação" do Mercado Pago para baixar automático de reservas via PIX.
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-blue-50/50 border-blue-100 shadow-none border-dashed border-2">
                <CardContent className="p-4 flex flex-col gap-3">
                  <div className="flex items-center gap-2 text-blue-700 font-bold text-xs uppercase">
                    <AlertCircle size={14} /> Dica de Configuração
                  </div>
                  <p className="text-xs text-blue-600 leading-relaxed">
                    As chaves de produção ficam em "Suas Aplicações" dentro do painel do Mercado Pago. Nunca compartilhe seu Access Token com ninguém.
                  </p>
                  <a 
                    href="https://www.mercadopago.com.br/developers/panel" 
                    target="_blank" 
                    rel="noreferrer"
                    className="text-xs font-bold text-blue-700 hover:underline flex items-center gap-1"
                  >
                    Abrir Painel do Desenvolvedor <Globe size={12} />
                  </a>
                </CardContent>
              </Card>
            </div>
          </div>
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
