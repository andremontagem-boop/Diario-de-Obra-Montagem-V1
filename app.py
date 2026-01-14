import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from io import BytesIO

st.set_page_config(
    page_title="Diário de Obra – Montagem",
    layout="centered"
)

st.title("Gerador de Diário de Obra")
st.write("Upload do cronograma em XML. O sistema extrai apenas a etapa **MONTAGEM**.")

uploaded_file = st.file_uploader(
    "Selecionar arquivo XML do cronograma",
    type=["xml"]
)

if uploaded_file:
    try:
        tree = ET.parse(uploaded_file)
        root = tree.getroot()

        atividades = []

        for task in root.iter("Task"):
            nivel = task.findtext("OutlineLevel")
            nome = task.findtext("Name")

            # REGRA DE NEGÓCIO DEFINITIVA
            if nivel == "2" and nome:
                atividades.append({
                    "Atividade": nome
                })

        if not atividades:
            st.error("Nenhuma atividade de MONTAGEM (nível 2) encontrada.")
        else:
            df = pd.DataFrame(atividades)

            buffer = BytesIO()
            df.to_excel(buffer, index=False)
            buffer.seek(0)

            st.success("Diário de obra gerado com sucesso.")

            st.download_button(
                label="📥 Baixar Diário de Obra",
                data=buffer,
                file_name="diario_obra_montagem.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error("Erro ao processar o arquivo. Verifique se o XML é válido.")
