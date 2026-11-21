"""
Testes de unidade: chamam as funções do servidor diretamente, como Python comum.
Verificam a lógica das tools, resources e prompt, sem passar pelo protocolo MCP.
"""

import json

import research_server as rs

# ───────────────────── search_papers ─────────────────────

def test_search_papers_devolve_ids(papers_dir, fake_arxiv):
    ids = rs.search_papers("LLM interpretability", max_results=3)
    assert ids == ["2601.00001v1", "2601.00002v1", "2601.00003v1"]


def test_search_papers_repassa_parametros_ao_arxiv(papers_dir, fake_arxiv):
    rs.search_papers("física quântica", max_results=2)
    assert fake_arxiv == [{"query": "física quântica", "max_results": 2}]


def test_search_papers_usa_5_resultados_por_padrao(papers_dir, fake_arxiv):
    assert len(rs.search_papers("llm")) == 5


def test_search_papers_salva_json_na_pasta_do_tema(papers_dir, fake_arxiv):
    rs.search_papers("LLM interpretability", max_results=1)
    arquivo = papers_dir / "llm_interpretability" / "papers_info.json"
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    paper = dados["2601.00001v1"]
    assert paper["authors"] == ["Ana Silva", "Bruno Lima"]
    assert paper["published"] == "2026-01-01"
    assert set(paper) == {"title", "authors", "summary", "pdf_url", "published"}


def test_search_papers_acumula_buscas_no_mesmo_tema(papers_dir, monkeypatch):
    from conftest import FakePaper

    monkeypatch.setattr(rs.arxiv.Client, "results", lambda self, s: [FakePaper(1)])
    rs.search_papers("llm")
    monkeypatch.setattr(rs.arxiv.Client, "results", lambda self, s: [FakePaper(2)])
    rs.search_papers("llm")

    dados = json.loads((papers_dir / "llm" / "papers_info.json").read_text(encoding="utf-8"))
    assert set(dados) == {"2601.00001v1", "2601.00002v1"}


def test_search_papers_nao_escreve_no_stdout(papers_dir, fake_arxiv, capsys):
    """No stdio, o stdout é o canal do protocolo: logs precisam ir para o stderr."""
    rs.search_papers("llm", max_results=1)
    saida = capsys.readouterr()
    assert saida.out == ""
    assert "Resultados salvos" in saida.err


# ───────────────────── extract_info ─────────────────────

def test_extract_info_sem_pasta_nao_quebra(papers_dir):
    assert "search_papers first" in rs.extract_info("2601.00001v1")


def test_extract_info_encontra_artigo_salvo(papers_salvos):
    info = json.loads(rs.extract_info(papers_salvos[0]))
    assert info["title"].startswith("Paper 1")


def test_extract_info_artigo_inexistente(papers_salvos):
    assert "no saved information" in rs.extract_info("9999.99999v9")


# ───────────────────── resources ─────────────────────

def test_resource_folders_vazio(papers_dir):
    assert "No topics found" in rs.get_available_folders()


def test_resource_folders_lista_temas(papers_salvos):
    assert "- llm_interpretability" in rs.get_available_folders()


def test_resource_topico_formata_markdown(papers_salvos):
    texto = rs.get_topic_papers("llm_interpretability")
    assert texto.startswith("# Papers on Llm Interpretability")
    assert "Total: 2" in texto
    assert "**Authors**: Ana Silva, Bruno Lima" in texto


def test_resource_topico_aceita_espacos(papers_salvos):
    assert "Total: 2" in rs.get_topic_papers("LLM interpretability")


def test_resource_topico_inexistente(papers_dir):
    assert "No papers found" in rs.get_topic_papers("astronomia")


# ───────────────────── prompt ─────────────────────

def test_prompt_inclui_tema_e_quantidade():
    texto = rs.generate_search_prompt("history", num_papers=2)
    assert "'history'" in texto
    assert "find 2 papers" in texto
    assert "search_papers" in texto
