# -*- coding: utf-8 -*-
"""
Catálogo local de funções Excel para busca no Instruct Mode.
Cada entrada: (nome, categoria, descrição_curta, palavras_chave).
Não vai para o LLM — serve apenas para busca textual local + sugestão do agente.
"""

CATALOG: list[tuple[str, str, str, str]] = [
    # Busca e referência
    ("VLOOKUP / PROCV", "Busca", "Busca um valor na primeira coluna e retorna dado da mesma linha.", "procv buscar achar encontrar valor tabela planilha referência"),
    ("HLOOKUP / PROCH", "Busca", "Busca um valor na primeira linha e retorna dado da mesma coluna.", "proch buscar horizontal linha"),
    ("XLOOKUP / PROCX", "Busca", "Busca flexível — substitui PROCV/PROCH. Aceita buscas inversas.", "procx buscar flexível moderno"),
    ("INDEX / ÍNDICE", "Busca", "Retorna o valor de uma célula em um intervalo pela posição (linha, coluna).", "índice posição célula intervalo"),
    ("MATCH / CORRESP", "Busca", "Retorna a posição de um valor dentro de um intervalo.", "corresp posição encontrar onde"),

    # Matemática e estatística
    ("SUM / SOMA", "Matemática", "Soma valores de um intervalo.", "soma somar total adicionar"),
    ("SUMIF / SOMASE", "Matemática", "Soma valores que atendem a uma condição.", "somase soma condicional critério"),
    ("SUMIFS / SOMASES", "Matemática", "Soma valores com múltiplas condições.", "somases soma múltiplas condições"),
    ("AVERAGE / MÉDIA", "Matemática", "Calcula a média aritmética.", "média calcular average"),
    ("AVERAGEIF / MÉDIASE", "Matemática", "Média com condição.", "médiase média condicional"),
    ("COUNT / CONT.NÚM", "Matemática", "Conta células com números.", "contar número quantidade"),
    ("COUNTA / CONT.VALORES", "Matemática", "Conta células não vazias.", "contar valores preenchidos"),
    ("COUNTIF / CONT.SE", "Matemática", "Conta células que atendem a uma condição.", "contse contar condição critério"),
    ("COUNTIFS / CONT.SES", "Matemática", "Conta com múltiplas condições.", "contses contar múltiplas"),
    ("MIN", "Matemática", "Retorna o menor valor.", "mínimo menor"),
    ("MAX", "Matemática", "Retorna o maior valor.", "máximo maior"),
    ("ROUND / ARRED", "Matemática", "Arredonda um número para N casas decimais.", "arredondar decimal casas"),
    ("ABS", "Matemática", "Retorna o valor absoluto (sem sinal negativo).", "absoluto positivo módulo"),
    ("PRODUCT / MULT", "Matemática", "Multiplica todos os valores de um intervalo.", "multiplicar produto"),

    # Texto
    ("CONCATENATE / CONCATENAR", "Texto", "Junta textos de várias células em um só.", "concatenar juntar texto unir"),
    ("TEXTJOIN / UNIRTEXTO", "Texto", "Junta textos com separador personalizável.", "unir texto separador vírgula"),
    ("LEFT / ESQUERDA", "Texto", "Extrai os primeiros N caracteres.", "esquerda início primeiros"),
    ("RIGHT / DIREITA", "Texto", "Extrai os últimos N caracteres.", "direita final últimos"),
    ("MID / EXT.TEXTO", "Texto", "Extrai parte do meio de um texto.", "meio extrair parte substring"),
    ("LEN / NÚM.CARACT", "Texto", "Conta o número de caracteres.", "comprimento tamanho caracteres"),
    ("TRIM / ARRUMAR", "Texto", "Remove espaços extras de um texto.", "espaço limpar arrumar"),
    ("UPPER / MAIÚSCULA", "Texto", "Converte texto para MAIÚSCULAS.", "maiúscula upper caixa alta"),
    ("LOWER / MINÚSCULA", "Texto", "Converte texto para minúsculas.", "minúscula lower caixa baixa"),
    ("PROPER / PRI.MAIÚSCULA", "Texto", "Primeira letra de cada palavra em maiúscula.", "capitalizar título"),
    ("SUBSTITUTE / SUBSTITUIR", "Texto", "Substitui parte do texto por outro.", "substituir trocar replace"),
    ("TEXT / TEXTO", "Texto", "Formata número/data como texto personalizado.", "formatar texto número data"),

    # Data e hora
    ("TODAY / HOJE", "Data", "Retorna a data de hoje.", "hoje data atual"),
    ("NOW / AGORA", "Data", "Retorna a data e hora atuais.", "agora data hora atual"),
    ("YEAR / ANO", "Data", "Extrai o ano de uma data.", "ano extrair data"),
    ("MONTH / MÊS", "Data", "Extrai o mês de uma data.", "mês extrair data"),
    ("DAY / DIA", "Data", "Extrai o dia de uma data.", "dia extrair data"),
    ("DATEDIF", "Data", "Calcula a diferença entre duas datas (dias, meses, anos).", "diferença datas idade período"),
    ("EDATE / DATAM", "Data", "Retorna uma data N meses à frente ou atrás.", "meses frente atrás futuro passado"),
    ("WEEKDAY / DIA.DA.SEMANA", "Data", "Retorna o dia da semana (1=dom, 2=seg...).", "semana dia segunda terça"),

    # Lógica
    ("IF / SE", "Lógica", "Retorna um valor se verdadeiro, outro se falso.", "se condição verdadeiro falso"),
    ("IFS / SES", "Lógica", "Avalia múltiplas condições em sequência.", "ses múltiplas condições cascata"),
    ("AND / E", "Lógica", "Retorna VERDADEIRO se todas as condições forem verdadeiras.", "e todas condições"),
    ("OR / OU", "Lógica", "Retorna VERDADEIRO se qualquer condição for verdadeira.", "ou qualquer condição"),
    ("NOT / NÃO", "Lógica", "Inverte VERDADEIRO para FALSO e vice-versa.", "não inverter negar"),
    ("IFERROR / SEERRO", "Lógica", "Retorna valor alternativo se a fórmula der erro.", "seerro erro tratar capturar"),

    # Filtro e organização
    ("SORT / CLASSIFICAR", "Organização", "Ordena um intervalo por coluna.", "ordenar classificar crescente decrescente"),
    ("FILTER / FILTRO", "Organização", "Filtra linhas que atendem a uma condição.", "filtrar filtro condição linhas"),
    ("UNIQUE / ÚNICO", "Organização", "Retorna valores únicos (sem repetição).", "único distintos sem duplicata"),
    ("TRANSPOSE / TRANSPOR", "Organização", "Troca linhas por colunas.", "transpor girar inverter linhas colunas"),
    ("REMOVE DUPLICATES", "Organização", "Remove linhas duplicadas.", "duplicata remover repetido limpar"),

    # Formatação condicional (conceito)
    ("Formatação Condicional", "Formatação", "Muda cor/estilo de células conforme regra.", "cor destaque regra condicional formatar vermelho verde"),
    ("Validação de Dados", "Formatação", "Restringe o que pode ser digitado em uma célula.", "validar lista dropdown restringir"),

    # Gráficos (conceito)
    ("Gráfico de Barras", "Gráfico", "Cria gráfico de barras comparando categorias.", "barras gráfico comparar categorias"),
    ("Gráfico de Pizza", "Gráfico", "Cria gráfico de pizza mostrando proporções.", "pizza gráfico proporção percentual"),
    ("Gráfico de Linhas", "Gráfico", "Cria gráfico de linhas mostrando tendência.", "linhas gráfico tendência evolução"),
]


