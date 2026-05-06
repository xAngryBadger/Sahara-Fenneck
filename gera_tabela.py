import pandas as pd
from pathlib import Path

# caminhos
INPUT = Path(r"E:\Sahara Fenneck\tabela papai.xlsx")
OUTPUT = Path(r"E:\Sahara Fenneck\tabela_papai_out.xlsx")

# parâmetros
HORAS_HOMEM_OBJ = 8.0     # horas-homem orçadas por hectare
HORAS_REAIS_COLAB = 4.3   # horas reais rendidas por colaborador
MAX_COLAB = 8             # simular 1..8

# ler planilha (usa primeira aba)
xls = pd.ExcelFile(INPUT)
sheet_src = xls.sheet_names[0]
df_base = pd.read_excel(xls, sheet_name=sheet_src)

# assumir primeiras duas colunas: Atividade / Area
df_base = df_base.rename(columns={
    df_base.columns[0]: "Atividade",
    df_base.columns[1]: "Area"
})
df_base["Area"] = pd.to_numeric(df_base["Area"], errors="coerce")
df_base = df_base.dropna(subset=["Area"]).reset_index(drop=True)

# simulação
sims = []
for n in range(1, MAX_COLAB + 1):
    d = df_base.copy()
    d["Colab"] = n
    d["HH_disponivel"] = n * HORAS_REAIS_COLAB
    d["Hectares_possiveis"] = d["HH_disponivel"] / HORAS_HOMEM_OBJ
    d["Hectares_inteiros"] = d["Hectares_possiveis"].astype(int)
    d["Sobra_HH"] = d["HH_disponivel"] - d["Hectares_inteiros"] * HORAS_HOMEM_OBJ
    d["Hectares_rel_area"] = d["Hectares_possiveis"] / d["Area"]
    d["Status"] = d["Hectares_rel_area"].apply(lambda x: "Cobre área" if x >= 1 else "Não cobre")
    d["Colab_sim"] = n
    sims.append(d)

tabela = pd.concat(sims, ignore_index=True)

# gravar saída
with pd.ExcelWriter(OUTPUT, engine="openpyxl", mode="w") as w:
    df_base.to_excel(w, sheet_name=sheet_src, index=False)  # copia base
    tabela.to_excel(w, sheet_name="Simulacao", index=False)  # nova aba

print("✓ Gerado:", OUTPUT.resolve())