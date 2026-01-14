import streamlit as st
import pandas as pd
from lxml import etree
from io import BytesIO

# ======================================================
# CONFIGURAÇÃO DA APLICAÇÃO
# ======================================================
st.set_page_config(
    page_title="Diário de Obra – Montagem",
    layout="centered"
)

st.title("Gerador de Diário de Obra – Montagem")
st.write(
    "Importe o cronograma do MS Project (XML). "
    "O sistema gera o XLSX exatamente no padrão aceito pelo Diário de Obra."
)

# ======================================================
# FUNÇÃO PRINCIPAL
# ======================================================
def gerar_diario_obra(xml_file):
    tree = etree.parse(xml_file)
    root = tree.getroot()

    # Namespace fixo do MS Project
    ns = {"ms": "http://schemas.microsoft.com/project"}

    registros = []

    # --------------------------------------------------
    # LEITURA DAS TAREFAS
    # --------------------------------------------------
    for task in root.findall(".//ms:Task", ns):
        nome = task.findtext("ms:Name", default="", namespaces=ns).strip()
        nivel = task.findtext("ms:OutlineLevel", default="", namespaces=ns).strip()
        percentual = task.findtext("ms:PercentComplete", default="0", namespaces=ns)

        if not nome or not nivel.isdigit():
            continue

        registros.append({
            "nome": nome,
            "nivel": int(nivel),
            "percentual": float(percentual)
        })

    if not registros:
        raise RuntimeError("Nenhuma tarefa válida encontrada no XML.")

    df = pd.DataFrame(registros)

    # --------------------------------------------------
    # LOCALIZA MARCO MONTAGEM (EXATO, NÍVEL 2)
    # --------------------------------------------------
    marco_idx = df[
        (df["nivel"] == 2) &
        (df["nome"] == "MONTAGEM")
    ].index

    if marco_idx.empty:
        raise RuntimeError("Marco 'MONTAGEM' (nível 2) não encontrado no cronograma.")

    inicio = marco_idx[0]
    fim = len(df)

    # --------------------------------------------------
    # CORTE HIERÁRQUICO (APÓS MONTAGEM)
    # --------------------------------------------------
    for i in range(inicio + 1, len(df)):
        if df.loc[i, "nivel"] <= 2:
            fim = i
            break

    df = df.iloc[inicio:fim].reset_index(drop=True)

    # --------------------------------------------------
    # NUMERAÇÃO HIERÁRQUICA (ITEM)
    # --------------------------------------------------
    contador = {}
    itens = []

    for _, row in df.iterrows():
        nivel = row["nivel"]

        contador.setdefault(nivel, 0)
        contador[nivel] += 1

        for k in list(contador.keys()):
            if k > nivel:
                contador[k] = 0

        item = ".".join(
            str(contador[n]) for n in sorted(contador) if contador[n] > 0
        )
        itens.append(item)

    df["Item"] = itens

    # --------------------------------------------------
    # DEFINIÇÃO ETAPA x TAREFA
    # --------------------------------------------------
    df["nivel_prox"] = df["nivel"].shift(-1)
    df["TIPO"] = df["nivel_prox"] > df["nivel"]
    df["TIPO"] = df["TIPO"].apply(lambda x: "ETAPA" if x else "TAREFA")

    # --------------------------------------------------
    # MONTAGEM DO XLSX FINAL (PADRÃO VALIDADO)
    # --------------------------------------------------
    df_final = pd.DataFrame({
        "Item": df["Item"],
        "Descrição": df["nome"],
        "Etapa": df["TIPO"].apply(lambda x: "etapa" if x == "ETAPA" else ""),
        "Unidade": "",
        "Quantidade": "",
        "Realizado": "",
        "Porcentagem": df.apply(
            lambda r: "" if r["TIPO"] == "ETAPA" else r["percentual"],
            axis=1
        )
    })

    output = BytesIO()
    df_final.to_excel(output, index=False)
    output.seek(0)

    return df_final, output


# ======================================================
# INTERFACE STREAMLIT
# ======================================================
uploaded = st.file_uploader(
    "Upload do cronograma (XML do MS Project)",
    type=["xml"]
)

if uploaded:
    st.info("Arquivo carregado. Processando conforme padrão oficial…")

    try:
        df_res, excel = gerar_diario_obra(uploaded)

        st.success(
            f"Processamento concluído com sucesso. {len(df_res)} linhas geradas."
        )

        st.download_button(
            label="📥 Baixar arquivo XLSX",
            data=excel,
            file_name="lista-de-tarefas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(str(e))