def search_functions(query: str, limit: int = 6) -> list[tuple[str, str, str]]:
    """
    Busca funções no catálogo local por texto.
    Retorna lista de (nome, categoria, descrição).
    """
    if not query or not query.strip():
        return []

    import unicodedata

    def _norm(t: str) -> str:
        t = unicodedata.normalize("NFD", t.lower())
        return "".join(c for c in t if unicodedata.category(c) != "Mn")

    q_parts = _norm(query).split()
    results: list[tuple[float, str, str, str]] = []

    for name, cat, desc, keywords in CATALOG:
        searchable = _norm(f"{name} {cat} {desc} {keywords}")
        # Substring match: "filtrar" matches "filtro", "filtr" matches both
        score = sum(1.0 for w in q_parts if any(w[:3] in s_word for s_word in searchable.split()) or w in searchable)
        if score > 0:
            results.append((score, name, cat, desc))

    results.sort(key=lambda x: -x[0])
    return [(name, cat, desc) for _, name, cat, desc in results[:limit]]


def format_suggestions_text(results: list[tuple[str, str, str]]) -> str:
    """Formata resultados de busca para exibição no chat."""
    if not results:
        return "Nenhuma função encontrada para essa busca."
    lines = ["Funções sugeridas:\n"]
    for name, cat, desc in results:
        lines.append(f"• {name} [{cat}] — {desc}")
    return "\n".join(lines)
