import streamlit as st
import pandas as pd
from lxml import etree
from io import BytesIO

# ======================================================
# CONFIGURAÇÃO DA PÁGINA
# ======================================================
st.set_page_config(
    page_title="Diário de Obra – Montagem",
    layout="centered"
)

st.title("Gerador de Diário de Obra – Montagem")
st.write(
    "Faça upload do cronograma em XML (Project). "
    "O sistema extrai automaticamente apenas a etapa de **MONTAGEM**."
)

# ======================================================
# FUNÇÃO PRINCIPAL
# ======================================================
def gerar_diario_obra(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()

    # Detecta namespace automaticamente
    if root.tag.startswith("{"):
        ns_uri = root.tag.split("}")[0].replace("{", "")
        ns = {"ms": ns_uri}
        task_path = ".//ms:Task"
        def get_text(el, tag):
            return el.findtext(f"ms:{tag}", default="", namespaces=ns)
    else:
        ns = None
        task_path = ".//Task"
        def get_text(el, tag):
            return el.findtext(tag, default="")

    tasks = []

    for task in root.findall(task_path, ns):
        name = get_text(task, "Name").strip()
        outline = get_text(task, "OutlineLevel").strip()
        percent = get_text(task, "PercentComplete").strip()

        if not name or not outline.isdigit():
            continue

        tasks.append({
            "name": name,
            "outline_level": int(outline),
            "percent_complete": float(percent) if percent else 0.0
        })

    if not tasks:
        raise RuntimeError("Nenhuma tarefa encontrada no XML.")

    df = pd.DataFrame(tasks)
    df["name_lower"] = df["name"].str.lower()

    # ======================================================
    # LOCALIZA MARCO MONTAGEM (NÍVEL 2)
    # ======================================================
    idx = df[
        (df["outline_level"] == 2) &
        (df["name_lower"].str.contains("montagem"))
    ].index

    if idx.empty:
        raise RuntimeError(
            "Nenhuma etapa contendo 'montagem' foi encontrada no nível 2 do cronograma."
        )

    inicio = idx[0]
    fim = len(df)

    for i in range(inicio + 1, len(df)):
        if df.loc[i, "outline_level"] <= 2:
            fim = i
            break

    df = df.iloc[inicio:fim].reset_index(drop=True)

    # ======================================================
    # NUMERAÇÃO HIERÁRQUICA
    # ======================================================
    contador = {}
    itens = []

    for _, row in df.iterrows():
        nivel = row["outline_level"]
        contador.setdefault(nivel, 0)
        contador[nivel] += 1

        for k in list(contador.keys()):
            if k > nivel:
                contador[k] = 0

        itens.append(
            ".".join(str(contador[i]) for i in sorted(contador) if contador[i] > 0)
        )

    df["Item"] = itens

    # ======================================================
    # DEFINIÇÃO ETAPA / TAREFA
    # ======================================================
    df["next_level"] = df["outline_level"].shift(-1)
    df["TIPO"] = df["next_level"] > df["outline_level"]
    df["TIPO"] = df["TIPO"].apply(lambda x: "ETAPA" if x else "TAREFA")

    # ======================================================
    # EXCEL FINAL (PADRÃO DIÁRIO DE OBRA)
    # ======================================================
    df_final = pd.DataFrame({
        "Item": df["Item"],
        "Descrição": df["name"],
        "Etapa": df["TIPO"].apply(lambda x: "etapa" if x == "ETAPA" else ""),
        "Unidade": "",
        "Quantidade": "",
        "Realizado": "",
        "Porcentagem": df.apply(
            lambda r: "" if r["TIPO"] == "ETAPA" else r["percent_complete"],
            axis=1
        )
    })

    output = BytesIO()
    df_final.to_excel(output, index=False)
    output.seek(0)

    return df_final, output


# ======================================================
# INTERFACE
# ======================================================
uploaded = st.file_uploader(
    "Upload do cronograma (XML)",
    type=["xml"]
)

if uploaded:
    st.info("Arquivo carregado. Processando cronograma…")

    try:
        df_resultado, excel = gerar_diario_obra(uploaded)

        st.success(
            f"Processamento concluído. "
            f"{len(df_resultado)} linhas de montagem identificadas."
        )

        st.download_button(
            label="📥 Baixar Diário de Obra",
            data=excel,
            file_name="diario_obra_montagem.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(str(e))
