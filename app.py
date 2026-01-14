import streamlit as st
from io import BytesIO

# === IMPORTA A LÓGICA CONSOLIDADA ===
import pandas as pd
from lxml import etree

def gerar_diario_obra(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()
    ns = {'ms': 'http://schemas.microsoft.com/project'}

    tasks = []
    for task in root.findall('.//ms:Task', ns):
        name = task.findtext('ms:Name', default='', namespaces=ns)
        outline = task.findtext('ms:OutlineLevel', default='0', namespaces=ns)
        percent = task.findtext('ms:PercentComplete', default='0', namespaces=ns)

        if not name.strip():
            continue

        tasks.append({
            "name": name.strip(),
            "outline_level": int(outline),
            "percent_complete": float(percent)
        })

    df = pd.DataFrame(tasks)
    df["name_lower"] = df["name"].str.lower()

    idx = df[
        (df["outline_level"] == 2) &
        (df["name_lower"] == "montagem")
    ].index

    if idx.empty:
        raise RuntimeError("Marco MONTAGEM nível 2 não encontrado.")

    inicio = idx[0]
    fim = len(df)

    for i in range(inicio + 1, len(df)):
        if df.loc[i, "outline_level"] <= 2:
            fim = i
            break

    df = df.iloc[inicio:fim].reset_index(drop=True)

    contador = {}
    itens = []

    for _, row in df.iterrows():
        nivel = row["outline_level"]
        contador.setdefault(nivel, 0)
        contador[nivel] += 1
        for k in list(contador.keys()):
            if k > nivel:
                contador[k] = 0
        itens.append(".".join(str(contador[i]) for i in sorted(contador) if contador[i] > 0))

    df["Item"] = itens
    df["next"] = df["outline_level"].shift(-1)
    df["TIPO"] = df["next"] > df["outline_level"]
    df["TIPO"] = df["TIPO"].apply(lambda x: "ETAPA" if x else "TAREFA")

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
    return output


# === INTERFACE STREAMLIT ===
st.set_page_config(page_title="Diário de Obra", layout="centered")
st.title("Gerador de Diário de Obra – Montagem")

uploaded = st.file_uploader(
    "Faça upload do cronograma (XML do Project)",
    type=["xml"]
)

if uploaded:
    try:
        excel = gerar_diario_obra(uploaded)

        st.success("Arquivo gerado com sucesso.")
        st.download_button(
            "📥 Baixar Diário de Obra",
            excel,
            file_name="diario_obra.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(str(e))
