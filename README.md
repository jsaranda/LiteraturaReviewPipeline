# lit_review_pipeline — busca e triagem para revisão sistemática

Pipeline em Python (scripts independentes, sem framework) para automatizar a
parte pesada de uma revisão sistemática de literatura: busca em várias bases,
remoção de impurezas, triagem por título e por abstract com apoio de LLM,
combinação e deduplicação, e geração da planilha para a leitura em três
passadas. O fluxo segue o funil clássico:

```
Initial Search → Impurity Removal → Filter by Title → Filter by Abstract
→ Combination → Duplicate Removal → Addition by Heuristics → Three-pass filter
```

Cada base percorre o próprio funil (impurezas → título → abstract) e só no fim
tudo é combinado e deduplicado — assim a tabela "por base" do artigo sai
direto dos arquivos intermediários.

O pipeline foi usado pela primeira vez na revisão *"AI Agents and Agentic AI in
Logistics Operations: A Systematic Literature Review and Taxonomy"*. A string
de busca, a janela temporal e os critérios dessa revisão estão em `config.py`
como exemplo — para outra revisão, troque-os lá (e ajuste os prompts das
etapas 06 e 11, que descrevem o tema em linguagem natural).

---

## 1. Instalação

```bash
git clone <este repositório>
cd lit_review_pipeline
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Requer Python 3.10+.

### Credenciais

Nenhuma chave fica no código. Copie `.env.example` para `.env` e preencha:

| Variável | Para quê | Onde obter |
|---|---|---|
| `SPRINGER_API_KEY` | Springer Nature Meta API | https://dev.springernature.com/ |
| `ELSEVIER_API_KEY` | Scopus Search API, Abstract Retrieval API, ScienceDirect | https://dev.elsevier.com/ |
| `ELSEVIER_INST_TOKEN` | opcional; só se a Elsevier fornecer (uso fora da rede institucional) | e-mail à Elsevier |
| `IEEE_API_KEY` | IEEE Xplore Metadata Search API | https://developer.ieee.org/ |
| `ANTHROPIC_API_KEY` | triagem por LLM (etapas 06/07 e 11/12) | https://console.anthropic.com/ |
| `OPENALEX_MAILTO` | seu e-mail (OpenAlex "polite pool"; não é chave) | — |
| `LLM_MODEL` | opcional; modelo da triagem (padrão `claude-haiku-4-5-20251001`) | — |

O `.env` está no `.gitignore`. Se preferir, exporte as variáveis no shell em vez
de usar o arquivo. Um script que precisa de uma chave ausente aborta com uma
mensagem dizendo qual variável falta.

**Todos os scripts devem ser executados a partir da raiz do projeto** (os
caminhos `data/...` são relativos a ela).

---

## 2. Estrutura

```
config.py                   protocolo (string de busca, critérios, janela) + credenciais via .env
connectors/                 busca automática por API → data/raw/<base>_results.csv
  base.py                   schema comum (Paper) e normalização de DOI/título
  openalex.py  springer.py  scopus.py  ieee_xplore.py  sciencedirect.py
  diagnostics/              testes de chave/query e contagem de totais (opcionais)
ingest/manual_import.py     lê exportações BibTeX/CSV de data/manual_exports/
pipeline/                   etapas numeradas, na ordem de execução (01 → 16)
  extras/                   relatórios e amostragens para conferência (não geram arquivos do fluxo)
heuristics/                 "Addition by Heuristics": reavaliação manual de candidatos a falso negativo
data/
  raw/                      saída dos conectores (ignorado pelo git)
  manual_exports/           .bib/.csv exportados à mão das bases sem API (ignorado pelo git)
  processed/                arquivos intermediários e finais (ignorado pelo git)
  heuristic_lists/          listas de títulos para heuristics/ (exemplos da primeira revisão)
  initial_search_counts.json  totais da busca inicial por base (preenchido à mão, ver §5)
