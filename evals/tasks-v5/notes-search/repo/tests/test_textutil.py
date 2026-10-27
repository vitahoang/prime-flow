from jotter import textutil


def test_slugify():
    assert textutil.slugify("Café à Montréal!") == "cafe-a-montreal"
    assert textutil.slugify("???") == "untitled"
    assert len(textutil.slugify("word " * 40)) <= 60


def test_excerpt():
    body = "# Heading\n\nThe **first** line with a [link](http://x) in it.\n"
    assert textutil.excerpt(body) == "Heading"
    assert textutil.excerpt("\n\n" + "word " * 30, limit=20).endswith("…")


def test_word_count():
    assert textutil.word_count("un deux, trois\nquatre") == 4
