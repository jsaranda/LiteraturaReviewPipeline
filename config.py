"""
Configuração central da revisão sistemática.

Este arquivo é a ÚNICA fonte da verdade para:
  1. a string de busca (SEARCH_BLOCKS), a janela temporal e o idioma;
  2. os critérios de inclusão/exclusão (referência para a triagem);
  3. o status das bases de dados;
  4. as credenciais de API — que NÃO ficam aqui no código, e sim em
     variáveis de ambiente (ou num arquivo .env na raiz do projeto,
     ver .env.example). Nunca commite o .env.

Para reutilizar o pipeline em outra revisão, basta trocar SEARCH_BLOCKS,
YEAR_FROM/YEAR_TO e os critérios; os scripts em pipeline/ não precisam
ser alterados (exceto os prompts de triagem por LLM em 06 e 11, que
descrevem o tema da revisão em linguagem natural).

Exemplo de protocolo usado na primeira execução deste pipeline:
"AI Agents and Agentic AI in Logistics Operations: A Systematic
Literature Review and Taxonomy".
"""

import os

# ---------------------------------------------------------------------------
# Credenciais (via variáveis de ambiente / arquivo .env)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv  # pip install python-dotenv (opcional)
    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # sem python-dotenv, exporte as variáveis no shell antes de rodar

