from __future__ import annotations

import re
from decimal import Decimal


NOME_MIN = 3
NOME_MAX = 100
SALA_MAX = 10
NOTA_MIN = Decimal("0")
NOTA_MAX = Decimal("10")
NOTA_CASAS_DECIMAIS = 2
NOTAS_LIMITE = 10
COMPORTAMENTO_MAX = 500

_PADRAO_SALA = re.compile(r"[0-9]{1,2}[A-Z]{1,2}")
_PADRAO_NOTA = re.compile(r"([0-9]+)(?:[.,]([0-9]+))?")
_SEPARADORES_NOTAS = re.compile(r"[;\s]+")


class ErroValidacao(ValueError):

    def __init__(self, campo: str, mensagem: str):
        super().__init__(mensagem)
        self.campo = campo
        self.mensagem = mensagem


def validar_nome(texto: str) -> str:

    nome = (texto or "").strip()
    if not nome:
        raise ErroValidacao("nome", "Informe o nome do aluno. Este campo é obrigatório.")
    if not NOME_MIN <= len(nome) <= NOME_MAX:
        raise ErroValidacao(
            "nome",
            f"O nome deve ter de {NOME_MIN} a {NOME_MAX} caracteres "
            f"(atualmente tem {len(nome)}).",
        )
    if not all(caractere.isalpha() or caractere == " " for caractere in nome):
        raise ErroValidacao(
            "nome", "O nome deve conter apenas letras, espaços e acentos (sem números ou símbolos)."
        )
    return nome


def validar_sala(texto: str) -> str:
    
    bruto = (texto or "").strip()
    if not bruto:
        raise ErroValidacao("sala", "Informe a sala do aluno. Este campo é obrigatório.")
    if len(bruto) > SALA_MAX:
        raise ErroValidacao("sala", f"A sala deve ter no máximo {SALA_MAX} caracteres.")
    sala = re.sub(r"[\s\u00ba\u00b0]", "", bruto).upper()  
    if not _PADRAO_SALA.fullmatch(sala):
        raise ErroValidacao(
            "sala", "Sala inválida. Use o padrão série + turma, por exemplo: 8B ou 9A."
        )
    return sala


def validar_nota(texto: str) -> float:
    
    token = (texto or "").strip()
    if not token:
        raise ErroValidacao("nota", "Informe a nota.")
    partes = _PADRAO_NOTA.fullmatch(token)
    if not partes:
        raise ErroValidacao(
            "nota",
            f"Nota inválida: '{token}'. Use números de 0 a 10 com até "
            f"{NOTA_CASAS_DECIMAIS} casas decimais (exemplo: 7,5).",
        )
    decimais = partes.group(2) or ""
    if len(decimais) > NOTA_CASAS_DECIMAIS:
        raise ErroValidacao(
            "nota", f"A nota '{token}' tem mais de {NOTA_CASAS_DECIMAIS} casas decimais."
        )
    valor = Decimal(token.replace(",", "."))
    if not NOTA_MIN <= valor <= NOTA_MAX:
        raise ErroValidacao("nota", f"A nota '{token}' está fora do limite. Use valores de 0 a 10.")
    return float(valor)


def validar_notas(texto: str) -> list[float]:
   
    partes = [p.rstrip(",") for p in _SEPARADORES_NOTAS.split((texto or "").strip())]
    partes = [p for p in partes if p]
    if len(partes) > NOTAS_LIMITE:
        raise ErroValidacao(
            "notas", f"Limite excedido: cada aluno pode ter no máximo {NOTAS_LIMITE} notas."
        )
    notas = []
    for parte in partes:
        try:
            notas.append(validar_nota(parte))
        except ErroValidacao as erro:
            raise ErroValidacao("notas", erro.mensagem) from None
    return notas


def validar_comportamento(texto: str) -> str:

    relato = (texto or "").strip()
    if len(relato) > COMPORTAMENTO_MAX:
        raise ErroValidacao(
            "comportamento",
            f"A avaliação comportamental deve ter no máximo {COMPORTAMENTO_MAX} caracteres "
            f"(atualmente tem {len(relato)}).",
        )
    return relato