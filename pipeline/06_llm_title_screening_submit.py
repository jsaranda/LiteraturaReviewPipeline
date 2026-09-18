"""
Etapa Filter by Title via LLM (Claude Haiku 4.5 + Batch API), em lotes
INCREMENTAIS: cada execução processa só os próximos BATCH_SIZE_TITLES
títulos que ainda NÃO têm uma decisão resolvida no CSV de resultado —
isso inclui tanto títulos nunca enviados quanto títulos cujo lote deu
erro de parse anteriormente (retry automático, sem script separado).

FLUXO:
1. Rode este script -> envia os próximos títulos pendentes.
2. Espere um pouco, rode 07_llm_title_screening_retrieve.py.
3. Confira a qualidade dessa leva.
4. Rode este script de novo -> pega a próxima fatia (e reprocessa
   automaticamente qualquer título que tenha falhado antes).
5. Repete até "Restantes: 0".

CUSTO POR EXECUÇÃO (3.000 títulos, Haiku 4.5 + Batch API): ~US$ 0,19 (referência, out/2025)
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from config import LLM_MODEL, require_env

IN_PATH = os.path.join("data", "processed", "after_language_filter.csv")
RESULTS_PATH = os.path.join("data", "processed", "title_screening_results.csv")
REGISTRY_PATH = os.path.join("data", "processed", "title_screening_batches_registry.json")

MODEL = LLM_MODEL  # definido em config.py / .env
TITLES_PER_REQUEST = 75         # reduzido de 100 -> 75, mais folga de max_tokens por chamada
BATCH_SIZE_TITLES = 3000
MAX_TOKENS_PER_REQUEST = 4096   # aumentado de 3000 -> evita truncar o JSON de resposta

SYSTEM_PROMPT = """Você está triando títulos de artigos para uma revisão sistemática sobre \
"AI Agents and Agentic AI in Logistics Operations".

Decida INCLUIR ou EXCLUIR cada título com base SOMENTE no texto do título \
(sem inferir conteúdo que não esteja explícito). Critérios:

INCLUIR somente se o título tiver AMBOS:
(A) Termo explícito de agente: "AI agent(s)", "agentic AI", "intelligent agent(s)", \
"autonomous agent(s)", "multi-agent system(s)", "agent-based system(s)", "LLM agent(s)", \
"large language model agent(s)", "generative agent(s)", ou variação clara e direta desses termos.
(B) Contexto explícito de logística: "logistics", "supply chain", "intralogistics", \
"warehouse operations", "transportation logistics", "last-mile delivery", ou variação \
clara e direta desses termos (ex: "delivery", "routing", "vehicle routing", "supply chain \
management", "warehouse", "port operations", "fleet" quando claramente ligados a operações \
logísticas — NÃO conte "port"/"transport" isolados fora de contexto logístico, ex: rede \
elétrica, transporte público de passageiros).

EXCLUIR em qualquer um destes casos:
- Falta (A) ou falta (B) no título — verifique literalmente, não infira nem "empreste" \
contexto de domínio que o título não afirma (ex: não assuma "supply chain" só porque o tema \
parece industrial/empresarial).
- O termo "agent"/"agency" aparece em sentido NÃO relacionado a IA (ex: agência de viagem, \
agência governamental, agência humana/social, trabalhador rural, migração).
- É claramente uma revisão de literatura, survey, mapeamento sistemático (ex: "A Survey", \
"A Review", "Systematic Review", "Systematic Mapping", "Comprehensive Survey").
- Usa "robot(s)"/"robotic"/RL puro (actor-critic, policy gradient, deep RL) SEM mencionar \
literalmente um dos termos de agente da lista (A) — não infira que robô ou política de RL \
seja "agente" para fins deste critério.
- Aborda ML/otimização/simulação/heurísticas SEM componente de agente explícito.
- Modelagem baseada em agentes (agent-based modeling) usada só para simulação descritiva \
(ex: comportamento social, epidemiologia, adoção de tecnologia), sem contribuição \
operacional/decisória em logística.
- Termos que soam similares mas são de outro domínio (ex: "last mile" de rede elétrica de \
distribuição de energia, não de entrega/logística).

Na dúvida, EXCLUA. Este é um critério propositalmente rígido e literal — não amplie por \
interpretação ou conhecimento externo sobre o artigo. Não invente conexão com logística ou \
supply chain que o título não afirme explicitamente.

Responda APENAS com um array JSON compacto, sem nenhum texto antes ou depois, no formato:
[{"i": 1, "d": "include", "r": "motivo em até 5 palavras"}, {"i": 2, "d": "exclude", "r": "..."}, ...]

"d" deve ser exatamente "include" ou "exclude". "r" deve ser bem curto (máximo 5 palavras)."""


def load_source_rows():
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def get_resolved_indices():
    """Índices com decisão real (include/exclude) já no CSV de resultado."""
    resolved = set()
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if row.get("title_decision") in ("include", "exclude"):
                    resolved.add(i)
    return resolved


def get_in_flight_indices(registry):
    """Índices em batches ainda não recuperados (evita reenviar enquanto processa)."""
    in_flight = set()
    for entry in registry:
        if not entry.get("retrieved", False):
            for indices in entry["chunk_map"].values():
                in_flight.update(indices)
    return in_flight


def load_registry():
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_registry(registry):
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f)


def build_user_content(titles):
    lines = [f"{i+1}. {t}" for i, t in enumerate(titles)]
    return "Títulos a classificar:\n\n" + "\n".join(lines)


def main():
    rows, _ = load_source_rows()
    registry = load_registry()

    resolved = get_resolved_indices()
    in_flight = get_in_flight_indices(registry)

    remaining = [i for i in range(len(rows)) if i not in resolved and i not in in_flight]

    print(f"Total de títulos: {len(rows)}")
    print(f"Já resolvidos (include/exclude): {len(resolved)}")
    print(f"Em andamento (batch pendente de retrieve): {len(in_flight)}")
    print(f"Restantes: {len(remaining)}")

    if not remaining:
        if in_flight:
            print("\nNada novo para enviar — ainda há um batch pendente. "
                  "Rode 07_llm_title_screening_retrieve.py.")
        else:
            print("\nTudo processado!")
        return

    slice_indices = remaining[:BATCH_SIZE_TITLES]
    print(f"Enviando {len(slice_indices)} títulos nesta execução.")

    sub_chunks = [slice_indices[i:i + TITLES_PER_REQUEST]
                  for i in range(0, len(slice_indices), TITLES_PER_REQUEST)]

    client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    requests = []
    chunk_map = {}
    run_id = len(registry)

    for i, idx_group in enumerate(sub_chunks):
        custom_id = f"run{run_id}-chunk{i}"
        titles = [rows[idx]["title"] for idx in idx_group]
        requests.append({
            "custom_id": custom_id,
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS_PER_REQUEST,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": build_user_content(titles)}],
            },
        })
        chunk_map[custom_id] = idx_group

    batch = client.messages.batches.create(requests=requests)
    print(f"\nBatch criado: {batch.id} ({len(requests)} chamadas, {len(slice_indices)} títulos)")

    registry.append({"batch_id": batch.id, "chunk_map": chunk_map, "retrieved": False})
    save_registry(registry)

    print("Rode 07_llm_title_screening_retrieve.py daqui a alguns minutos.")


if __name__ == "__main__":
    main()