```

Os arquivos de dados não são versionados (facilmente passam de 250 MB). Cada
pessoa gera os seus rodando o pipeline.

---

## 3. Etapa 0 — Initial Search (coleta)

### 3a. Bases com API

```bash
python connectors/openalex.py        # sem chave
python connectors/springer.py        # 500 req/dia; retomável: python connectors/springer.py <start>
python connectors/scopus.py          # não retorna abstract (resolvido na etapa 10)
python connectors/ieee_xplore.py     # 200 req/dia
python connectors/sciencedirect.py   # só se a chave Elsevier tiver entitlement (senão dá 401 → use exportação manual)
```

Cada um grava `data/raw/<base>_results.csv` no schema comum
(`source_db, title, authors, year, venue, doi, abstract, url, raw_id, query_used`).
Os conectores respeitam os limites de cota e imprimem de onde retomar caso a
cota diária acabe (o da Springer faz *append* no CSV ao retomar). Antes de
uma busca completa, vale rodar os `connectors/diagnostics/*_test.py` para
confirmar que a chave está ativa sem gastar cota.

### 3b. Bases sem API (exportação manual)

ACM DL, Wiley, Taylor & Francis, Web of Science, ScienceDirect (via site) e
Google Scholar (via *Publish or Perish*): faça a busca no site com a mesma
string de `config.py`, exporte em **BibTeX** (ou CSV, no caso do Publish or
Perish) e salve em `data/manual_exports/` com o nome começando pelo prefixo da
base — ele é o que define o `source_db`:

| Prefixo do arquivo | source_db |
|---|---|
| `acm_*` | acm_dl |
| `wiley_*` | wiley |
| `tandf_*` ou `taylor_*` | taylor_francis |
| `wos_*` | web_of_science |
| `sciencedirect_*` ou `sd_*` | sciencedirect |
| `google_scholar_*` ou `scholar_*` | google_scholar |

Confira a contagem com `python ingest/manual_import.py`. Os `.bib` originais
são lidos de novo nas etapas 02 e 15 (tipo de publicação e número de páginas),
então mantenha-os na pasta até o fim.

---

## 4. Pipeline principal (`pipeline/01_…16_`)

Rode na ordem. Cada script lê o arquivo da etapa anterior em
`data/processed/` e grava o seguinte; os scripts imprimem as contagens
(antes / excluídos / restantes) que vão para a tabela do funil.

| # | Script | Lê | Gera | O que faz |
|---|---|---|---|---|
| 01 | `01_build_raw_pool.py` | `data/raw/*.csv` + `data/manual_exports/*` | `raw_pool_no_dedup.csv` | Junta tudo **sem** deduplicar (ponto de partida do funil por base) |
| 02 | `02_check_publication_type.py` | raw_pool | `publication_type_check.csv` | Tipo de publicação (do `.bib`) + flag de título suspeito (erratum, editorial…) |
| 03 | `03_apply_impurity_filters.py` | publication_type_check | `after_type_filter.csv` | Remove livros, proceedings inteiros, capítulos, relatórios, títulos suspeitos (EC1/EC2) |
| 04 | `04_check_language.py` | raw_pool | `language_check.csv` | Detecta idioma por título+abstract (`langdetect`, seed fixa) |
| 05 | `05_apply_language_filter.py` | after_type_filter + language_check | `after_language_filter.csv` | Remove não-inglês confirmado (EC10). **Fim do Impurity Removal** |
| 06 | `06_llm_title_screening_submit.py` | after_language_filter | `title_screening_batches_registry.json` | Envia títulos ao Claude (Batch API) em fatias de 3.000 |
| 07 | `07_llm_title_screening_retrieve.py` | registry | `title_screening_results.csv` | Recupera as decisões dos batches prontos (acumulativo) |
| 08 | `08_apply_title_filter.py` | title_screening_results | `after_title_filter.csv` | Mantém só `include` |
| 09 | `09_apply_ssrn_retracted_filter.py` | after_title_filter | `after_title_filter_clean.csv` | Remove preprints SSRN e retratados. **Fim do Filter by Title** |
| 10 | `10_fetch_missing_scopus_abstracts.py` | after_title_filter_clean | `after_title_filter_with_abstracts.csv` | Busca abstracts do Scopus na Abstract Retrieval API (1 chamada/DOI) |
| 11 | `11_llm_abstract_screening_submit.py` | with_abstracts (ou clean, se 10 não rodou) | `abstract_screening_batches_registry.json` | Envia título+venue+abstract ao Claude (Batch API) |
| 12 | `12_llm_abstract_screening_retrieve.py` | registry | `abstract_screening_results.csv` | Recupera as decisões |
| 13 | `13_apply_abstract_filter.py` | abstract_screening_results | `after_abstract_filter.csv` | Mantém só `include`. **Fim do Filter by Abstract** |
| 14 | `14_final_combination.py` | after_abstract_filter | `final_combined_deduplicated.csv` | **Combination + Duplicate Removal** por DOI (fallback título); entre duplicatas, prefere a cópia com abstract |
| 15 | `15_apply_short_paper_filter.py` | final_combined_deduplicated + `.bib` | `final_after_ec6.csv` | Remove artigos com ≤ 4 páginas (só bases manuais têm essa info) |
| 16 | `16_generate_three_pass_tracking_sheet.py` | final_after_ec6 | `Three_Pass_Tracking.xlsx` | Planilha de acompanhamento da leitura em três passadas (coluna "Válido? S/N") |

### Como funcionam as etapas de LLM (06/07 e 11/12)

As triagens usam a **Message Batches API** da Anthropic (50 % mais barata,
processamento assíncrono). O fluxo é *submit → esperar alguns minutos →
retrieve*, repetido até o submit dizer "Tudo processado!":

```bash
python pipeline/06_llm_title_screening_submit.py     # envia a próxima fatia pendente
# ... aguarde (minutos) ...
python pipeline/07_llm_title_screening_retrieve.py   # funde o que já terminou no CSV
python pipeline/06_llm_title_screening_submit.py     # próxima fatia (reenvia falhas de parse automaticamente)
```

O progresso fica em `*_batches_registry.json` + `*_results.csv`, então dá para
parar e continuar outro dia. Os prompts (critérios em linguagem natural) estão
no topo de `06_…submit.py` e `11_…submit.py` — são a parte a adaptar para outra
revisão. Custo de referência (Haiku 4.5, out/2025): ~US$ 0,19 por 3.000
títulos; < US$ 0,50 para ~2.000 abstracts.

Antes de aplicar o filtro (08 / 13), confira uma amostra das decisões com
`pipeline/extras/sample_titles_for_calibration.py` e
`pipeline/extras/sample_abstract_decisions.py`.

---

## 5. Extras (conferência, opcionais)

Todos em `pipeline/extras/`, só imprimem no terminal, nunca alteram o fluxo:

| Script | Quando usar |
|---|---|
| `report_per_base_funnel.py` | Tabela do funil por base (Initial → Impurity → Title → Abstract). A coluna *Initial* vem de `data/initial_search_counts.json`, preenchido à mão com o total que cada base reportou (os `connectors/diagnostics/*_count_check.py` ajudam); sem o arquivo, usa a contagem do pool bruto |
| `review_language_flags.py [idioma]` | Lista os títulos marcados como não-inglês pela etapa 04, antes de aplicar a 05 |
| `sample_titles_for_calibration.py` | Amostra estratificada de títulos para calibrar o prompt da etapa 06 |
| `sample_abstract_decisions.py` | Amostra das decisões da etapa 12 (include/exclude por base) para revisão |
| `check_ssrn_and_retracted.py` | Pré-visualiza o que a etapa 09 vai remover |
| `check_abstract_coverage.py` | % de registros com abstract por base após o Filter by Title |
| `check_abstract_recovery_via_dedup.py` | Quantos "sem abstract" têm duplicata com abstract em outra base |
| `check_short_papers.py` | Pré-visualiza o que a etapa 15 vai remover |
| `diag_scopus_abstract_retrieval.py` | Testa a Abstract Retrieval API com um DOI (usado para descobrir que é preciso `view=FULL`) |

---

## 6. Addition by Heuristics (`heuristics/`)

Parte **manual** do processo: depois do Filter by Title, revisa-se a lista de
excluídos em busca de falsos negativos (ex.: títulos com só um dos dois blocos
da string de busca, ou com ambos mas ainda assim excluídos pelo LLM). Isso
gera listas de candidatos que precisam ser lidos pelo abstract. Os scripts:

1. **Monte a lista** de candidatos num `.txt` (uma linha por artigo, formato
   `source_db|~|título|~|ano|~|venue|~|url`). Os três arquivos em
   `data/heuristic_lists/` são as listas reais da primeira revisão e servem
   de exemplo de formato — apague-os ou substitua pelos seus.
2. `python heuristics/check_abstract_for_list.py data/heuristic_lists/lista.txt`
   → gera `data/processed/Abstracts_lista.xlsx` com o abstract de cada artigo
   que já esteja em algum CSV intermediário.
3. `python heuristics/fetch_abstracts_for_list.py data/heuristic_lists/lista.txt`
   → para os que ficaram sem abstract, tenta buscar na OpenAlex e no Semantic
   Scholar (sem chave). Gera `lista_com_abstracts.csv` ao lado da lista.
4. `python heuristics/prioritize_list_review.py data/processed/Abstracts_lista.xlsx`
   → adiciona uma coluna "Prioridade" (ALTA = menciona LLM/agentic/etc.,
   BAIXA = só multiagente clássico) para você ler primeiro o que importa.
5. Os artigos aprovados nessa revisão manual entram no corpus final à mão
   (na planilha da etapa 16).

---

## 7. Resumo de uma execução completa

```bash
# 0. coleta
python connectors/openalex.py; python connectors/springer.py
python connectors/scopus.py;   python connectors/ieee_xplore.py
#    + exportações manuais em data/manual_exports/

# 1. impurity removal
python pipeline/01_build_raw_pool.py
python pipeline/02_check_publication_type.py
python pipeline/03_apply_impurity_filters.py
python pipeline/04_check_language.py
python pipeline/extras/review_language_flags.py      # opcional
python pipeline/05_apply_language_filter.py

# 2. filter by title (repita 06/07 até "Tudo processado!")
python pipeline/06_llm_title_screening_submit.py
python pipeline/07_llm_title_screening_retrieve.py
python pipeline/08_apply_title_filter.py
python pipeline/09_apply_ssrn_retracted_filter.py

# 3. filter by abstract
python pipeline/10_fetch_missing_scopus_abstracts.py
python pipeline/11_llm_abstract_screening_submit.py
python pipeline/12_llm_abstract_screening_retrieve.py
python pipeline/extras/sample_abstract_decisions.py   # opcional
python pipeline/13_apply_abstract_filter.py

# 4. combination + dedup + EC6 + planilha
python pipeline/14_final_combination.py
python pipeline/15_apply_short_paper_filter.py
python pipeline/16_generate_three_pass_tracking_sheet.py

# 5. funil por base para o artigo
python pipeline/extras/report_per_base_funnel.py
```

---

## 8. Limitações conhecidas

- A Scopus Search API e a ScienceDirect Search API não devolvem abstract; a
  etapa 10 resolve para o Scopus (uma chamada por DOI). Registros de bases
  manuais sem abstract no `.bib` são julgados na etapa 11 só por título+venue,
  com instrução de excluir na dúvida.
- Tipo de publicação (etapa 02) e número de páginas (etapa 15) só existem
  para as bases importadas por BibTeX; para as bases via API vale apenas a
  heurística de título suspeito.
- `langdetect` erra em textos muito curtos; a etapa 04 marca como `unknown`
  (e não exclui) qualquer registro com menos de 60 caracteres.
- Os conectores foram escritos contra a documentação pública de cada API em
  2025; se uma API mudar, `connectors/diagnostics/` ajuda a isolar o problema
  sem gastar cota.
