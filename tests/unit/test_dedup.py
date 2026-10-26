"""Unit test T027: RegistroMensajeProcesado (dedup)."""
import os
import tempfile

from src.services.dedup import RegistroMensajeProcesado


def test_existe_false_para_id_nuevo_y_true_tras_registrar():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "dedup.db")
        registro = RegistroMensajeProcesado(db_path)

        assert registro.existe(123) is False

        registro.registrar(123, "mail")

        assert registro.existe(123) is True


def test_registrar_es_idempotente():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "dedup.db")
        registro = RegistroMensajeProcesado(db_path)

        registro.registrar(5, "push")
        registro.registrar(5, "push")  # no debe lanzar excepción

        assert registro.existe(5) is True
