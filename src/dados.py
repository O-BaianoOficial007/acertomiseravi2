from __future__ import annotations

import contextlib
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import regras
from validacoes import ErroValidacao

log = logging.getLogger(__name__)

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DADOS = PASTA_PROJETO / "dados"
ARQUIVO_ALUNOS = PASTA_DADOS / "alunos.json"
ARQUIVO_LOG = PASTA_DADOS / "acertomizeravi.log"
PASTA_BACKUPS = PASTA_DADOS / "backups"
BACKUP_ANTERIOR = PASTA_BACKUPS / "alunos_anterior.json"
MAX_BACKUPS_DE_SESSAO = 15
_PADRAO_BACKUP = "alunos_????????_??????.json"


class ErroDeDados(Exception):
    
    def __init__(self, mensagem: str, corrompido: bool = False):
        super().__init__(mensagem)
        self.corrompido = corrompido


def garantir_pastas() -> None:
    try:
        PASTA_BACKUPS.mkdir(parents=True, exist_ok=True)
    except OSError as erro:
        log.exception("Não foi possível criar a pasta de dados %s", PASTA_DADOS)
        raise ErroDeDados(f"Não foi possível criar a pasta de dados: {erro}") from erro


def _agora() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")



def _ler_arquivo(caminho: Path) -> tuple[list[dict], int]:
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            bruto = json.load(arquivo)
    except ValueError as erro:  
        log.error("Arquivo %s inválido: %s", caminho, erro)
        raise ErroDeDados(
            f"O arquivo {caminho.name} está corrompido ({erro}).", corrompido=True
        ) from erro
    except OSError as erro:
        log.exception("Não foi possível ler %s", caminho)
        raise ErroDeDados(f"Não foi possível ler o arquivo {caminho.name}: {erro}") from erro

    if not isinstance(bruto, list):
        raise ErroDeDados(
            f"O arquivo {caminho.name} não tem o formato esperado (uma lista de alunos).",
            corrompido=True,
        )

    alunos, ignorados = [], 0
    for posicao, registro in enumerate(bruto, start=1):
        try:
            alunos.append(regras.normalizar_registro(registro))
        except ErroValidacao as erro:
            ignorados += 1
            log.warning("Registro %d de %s ignorado: %s", posicao, caminho.name, erro)
    return alunos, ignorados


def carregar_alunos() -> tuple[list[dict], int]:
    garantir_pastas()
    if not ARQUIVO_ALUNOS.exists():
        salvar_alunos([])
        return [], 0
    return _ler_arquivo(ARQUIVO_ALUNOS)


def salvar_alunos(alunos: list[dict]) -> None:
    garantir_pastas()
    temporario = ARQUIVO_ALUNOS.with_name(ARQUIVO_ALUNOS.name + ".tmp")
    try:
        if ARQUIVO_ALUNOS.exists():
            shutil.copy2(ARQUIVO_ALUNOS, BACKUP_ANTERIOR)
        with open(temporario, "w", encoding="utf-8") as arquivo:
            json.dump(alunos, arquivo, ensure_ascii=False, indent=2)
            arquivo.flush()
            os.fsync(arquivo.fileno())
        os.replace(temporario, ARQUIVO_ALUNOS)
    except (OSError, TypeError, ValueError) as erro:
        log.exception("Falha ao gravar %s", ARQUIVO_ALUNOS)
        with contextlib.suppress(OSError):
            temporario.unlink(missing_ok=True)
        raise ErroDeDados(f"Não foi possível salvar os dados: {erro}") from erro


def _backups_de_sessao() -> list[Path]:
    return sorted(PASTA_BACKUPS.glob(_PADRAO_BACKUP))


def _candidatos_de_restauracao() -> list[Path]:
    candidatos = _backups_de_sessao()
    if BACKUP_ANTERIOR.exists():
        candidatos.append(BACKUP_ANTERIOR)
    return sorted(candidatos, key=lambda caminho: caminho.stat().st_mtime, reverse=True)


def contar_backups() -> int:
    if not PASTA_BACKUPS.exists():
        return 0
    return len(_candidatos_de_restauracao())


def criar_backup() -> Path | None:

    if not ARQUIVO_ALUNOS.exists():
        return None
    garantir_pastas()
    destino = PASTA_BACKUPS / f"alunos_{_agora()}.json"
    try:
        shutil.copy2(ARQUIVO_ALUNOS, destino)
        for antigo in _backups_de_sessao()[:-MAX_BACKUPS_DE_SESSAO]:
            antigo.unlink()
    except OSError as erro:
        log.exception("Falha ao criar backup em %s", destino)
        raise ErroDeDados(f"Não foi possível criar o backup: {erro}") from erro
    log.info("Backup criado: %s", destino.name)
    return destino


def _preservar_arquivo_atual(prefixo: str) -> None:
    if not ARQUIVO_ALUNOS.exists():
        return
    garantir_pastas()
    destino = PASTA_BACKUPS / f"{prefixo}_{_agora()}.json"
    try:
        os.replace(ARQUIVO_ALUNOS, destino)
    except OSError as erro:
        log.exception("Falha ao preservar %s", ARQUIVO_ALUNOS)
        raise ErroDeDados(f"Não foi possível preservar o arquivo atual: {erro}") from erro
    log.info("Arquivo atual preservado em %s", destino.name)


def iniciar_vazio_preservando_arquivo() -> None:
    _preservar_arquivo_atual("alunos_corrompido")
    salvar_alunos([])


def restaurar_ultimo_backup() -> tuple[Path, list[dict]]:
    
    garantir_pastas()
    for candidato in _candidatos_de_restauracao():
        try:
            alunos, _ = _ler_arquivo(candidato)
        except ErroDeDados:
            continue  
        _preservar_arquivo_atual("alunos_substituido")
        salvar_alunos(alunos)
        log.info("Dados restaurados a partir de %s", candidato.name)
        return candidato, alunos
    raise ErroDeDados("Nenhum backup válido foi encontrado.")