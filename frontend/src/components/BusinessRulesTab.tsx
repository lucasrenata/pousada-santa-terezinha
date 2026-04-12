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
  const { toast } = useToast();

  const loadRules = async () => {
    try {
      const response = await api.get('/business-rules/');
      setRules(response.data);
    } catch (error) {
      console.error('Erro ao carregar regras:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  const handleSaveRule = async (rule: BusinessRule) => {
    try {
      await api.post('/business-rules/', rule);
      toast({
        title: "Regra Salva",
        description: `A regra '${rule.name}' foi atualizada com sucesso.`,
      });
      loadRules();
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

  // Regras Padrão (Seed se não existirem)
  const defaultRules = [
    {
      name: "Tarifa Fim de Semana",
      description: "Aplica um multiplicador no valor da diária para Sexta, Sábado e Domingo.",
      rule_type: "price_modifier",
      config: { multiplier: 1.2 },
      is_active: false
    },
    {
      name: "Restrição de Casal",
      description: "Restringe reservas de casal em quartos específicos em determinados dias.",
      rule_type: "booking_restriction",
      config: { room_ids: "", days: [5, 6, 0] },
      is_active: false
    },
    {
      name: "Desconto Estadia Longa",
      description: "Aplica desconto para reservas acima de X dias.",
      rule_type: "discount",
      config: { min_days: 5, discount_percent: 10 },
      is_active: false
    }
  ];

  const getRule = (name: string) => {
    return rules.find(r => r.name === name) || defaultRules.find(r => r.name === name);
  };

  if (loading) return <div className="p-4 text-center">Carregando regras...</div>;

  return (
    <div className="space-y-6">
      <Card className="border-indigo-100 shadow-sm">
        <CardHeader className="bg-indigo-50/50">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-indigo-600" />
            <CardTitle className="text-lg">Inteligência de Negócio</CardTitle>
          </div>
          <CardDescription>
            Estas regras alimentam os Robôs da IA e os cálculos automáticos do sistema.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6 space-y-8">
          
          {/* REGRA: TARIFA FDS */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-slate-100 bg-white">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <p className="font-bold text-slate-800">Tarifa Fim de Semana (Sex-Dom)</p>
                <Switch 
                  checked={getRule("Tarifa Fim de Semana")?.is_active} 
                  onCheckedChange={(val) => toggleActive("Tarifa Fim de Semana", val)}
                />
              </div>
              <p className="text-xs text-slate-500 max-w-md">Multiplicador aplicado sobre o valor base da diária.</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-slate-600">Multiplicar por:</span>
              <Input 
                className="w-20" 
                type="number" 
                step="0.1"
                value={getRule("Tarifa Fim de Semana")?.config.multiplier}
                onChange={(e) => updateLocalConfig("Tarifa Fim de Semana", "multiplier", parseFloat(e.target.value))}
              />
              <Button size="sm" onClick={() => handleSaveRule(getRule("Tarifa Fim de Semana") as BusinessRule)}>
                <Save className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* REGRA: DISCONTO LONGA ESTADIA */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-4 rounded-xl border border-slate-100 bg-white">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <p className="font-bold text-slate-800">Desconto Estadia Longa</p>
                <Switch 
                  checked={getRule("Desconto Estadia Longa")?.is_active} 
                  onCheckedChange={(val) => toggleActive("Desconto Estadia Longa", val)}
                />
              </div>
              <p className="text-xs text-slate-500 max-w-md">Incentiva reservas de longa duração com descontos automáticos.</p>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-600">Mín. Dias:</span>
                <Input 
                  className="w-16 h-8 text-xs" 
                  type="number"
                  value={getRule("Desconto Estadia Longa")?.config.min_days}
                  onChange={(e) => updateLocalConfig("Desconto Estadia Longa", "min_days", parseInt(e.target.value))}
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-600">Desc %:</span>
                <Input 
                  className="w-16 h-8 text-xs" 
                  type="number"
                  value={getRule("Desconto Estadia Longa")?.config.discount_percent}
                  onChange={(e) => updateLocalConfig("Desconto Estadia Longa", "discount_percent", parseInt(e.target.value))}
                />
              </div>
              <Button size="sm" onClick={() => handleSaveRule(getRule("Desconto Estadia Longa") as BusinessRule)}>
                <Save className="w-4 h-4" />
              </Button>
            </div>
          </div>

           {/* REGRA: RESTRIÇÃO DE CASAL */}
           <div className="flex flex-col gap-4 p-4 rounded-xl border border-slate-100 bg-white">
            <div className="flex items-center justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <p className="font-bold text-slate-800">Restrição de Casal em Quartos Específicos</p>
                  <Switch 
                    checked={getRule("Restrição de Casal")?.is_active} 
                    onCheckedChange={(val) => toggleActive("Restrição de Casal", val)}
                  />
                </div>
                <p className="text-xs text-slate-500">Bloqueia reservas de casal em quartos selecionados nos finais de semana.</p>
              </div>
              <Button size="sm" onClick={() => handleSaveRule(getRule("Restrição de Casal") as BusinessRule)}>
                <Save className="w-4 h-4" />
              </Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-[10px] font-bold text-slate-500 uppercase mb-1 block">IDs dos Quartos (separados por vírgula)</label>
                <Input 
                  placeholder="Ex: 101, 102, 201" 
                  value={getRule("Restrição de Casal")?.config.room_ids}
                  onChange={(e) => updateLocalConfig("Restrição de Casal", "room_ids", e.target.value)}
                />
              </div>
              <div className="p-3 bg-amber-50 rounded-lg border border-amber-100 flex items-start gap-2">
                <Info className="w-4 h-4 text-amber-600 mt-0.5" />
                <p className="text-[10px] text-amber-800">
                  Esta regra é comumente usada para priorizar grupos maiores em quartos de alta capacidade durante o pico do fim de semana.
                </p>
              </div>
            </div>
          </div>

        </CardContent>
      </Card>
    </div>
  );
}
