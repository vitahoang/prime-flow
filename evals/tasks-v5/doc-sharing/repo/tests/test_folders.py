from folio import folders


def test_ancestors_nearest_first(world):
    s = world["store"]
    deep = s.create_folder(world["ws"], "Drawings", world["olive"], world["harbour"])
    assert folders.ancestors(s, deep) == [deep, world["harbour"], world["projects"]]
    assert folders.depth(s, deep) == 2


def test_paths(world):
    s = world["store"]
    assert folders.path(s, world["harbour"]) == "/Projects/Harbour"
    assert folders.document_path(s, world["doc"]) == "/Projects/Harbour/Brief"
    assert folders.find(s, world["ws"], "/Projects/Harbour").id == world["harbour"]
    assert folders.find(s, world["ws"], "/Projects/Nope") is None


def test_documents_in_recursive(world):
    s = world["store"]
    top = s.create_document(world["projects"], "Index", world["olive"])
    assert [d.id for d in folders.documents_in(s, world["projects"])] == [top]
    got = {d.id for d in folders.documents_in(s, world["projects"], recursive=True)}
    assert got == {top, world["doc"]}
