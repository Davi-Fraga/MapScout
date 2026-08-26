"""Verifica que o pacote importa e expõe a versão."""

import mapscout


def test_pacote_expoe_versao() -> None:
    assert isinstance(mapscout.__version__, str)
    assert mapscout.__version__ == "0.1.0"
