"""
AgenteFinanceiro — Especialista em Relatórios, Finanças e Analytics.
Responsabilidade: PDFs, despesas, análise de dados, histórico de caixa e estoque.
SEPARADO TOTALMENTE DO AGENTE CUSTOMER.
"""
import os
import logging
from typing import List, Optional, Dict, Any

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition

from agents.schemas.admin_state import AdminState

logger = logging.getLogger("ADMIN.FINANCEIRO")

FINANCEIRO_SYSTEM_PROMPT = """Você é o AGENTE FINANCEIRO da pousada — contador, analista e gerador de relatórios.

## SUA FUNÇÃO
Fornecer ao gerente visibilidade financeira completa: receitas, despesas, estoque e relatórios profissionais em PDF.

## SUAS FERRAMENTAS
- `robot_finance_summary`: Resumo rápido de saúde financeira (total de receitas e transações)
- `robot_expense_launcher`: Lança despesas operacionais (água, luz, fornecedor, salários, etc)
- `robot_pdf_reporter`: Gera relatórios PDF oficiais: 'finance', 'inventory' ou 'shopping'
- `robot_get_analytics_data`: Busca dados brutos de faturamento e ocupação para análise
- `robot_dynamic_pdf_composer`: Compõe PDF personalizado com seções e tabelas customizadas
- `robot_cashier_history_viewer`: Histórico de sessões de caixa (PDV)
- `robot_inventory_viewer`: Consulta estoque de produtos
- `robot_inventory_sync`: Entrada/saída de estoque ou cadastro de novos produtos

## PROTOCOLO DE RELATÓRIOS (MUITO IMPORTANTE)
Quando o usuário pedir um relatório ou análise:
1. **Anuncie que está processando**: Diga algo como "Estou gerando o relatório financeiro agora, um momento..." ANTES de chamar a ferramenta.
2. **Execute a ferramenta**: Chame robot_pdf_reporter ou robot_dynamic_pdf_composer.
3. **Entregue o resultado**: Confirme que o documento está pronto e disponível na tela.
4. **NUNCA leia URLs em voz alta**: Apenas confirme verbalmente que o link está disponível.

## REGRAS DE OURO
1. **Análise antes do PDF**: Para relatórios personalizados, use robot_get_analytics_data primeiro para ter os dados.
2. **Categorias de despesa válidas**: agua, energia, internet, manutencao, fornecedor, salarios, limpeza, alimentacao, marketing, impostos, aluguel, outros.
3. **Modo de relatório financeiro**: 'summary' para KPIs rápidos, 'full' para relatório completo com extrato.
4. **Contexto temporal**: Mencione o período analisado ao apresentar qualquer dado financeiro.

## EXEMPLOS
- "Gera o relatório financeiro do mês" → Anuncia → robot_pdf_reporter(report_type="finance", mode="full")
- "Lança conta de luz de R$350" → robot_expense_launcher(description="Conta de Luz", amount=350, category="energia")
- "Lista de compras urgentes" → robot_pdf_reporter(report_type="shopping")
- "Como está nosso estoque de bebidas?" → robot_inventory_viewer(name="")
- "Análise de faturamento da semana" → robot_get_analytics_data(start_date=...) → robot_dynamic_pdf_composer(...)

Responda sempre em português brasileiro. Tom analítico e preciso, como um CFO de hotel boutique.
"""


