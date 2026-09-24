from __future__ import annotations

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from validacoes import (
    NOTAS_LIMITE,
    ErroValidacao,
    validar_comportamento,
    validar_nome,
    validar_nota,
    validar_sala,
)

SITUACOES = ("Aprovado", "Recuperação", "Reprovado", "Em andamento")
MEDIA_APROVACAO = Decimal("6")
MEDIA_RECUPERACAO = Decimal("4")
_DUAS_CASAS = Decimal("0.01")



def _arredondar(valor: Decimal) -> float:
    return float(valor.quantize(_DUAS_CASAS, rounding=ROUND_HALF_UP))


def calcular_media(notas: list[float]) -> float | None:
    if not notas:
        return None
    total = sum(Decimal(str(nota)) for nota in notas)
    return _arredondar(total / len(notas))


def definir_situacao(media: float | None) -> str:
    if media is None:
        return "Em andamento"
    valor = Decimal(str(media))
    if valor >= MEDIA_APROVACAO:
        return "Aprovado"
    if valor >= MEDIA_RECUPERACAO:
        return "Recuperação"
    return "Reprovado"


def criar_aluno(nome: str, sala: str, notas: list[float], comportamento: str) -> dict:

    media = calcular_media(notas)
    return {
        "nomeAluno": nome,
        "sala": sala,
        "notas": list(notas),
        "media": media,
        "situacao": definir_situacao(media),
        "avaliacaoComportamental": comportamento,
    }


def normalizar_registro(bruto: object) -> dict:

    if not isinstance(bruto, dict):
        raise ErroValidacao("registro", "O registro não é um objeto JSON.")

    def texto(chave: str) -> str:
        valor = bruto.get(chave, "")
        return valor if isinstance(valor, str) else ""

    notas_brutas = bruto.get("notas", [])
    if not isinstance(notas_brutas, list):
        raise ErroValidacao("notas", "O campo 'notas' deve ser uma lista.")
    if len(notas_brutas) > NOTAS_LIMITE:
        raise ErroValidacao("notas", f"Mais de {NOTAS_LIMITE} notas no registro.")
    notas = []
    for nota in notas_brutas:
        if isinstance(nota, bool) or not isinstance(nota, (int, float)):
            raise ErroValidacao("notas", f"Nota inválida no registro: {nota!r}.")
        notas.append(validar_nota(format(Decimal(str(nota)), "f")))

    return criar_aluno(
        validar_nome(texto("nomeAluno")),
        validar_sala(texto("sala")),
        notas,
        validar_comportamento(texto("avaliacaoComportamental")),
    )


def adicionar_nota(notas: list[float], texto_nota: str) -> list[float]:
    if len(notas) >= NOTAS_LIMITE:
        raise ErroValidacao(
            "nota", f"Limite atingido: cada aluno pode ter no máximo {NOTAS_LIMITE} notas."
        )
    return [*notas, validar_nota(texto_nota)]


def remover_nota(notas: list[float], posicao: int) -> list[float]:
    return [nota for i, nota in enumerate(notas) if i != posicao]


def existe_duplicado(
    alunos: list[dict], nome: str, sala: str, ignorar_indice: int | None = None
) -> bool:
    chave = (_simplificar(nome), sala)
    for indice, aluno in enumerate(alunos):
        if indice == ignorar_indice:
            continue
        if (_simplificar(aluno["nomeAluno"]), aluno["sala"]) == chave:
            return True
    return False


def _simplificar(texto: str) -> str:
    decomposto = unicodedata.normalize("NFD", texto.casefold())
    return "".join(c for c in decomposto if not unicodedata.combining(c))


def _chave_sala(sala: str) -> tuple[int, str]:
    partes = re.match(r"(\d+)(.*)", sala)
    return (int(partes.group(1)), partes.group(2)) if partes else (0, sala)


def listar_salas(alunos: list[dict]) -> list[str]:
    return sorted({aluno["sala"] for aluno in alunos}, key=_chave_sala)


def filtrar(alunos: list[dict], texto_nome: str = "", sala: str = "") -> list[tuple[int, dict]]:

    busca = _simplificar(texto_nome.strip())
    encontrados = []
    for indice, aluno in enumerate(alunos):
        if sala and aluno["sala"] != sala:
            continue
        if busca and busca not in _simplificar(aluno["nomeAluno"]):
            continue
        encontrados.append((indice, aluno))
    encontrados.sort(key=lambda par: (_chave_sala(par[1]["sala"]), _simplificar(par[1]["nomeAluno"])))
    return encontrados


def resumir(alunos: list[dict]) -> dict:
    medias = [aluno["media"] for aluno in alunos if aluno["media"] is not None]
    media_geral = None
    if medias:
        media_geral = _arredondar(sum(Decimal(str(m)) for m in medias) / len(medias))
    por_situacao = {situacao: 0 for situacao in SITUACOES}
    for aluno in alunos:
        por_situacao[aluno["situacao"]] += 1
    return {"total": len(alunos), "media_geral": media_geral, "situacoes": por_situacao}