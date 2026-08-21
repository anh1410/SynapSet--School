from app.core import image_store


def test_save_and_resolve_image(tmp_path, monkeypatch):
    monkeypatch.setattr(image_store, "_images_dir", lambda: tmp_path)

    image_id = image_store.save_image(b"fake-png-bytes")
    path = image_store.image_path(image_id)

    assert path is not None
    assert path.read_bytes() == b"fake-png-bytes"


def test_unknown_id_resolves_to_none(tmp_path, monkeypatch):
    monkeypatch.setattr(image_store, "_images_dir", lambda: tmp_path)
    assert image_store.image_path("deadbeef00000000000000000000000") is None


def test_malformed_id_is_rejected_before_touching_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(image_store, "_images_dir", lambda: tmp_path)
    assert image_store.image_path("../../etc/passwd") is None
    assert image_store.image_path("not-a-hex-id") is None
    assert image_store.image_path("..\\..\\windows\\system32") is None
