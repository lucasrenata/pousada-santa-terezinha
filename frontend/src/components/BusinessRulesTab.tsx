import { useState, useEffect } from 'react';
import api from '../services/api';
import { Save, ShieldCheck, Info } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Switch } from '../components/ui/switch';
import { useToast } from '../hooks/use-toast';

interface BusinessRule {
  id?: number;
  name: string;
  description: string;
  rule_type: string;
  config: any;
  is_active: boolean;
}

export default function BusinessRulesTab() {
  const [rules, setRules] = useState<BusinessRule[]>([]);
  const [loading, setLoading] = useState(true);

  // Estados para as Configurações Individuais
  const [settings, setSettings] = useState<any>({
    pousada_deposit_percentage: '100',
    check_in_time: '14:00',
    check_out_time: '12:00',
    house_rules_description: ''
  });

  const [savingSettings, setSavingSettings] = useState<string | null>(null);
  const { toast } = useToast();

  const loadData = async () => {
    try {
      const [rulesResp, settingsResp] = await Promise.all([
        api.get('/business-rules/'),
        api.get('/settings/')
      ]);

      setRules(rulesResp.data);

      // Mapeia os valores vindo do banco para o estado local
      const dbSettings: any = {};
      settingsResp.data.forEach((s: any) => {
        dbSettings[s.key] = s.value;
      });

      setSettings((prev: any) => ({ ...prev, ...dbSettings }));
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSaveSetting = async (key: string, value: string, description: string) => {
    setSavingSettings(key);
    try {
      await api.post('/settings/', { key, value, description });
      toast({
        title: "Configuração Salva",
        description: "As alterações foram aplicadas com sucesso.",
      });
      loadData();
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

  const updateLocalConfig = (name: string, key: string, value: any) => {
    setRules(prev => prev.map(r => {
      if (r.name === name) {
        return { ...r, config: { ...r.config, [key]: value } };
      }
      return r;
    }));
  };

  const toggleActive = (name: string, val: boolean) => {
    setRules(prev => prev.map(r => {
      if (r.name === name) {
        return { ...r, is_active: val };
      }
      return r;
    }));
  };

  const getRule = (namePart: string) => {
    return rules.find(r => r.name.toLowerCase().includes(namePart.toLowerCase()));
  };

  if (loading) return <div className="p-4 text-center">Carregando inteligência de negócio...</div>;

  return (
    <div className="space-y-6">

      {/* CARD 1: REGRAS DA CASA (O CÉREBRO DA IA) */}
      <Card className="border-indigo-100 shadow-sm overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-indigo-600 to-violet-600 text-white">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5" />
            <CardTitle>Manual de Operação e Persona da IA</CardTitle>
          </div>
          <CardDescription className="text-indigo-100">
            Descreva como a IA deve se comportar e quais as regras fundamentais da sua pousada.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6 space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-bold text-slate-700">Regras da Casa, Políticas de Cancelamento e Observações</label>
            <textarea
              className="w-full h-32 p-3 rounded-lg border border-slate-200 focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
              placeholder="Ex: Não aceitamos pets. Cancelamento grátis até 7 dias antes. Café da manhã incluso..."
              value={settings.house_rules_description}
              onChange={(e) => setSettings({ ...settings, house_rules_description: e.target.value })}
            />
            <Button
              className="w-full bg-indigo-600 hover:bg-indigo-700"
              disabled={savingSettings === 'house_rules_description'}
              onClick={() => handleSaveSetting('house_rules_description', settings.house_rules_description, 'Regras da casa e políticas lidas pela IA')}
            >
              {savingSettings === 'house_rules_description' ? 'Salvando...' : 'Salvar Manual da Pousada'}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* CARD 2: LOGÍSTICA DE HORÁRIOS */}
        <Card>
          <CardHeader>
            <CardTitle className="text-md flex items-center gap-2">
              <span className="p-1.5 bg-amber-100 text-amber-700 rounded-md">🕒</span>
              Logística de Horários
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="text-sm text-slate-600">Check-in Padrão</label>
              <Input
                type="time"
                className="w-32"
                value={settings.check_in_time}
                onChange={(e) => setSettings({ ...settings, check_in_time: e.target.value })}
                onBlur={() => handleSaveSetting('check_in_time', settings.check_in_time, 'Horário padrão de entrada')}
              />
            </div>
            <div className="flex items-center justify-between">
              <label className="text-sm text-slate-600">Check-out Padrão</label>
              <Input
                type="time"
                className="w-32"
                value={settings.check_out_time}
                onChange={(e) => setSettings({ ...settings, check_out_time: e.target.value })}
                onBlur={() => handleSaveSetting('check_out_time', settings.check_out_time, 'Horário padrão de saída')}
              />
            </div>
          </CardContent>
        </Card>

      </div>

      {/* CARD 4: REGRAS FINANCEIRAS E DESCONTOS */}
      <Card>
        <CardHeader>
          <CardTitle className="text-md">Regras Financeiras e Descontos</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Sinal */}
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
            <div>
              <p className="text-sm font-bold">Percentual de Sinal</p>
              <p className="text-[10px] text-slate-500">Valor para garantia de reserva</p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                className="w-20"
                value={settings.pousada_deposit_percentage}
                onChange={(e) => setSettings({ ...settings, pousada_deposit_percentage: e.target.value })}
                onBlur={() => handleSaveSetting('pousada_deposit_percentage', settings.pousada_deposit_percentage, 'Percentual de sinal')}
              />
              <span className="text-sm font-bold text-slate-400">%</span>
            </div>
          </div>

          {/* Tarifa FDS */}
          {getRule("Fim de Semana") && (
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div className="flex items-center gap-3">
                <Switch
                  checked={getRule("Fim de Semana")?.is_active}
                  onCheckedChange={(val) => {
                    toggleActive(getRule("Fim de Semana")!.name, val);
                    handleSaveRule({ ...getRule("Fim de Semana")!, is_active: val });
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
                  value={getRule("Fim de Semana")?.config.multiplier}
                  onChange={(e) => updateLocalConfig(getRule("Fim de Semana")!.name, "multiplier", e.target.value)}
                  onBlur={() => handleSaveRule(getRule("Fim de Semana")!)}
                />
              </div>
            </div>
          )}

          {/* Desconto Longa Estadia */}
          {getRule("Estadia Longa") && (
            <div className="flex items-center justify-between p-3 border rounded-lg">
              <div className="flex items-center gap-3">
                <Switch
                  checked={getRule("Estadia Longa")?.is_active}
                  onCheckedChange={(val) => {
                    toggleActive(getRule("Estadia Longa")!.name, val);
                    handleSaveRule({ ...getRule("Estadia Longa")!, is_active: val });
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
                  className="w-16"
                  value={getRule("Estadia Longa")?.config.min_days}
                  onChange={(e) => updateLocalConfig(getRule("Estadia Longa")!.name, "min_days", e.target.value)}
                  onBlur={() => handleSaveRule(getRule("Estadia Longa")!)}
                />
                <span className="text-xs">dias</span>
                <Input
                  type="number"
                  className="w-16"
                  value={getRule("Estadia Longa")?.config.discount_percent}
                  onChange={(e) => updateLocalConfig(getRule("Estadia Longa")!.name, "discount_percent", e.target.value)}
                  onBlur={() => handleSaveRule(getRule("Estadia Longa")!)}
                />
                <span className="text-xs">%</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
