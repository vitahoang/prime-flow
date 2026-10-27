from jotter import links


def test_extract_forms():
    body = "See [[Garden plan]], [[Tomato varieties|tomatoes]] and [[Garden plan#Seeds]]."
    assert links.extract(body) == ["Garden plan", "Tomato varieties", "Garden plan"]


def test_resolve_and_backlinks(store):
    a = store.create("Garden plan", body="See [[Tomato varieties]].\n")
    b = store.create("Tomato varieties")
    assert links.resolve(store, "Tomato varieties") == b.path
    assert [n.path for n in links.backlinks(store, b)] == [a.path]


def test_broken(store):
    store.create("Lonely", body="[[Nowhere]]\n")
    assert [(n.title, t) for n, t in links.broken(store)] == [("Lonely", "Nowhere")]


def test_rewrite_target_keeps_label():
    body = "[[Old|label]] and [[Old#Part]] and [[Other]]"
    assert links.rewrite_target(body, "Old", "New") == "[[New|label]] and [[New#Part]] and [[Other]]"


def test_sample_vault_links_resolve(sample):
    assert links.broken(sample) == []
