"""
Etapa Filter by Abstract via LLM (Claude Haiku 4.5 + Batch API).

Usa abstract quando disponível; cai para título+venue quando não tiver
(instruindo o modelo a ser mais rígido nesses casos — informação
insuficiente para confirmar os critérios = excluir).

Mesma arquitetura incremental do Filter by Title: pode ser rodado em
mais de uma execução sem reprocessar o que já tem decisão.

CUSTO ESTIMADO (~2.000 registros, Haiku 4.5 + Batch API): < US$ 0,50 (referência, out/2025)
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic

from config import LLM_MODEL, require_env

# Entrada: o corpus pós-título já enriquecido com abstracts do Scopus
# (etapa 10). Se a etapa 10 não foi rodada, usa o corpus da etapa 09.
_WITH_ABSTRACTS = os.path.join("data", "processed", "after_title_filter_with_abstracts.csv")
_CLEAN = os.path.join("data", "processed", "after_title_filter_clean.csv")
IN_PATH = _WITH_ABSTRACTS if os.path.exists(_WITH_ABSTRACTS) else _CLEAN
RESULTS_PATH = os.path.join("data", "processed", "abstract_screening_results.csv")
REGISTRY_PATH = os.path.join("data", "processed", "abstract_screening_batches_registry.json")

MODEL = LLM_MODEL  # definido em config.py / .env
ITEMS_PER_REQUEST = 15       # menos que no título, porque abstract é bem mais longo
BATCH_SIZE_ITEMS = 2100      # cobre tudo numa execução só (custo é baixo)
MAX_TOKENS_PER_REQUEST = 4096

SYSTEM_PROMPT = """Você está triando artigos (título + resumo) para uma revisão sistemática \
sobre "AI Agents and Agentic AI in Logistics Operations".

Para cada item, decida INCLUIR ou EXCLUIR com base nos critérios abaixo. Use o resumo \
quando disponível. QUANDO O RESUMO NÃO ESTIVER DISPONÍVEL (marcado como "[SEM ABSTRACT]"), \
julgue apenas pelo título e pelo periódico/venue — se a informação disponível não for \
suficiente para confirmar os critérios de inclusão com confiança, EXCLUA (na dúvida, exclua).

CRITÉRIOS DE INCLUSÃO — o estudo precisa satisfazer TODOS:
IC5: Aborda AI agents, agentic AI, intelligent agents, autonomous agents, multi-agent \
systems, LLM-based agents, generative agents, ou abordagens agent-based relacionadas.
IC6: Aplica essas abordagens a logistics operations, supply chain management, \
intralogistics, warehouse operations, transportation logistics, last-mile delivery, ou \
processos logísticos relacionados.
IC7: Aborda ao menos uma tarefa logística (planning, routing, scheduling, forecasting, \
optimization, coordination, monitoring, decision support, automation, ou autonomous \
execution).

CRITÉRIOS DE EXCLUSÃO — exclua se QUALQUER um se aplicar:
EC1: É revisão de literatura, revisão sistemática, mapeamento sistemático, survey, revisão \
bibliométrica, ou estudo secundário.
EC2: É editorial, prefácio, resenha de livro, resumo de pôster, resumo de keynote, resumo \
de tutorial, ou abstract curto sem conteúdo de pesquisa completo.
EC3: Não é relacionado a logistics operations, supply chain management, intralogistics, \
warehouse operations, transportation logistics, last-mile delivery, ou processos \
logísticos relacionados.
EC4: Não aborda AI agents, agentic AI, intelligent agents, autonomous agents, multi-agent \
systems, LLM-based agents, generative agents, ou abordagens agent-based relacionadas.
EC5: Aplica machine learning, otimização, simulação, heurísticas, ou programação \
matemática, mas SEM componente agent-based ou agêntico.
EC6: Aborda IA generativa ou LLMs apenas como chatbot, gerador de texto, ou assistente de \
propósito geral, sem comportamento agêntico, uso de ferramentas, planejamento autônomo, \
coordenação, ou tomada de decisão relacionada a logística.
EC7: Usa agent-based modeling apenas para simulação descritiva, sem tomada de decisão, \
automação, coordenação, otimização, ou contribuição operacional em logística.

Responda APENAS com um array JSON compacto, sem texto antes ou depois:
[{"i": 1, "d": "include", "r": "critério/motivo em até 8 palavras"}, {"i": 2, "d": "exclude", "r": "EC5: ..."}, ...]

"d" deve ser exatamente "include" ou "exclude". "r" deve citar o critério quando for exclusão \
(ex: "EC3: sem contexto logístico") e ser bem curto."""


def load_source_rows():
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), reader.fieldnames


def get_resolved_indices():
    resolved = set()
    if os.path.exists(RESULTS_PATH):
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if row.get("abstract_decision") in ("include", "exclude"):
                    resolved.add(i)
    return resolved


def get_in_flight_indices(registry):
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


def build_item_text(row) -> str:
    title = row.get("title", "")
    abstract = row.get("abstract", "").strip()
    venue = row.get("venue", "")
    if abstract:
        return f"Título: {title}\nVenue: {venue}\nAbstract: {abstract}"
    return f"Título: {title}\nVenue: {venue}\nAbstract: [SEM ABSTRACT]"


def build_user_content(items) -> str:
    blocks = [f"{i+1}. {build_item_text(row)}" for i, row in enumerate(items)]
    return "Itens a classificar:\n\n" + "\n\n".join(blocks)


def main():
    rows, _ = load_source_rows()
    registry = load_registry()

    resolved = get_resolved_indices()
    in_flight = get_in_flight_indices(registry)
    remaining = [i for i in range(len(rows)) if i not in resolved and i not in in_flight]

    print(f"Total de registros: {len(rows)}")
    print(f"Já resolvidos: {len(resolved)}")
    print(f"Em andamento: {len(in_flight)}")
    print(f"Restantes: {len(remaining)}")

    if not remaining:
        if in_flight:
            print("\nAinda há um batch pendente. Rode 12_llm_abstract_screening_retrieve.py.")
        else:
            print("\nTudo processado!")
        return

    slice_indices = remaining[:BATCH_SIZE_ITEMS]
    print(f"Enviando {len(slice_indices)} itens nesta execução.")

    sub_chunks = [slice_indices[i:i + ITEMS_PER_REQUEST]
                  for i in range(0, len(slice_indices), ITEMS_PER_REQUEST)]

    client = anthropic.Anthropic(api_key=require_env("ANTHROPIC_API_KEY"))
    requests = []
    chunk_map = {}
    run_id = len(registry)

    for i, idx_group in enumerate(sub_chunks):
        custom_id = f"run{run_id}-chunk{i}"
        items = [rows[idx] for idx in idx_group]
        requests.append({
            "custom_id": custom_id,
            "params": {
                "model": MODEL,
                "max_tokens": MAX_TOKENS_PER_REQUEST,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": build_user_content(items)}],
            },
        })
        chunk_map[custom_id] = idx_group

    batch = client.messages.batches.create(requests=requests)
    print(f"\nBatch criado: {batch.id} ({len(requests)} chamadas, {len(slice_indices)} itens)")

    registry.append({"batch_id": batch.id, "chunk_map": chunk_map, "retrieved": False})
    save_registry(registry)

    print("Rode 12_llm_abstract_screening_retrieve.py daqui a alguns minutos.")


if __name__ == "__main__":
    main()