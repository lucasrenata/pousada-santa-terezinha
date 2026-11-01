import { useState, useEffect, type ChangeEvent } from 'react';
import api from '../services/api';
import { Save, Settings as SettingsIcon, AlertCircle, ListChecks, Copy, CreditCard, Lock, CheckCircle2, Globe, Clock } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { useToast } from '../hooks/use-toast';
import { Switch } from '../components/ui/switch';

interface Setting {
  key: string;
  value: string;
  description: string | null;
}

interface BusinessRule {
  id?: number;
  name: string;
  description: string;
  rule_type: string;
  config: any;
  is_active: boolean;
}

export default function Settings() {
  const [settings, setSettings] = useState<Setting[]>([]);
  const [rules, setRules] = useState<BusinessRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState<string | null>(null);
  const [mpConfig, setMpConfig] = useState<any>({
    hasToken: false,
    accessToken: '',
    publicKey: '',
    manualPixKey: ''
  });
  const [tenantInfo, setTenantInfo] = useState({
    name: '',
    cnpj: '',
    address: ''
  });
  const [savingTenant, setSavingTenant] = useState(false);
  const [testingMp, setTestingMp] = useState(false);
  const [savingManual, setSavingManual] = useState(false);
  const [isValidated, setIsValidated] = useState(false);
  const { toast } = useToast();
  
  const tenantId = localStorage.getItem('tenant_id') || '0';
  const publicAgentUrl = `${window.location.origin}/${tenantId}/book`;

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(publicAgentUrl);
      toast({ title: "Link copiado para a área de transferência!" });
    } catch (err) {
      toast({ title: "Erro ao copiar o link", variant: "destructive" });
    }
  };

  const loadData = async () => {
    try {
      const [settingsResp, mpResp, tenantResp, rulesResp] = await Promise.all([
        api.get('/settings/'),
        api.get('/payments/config'),
        api.get('/settings/tenant'),
        api.get('/business-rules/')
      ]);
      setSettings(settingsResp.data);
      setMpConfig({
        hasToken: mpResp.data.has_token,
        accessToken: '',
        publicKey: mpResp.data.mp_public_key || '',
        manualPixKey: mpResp.data.manual_pix_key || ''
      });
      setTenantInfo({
        name: tenantResp.data.name || '',
        cnpj: tenantResp.data.cnpj || '',
        address: tenantResp.data.address || ''
      });
      setRules(rulesResp.data);
    } catch (error) {
      console.error('Erro ao carregar configurações:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleUpdateSetting = async (key: string, value: string, description: string | null) => {
    setSavingSettings(key);
    try {
      await api.post('/settings/', { key, value, description });
      toast({
        title: "Sucesso",
        description: "Configuração atualizada!",
      });
      await loadData();
    } catch (error) {
      toast({
        title: "Erro",
        description: "Falha ao salvar configuração.",
        variant: "destructive"
      });
    } finally {
      setSavingSettings(null);
    }
  };

  const handleSaveRule = async (rule: BusinessRule) => {
    try {
      await api.post('/business-rules/', rule);
      toast({
        title: "Regra Salva",
        description: `A regra '${rule.name}' foi atualizada com sucesso.`,
      });
      loadData();
    } catch (error) {
      toast({
        title: "Erro",
        description: "Falha ao salvar a regra de negócio.",
        variant: "destructive"
      });
    }
  };

  const updateLocalConfig = (ruleBase: BusinessRule, key: string, value: any) => {
    setRules(prev => {
      const exists = prev.find(r => r.name === ruleBase.name);
      if (exists) {
        return prev.map(r => r.name === ruleBase.name ? { ...r, config: { ...r.config, [key]: value } } : r);
      }
      return [...prev, { ...ruleBase, config: { ...ruleBase.config, [key]: value } }];
    });
  };

  const toggleActive = (ruleBase: BusinessRule, val: boolean) => {
    setRules(prev => {
      const exists = prev.find(r => r.name === ruleBase.name);
      if (exists) {
        return prev.map(r => r.name === ruleBase.name ? { ...r, is_active: val } : r);
      }
      return [...prev, { ...ruleBase, is_active: val }];
    });
  };

  const getSettingValue = (key: string) => {
    const setting = settings.find(s => s.key === key);
    if (!setting) {
      if (key === 'pousada_pricing_model') return 'per_person';
      if (key === 'pousada_rate_child_percentage') return '50';
      if (key === 'pousada_rate_infant_fixed') return '25';
      if (key === 'pousada_name') return 'Estabelecimento';
      if (key === 'check_in_time') return '14:00';
      if (key === 'check_out_time') return '12:00';
      if (key === 'pousada_deposit_percentage') return '50';
      if (key === 'caixa_pin') return '';
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
      if (mpConfig.accessToken) {
        const testResp = await api.post('/payments/test-config', { token: mpConfig.accessToken });
        
        if (!testResp.data.valid) {
          toast({ 
            title: "Falha na Conexão", 
            description: testResp.data.message || "As credenciais não são válidas.", 
            variant: "destructive" 
          });
          return;
        }
      }

      await api.post('/payments/config', {
        mp_access_token: mpConfig.accessToken || undefined,
        mp_public_key: mpConfig.publicKey,
        manual_pix_key: mpConfig.manualPixKey
      });

      toast({ 
        title: "Configuração Atualizada!", 
        description: "Suas credenciais do Mercado Pago foram salvas.",
      });
      
      setIsValidated(true);
      setTimeout(() => setIsValidated(false), 5000);
      loadData();
    } catch (error) {
      toast({ 
        title: "Erro de Conexão", 
        description: "Não foi possível validar ou salvar as credenciais.", 
        variant: "destructive" 
      });
    } finally {
      setTestingMp(false);
    }
  };

  const handleSaveManualPix = async () => {
    if (!mpConfig.manualPixKey) {
      toast({ title: "Atenção", description: "Por favor, insira uma chave PIX válida.", variant: "destructive" });
      return;
    }
    setSavingManual(true);
    try {
      await api.post('/payments/config-manual', { manual_pix_key: mpConfig.manualPixKey });
      toast({ title: "PIX Manual Salvo!" });
      loadData();
    } catch (error) {
      toast({ title: "Erro ao Salvar", variant: "destructive" });
    } finally {
      setSavingManual(false);
    }
  };

  const handleUpdateTenant = async () => {
    setSavingTenant(true);
    try {
      await api.patch('/settings/tenant', tenantInfo);
      toast({ title: "Dados oficiais atualizados!" });
      loadData();
    } catch (error) {
      toast({ title: "Erro ao atualizar dados do estabelecimento", variant: "destructive" });
    } finally {
      setSavingTenant(false);
    }
  };

  if (loading) return <div className="p-8 text-center text-slate-500">Carregando configurações...</div>;

  const fdsRule = rules.find(r => r.name === "Fim de Semana") || {
    name: "Fim de Semana",
    description: "Multiplicador de preço para Sexta, Sábado e Domingo",
    rule_type: "price_modifier",
    config: { multiplier: 1.0 },
    is_active: false
  };

  const longaRule = rules.find(r => r.name === "Estadia Longa") || {
    name: "Estadia Longa",
    description: "Desconto automático para estadias acima de X dias",
    rule_type: "discount",
    config: { min_days: 7, discount_percent: 0 },
    is_active: false
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center gap-3 mb-2">
        <SettingsIcon className="w-8 h-8 text-blue-600" />
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Configurações</h1>
          <p className="text-slate-500">Gerencie valores padrões, regras de preços, logística de horários e informações da pousada.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* COLUNA 1: DADOS DO ESTABELECIMENTO E HORÁRIOS */}
        <div className="space-y-6">
          <Card className="shadow-md border-slate-200 overflow-hidden">
            <div className="h-2 bg-gradient-to-r from-indigo-500 to-purple-500" />
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <SettingsIcon className="w-5 h-5 text-indigo-600" /> Informações do Estabelecimento
              </CardTitle>
              <CardDescription>Dados oficiais e de contato público.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Nome do Estabelecimento</label>
                <Input 
                  placeholder="Nome oficial da Pousada"
                  value={tenantInfo.name} 
                  onChange={(e) => setTenantInfo({...tenantInfo, name: e.target.value})}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">CNPJ (Opcional)</label>
                <Input 
                  placeholder="00.000.000/0001-00"
                  value={tenantInfo.cnpj} 
                  onChange={(e) => setTenantInfo({...tenantInfo, cnpj: e.target.value})}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Endereço Completo</label>
                <Input 
                  placeholder="Rua, Número, Bairro, Cidade - UF"
                  value={tenantInfo.address} 
                  onChange={(e) => setTenantInfo({...tenantInfo, address: e.target.value})}
                />
              </div>

              <Button 
                className="w-full bg-indigo-600 hover:bg-indigo-700" 
                onClick={handleUpdateTenant}
                disabled={savingTenant}
              >
                {savingTenant ? "Salvando..." : <><Save className="w-4 h-4 mr-2" /> Salvar Dados Oficiais</>}
              </Button>

              <div className="space-y-2 pt-2 border-t border-slate-100">
                <label className="text-sm font-medium">Telefone de Contato</label>
                <div className="flex gap-2">
                  <Input 
                    value={getSettingValue('pousada_phone') || ''} 
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_phone', e.target.value)}
                  />
                  <Button 
                    onClick={() => handleUpdateSetting('pousada_phone', getSettingValue('pousada_phone'), 'Telefone visível para clientes')}
                    disabled={savingSettings === 'pousada_phone'}
                  >
                    {savingSettings === 'pousada_phone' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Link do Portal de Reservas (Público)</label>
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

          {/* CARD 2: LOGÍSTICA DE HORÁRIOS */}
          <Card className="shadow-md border-slate-200 overflow-hidden">
            <div className="h-2 bg-amber-500" />
            <CardHeader>
              <CardTitle className="text-md flex items-center gap-2">
                <Clock className="w-5 h-5 text-amber-600" /> Logística de Horários
              </CardTitle>
              <CardDescription>Configurações para entrada e saída de hóspedes.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <label className="text-sm text-slate-600 font-medium">Check-in Padrão</label>
                <div className="flex items-center gap-2">
                  <Input
                    type="time"
                    className="w-32"
                    value={getSettingValue('check_in_time')}
                    onChange={(e) => setLocalValue('check_in_time', e.target.value)}
                  />
                  <Button 
                    onClick={() => handleUpdateSetting('check_in_time', getSettingValue('check_in_time'), 'Horário padrão de entrada')}
                    disabled={savingSettings === 'check_in_time'}
                  >
                    {savingSettings === 'check_in_time' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
              <div className="flex items-center justify-between pt-2">
                <label className="text-sm text-slate-600 font-medium">Check-out Padrão</label>
                <div className="flex items-center gap-2">
                  <Input
                    type="time"
                    className="w-32"
                    value={getSettingValue('check_out_time')}
                    onChange={(e) => setLocalValue('check_out_time', e.target.value)}
                  />
                  <Button 
                    onClick={() => handleUpdateSetting('check_out_time', getSettingValue('check_out_time'), 'Horário padrão de saída')}
                    disabled={savingSettings === 'check_out_time'}
                  >
                    {savingSettings === 'check_out_time' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* CARD 3: SEGURANÇA DE CAIXA */}
          <Card className="shadow-md border-slate-200 overflow-hidden">
            <div className="h-2 bg-gradient-to-r from-red-600 to-rose-500" />
            <CardHeader>
              <CardTitle className="text-md flex items-center gap-2">
                <Lock className="w-5 h-5 text-red-600" /> Segurança de Caixa
              </CardTitle>
              <CardDescription>Configuração de autorização para o caixa do PDV.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">PIN do Gerente (Fechamento)</label>
                <div className="flex gap-2">
                  <Input 
                    type="password" 
                    maxLength={6}
                    placeholder="Mínimo 4 dígitos"
                    value={getSettingValue('caixa_pin')} 
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('caixa_pin', e.target.value.replace(/\D/g, ''))}
                  />
                  <Button 
                    onClick={() => {
                      const pin = getSettingValue('caixa_pin');
                      if (pin && pin.length < 4) {
                        toast({ title: "Erro", description: "O PIN deve conter no mínimo 4 dígitos.", variant: "destructive" });
                        return;
                      }
                      handleUpdateSetting('caixa_pin', pin, 'PIN numérico de autorização para divergências de fechamento de caixa');
                    }}
                    disabled={savingSettings === 'caixa_pin'}
                  >
                    {savingSettings === 'caixa_pin' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
                <p className="text-[10px] text-slate-500">Utilizado pelo gerente para autorizar fechamentos com divergência física.</p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* COLUNA 2: REGRAS DE PRECIFICAÇÃO E DESCONTOS */}
        <div className="space-y-6">
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
                    value={getSettingValue('pousada_rate_child_percentage')} 
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_rate_child_percentage', e.target.value)}
                  />
                  <Button 
                    onClick={() => handleUpdateSetting('pousada_rate_child_percentage', getSettingValue('pousada_rate_child_percentage'), 'Porcentagem cobrada para crianças de 7 a 12 anos')}
                    disabled={savingSettings === 'pousada_rate_child_percentage'}
                  >
                    {savingSettings === 'pousada_rate_child_percentage' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Taxa Fixa (0-6 anos) - R$</label>
                <div className="flex gap-2">
                  <Input 
                    type="number" 
                    value={getSettingValue('pousada_rate_infant_fixed')} 
                    onChange={(e: ChangeEvent<HTMLInputElement>) => setLocalValue('pousada_rate_infant_fixed', e.target.value)}
                  />
                  <Button 
                    onClick={() => handleUpdateSetting('pousada_rate_infant_fixed', getSettingValue('pousada_rate_infant_fixed'), 'Valor fixo diário para crianças até 6 anos')}
                    disabled={savingSettings === 'pousada_rate_infant_fixed'}
                  >
                    {savingSettings === 'pousada_rate_infant_fixed' ? '...' : <Save className="w-4 h-4" />}
                  </Button>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Modelo de Cobrança (Diárias)</label>
                  <div className="flex gap-2">
                    <select 
                      className="flex h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-950 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                      value={getSettingValue('pousada_pricing_model')} 
                      onChange={(e) => setLocalValue('pousada_pricing_model', e.target.value)}
                    >
                      <option value="per_person">Por Pessoa (Soma diárias individuais)</option>
                      <option value="per_room">Por Quarto (Valor fixo por unidade)</option>
                    </select>
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_pricing_model', getSettingValue('pousada_pricing_model'), 'Modelo de cálculo: por pessoa ou por quarto')}
                      disabled={savingSettings === 'pousada_pricing_model'}
                    >
                      {savingSettings === 'pousada_pricing_model' ? '...' : <Save className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-slate-100">
                <div className="flex items-center justify-between">
                  <div>
                    <label className="text-sm font-medium">Percentual de Sinal</label>
                    <p className="text-[10px] text-slate-500">Valor padrão sugerido para garantia de reserva</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Input
                      type="number"
                      className="w-20"
                      value={getSettingValue('pousada_deposit_percentage')}
                      onChange={(e) => setLocalValue('pousada_deposit_percentage', e.target.value)}
                    />
                    <span className="text-sm font-bold text-slate-400">%</span>
                    <Button 
                      onClick={() => handleUpdateSetting('pousada_deposit_percentage', getSettingValue('pousada_deposit_percentage'), 'Percentual de sinal')}
                      disabled={savingSettings === 'pousada_deposit_percentage'}
                    >
                      {savingSettings === 'pousada_deposit_percentage' ? '...' : <Save className="w-4 h-4" />}
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* CARD: DESCONTOS E MODIFICADORES */}
          <Card className="shadow-md border-slate-200 overflow-hidden">
            <div className="h-2 bg-violet-500" />
            <CardHeader>
              <CardTitle className="text-md">Regras de Fim de Semana e Descontos</CardTitle>
              <CardDescription>Acréscimos e descontos automáticos na reserva.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Tarifa FDS */}
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Switch
                    checked={fdsRule.is_active}
                    onCheckedChange={(val) => {
                      toggleActive(fdsRule, val);
                      handleSaveRule({ ...fdsRule, is_active: val });
                    }}
                  />
                  <div>
                    <p className="text-sm font-bold">Tarifa Fim de Semana</p>
                    <p className="text-[10px] text-slate-500">Multiplicador Sex-Dom</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    step="0.1"
                    className="w-20"
                    value={fdsRule.config.multiplier}
                    onChange={(e) => updateLocalConfig(fdsRule, "multiplier", e.target.value)}
                    onBlur={() => handleSaveRule(fdsRule)}
                  />
                </div>
              </div>

              {/* Desconto Longa Estadia */}
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div className="flex items-center gap-3">
                  <Switch
                    checked={longaRule.is_active}
                    onCheckedChange={(val) => {
                      toggleActive(longaRule, val);
                      handleSaveRule({ ...longaRule, is_active: val });
                    }}
                  />
                  <div>
                    <p className="text-sm font-bold">Desconto Longa Estadia</p>
                    <p className="text-[10px] text-slate-500">Acima de X dias</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    className="w-14"
                    value={longaRule.config.min_days}
                    onChange={(e) => updateLocalConfig(longaRule, "min_days", e.target.value)}
                    onBlur={() => handleSaveRule(longaRule)}
                  />
                  <span className="text-xs">dias</span>
                  <Input
                    type="number"
                    className="w-14"
                    value={longaRule.config.discount_percent}
                    onChange={(e) => updateLocalConfig(longaRule, "discount_percent", e.target.value)}
                    onBlur={() => handleSaveRule(longaRule)}
                  />
                  <span className="text-xs">%</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* MERCADO PAGO E MANUAL PIX */}
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
                  value={mpConfig.accessToken || ''}
                  onChange={(e) => {setMpConfig({...mpConfig, accessToken: e.target.value}); setIsValidated(false);}}
                />
                <Lock className="absolute right-3 top-2.5 w-4 h-4 text-slate-300" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">Public Key</label>
              <Input 
                placeholder="APP_USR-..."
                value={mpConfig.publicKey || ''}
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
                  value={mpConfig.manualPixKey || ''}
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
                Use este link no campo "URL de Notificação" do Mercado Pago para baixa automática de reservas via PIX.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>

      <Card className="bg-blue-50 border-blue-100 border shadow-none">
        <CardContent className="p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
          <div className="text-sm text-blue-700">
            <strong>Aviso:</strong> Estas configurações afetam diretamente o painel de administração e o motor de reservas do cliente.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