SPRINGER_API_KEY = os.getenv("SPRINGER_API_KEY", "")
ELSEVIER_API_KEY = os.getenv("ELSEVIER_API_KEY", "")      # Scopus + ScienceDirect
ELSEVIER_INST_TOKEN = os.getenv("ELSEVIER_INST_TOKEN", "")  # opcional (fora da rede institucional)
IEEE_API_KEY = os.getenv("IEEE_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# E-mail de contato enviado à OpenAlex ("polite pool" = rate limit melhor).
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

# Modelo usado nas etapas de triagem por LLM (06/07 e 11/12).
LLM_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")


def require_env(var_name: str) -> str:
    """Retorna o valor da variável de ambiente ou aborta com uma mensagem
    clara, em vez de deixar a API responder 401/403 sem explicação."""
    value = os.getenv(var_name, "")
    if not value:
        raise SystemExit(
            f"Variável de ambiente {var_name} não definida.\n"
            f"Copie .env.example para .env e preencha, ou exporte no shell:\n"
            f"  export {var_name}=\"...\""
        )
    return value


# ---------------------------------------------------------------------------
# Blocos da string de busca (main term string do protocolo)
# Cada bloco é combinado com OR internamente, e os blocos são combinados
# com AND entre si.
#
# String completa do protocolo:
# (Logistics Operations) AND (AI Agents and Agentic AI)
# ---------------------------------------------------------------------------
SEARCH_BLOCKS = {
    "logistics_operations": [
        "logistics",
        "logistics operations",
        "logistic operations",
        "supply chain",
        "supply chain management",
        "intralogistics",
        "warehouse operations",
        "transportation logistics",
        "last-mile delivery",
    ],
    "ai_agents_agentic": [
        "AI agent",
        "AI agents",
        "agentic AI",
        "intelligent agent",
        "intelligent agents",
        "autonomous agent",
        "autonomous agents",
        "multi-agent system",
        "multi-agent systems",
        "agent-based system",
        "agent-based systems",
        "LLM agent",
        "LLM agents",
        "large language model agent",
        "large language model agents",
        "generative agent",
        "generative agents",
    ],
}

# Janela temporal (protocolo: January 2016 até a data de execução da busca)
YEAR_FROM = 2016
YEAR_TO = None  # None = sem limite superior (até o presente)

# Idioma
LANGUAGE = "en"

# ---------------------------------------------------------------------------
# Critérios de inclusão/exclusão — mantidos aqui só como referência para
# quem for revisar manualmente (filtro por abstract, full text etc.)
# ---------------------------------------------------------------------------
INCLUSION_CRITERIA = {
    "IC1": "Publicado em periódico, conferência ou workshop revisado por pares.",
    "IC2": "Contém termos que satisfazem a string de busca definida.",
    "IC3": "Escrito em inglês.",
    "IC4": "Publicado entre janeiro de 2016 e a data de execução da busca.",
    "IC5": "Aborda AI agents, agentic AI, intelligent agents, autonomous agents, "
           "multi-agent systems, LLM-based agents, generative agents ou "
           "abordagens agent-based correlatas.",
    "IC6": "Aplica essas abordagens a operações logísticas, supply chain, "
           "intralogística, operações de armazém, transporte ou last-mile delivery.",
    "IC7": "Aborda ao menos uma tarefa logística (planejamento, roteirização, "
           "escalonamento, previsão, otimização, coordenação, monitoramento, "
           "suporte à decisão, automação ou execução autônoma).",
}

EXCLUSION_CRITERIA = {
    "EC1": "Revisão de literatura, revisão sistemática, mapeamento sistemático, "
           "survey, revisão bibliométrica ou estudo secundário.",
    "EC2": "Editorial, prefácio, resenha de livro, resumo de pôster, resumo de "
           "keynote, resumo de tutorial, ou abstract curto sem conteúdo de pesquisa.",
    "EC3": "Não relacionado a operações logísticas / supply chain / intralogística "
           "/ operações de armazém / transporte / last-mile delivery.",
    "EC4": "Não aborda AI agents, agentic AI, intelligent agents, autonomous "
           "agents, multi-agent systems, LLM-based agents, generative agents "
           "ou abordagens agent-based correlatas.",
    "EC5": "Aplica ML, otimização, simulação, heurísticas ou programação "
           "matemática, mas sem componente agent-based ou agêntico.",
    "EC6": "Aborda IA generativa ou LLMs apenas como chatbot, gerador de texto "
           "ou assistente de propósito geral, sem comportamento agêntico, uso "
           "de ferramentas, planejamento autônomo, coordenação ou tomada de "
           "decisão logística.",
    "EC7": "Usa agent-based modeling apenas para simulação descritiva, sem "
           "tomada de decisão, automação, coordenação, otimização ou "
           "contribuição operacional logística.",
    "EC8": "Duplicado entre bases (mantém-se apenas uma ocorrência).",
    "EC9": "Publicado antes de janeiro de 2016.",
    "EC10": "Não escrito em inglês.",
}

# ---------------------------------------------------------------------------
# Bases de dados alvo e como cada uma entra no pipeline
# ---------------------------------------------------------------------------
DATABASES = {
    "openalex":       {"how": "api",    "key_env": None,               "connector": "connectors/openalex.py"},
    "springer":       {"how": "api",    "key_env": "SPRINGER_API_KEY", "connector": "connectors/springer.py"},
    "scopus":         {"how": "api",    "key_env": "ELSEVIER_API_KEY", "connector": "connectors/scopus.py"},
    "ieee_xplore":    {"how": "api",    "key_env": "IEEE_API_KEY",     "connector": "connectors/ieee_xplore.py"},
    "sciencedirect":  {"how": "manual", "key_env": "ELSEVIER_API_KEY", "connector": "connectors/sciencedirect.py (API pode exigir entitlement extra; na prática usou-se exportação manual)"},
    "web_of_science": {"how": "manual", "key_env": None,               "connector": "exportação BibTeX -> data/manual_exports/wos_*.bib"},
    "acm_dl":         {"how": "manual", "key_env": None,               "connector": "exportação BibTeX -> data/manual_exports/acm_*.bib"},
    "wiley":          {"how": "manual", "key_env": None,               "connector": "exportação BibTeX -> data/manual_exports/wiley_*.bib"},
    "taylor_francis": {"how": "manual", "key_env": None,               "connector": "exportação BibTeX -> data/manual_exports/tandf_*.bib"},
    "google_scholar": {"how": "manual", "key_env": None,               "connector": "Publish or Perish -> data/manual_exports/google_scholar_*.csv"},
}
