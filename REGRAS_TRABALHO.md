# Regras Obrigatórias de Desenvolvimento - Antigravity

Este arquivo define os protocolos de atuação do assistente de IA neste projeto. O descumprimento de qualquer regra deve ser sinalizado imediatamente.

## 1. Aprovação Prévia de Alterações
- **NUNCA** faça alterações no código fonte (Python, JS/TS, CSS, etc.) sem que o usuário aprove o plano de implementação explicitamente.
- Antes de qualquer mudança, apresente o que será feito, por que será feito e quais os impactos esperados.

## 2. Discussão de Melhorias
- Qualquer oportunidade de melhoria observada (performance, segurança, refatoração) deve ser discutida primeiro. 
- O assistente deve explicar a lógica por trás da melhoria proposta antes de pedir permissão para agir.

## 3. Estabilidade do Modelo de IA
- **PROIBIDO** alterar o modelo de IA configurado (`gemini-2.5-flash-lite`).
- O modelo só será alterado mediante solicitação expressa do usuário.

## 4. Soluções Profundas vs. Remendos
- O assistente deve buscar a causa raiz dos problemas.
- Evitar "band-aids", remendos superficiais ou alterações constantes no prompt da IA para tentar "adivinhar" a solução. 
- A solução deve ser tecnicamente sólida e baseada em evidências (logs, testes, comportamento do código).

## 5. Raciocínio Ativo e Pesquisa Externa
- O assistente deve agir com inteligência e raciocínio lógico, não de forma mecânica.
- Sempre que houver dúvida técnica ou comportamento inesperado de bibliotecas/modelos, deve-se realizar pesquisas na rede para obter informações atualizadas antes de propor uma solução.
