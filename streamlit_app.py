import streamlit as st
import requests
import pandas as pd
import re
import io

# --- FUNÇÕES DE UTILIDADE ---
def clean_text(text):
    if isinstance(text, str):
        return re.sub(r'[^ -~]', '', text)
    return text

def extract_codigo_barras(codigos_barras):
    if isinstance(codigos_barras, list) and codigos_barras:
        primeiro_codigo = codigos_barras[0].get('codigoBarras', '') if isinstance(codigos_barras[0], dict) else ''
        return clean_text(primeiro_codigo)
    return ''

def gera_token_dinamico(client_id, client_secret):
    AUTH_URL = "https://supply.rac.totvs.app/totvs.rac/connect/token"
    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
        "scope": "authorization_api"
    }
    try:
        response = requests.post(AUTH_URL, data=token_data, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            st.error(f"Erro na Autenticação: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Falha na conexão: {e}")
        return None

st.set_page_config(page_title="Consulta de Produtos WMS", layout="wide")
st.title("📦 Consulta de Cadastro de Produtos WMS")

with st.sidebar:
    st.header("🔑 Credenciais")
    c_id = st.text_input("WMS Client ID", type="password")
    c_secret = st.text_input("WMS Client Secret", type="password")
    u_id = st.text_input("Unidade ID (UUID)", value="ac275b55-90f8-44b8-b8cb-bdcfca969526")

if st.button("🚀 Iniciar Consulta de Produtos"):
    if not all([c_id, c_secret, u_id]):
        st.warning("⚠️ Preencha os campos na barra lateral.")
    else:
        with st.status("Consultando API...", expanded=True) as status:
            access_token = gera_token_dinamico(c_id, c_secret)
            if access_token:
                headers = {"Authorization": f"Bearer {access_token}"}
                all_data = []
                page = 1
                api_url = "https://supply.logistica.totvs.app/wms/query/api/v1/produtos"

                while True:
                    st.write(f"Buscando Página {page}...")
                    params = {"page": page, "pageSize": 500, "unidadeId": u_id}
                    
                    api_response = requests.get(api_url, params=params, headers=headers, timeout=60)
                    if api_response.status_code == 200:
                        data = api_response.json()
                        produtos = data.get('items', [])
                        if not produtos: break

                        for produto in produtos:
                            # --- TRATAMENTO DA CATEGORIA ---
                            cat_data = produto.get('categoriaProduto')
                            # Se cat_data for um dicionário, pega 'descricao', senão põe 'Sem Categoria'
                            desc_categoria = clean_text(cat_data.get('descricao', 'Sem Categoria')) if isinstance(cat_data, dict) else 'Sem Categoria'

                            controla_lote = any('Lote' in c.get('descricao', '') for c in produto.get('caracteristicas', []))
                            controla_validade = any('Data de Validade' in c.get('descricao', '') for c in produto.get('caracteristicas', []))
                            
                            skus_list = produto.get('skus', [])
                            for sku in skus_list:
                                if not isinstance(sku, dict): continue
                                all_data.append({
                                    'Código': clean_text(produto.get('codigo')),
                                    'Descrição': clean_text(produto.get('descricaoComercial')),
                                    'Categoria': desc_categoria, # <--- Agora garantido
                                    'Unidade Medida': clean_text(produto.get('unidadeMedida', '')),
                                    'Descrição SKU': clean_text(sku.get('descricao', '')),
                                    'Código de Barras': extract_codigo_barras(sku.get('codigosBarras')),
                                    'Situação SKU': clean_text(sku.get('situacao', '')),
                                    'Controla Lote': controla_lote,
                                    'Controla Validade': controla_validade
                                })

                        if not data.get('hasNext'): break
                        page += 1
                    else:
                        st.error(f"Erro na página {page}")
                        break

                if all_data:
                    df = pd.DataFrame(all_data)
                    status.update(label="Concluído!", state="complete")
                    st.dataframe(df, use_container_width=True)
                    
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                        df.to_excel(writer, index=False)
                    st.download_button("📥 Baixar Excel", data=buffer.getvalue(), file_name="produtos_wms.xlsx")
