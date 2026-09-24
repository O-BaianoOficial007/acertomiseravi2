from __future__ import annotations

import copy
import logging
import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from tkinter import messagebox, ttk

import dados
import regras
from dados import ErroDeDados
from validacoes import (
    COMPORTAMENTO_MAX,
    NOTAS_LIMITE,
    ErroValidacao,
    validar_comportamento,
    validar_nome,
    validar_notas,
    validar_sala,
)

log = logging.getLogger(__name__)

NOME_APP = "AcertôMizeravi"
VERSAO = "1.0"
TODAS_AS_SALAS = "Todas"
TRACO = "—"

COR_FUNDO = "#eef2f7"
COR_DESTAQUE = "#1f4e8c"
COR_ALERTA = "#b3261e"
COR_STATUS = "#dde5f0"

TAGS_SITUACAO = {
    "Aprovado": "aprovado",
    "Recuperação": "recuperacao",
    "Reprovado": "reprovado",
    "Em andamento": "andamento",
}

def formatar_nota(valor: float) -> str:
    return f"{valor:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def formatar_media(valor: float | None) -> str:
    return TRACO if valor is None else f"{valor:.2f}".replace(".", ",")


def formatar_notas(notas: list[float], separador: str = " · ") -> str:
    return separador.join(formatar_nota(nota) for nota in notas) if notas else TRACO