def build_financeiro_graph(tenant_id: int):
    """
    Constrói e retorna o grafo LangGraph do Agente Financeiro compilado.
    """
    from agents.admin_agent import (
        finance_summary_logic,
        expense_logic,
        pdf_generator_logic,
        pdv_session_logic,
        inventory_viewer_logic,
        inventory_sync_logic,
        robot_dynamic_pdf_composer as pdf_composer_logic,
    )
    from agents.shared_tools import get_raw_analytics_logic

    google_key = os.getenv("GOOGLE_API_KEY")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    llm = ChatGoogleGenerativeAI(model=gemini_model, google_api_key=google_key, temperature=0.1)

    # ── FERRAMENTAS RESTRITAS ──────────────────────────────────────────────────

    @tool
    def robot_finance_summary() -> dict:
        """Resumo rápido da saúde financeira: total de receitas e número de transações."""
        return finance_summary_logic(tenant_id)

    @tool
    def robot_expense_launcher(
        description: str,
        amount: float,
        category: str = "outros",
        is_paid: bool = True,
        payment_method: str = "pix",
        due_date: Optional[str] = None
    ) -> dict:
        """Lança uma despesa operacional ou conta a pagar.
        Categorias válidas: agua, energia, internet, manutencao, fornecedor, salarios,
        limpeza, alimentacao, marketing, impostos, aluguel, outros.
        due_date: formato YYYY-MM-DD. Se data futura, is_paid será automaticamente False."""
        return expense_logic(tenant_id, description, amount, category, is_paid, payment_method, due_date)

    @tool
    def robot_pdf_reporter(
        report_type: str,
        mode: str = "full",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> dict:
        """Gera relatórios PDF oficiais profissionais.
        report_type: 'finance' (financeiro), 'inventory' (estoque), 'shopping' (lista de compras).
        mode (apenas para finance): 'full' (completo com extrato) ou 'summary' (só KPIs).
        start_date/end_date: formato YYYY-MM-DD. Sem datas, usa os últimos 30 dias."""
        return pdf_generator_logic(tenant_id, report_type, mode, start_date, end_date)

    @tool
    def robot_get_analytics_data(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        compare_with_previous: bool = False
    ) -> dict:
        """Retorna dados brutos de faturamento, despesas, ocupação e PDV para análise.
        Use ANTES de robot_dynamic_pdf_composer para coletar os dados do relatório personalizado.
        compare_with_previous=True: inclui dados do período anterior para comparação."""
        return get_raw_analytics_logic(tenant_id, start_date, end_date, compare_with_previous)

    @tool
    def robot_dynamic_pdf_composer(
        title: str,
        sections: List[Dict[str, Any]]
    ) -> dict:
        """Compõe um PDF personalizado com o cabeçalho oficial do hotel.
        title: título do documento.
        sections: lista de seções com tipo (table/kpi/text) e dados.
        Use para relatórios específicos que não se encaixam nos templates padrão."""
        return pdf_composer_logic(tenant_id, title, sections)

    @tool
    def robot_cashier_history_viewer(date_str: Optional[str] = None) -> dict:
        """Consulta o histórico de fechamentos de caixa (sessões PDV).
        date_str: data específica no formato YYYY-MM-DD. Sem data, retorna os últimos 10."""
        from agents.admin_agent import robot_cashier_history_viewer as cashier_logic
        return cashier_logic(tenant_id, date_str)

    @tool
    def robot_inventory_viewer(name: str = "", only_alerts: bool = False) -> dict:
        """Consulta o estoque de produtos.
        name: filtra por nome (parcial). Deixe vazio para ver todos.
        only_alerts=True: mostra apenas itens com estoque abaixo do mínimo."""
        return inventory_viewer_logic(tenant_id, name, only_alerts)

    @tool
    def robot_inventory_sync(
        name: str,
        quantity_change: int = 0,
        price: Optional[float] = None,
        cost_price: Optional[float] = None,
        markup_percent: Optional[float] = None,
        category: Optional[str] = None
    ) -> dict:
        """Atualiza estoque ou cadastra novo produto.
        quantity_change: positivo para entrada, negativo para saída.
        Se o produto não existir, será cadastrado automaticamente."""
        return inventory_sync_logic(tenant_id, name, quantity_change, price, category=category,
                                    cost_price=cost_price, markup_percent=markup_percent)

    tools = [
        robot_finance_summary,
        robot_expense_launcher,
        robot_pdf_reporter,
        robot_get_analytics_data,
        robot_dynamic_pdf_composer,
        robot_cashier_history_viewer,
        robot_inventory_viewer,
        robot_inventory_sync,
    ]
    llm_with_tools = llm.bind_tools(tools)

    # ── NÓS DO GRAFO ──────────────────────────────────────────────────────────

    async def call_financeiro_model(state: AdminState):
        logger.info(f"[FINANCEIRO] Processando para tenant {tenant_id}")
        try:
            sys_msg = SystemMessage(content=FINANCEIRO_SYSTEM_PROMPT)

            # Injeta contexto financeiro se disponível
            context_parts = []
            if state.get("task_context"):
                for k, v in state["task_context"].items():
                    context_parts.append(f"{k}: {v}")

            if context_parts:
                context_sys = SystemMessage(content="📍 CONTEXTO FINANCEIRO:\n" + "\n".join(context_parts))
                messages_to_send = [sys_msg, context_sys] + state["messages"]
            else:
                messages_to_send = [sys_msg] + state["messages"]

            response = await llm_with_tools.ainvoke(messages_to_send)
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"[FINANCEIRO] Erro crítico: {e}", exc_info=True)
            return {"messages": [AIMessage(content="Tive um problema ao processar os dados financeiros. Pode tentar novamente?")]}

    # ── GRAFO ─────────────────────────────────────────────────────────────────

    workflow = StateGraph(AdminState)
    workflow.add_node("financeiro_agent", call_financeiro_model)
    workflow.add_node("tools", ToolNode(tools))
    workflow.add_edge(START, "financeiro_agent")
    workflow.add_conditional_edges("financeiro_agent", tools_condition)
    workflow.add_edge("tools", "financeiro_agent")

    return workflow.compile()
