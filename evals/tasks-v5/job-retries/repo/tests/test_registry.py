import pytest

from taskmill.errors import UnknownJobKind
from taskmill.registry import Registry


def test_register_and_get():
    r = Registry()
    fn = r.register("a.b", lambda p: 1)
    assert r.get("a.b") is fn
    assert "a.b" in r and len(r) == 1


def test_decorator_form():
    r = Registry()

    @r.register("img.thumb")
    def thumb(p):
        return p

    assert r.get("img.thumb") is thumb


def test_bad_kind_rejected():
    with pytest.raises(ValueError):
        Registry().register("Not Valid", lambda p: None)


def test_duplicate_rejected():
    r = Registry()
    r.register("a", lambda p: None)
    with pytest.raises(ValueError):
        r.register("a", lambda p: None)


def test_unknown():
    with pytest.raises(UnknownJobKind):
        Registry().get("missing")


def test_load_builtin_modules():
    r = Registry()
    r.load_modules(["taskmill.handlers"])
    assert r.kinds() == ["email.send", "image.thumbnail", "webhook.deliver"]