def centralizar(janela: tk.Misc, largura: int, altura: int) -> None:
    janela.update_idletasks()
    largura = min(largura, janela.winfo_screenwidth() - 40)
    altura = min(altura, janela.winfo_screenheight() - 80)
    x = (janela.winfo_screenwidth() - largura) // 2
    y = max((janela.winfo_screenheight() - altura) // 2 - 20, 0)
    janela.geometry(f"{largura}x{altura}+{x}+{y}")


def tornar_modal(janela: tk.Toplevel) -> None:
    try:
        janela.wait_visibility()
        janela.grab_set()
    except tk.TclError:
        log.warning("Não foi possível tornar a janela modal", exc_info=True)
    janela.focus_set()


def _proximo_campo(evento: tk.Event) -> str:
    evento.widget.tk_focusNext().focus_set()
    return "break"


def _campo_anterior(evento: tk.Event) -> str:
    evento.widget.tk_focusPrev().focus_set()
    return "break"


class Aplicativo:
    COLUNAS = (
        ("nome", "Nome do Aluno", 190, "w"),
        ("sala", "Sala", 60, "center"),
        ("notas", "Notas", 170, "w"),
        ("media", "Média", 70, "center"),
        ("situacao", "Situação", 100, "center"),
        ("comportamento", "Avaliação Comportamental", 300, "w"),
    )

    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.alunos: list[dict] = []
        self.indice_selecionado: int | None = None
        self._instantaneo_formulario: tuple = ("", "", "", "")
        self._ignorar_selecao = False

        raiz.title(f"{NOME_APP} v{VERSAO} - Organização de Notas de Alunos")
        centralizar(raiz, 1120, 720)
        raiz.minsize(980, 640)
        raiz.protocol("WM_DELETE_WINDOW", self.sair)

        self._configurar_estilo()
        self._criar_variaveis()
        self._montar_layout()
        self._registrar_atalhos()

    def _configurar_estilo(self) -> None:
        estilo = ttk.Style(self.raiz)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam") 

        self.fonte_negrito = tkfont.nametofont("TkDefaultFont").copy()
        self.fonte_negrito.configure(weight="bold")
        self.fonte_titulo = tkfont.nametofont("TkDefaultFont").copy()
        self.fonte_titulo.configure(size=20, weight="bold")
        self.fonte_subtitulo = tkfont.nametofont("TkDefaultFont").copy()
        self.fonte_subtitulo.configure(size=11)

        self.raiz.configure(background=COR_FUNDO)
        estilo.configure("TFrame", background=COR_FUNDO)
        estilo.configure("TLabel", background=COR_FUNDO)
        estilo.configure("TLabelframe", background=COR_FUNDO)
        estilo.configure(
            "TLabelframe.Label", background=COR_FUNDO, foreground=COR_DESTAQUE, font=self.fonte_negrito
        )
        estilo.configure("Cabecalho.TFrame", background="#ffffff")
        estilo.configure(
            "Titulo.TLabel", background="#ffffff", foreground=COR_DESTAQUE, font=self.fonte_titulo
        )
        estilo.configure(
            "Subtitulo.TLabel", background="#ffffff", foreground="#444444", font=self.fonte_subtitulo
        )
        estilo.configure("Lateral.TButton", padding=(10, 9), anchor="w")
        estilo.configure("Acao.TButton", padding=(12, 5))
        estilo.configure("Aviso.TLabel", foreground="#8a4b00")
        estilo.configure("Destaque.TLabel", foreground=COR_DESTAQUE, font=self.fonte_negrito)
        estilo.configure("Dica.TLabel", foreground="#5f6b7a")
        estilo.configure("Status.TFrame", background=COR_STATUS)
        estilo.configure("Status.TLabel", background=COR_STATUS)
        estilo.configure("Treeview", rowheight=24)
        estilo.configure("Treeview.Heading", font=self.fonte_negrito, padding=4)
        estilo.map(
            "Treeview",
            background=[("selected", COR_DESTAQUE)],
            foreground=[("selected", "#ffffff")],
        )

    def _criar_variaveis(self) -> None:
        self.var_busca = tk.StringVar()
        self.var_filtro_sala = tk.StringVar(value=TODAS_AS_SALAS)
        self.var_nome = tk.StringVar()
        self.var_sala = tk.StringVar()
        self.var_notas = tk.StringVar()
        self.var_media = tk.StringVar(value=TRACO)
        self.var_situacao = tk.StringVar(value=TRACO)
        self.var_contador = tk.StringVar(value=f"0/{COMPORTAMENTO_MAX}")
        self.var_aviso_tabela = tk.StringVar()
        self.var_resumo = tk.StringVar()

    def _montar_layout(self) -> None:
        self.raiz.columnconfigure(1, weight=1)
        self.raiz.rowconfigure(1, weight=1)
        self._montar_cabecalho()
        self._montar_menu_lateral()
        self._montar_area_principal()
        self._montar_barra_status()
        self.var_busca.trace_add("write", lambda *_: self.atualizar_tabela())
        self.var_notas.trace_add("write", lambda *_: self._atualizar_previa())

    def _montar_cabecalho(self) -> None:
        quadro = ttk.Frame(self.raiz, style="Cabecalho.TFrame", padding=(16, 10))
        quadro.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(quadro, text=NOME_APP, style="Titulo.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(quadro, text="(App de Apoio Docente)", style="Subtitulo.TLabel").grid(
            row=0, column=1, sticky="sw", padx=(8, 0), pady=(0, 4)
        )
        ttk.Label(quadro, text="Simplificando Notas & Avaliações", style="Subtitulo.TLabel").grid(
            row=1, column=0, columnspan=2, sticky="w"
        )

    def _montar_menu_lateral(self) -> None:
        menu = ttk.Frame(self.raiz, padding=(10, 10, 4, 10))
        menu.grid(row=1, column=0, sticky="ns")
        botoes = (
            ("Pesquisar por Nome", self.focar_pesquisa),
            ("Listar por Sala", self.focar_filtro_sala),
            ("Registrar Notas", self.abrir_ficha_notas),
            ("Calcular Média", self.calcular_medias),
            ("Relatar Comportamento", self.abrir_ficha_comportamento),
            ("Gerenciar Alunos", self.novo_aluno),
            ("Configurações", self.abrir_configuracoes),
            ("Sobre", self.mostrar_sobre),
            ("Sair", self.sair),
        )
        for linha, (texto, comando) in enumerate(botoes):
            ttk.Button(menu, text=texto, command=comando, style="Lateral.TButton", width=22).grid(
                row=linha, column=0, sticky="ew", pady=3
            )

    def _montar_area_principal(self) -> None:
        area = ttk.Frame(self.raiz, padding=(6, 10, 10, 10))
        area.grid(row=1, column=1, sticky="nsew")
        area.columnconfigure(0, weight=1)
        area.rowconfigure(1, weight=1)
        self._montar_filtro(area)
        self._montar_tabela(area)
        self._montar_formulario(area)

    def _montar_filtro(self, area: ttk.Frame) -> None:
        filtro = ttk.LabelFrame(area, text="Pesquisa e filtro", padding=8)
        filtro.grid(row=0, column=0, sticky="ew")
        filtro.columnconfigure(1, weight=1)

        ttk.Label(filtro, text="Nome:").grid(row=0, column=0, sticky="w")
        self.ent_busca = ttk.Entry(filtro, textvariable=self.var_busca)
        self.ent_busca.grid(row=0, column=1, sticky="ew", padx=(6, 14))

        ttk.Label(filtro, text="Sala:").grid(row=0, column=2, sticky="w")
        self.cmb_filtro_sala = ttk.Combobox(
            filtro,
            textvariable=self.var_filtro_sala,
            values=[TODAS_AS_SALAS],
            state="readonly",
            width=10,
        )
        self.cmb_filtro_sala.grid(row=0, column=3, padx=(6, 14))
        self.cmb_filtro_sala.bind("<<ComboboxSelected>>", lambda _e: self.atualizar_tabela())

        ttk.Button(filtro, text="Limpar filtros", command=self.limpar_filtros).grid(row=0, column=4)

    def _montar_tabela(self, area: ttk.Frame) -> None:
        quadro = ttk.LabelFrame(area, text="Alunos cadastrados", padding=6)
        quadro.grid(row=1, column=0, sticky="nsew", pady=8)
        quadro.columnconfigure(0, weight=1)
        quadro.rowconfigure(0, weight=1)

        identificadores = [coluna[0] for coluna in self.COLUNAS]
        self.tabela = ttk.Treeview(
            quadro, columns=identificadores, show="headings", selectmode="browse", height=9
        )
        for identificador, titulo, largura, alinhamento in self.COLUNAS:
            self.tabela.heading(identificador, text=titulo)
            self.tabela.column(
                identificador,
                width=largura,
                anchor=alinhamento,
                stretch=(identificador == "comportamento"),
            )
        self.tabela.tag_configure("aprovado", background="#e4f4e8")
        self.tabela.tag_configure("recuperacao", background="#fff3d6")
        self.tabela.tag_configure("reprovado", background="#fbe3e1")
        self.tabela.tag_configure("andamento", background="#eceff3")

        barra_v = ttk.Scrollbar(quadro, orient="vertical", command=self.tabela.yview)
        barra_h = ttk.Scrollbar(quadro, orient="horizontal", command=self.tabela.xview)
        self.tabela.configure(yscrollcommand=barra_v.set, xscrollcommand=barra_h.set)
        self.tabela.grid(row=0, column=0, sticky="nsew")
        barra_v.grid(row=0, column=1, sticky="ns")
        barra_h.grid(row=1, column=0, sticky="ew")

        ttk.Label(quadro, textvariable=self.var_aviso_tabela, style="Aviso.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )

        self.tabela.bind("<<TreeviewSelect>>", self._ao_selecionar)
        self.tabela.bind("<Double-1>", self._ao_duplo_clique)
        self.tabela.bind("<Return>", lambda _e: self.abrir_ficha_notas())
        self.tabela.bind("<Delete>", lambda _e: self.excluir_aluno())

    def _montar_formulario(self, area: ttk.Frame) -> None:
        self.quadro_formulario = ttk.LabelFrame(area, text="Novo Registro", padding=10)
        form = self.quadro_formulario
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        ttk.Label(form, text="Nome do Aluno:").grid(row=0, column=0, sticky="w", pady=3)
        self.ent_nome = ttk.Entry(form, textvariable=self.var_nome)
        self.ent_nome.grid(row=0, column=1, sticky="ew", padx=(6, 14), pady=3)

        ttk.Label(form, text="Sala:").grid(row=0, column=2, sticky="w", pady=3)
        self.cmb_sala = ttk.Combobox(form, textvariable=self.var_sala, width=12)
        self.cmb_sala.grid(row=0, column=3, sticky="w", padx=(6, 0), pady=3)

        ttk.Label(form, text="Notas:").grid(row=1, column=0, sticky="w", pady=3)
        self.ent_notas = ttk.Entry(form, textvariable=self.var_notas)
        self.ent_notas.grid(row=1, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=3)
        ttk.Label(
            form,
            text=f"Separe as notas com ; ou espaço. De 0 a 10, até 2 casas decimais, "
            f"no máximo {NOTAS_LIMITE} notas. Exemplo: 7,5; 8; 6,25",
            style="Dica.TLabel",
        ).grid(row=2, column=1, columnspan=3, sticky="w", padx=(6, 0))

        ttk.Label(form, text="Média (Auto):").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(
            form, textvariable=self.var_media, state="readonly", takefocus=False, width=14
        ).grid(row=3, column=1, sticky="w", padx=(6, 14), pady=3)
        ttk.Label(form, text="Situação (Auto):").grid(row=3, column=2, sticky="w", pady=3)
        ttk.Entry(
            form, textvariable=self.var_situacao, state="readonly", takefocus=False, width=16
        ).grid(row=3, column=3, sticky="w", padx=(6, 0), pady=3)

        ttk.Label(form, text="Avaliação Comportamental:").grid(row=4, column=0, sticky="nw", pady=3)
        self.txt_comportamento = tk.Text(
            form, height=3, wrap="word", font="TkDefaultFont", undo=True, relief="solid", borderwidth=1
        )
        self.txt_comportamento.grid(row=4, column=1, columnspan=3, sticky="ew", padx=(6, 0), pady=3)
        self.txt_comportamento.bind("<Tab>", _proximo_campo)
        self.txt_comportamento.bind("<<PrevWindow>>", _campo_anterior)
        self.txt_comportamento.bind("<<Modified>>", self._ao_modificar_comportamento)
        self.lbl_contador = ttk.Label(form, textvariable=self.var_contador, style="Dica.TLabel")
        self.lbl_contador.grid(row=5, column=3, sticky="e")

        botoes = ttk.Frame(form)
        botoes.grid(row=6, column=0, columnspan=4, pady=(6, 0))
        ttk.Button(
            botoes, text="Adicionar/Atualizar", command=self.salvar_formulario, style="Acao.TButton"
        ).grid(row=0, column=0, padx=6)
        ttk.Button(
            botoes, text="Limpar", command=self.limpar_formulario, style="Acao.TButton"
        ).grid(row=0, column=1, padx=6)
        ttk.Button(
            botoes, text="Excluir Aluno", command=self.excluir_aluno, style="Acao.TButton"
        ).grid(row=0, column=2, padx=6)

        for campo in (self.ent_nome, self.cmb_sala, self.ent_notas):
            campo.bind("<Return>", lambda _e: self.salvar_formulario())

    def _montar_barra_status(self) -> None:
        barra = ttk.Frame(self.raiz, style="Status.TFrame", padding=(10, 4))
        barra.grid(row=2, column=0, columnspan=2, sticky="ew")
        barra.columnconfigure(0, weight=1)
        ttk.Label(barra, textvariable=self.var_resumo, style="Status.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            barra, text=f"Data: {date.today():%d/%m/%Y} | {NOME_APP} ©", style="Status.TLabel"
        ).grid(row=0, column=1, sticky="e")

    def _registrar_atalhos(self) -> None:
        self.raiz.bind("<Control-f>", lambda _e: self.focar_pesquisa())
        self.raiz.bind("<Control-n>", lambda _e: self.novo_aluno())
        self.raiz.bind("<Control-s>", lambda _e: self.salvar_formulario())
        self.raiz.bind("<Control-q>", lambda _e: self.sair())

    def iniciar(self) -> bool:
        if not self._carregar_dados_iniciais():
            return False
        self.atualizar_tabela()
        self.limpar_formulario()
        return True

    def _carregar_dados_iniciais(self) -> bool:
        ignorados = 0
        try:
            self.alunos, ignorados = dados.carregar_alunos()
        except ErroDeDados as erro:
            if not erro.corrompido:
                messagebox.showerror(
                    "Erro ao abrir os dados",
                    f"{erro}\n\nO programa será encerrado para não danificar os dados.",
                    parent=self.raiz,
                )
                return False
            resposta = messagebox.askyesnocancel(
                "Arquivo de dados corrompido",
                f"{erro}\n\n"
                "Sim: restaurar o último backup válido.\n"
                "Não: começar com uma lista vazia (o arquivo atual é guardado na pasta de backups).\n"
                "Cancelar: fechar o programa sem alterar nada.",
                icon="warning",
                parent=self.raiz,
            )
            if resposta is None:
                return False
            try:
                if resposta:
                    _, self.alunos = dados.restaurar_ultimo_backup()
                else:
                    dados.iniciar_vazio_preservando_arquivo()
                    self.alunos = []
            except ErroDeDados as erro_restauracao:
                messagebox.showerror(
                    "Não foi possível recuperar os dados", str(erro_restauracao), parent=self.raiz
                )
                return False

        if ignorados:
            messagebox.showwarning(
                "Registros ignorados",
                f"{ignorados} registro(s) do arquivo de dados eram inválidos e foram ignorados.\n\n"
                "Uma cópia do arquivo original é guardada na pasta de backups desta sessão. "
                "Os detalhes estão no arquivo de log.",
                parent=self.raiz,
            )
        try:
            dados.criar_backup()  
        except ErroDeDados as erro:
            messagebox.showwarning(
                "Backup não criado",
                f"{erro}\n\nO programa continuará funcionando, mas sem o backup desta sessão.",
                parent=self.raiz,
            )
        return True

    def _gravar(self, copia_anterior: list[dict]) -> bool:
        try:
            dados.salvar_alunos(self.alunos)
        except ErroDeDados as erro:
            self.alunos = copia_anterior
            messagebox.showerror(
                "Erro ao salvar",
                f"{erro}\n\nA alteração foi desfeita para manter os dados consistentes.",
                parent=self.raiz,
            )
            return False
        return True

    def atualizar_tabela(self) -> None:
        self._atualizar_valores_salas()
        sala = self.var_filtro_sala.get()
        encontrados = regras.filtrar(
            self.alunos, self.var_busca.get(), "" if sala == TODAS_AS_SALAS else sala
        )

        self._ignorar_selecao = True  
        try:
            self.tabela.delete(*self.tabela.get_children())
            for indice, aluno in encontrados:
                self.tabela.insert(
                    "",
                    "end",
                    iid=str(indice), 
                    values=(
                        aluno["nomeAluno"],
                        aluno["sala"],
                        formatar_notas(aluno["notas"]),
                        formatar_media(aluno["media"]),
                        aluno["situacao"],
                        " ".join(aluno["avaliacaoComportamental"].split()) or TRACO,
                    ),
                    tags=(TAGS_SITUACAO[aluno["situacao"]],),
                )
        finally:
            self.raiz.after_idle(self._liberar_selecao)

        if self.indice_selecionado is not None:
            self._definir_selecao_tabela(str(self.indice_selecionado))

        if not self.alunos:
            self.var_aviso_tabela.set("Nenhum aluno cadastrado. Preencha o formulário abaixo para começar.")
        elif not encontrados:
            self.var_aviso_tabela.set(
                "Nenhum aluno encontrado para a pesquisa/filtro atual. Use 'Limpar filtros' para ver todos."
            )
        else:
            self.var_aviso_tabela.set("")
        self._atualizar_resumo([aluno for _, aluno in encontrados])

    def _atualizar_valores_salas(self) -> None:
        salas = regras.listar_salas(self.alunos)
        self.cmb_filtro_sala["values"] = [TODAS_AS_SALAS, *salas]
        self.cmb_sala["values"] = salas
        if self.var_filtro_sala.get() not in (TODAS_AS_SALAS, *salas):
            self.var_filtro_sala.set(TODAS_AS_SALAS)

    def _atualizar_resumo(self, exibidos: list[dict]) -> None:
        resumo = regras.resumir(exibidos)
        situacoes = resumo["situacoes"]
        self.var_resumo.set(
            f"Alunos exibidos: {resumo['total']} de {len(self.alunos)} | "
            f"Média geral: {formatar_media(resumo['media_geral'])} | "
            f"Aprovados: {situacoes['Aprovado']} | Recuperação: {situacoes['Recuperação']} | "
            f"Reprovados: {situacoes['Reprovado']} | Em andamento: {situacoes['Em andamento']}"
        )

    def limpar_filtros(self) -> None:
        self.var_busca.set("")
        self.var_filtro_sala.set(TODAS_AS_SALAS)
        self.atualizar_tabela()

    def focar_pesquisa(self) -> None:
        self.ent_busca.focus_set()
        self.ent_busca.select_range(0, "end")

    def focar_filtro_sala(self) -> None:
        self.cmb_filtro_sala.focus_set()
        self.cmb_filtro_sala.event_generate("<Down>")  
    def _liberar_selecao(self) -> None:
        self._ignorar_selecao = False

    def _definir_selecao_tabela(self, iid: str | None) -> None:
        self._ignorar_selecao = True
        try:
            if iid is not None and self.tabela.exists(iid):
                self.tabela.selection_set(iid)
                self.tabela.focus(iid)
                self.tabela.see(iid)
            else:
                self.tabela.selection_remove(self.tabela.selection())
        finally:
            self.raiz.after_idle(self._liberar_selecao)

    def _ao_selecionar(self, _evento: tk.Event | None = None) -> None:
        if self._ignorar_selecao:
            return
        selecao = self.tabela.selection()
        if not selecao:
            return
        indice = int(selecao[0])
        if indice == self.indice_selecionado:
            return
        if not self._confirmar_descarte():
            self._definir_selecao_tabela(
                None if self.indice_selecionado is None else str(self.indice_selecionado)
            )
            return
        self._carregar_no_formulario(indice)

    def _ao_duplo_clique(self, evento: tk.Event) -> None:
        if self.tabela.identify_row(evento.y):
            self.abrir_ficha_notas()

    def _ler_formulario_bruto(self) -> tuple:
        return (
            self.var_nome.get().strip(),
            self.var_sala.get().strip(),
            self.var_notas.get().strip(),
            self.txt_comportamento.get("1.0", "end-1c").strip(),
        )

    def _tirar_instantaneo(self) -> None:
        self._instantaneo_formulario = self._ler_formulario_bruto()

    def _formulario_alterado(self) -> bool:
        return self._ler_formulario_bruto() != self._instantaneo_formulario

    def _confirmar_descarte(self) -> bool:
        if not self._formulario_alterado():
            return True
        return messagebox.askyesno(
            "Alterações não salvas",
            "O formulário tem alterações que ainda não foram salvas.\n\nDeseja descartá-las?",
            icon="warning",
            default="no",
            parent=self.raiz,
        )

    def _definir_comportamento(self, texto: str) -> None:
        self.txt_comportamento.delete("1.0", "end")
        self.txt_comportamento.insert("1.0", texto)
        self._atualizar_contador()

    def _ao_modificar_comportamento(self, _evento: tk.Event | None = None) -> None:
        if self.txt_comportamento.edit_modified():
            self._atualizar_contador()
            self.txt_comportamento.edit_modified(False)

    def _atualizar_contador(self) -> None:
        tamanho = len(self.txt_comportamento.get("1.0", "end-1c"))
        self.var_contador.set(f"{tamanho}/{COMPORTAMENTO_MAX}")
        self.lbl_contador.configure(foreground=COR_ALERTA if tamanho > COMPORTAMENTO_MAX else "#5f6b7a")

    def _atualizar_previa(self) -> None:
        try:
            notas = validar_notas(self.var_notas.get())
        except ErroValidacao:
            self.var_media.set(TRACO)
            self.var_situacao.set(TRACO)
            return
        media = regras.calcular_media(notas)
        self.var_media.set(formatar_media(media))
        self.var_situacao.set(regras.definir_situacao(media))

    def _carregar_no_formulario(self, indice: int) -> None:
        aluno = self.alunos[indice]
        self.indice_selecionado = indice
        self.var_nome.set(aluno["nomeAluno"])
        self.var_sala.set(aluno["sala"])
        self.var_notas.set("; ".join(formatar_nota(nota) for nota in aluno["notas"]))
        self._definir_comportamento(aluno["avaliacaoComportamental"])
        self._atualizar_previa()
        self.quadro_formulario.configure(text=f"Editando: {aluno['nomeAluno']}")
        self._tirar_instantaneo()

    def limpar_formulario(self) -> None:
        self.indice_selecionado = None
        self.var_nome.set("")
        self.var_sala.set("")
        self.var_notas.set("")
        self._definir_comportamento("")
        self._atualizar_previa()
        self._definir_selecao_tabela(None)
        self.quadro_formulario.configure(text="Novo Registro")
        self._tirar_instantaneo()
        self.ent_nome.focus_set()

    def novo_aluno(self) -> None:
        if self._confirmar_descarte():
            self.limpar_formulario()

    def _focar_campo(self, campo: str) -> None:
        alvo = {
            "nome": self.ent_nome,
            "sala": self.cmb_sala,
            "notas": self.ent_notas,
            "comportamento": self.txt_comportamento,
        }.get(campo, self.ent_nome)
        alvo.focus_set()

    def salvar_formulario(self) -> None:
        try:
            nome = validar_nome(self.var_nome.get())
            sala = validar_sala(self.var_sala.get())
            notas = validar_notas(self.var_notas.get())
            comportamento = validar_comportamento(self.txt_comportamento.get("1.0", "end-1c"))
        except ErroValidacao as erro:
            messagebox.showwarning("Dados inválidos", erro.mensagem, parent=self.raiz)
            self._focar_campo(erro.campo)
            return

        if regras.existe_duplicado(self.alunos, nome, sala, self.indice_selecionado):
            messagebox.showwarning(
                "Aluno já cadastrado",
                f"Já existe um aluno chamado '{nome}' na sala {sala}.",
                parent=self.raiz,
            )
            self.ent_nome.focus_set()
            return

        copia = copy.deepcopy(self.alunos)
        novo_registro = regras.criar_aluno(nome, sala, notas, comportamento)
        if self.indice_selecionado is None:
            self.alunos.append(novo_registro)
            indice = len(self.alunos) - 1
            mensagem = f"Aluno '{nome}' cadastrado com sucesso."
        else:
            indice = self.indice_selecionado
            self.alunos[indice] = novo_registro
            mensagem = f"Registro de '{nome}' atualizado com sucesso."
        if not self._gravar(copia):
            return

        self.limpar_formulario()
        self.atualizar_tabela()
        if self.tabela.exists(str(indice)):
            self.tabela.see(str(indice))
        else:
            mensagem += "\n\nObservação: o aluno não aparece na tabela por causa do filtro ativo."
        messagebox.showinfo("Sucesso", mensagem, parent=self.raiz)

    def excluir_aluno(self) -> None:
        if self.indice_selecionado is None:
            messagebox.showinfo(
                "Selecione um aluno", "Selecione um aluno na tabela para excluir.", parent=self.raiz
            )
            return
        nome = self.alunos[self.indice_selecionado]["nomeAluno"]
        confirmou = messagebox.askyesno(
            "Confirmar exclusão",
            f"Deseja excluir definitivamente o aluno '{nome}'?\n\nEsta ação não pode ser desfeita.",
            icon="warning",
            default="no",
            parent=self.raiz,
        )
        if not confirmou:
            return
        copia = copy.deepcopy(self.alunos)
        del self.alunos[self.indice_selecionado]
        if not self._gravar(copia):
            return
        self.limpar_formulario()
        self.atualizar_tabela()
        messagebox.showinfo("Aluno excluído", f"O aluno '{nome}' foi excluído.", parent=self.raiz)

    def calcular_medias(self) -> None:
        
        if not self.alunos:
            messagebox.showinfo("Sem alunos", "Nenhum aluno cadastrado ainda.", parent=self.raiz)
            return
        copia = copy.deepcopy(self.alunos)
        self.alunos = [
            regras.criar_aluno(a["nomeAluno"], a["sala"], a["notas"], a["avaliacaoComportamental"])
            for a in self.alunos
        ]
        if not self._gravar(copia):
            return
        self.atualizar_tabela()
        sala = self.var_filtro_sala.get()
        exibidos = [
            aluno
            for _, aluno in regras.filtrar(
                self.alunos, self.var_busca.get(), "" if sala == TODAS_AS_SALAS else sala
            )
        ]
        media_geral = regras.resumir(exibidos)["media_geral"]
        messagebox.showinfo(
            "Médias calculadas",
            f"Médias e situações recalculadas para {len(self.alunos)} aluno(s).\n"
            f"Média geral dos alunos exibidos: {formatar_media(media_geral)}",
            parent=self.raiz,
        )

 
    def abrir_ficha_notas(self) -> None:
        self._abrir_ficha("notas")

    def abrir_ficha_comportamento(self) -> None:
        self._abrir_ficha("comportamento")

    def _abrir_ficha(self, foco: str) -> None:
        if self.indice_selecionado is None:
            messagebox.showinfo(
                "Selecione um aluno",
                "Selecione um aluno na tabela para registrar notas ou comportamento.",
                parent=self.raiz,
            )
            return
        if not self._confirmar_descarte():
            return
        self._carregar_no_formulario(self.indice_selecionado)  
        FichaAluno(self, self.indice_selecionado, foco)

    def aplicar_ficha(self, indice: int, notas: list[float], comportamento: str) -> bool:
        copia = copy.deepcopy(self.alunos)
        aluno = self.alunos[indice]
        self.alunos[indice] = regras.criar_aluno(
            aluno["nomeAluno"], aluno["sala"], notas, comportamento
        )
        if not self._gravar(copia):
            return False
        self.atualizar_tabela()
        self._carregar_no_formulario(indice)
        self._definir_selecao_tabela(str(indice))
        return True

    def abrir_configuracoes(self) -> None:
        JanelaConfiguracoes(self)

    def criar_backup_manual(self, parent: tk.Misc | None = None) -> bool:
        parent = parent or self.raiz
        try:
            caminho = dados.criar_backup()
        except ErroDeDados as erro:
            messagebox.showerror("Erro no backup", str(erro), parent=parent)
            return False
        if caminho is None:
            messagebox.showinfo("Backup", "Ainda não há arquivo de dados para copiar.", parent=parent)
            return False
        messagebox.showinfo("Backup criado", f"Backup salvo em:\n{caminho}", parent=parent)
        return True

    def restaurar_backup(self, parent: tk.Misc | None = None) -> bool:
        parent = parent or self.raiz
        aviso = (
            "Os dados atuais serão substituídos pelo backup válido mais recente. "
            "O arquivo atual será guardado na pasta de backups."
        )
        if self._formulario_alterado():
            aviso += "\n\nAs alterações não salvas no formulário serão perdidas."
        if not messagebox.askyesno(
            "Restaurar backup", f"{aviso}\n\nDeseja continuar?", icon="warning", default="no", parent=parent
        ):
            return False
        try:
            caminho, alunos = dados.restaurar_ultimo_backup()
        except ErroDeDados as erro:
            messagebox.showerror("Não foi possível restaurar", str(erro), parent=parent)
            return False
        self.alunos = alunos
        self.limpar_formulario()
        self.atualizar_tabela()
        messagebox.showinfo(
            "Backup restaurado",
            f"Dados restaurados a partir de {caminho.name} ({len(alunos)} aluno(s)).",
            parent=parent,
        )
        return True

    def mostrar_sobre(self) -> None:
        messagebox.showinfo(
            f"Sobre o {NOME_APP}",
            f"{NOME_APP} v{VERSAO}\n"
            "App de apoio docente para organizar notas e avaliações de alunos.\n\n"
            f"Dados salvos em: {dados.ARQUIVO_ALUNOS}\n\n"
            "Atalhos:\n"
            "  Ctrl+F  pesquisar por nome\n"
            "  Ctrl+N  novo aluno\n"
            "  Ctrl+S  ou Enter  salvar o formulário\n"
            "  Delete  excluir o aluno selecionado\n"
            "  Ctrl+Q  sair",
            parent=self.raiz,
        )

    def sair(self) -> None:
        if self._formulario_alterado():
            sair_mesmo = messagebox.askyesno(
                "Sair com alterações pendentes",
                "Há alterações não salvas no formulário. Se sair agora, elas serão perdidas.\n\n"
                "Deseja sair mesmo assim?",
                icon="warning",
                default="no",
                parent=self.raiz,
            )
            if not sair_mesmo:
                return
        self.raiz.destroy()


class FichaAluno(tk.Toplevel):

    def __init__(self, app: Aplicativo, indice: int, foco: str = "notas"):
        super().__init__(app.raiz)
        self.app = app
        self.indice = indice
        aluno = app.alunos[indice]
        self.notas = list(aluno["notas"])
        self._notas_iniciais = list(self.notas)
        self._comportamento_inicial = aluno["avaliacaoComportamental"]

        self.title(f"Ficha do Aluno - {aluno['nomeAluno']}")
        self.configure(background=COR_FUNDO)
        self.transient(app.raiz)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        self.var_nova_nota = tk.StringVar()
        self.var_media = tk.StringVar(value=TRACO)
        self.var_situacao = tk.StringVar(value=TRACO)
        self.var_quantidade = tk.StringVar()
        self.var_contador = tk.StringVar(value=f"0/{COMPORTAMENTO_MAX}")

        self._montar(aluno)
        self._atualizar_tela()
        self._atualizar_contador()

        self.bind("<Control-s>", lambda _e: self._salvar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        centralizar(self, 560, 640)
        tornar_modal(self)
        (self.txt_comportamento if foco == "comportamento" else self.ent_nova_nota).focus_set()

    def _montar(self, aluno: dict) -> None:
        self.columnconfigure(0, weight=1)

        dados_aluno = ttk.LabelFrame(self, text="Aluno", padding=10)
        dados_aluno.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        ttk.Label(dados_aluno, text="Nome:").grid(row=0, column=0, sticky="w")
        ttk.Label(dados_aluno, text=aluno["nomeAluno"], style="Destaque.TLabel").grid(
            row=0, column=1, sticky="w", padx=(6, 24)
        )
        ttk.Label(dados_aluno, text="Sala:").grid(row=0, column=2, sticky="w")
        ttk.Label(dados_aluno, text=aluno["sala"], style="Destaque.TLabel").grid(
            row=0, column=3, sticky="w", padx=(6, 0)
        )

        quadro_notas = ttk.LabelFrame(self, text="Notas", padding=10)
        quadro_notas.grid(row=1, column=0, sticky="ew", padx=12, pady=6)
        quadro_notas.columnconfigure(0, weight=1)

        self.tabela = ttk.Treeview(
            quadro_notas, columns=("posicao", "nota"), show="headings", selectmode="browse", height=6
        )
        self.tabela.heading("posicao", text="Avaliação")
        self.tabela.heading("nota", text="Nota")
        self.tabela.column("posicao", width=110, anchor="center")
        self.tabela.column("nota", width=110, anchor="center")
        barra = ttk.Scrollbar(quadro_notas, orient="vertical", command=self.tabela.yview)
        self.tabela.configure(yscrollcommand=barra.set)
        self.tabela.grid(row=0, column=0, rowspan=4, sticky="nsw")
        barra.grid(row=0, column=1, rowspan=4, sticky="ns")

        ttk.Label(quadro_notas, text="Nova nota (0 a 10):").grid(
            row=0, column=2, sticky="sw", padx=(16, 0)
        )
        self.ent_nova_nota = ttk.Entry(quadro_notas, textvariable=self.var_nova_nota, width=12)
        self.ent_nova_nota.grid(row=1, column=2, sticky="nw", padx=(16, 0))
        self.ent_nova_nota.bind("<Return>", lambda _e: self._registrar_nota())
        ttk.Button(quadro_notas, text="Registrar nota", command=self._registrar_nota).grid(
            row=2, column=2, sticky="ew", padx=(16, 0), pady=(6, 3)
        )
        ttk.Button(quadro_notas, text="Remover selecionada", command=self._remover_nota).grid(
            row=3, column=2, sticky="new", padx=(16, 0)
        )
        ttk.Label(quadro_notas, textvariable=self.var_quantidade, style="Dica.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(6, 0)
        )

        resultado = ttk.LabelFrame(self, text="Resultado (automático)", padding=10)
        resultado.grid(row=2, column=0, sticky="ew", padx=12, pady=6)
        ttk.Label(resultado, text="Média:").grid(row=0, column=0, sticky="w")
        ttk.Label(resultado, textvariable=self.var_media, style="Destaque.TLabel").grid(
            row=0, column=1, sticky="w", padx=(6, 30)
        )
        ttk.Label(resultado, text="Situação:").grid(row=0, column=2, sticky="w")
        ttk.Label(resultado, textvariable=self.var_situacao, style="Destaque.TLabel").grid(
            row=0, column=3, sticky="w", padx=(6, 0)
        )

        comportamento = ttk.LabelFrame(self, text="Avaliação comportamental", padding=10)
        comportamento.grid(row=3, column=0, sticky="ew", padx=12, pady=6)
        comportamento.columnconfigure(0, weight=1)
        self.txt_comportamento = tk.Text(
            comportamento, height=6, wrap="word", font="TkDefaultFont", undo=True, relief="solid", borderwidth=1
        )
        self.txt_comportamento.grid(row=0, column=0, sticky="ew")
        self.txt_comportamento.insert("1.0", self._comportamento_inicial)
        self.txt_comportamento.edit_modified(False)
        self.txt_comportamento.bind("<Tab>", _proximo_campo)
        self.txt_comportamento.bind("<<PrevWindow>>", _campo_anterior)
        self.txt_comportamento.bind("<<Modified>>", self._ao_modificar_texto)
        self.lbl_contador = ttk.Label(comportamento, textvariable=self.var_contador, style="Dica.TLabel")
        self.lbl_contador.grid(row=1, column=0, sticky="e")

        botoes = ttk.Frame(self)
        botoes.grid(row=4, column=0, pady=(6, 12))
        ttk.Button(botoes, text="Salvar e fechar", command=self._salvar, style="Acao.TButton").grid(
            row=0, column=0, padx=6
        )
        ttk.Button(botoes, text="Cancelar", command=self._cancelar, style="Acao.TButton").grid(
            row=0, column=1, padx=6
        )

    def _atualizar_tela(self) -> None:
        self.tabela.delete(*self.tabela.get_children())
        for posicao, nota in enumerate(self.notas):
            self.tabela.insert(
                "", "end", iid=str(posicao), values=(f"Nota {posicao + 1}", formatar_nota(nota))
            )
        media = regras.calcular_media(self.notas)
        self.var_media.set(formatar_media(media))
        self.var_situacao.set(regras.definir_situacao(media))
        self.var_quantidade.set(f"Notas registradas: {len(self.notas)} de {NOTAS_LIMITE}")

    def _ao_modificar_texto(self, _evento: tk.Event | None = None) -> None:
        if self.txt_comportamento.edit_modified():
            self._atualizar_contador()
            self.txt_comportamento.edit_modified(False)

    def _atualizar_contador(self) -> None:
        tamanho = len(self.txt_comportamento.get("1.0", "end-1c"))
        self.var_contador.set(f"{tamanho}/{COMPORTAMENTO_MAX}")
        self.lbl_contador.configure(foreground=COR_ALERTA if tamanho > COMPORTAMENTO_MAX else "#5f6b7a")

    def _registrar_nota(self) -> None:
        try:
            self.notas = regras.adicionar_nota(self.notas, self.var_nova_nota.get())
        except ErroValidacao as erro:
            messagebox.showwarning("Nota inválida", erro.mensagem, parent=self)
            self.ent_nova_nota.focus_set()
            self.ent_nova_nota.select_range(0, "end")
            return
        self.var_nova_nota.set("")
        self._atualizar_tela()
        self.ent_nova_nota.focus_set()

    def _remover_nota(self) -> None:
        selecao = self.tabela.selection()
        if not selecao:
            messagebox.showinfo("Selecione uma nota", "Selecione a nota que deseja remover.", parent=self)
            return
        self.notas = regras.remover_nota(self.notas, int(selecao[0]))
        self._atualizar_tela()

    def _houve_alteracao(self) -> bool:
        texto = self.txt_comportamento.get("1.0", "end-1c").strip()
        return self.notas != self._notas_iniciais or texto != self._comportamento_inicial.strip()

    def _salvar(self) -> None:
        try:
            comportamento = validar_comportamento(self.txt_comportamento.get("1.0", "end-1c"))
        except ErroValidacao as erro:
            messagebox.showwarning("Dados inválidos", erro.mensagem, parent=self)
            self.txt_comportamento.focus_set()
            return
        if self.app.aplicar_ficha(self.indice, self.notas, comportamento):
            self.destroy()

    def _cancelar(self) -> None:
        if self._houve_alteracao() and not messagebox.askyesno(
            "Descartar alterações",
            "Há alterações que ainda não foram salvas.\n\nDeseja fechar e descartá-las?",
            icon="warning",
            default="no",
            parent=self,
        ):
            return
        self.destroy()


class JanelaConfiguracoes(tk.Toplevel):

    def __init__(self, app: Aplicativo):
        super().__init__(app.raiz)
        self.app = app
        self.title("Configurações")
        self.configure(background=COR_FUNDO)
        self.transient(app.raiz)
        self.resizable(False, False)
        self.columnconfigure(0, weight=1)

        quadro = ttk.LabelFrame(self, text="Dados e backups", padding=12)
        quadro.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        quadro.columnconfigure(0, weight=1)

        self.var_backups = tk.StringVar()
        ttk.Label(quadro, text="Arquivo de dados (JSON):").grid(row=0, column=0, sticky="w")
        ttk.Label(quadro, text=str(dados.ARQUIVO_ALUNOS), wraplength=430, style="Destaque.TLabel").grid(
            row=1, column=0, sticky="w", pady=(0, 8)
        )
        ttk.Label(quadro, textvariable=self.var_backups).grid(row=2, column=0, sticky="w")
        ttk.Button(quadro, text="Criar backup agora", command=self._criar_backup).grid(
            row=3, column=0, sticky="ew", pady=(10, 4)
        )
        ttk.Button(quadro, text="Restaurar último backup", command=self._restaurar).grid(
            row=4, column=0, sticky="ew", pady=4
        )
        ttk.Button(quadro, text="Fechar", command=self.destroy).grid(row=5, column=0, pady=(10, 0))

        self._atualizar_contagem()
        self.bind("<Escape>", lambda _e: self.destroy())
        centralizar(self, 480, 260)
        tornar_modal(self)

    def _atualizar_contagem(self) -> None:
        self.var_backups.set(f"Backups disponíveis: {dados.contar_backups()}")

    def _criar_backup(self) -> None:
        self.app.criar_backup_manual(parent=self)
        self._atualizar_contagem()

    def _restaurar(self) -> None:
        self.app.restaurar_backup(parent=self)
        self._atualizar_contagem()