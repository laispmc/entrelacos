"""Funções auxiliares usadas em várias partes do sistema."""
import re
from datetime import date

MESES = ["jan", "fev", "mar", "abr", "mai", "jun",
         "jul", "ago", "set", "out", "nov", "dez"]


def normalizar_telefone(valor):
    """Mantém apenas os dígitos do telefone (ex.: '(27) 99999-1234' -> '27999991234')."""
    return re.sub(r"\D", "", valor or "")


def telefone_valido(valor):
    """Aceita telefones brasileiros com DDD: 10 dígitos (fixo) ou 11 (celular)."""
    digitos = normalizar_telefone(valor)
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    if len(digitos) not in (10, 11):
        return False
    if digitos[0] == "0":
        return False
    if len(digitos) == 11 and digitos[2] != "9":
        return False
    return True


def telefone_padrao(valor):
    """Retorna o telefone apenas com DDD + número, sem o código do país."""
    digitos = normalizar_telefone(valor)
    if digitos.startswith("55") and len(digitos) in (12, 13):
        digitos = digitos[2:]
    return digitos


def formatar_telefone(digitos):
    """Formata para exibição na área administrativa."""
    if len(digitos) == 11:
        return f"({digitos[:2]}) {digitos[2:7]}-{digitos[7:]}"
    if len(digitos) == 10:
        return f"({digitos[:2]}) {digitos[2:6]}-{digitos[6:]}"
    return digitos


def formatar_data(valor, formato="curto"):
    if not valor:
        return ""
    if formato == "longo" and isinstance(valor, date):
        return f"{valor.day:02d} {MESES[valor.month - 1]} {valor.year}"
    if hasattr(valor, "hour"):
        return valor.strftime("%d/%m/%Y %H:%M")
    return valor.strftime("%d/%m/%Y")


def formatar_quantidade(valor):
    """Exibe 5 em vez de 5.0 e usa vírgula como separador decimal."""
    if valor is None:
        return "0"
    if float(valor).is_integer():
        return str(int(valor))
    return f"{valor:.2f}".rstrip("0").replace(".", ",")
