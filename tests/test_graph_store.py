from app.core.graph_store import KnowledgeGraphStore, normalize_topic_name


def test_normalize_topic_name():
    assert normalize_topic_name("Parallel Computing") == "parallel_computing"
    assert normalize_topic_name("  IaaS (Infrastructure) ") == "iaas_infrastructure"
    assert normalize_topic_name("A---B") == "a_b"


def test_normalize_topic_name_hindi_and_kannada_survive():
    # A plain [a-z0-9] allowlist collapses these to an empty string, and
    # merge_into_graph (entity_extraction.py) silently drops nodes with an
    # empty id - so a Hindi/Kannada-only topic never made it into the graph.
    hindi = normalize_topic_name("प्रकाश संश्लेषण")
    kannada = normalize_topic_name("ಬೆಳಕಿನ ಸಂಶ್ಲೇಷಣೆ")
    assert hindi != ""
    assert kannada != ""
    assert hindi != kannada


def test_normalize_topic_name_hindi_preserves_combining_marks():
    # A bare \w-based allowlist excludes Unicode combining marks (category
    # M) - matras/virama - fragmenting every word at each one instead of
    # only at real word boundaries. Two words differing only by a matra
    # must stay distinct, not collapse to the same fragmented id.
    assert normalize_topic_name("किताब") != normalize_topic_name("कताब")


def test_normalize_topic_name_mixed_script():
    assert normalize_topic_name("प्रकाश Synthesis 2") == "प्रकाश_synthesis_2"


def test_graph_store_add_and_pagerank(graph_store):
    assert graph_store.graph.number_of_nodes() == 4
    assert graph_store.graph.number_of_edges() == 3

    scores = graph_store.compute_pagerank()
    assert set(scores.keys()) == set(graph_store.graph.nodes)
    assert all(0 <= v <= 1 for v in scores.values())


def test_graph_store_persists(tmp_path):
    path = tmp_path / "g.gpickle"
    gs = KnowledgeGraphStore(str(path))
    gs.add_topic("a", name="A")
    gs.save()

    reloaded = KnowledgeGraphStore(str(path))
    assert reloaded.graph.has_node("a")


def test_graph_store_empty_pagerank(tmp_path):
    gs = KnowledgeGraphStore(str(tmp_path / "empty.gpickle"))
    assert gs.compute_pagerank() == {}
