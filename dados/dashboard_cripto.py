# dashboard_cripto.py
import streamlit as st
import pandas as pd
import plotly.express as px
import os
import glob
from datetime import datetime

# Tenta importar os módulos auxiliares do projeto
try:
    import gestao_carteira as gc
    GESTAO_OK = True
except Exception as e:
    GESTAO_OK = False
    ERRO_GESTAO = str(e)

try:
    import codigo_relatorio_cripto_potencial as relatorio
    RELATORIO_OK = True
except Exception as e:
    RELATORIO_OK = False
    ERRO_RELATORIO = str(e)

# Define o caminho da pasta 'dados' de forma relativa e dinâmica
DIRETORIO_BASE = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
PASTA_CSV = os.path.join(DIRETORIO_BASE, "dados")

st.set_page_config(page_title="Crypto Radar | Low-Cap + Carteira", page_icon="◈", layout="wide")

# =========================================================
# 1. AUTOMAÇÃO E MONITORAMENTO EM SEGUNDO PLANO (10 MINUTOS)
# =========================================================
# Atualiza a página do navegador automaticamente a cada 10 minutos (600.000 ms)
st.html(
    """
    <script>
        setTimeout(function(){
            window.location.reload();
        }, 600000);
    </script>
    """
)

# Cache de 10 minutos (ttl=600). Garante que a verificação de alertas e o envio de e-mails
# rodem de forma autônoma na nuvem do Streamlit sem requisições duplicadas.
@st.cache_data(ttl=600)
def executar_monitor_automatico():
    if not GESTAO_OK:
        return {"sucesso": False, "erro": "Módulo gestao_carteira indisponível."}

    status = gc.carregar_status()

    # Verifica se o monitor está ATIVO no painel
    if status.get("ativo", False):
        agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        try:
            # Executa a verificação e o envio de e-mails
            retorno = gc.gerar_e_enviar_alertas()
            
            # Atualiza e guarda a hora da última execução
            status["ultima_execucao"] = agora
            gc.salvar_status(status)
            
            return {
                "sucesso": True,
                "agora": agora,
                "alertas": [
                    r for r in retorno.get("resultados", [])
                    if isinstance(r, dict) and r.get("ok") and r.get("alerta") in ("VENDER", "RECOMPRAR")
                ],
                "email_status": retorno.get("email_status", {})
            }
        except Exception as e:
            return {"sucesso": False, "erro": str(e)}
    
    return {"sucesso": True, "ativo": False}

# Executa o ciclo de verificação a cada 10 minutos
resultado_monitor = executar_monitor_automatico()

# =========================================================
# ESTILOS CSS PERSONALIZADOS
# =========================================================
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; color: #0f172a; }
    h1, h2, h3 { color: #0f172a; font-weight: 600; }
    [data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 12px 16px;
    }
    .stLinkButton button {
        background-color: #2563eb !important;
        color: white !important;
        border-radius: 8px !important;
        border: none !important;
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; background: white; }
    th { background-color: #f1f5f9 !important; color: #334155 !important; padding: 10px 12px !important; border-bottom: 2px solid #e2e8f0 !important; text-align: left !important; }
    td { padding: 9px 12px !important; border-bottom: 1px solid #e2e8f0 !important; }
    tr:hover td { background-color: #f8fafc !important; }
</style>
""", unsafe_allow_html=True)

def encontrar_csv_mais_recente(pasta):
    if not os.path.exists(pasta):
        return None
    arquivos = glob.glob(os.path.join(pasta, "ranking_potencial_*.csv"))
    if not arquivos:
        return None
    return max(arquivos, key=os.path.getmtime)

def carregar_dados():
    caminho = encontrar_csv_mais_recente(PASTA_CSV)
    if caminho is None:
        return None, None
    return pd.read_csv(caminho), caminho

def classificar(score):
    if score >= 70: return "FORTE COMPRA", "#059669"
    elif score >= 50: return "BOA OPORTUNIDADE", "#16a34a"
    elif score >= 35: return "OBSERVAR", "#d97706"
    else: return "FRACO", "#dc2626"

aba1, aba2 = st.tabs(["📡 Radar de Oportunidades", "💼 Gestão de Carteira"])

# =========================================================
# ABA 1 – RADAR DE OPORTUNIDADES
# =========================================================
with aba1:
    col_titulo, col_btn_analise = st.columns([3, 1])
    with col_titulo:
        st.title("Crypto Radar")
    with col_btn_analise:
        st.write("")
        if st.button("🔄 Executar Nova Análise", type="primary", use_container_width=True):
            if RELATORIO_OK:
                with st.spinner("Analisando mercado e gerando novo relatório..."):
                    df_novo = relatorio.buscar_e_analisar()
                    if df_novo is not None:
                        st.success("Análise gerada com sucesso!")
                        st.rerun()
                    else:
                        st.warning("Nenhum token atendeu aos filtros da análise.")
            else:
                st.error(f"Erro ao carregar script de análise: {ERRO_RELATORIO}")

    df, caminho_arquivo = carregar_dados()

    if df is None:
        st.info("Nenhum relatório recente encontrado na pasta de dados.")
        st.caption("Clique no botão **'🔄 Executar Nova Análise'** acima para gerar o primeiro relatório de oportunidades.")
    else:
        for col in ["SCORE", "Preco_USD", "Liquidez_USD", "Volume_24h", "Var_1h_%", "Var_6h_%", "MCap_USD"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        if "Risco" not in df.columns:
            df["Risco"] = "OK"

        df = df.sort_values("SCORE", ascending=False).reset_index(drop=True)
        nome_arquivo = os.path.basename(caminho_arquivo)
        data_mod = datetime.fromtimestamp(os.path.getmtime(caminho_arquivo)).strftime("%d/%m/%Y %H:%M")

        st.caption(f"Arquivo ativo: `{nome_arquivo}`  •  Atualizado em {data_mod}")

        ocultar_risco = st.toggle("Ocultar tokens de RISCO", value=True, key="filtro_risco")

        if ocultar_risco:
            df_filtrado = df[df["Risco"] != "RISCO"].copy()
        else:
            df_filtrado = df.copy()

        st.caption(f"Mostrando {len(df_filtrado)} de {len(df)} tokens")

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Tokens (filtrados)", len(df_filtrado))
        c2.metric("Maior Score", f"{df_filtrado['SCORE'].max():.0f}" if len(df_filtrado) > 0 else "-")
        c3.metric("Score Médio", f"{df_filtrado['SCORE'].mean():.1f}" if len(df_filtrado) > 0 else "-")
        c4.metric("Oportunidades ≥ 50", len(df_filtrado[df_filtrado["SCORE"] >= 50]))
        c5.metric("Marcados como RISCO", len(df[df["Risco"] == "RISCO"]))

        st.divider()

        if len(df_filtrado) == 0:
            st.warning("Nenhum token restante após o filtro de risco.")
        else:
            st.subheader("Principais Oportunidades")
            top_n = min(6, len(df_filtrado))
            cols = st.columns(top_n)

            for i in range(top_n):
                row = df_filtrado.iloc[i]
                status, cor = classificar(row["SCORE"])
                link = row.get("DexScreener", "")
                risco = row.get("Risco", "OK")

                with cols[i]:
                    st.markdown(f"**#{i+1}  {row['Simbolo']}**")
                    if risco == "RISCO":
                        st.markdown("<span style='color:#dc2626; font-weight:700;'>⚠ RISCO</span>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='color:#2563eb; margin:4px 0;'>${row['Preco_USD']:.8f}</h3>", unsafe_allow_html=True)
                    st.markdown(f"<span style='color:{cor}; font-weight:600;'>{status}</span>", unsafe_allow_html=True)
                    st.write("")
                    st.markdown(f"**Score:** {row['SCORE']:.0f}")
                    st.markdown(f"**Rede:** {row['Rede']}")
                    st.markdown(f"**Liquidez:** ${row['Liquidez_USD']:,.0f}")
                    st.markdown(f"**Var 1h:** {row['Var_1h_%']:+.1f}%")

                    if pd.notna(link) and str(link).strip() != "":
                        st.link_button("Comprar →", link, use_container_width=True)

            st.divider()

            g1, g2 = st.columns(2)

            with g1:
                st.subheader("Distribuição de Score")
                fig_bar = px.bar(df_filtrado.head(12), x="Simbolo", y="SCORE", color="SCORE",
                                 color_continuous_scale=["#bfdbfe", "#3b82f6", "#1d4ed8"], text="SCORE")
                fig_bar.update_traces(texttemplate="%{text:.0f}", textposition="outside")
                fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      font_color="#334155", xaxis_tickangle=-40, height=400, coloraxis_showscale=False)
                st.plotly_chart(fig_bar, use_container_width=True)

            with g2:
                st.subheader("Mapa de Oportunidade")
                fig_scatter = px.scatter(df_filtrado, x="Liquidez_USD", y="SCORE", size="Volume_24h",
                                         color="Var_1h_%", hover_name="Simbolo", color_continuous_scale="RdYlGn", size_max=40)
                fig_scatter.add_hline(y=50, line_dash="dash", line_color="#16a34a", annotation_text="Zona de Compra")
                fig_scatter.add_hline(y=70, line_dash="dot", line_color="#059669", annotation_text="Forte Compra")
                fig_scatter.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                          font_color="#334155", height=400)
                st.plotly_chart(fig_scatter, use_container_width=True)

            st.divider()
            st.subheader("Análise Completa")

            df_tabela = df_filtrado.copy()
            df_tabela["Recomendação"] = df_tabela["SCORE"].apply(lambda x: classificar(x)[0])
            df_tabela["Preço"] = df_tabela["Preco_USD"].apply(lambda x: f"${x:.8f}" if pd.notna(x) else "-")
            df_tabela["Liquidez"] = df_tabela["Liquidez_USD"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "-")
            df_tabela["Vol 24h"] = df_tabela["Volume_24h"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "-")
            df_tabela["Var 1h"] = df_tabela["Var_1h_%"].apply(lambda x: f"{x:+.1f}%" if pd.notna(x) else "-")
            df_tabela["MCap"] = df_tabela["MCap_USD"].apply(lambda x: f"${x:,.0f}" if pd.notna(x) else "-")

            if "DexScreener" in df_tabela.columns:
                df_tabela["Ação"] = df_tabela["DexScreener"].apply(
                    lambda x: f'<a href="{x}" target="_blank" style="color:#2563eb;font-weight:600;text-decoration:none;">Comprar →</a>'
                    if pd.notna(x) and str(x).strip() != "" else "-"
                )

            df_tabela["Risco"] = df_tabela["Risco"].apply(
                lambda x: f'<span style="color:#dc2626;font-weight:700;">RISCO</span>' if x == "RISCO" else '<span style="color:#16a34a;font-weight:600;">OK</span>'
            )

            colunas = ["SCORE", "Risco", "Simbolo", "Rede", "Preço", "Liquidez", "Vol 24h", "Var 1h", "MCap", "Recomendação", "Ação"]
            st.markdown(df_tabela[colunas].to_html(escape=False, index=False), unsafe_allow_html=True)

            st.caption("Crypto Radar • Filtro de risco ativo • Dados via DexScreener")

# =========================================================
# ABA 2 – GESTÃO DE CARTEIRA
# =========================================================
with aba2:
    st.title("Gestão de Carteira")
    st.caption("Cadastre suas posições e receba alertas de venda / recompra")

    if not GESTAO_OK:
        st.error(f"Erro ao carregar gestao_carteira.py: {ERRO_GESTAO}")
        st.info("Verifique se o arquivo gestao_carteira.py está no mesmo repositório do projeto.")
        st.stop()

    # ----- Controle do Monitor Automático -----
    st.subheader("Status do Monitoramento Automático")

    status = gc.carregar_status()

    col_status, col_btn = st.columns([3, 1])

    with col_status:
        if status.get("ativo"):
            st.success("🟢 Monitor AUTOMÁTICO está ATIVO")
            if status.get("ultima_execucao"):
                st.caption(f"Última verificação: {status['ultima_execucao']}")
        else:
            st.warning("🔴 Monitor AUTOMÁTICO está DESATIVADO")

    with col_btn:
        if status.get("ativo"):
            if st.button("Desativar Monitor", type="secondary"):
                gc.salvar_status({"ativo": False, "ultima_execucao": status.get("ultima_execucao")})
                st.cache_data.clear()
                st.rerun()
        else:
            if st.button("Ativar Monitor", type="primary"):
                gc.salvar_status({"ativo": True, "ultima_execucao": status.get("ultima_execucao")})
                st.cache_data.clear()
                st.rerun()

    st.divider()

    # ----- Cadastro com BUSCA POR NOME -----
    with st.expander("➕ Cadastrar nova posição", expanded=True):
        st.markdown("**1. Buscar crypto pelo nome ou símbolo**")

        col_busca1, col_busca2 = st.columns([3, 1])
        with col_busca1:
            nome_busca = st.text_input("Nome ou símbolo", placeholder="Ex: PEPE, WIF, BONK", key="nome_busca")
        with col_busca2:
            st.write("")
            st.write("")
            botao_buscar = st.button("🔍 Buscar", type="primary")

        if botao_buscar and nome_busca.strip():
            with st.spinner("Buscando no DexScreener..."):
                resultados_busca = gc.buscar_token_por_nome(nome_busca.strip())
                st.session_state["resultados_busca"] = resultados_busca

        resultados_busca = st.session_state.get("resultados_busca", [])

        if resultados_busca:
            st.markdown("**2. Selecione o token correto:**")

            opcoes = []
            for i, r in enumerate(resultados_busca):
                texto = f"{r['simbolo']} - {r['rede']} - Preço: ${r['preco']:.8f} - Liq:${r['liquidez']:,.0f}"
                opcoes.append(texto)

            escolha = st.radio("Resultados encontrados:", opcoes, key="escolha_token")

            if escolha:
                idx = opcoes.index(escolha)
                token_escolhido = resultados_busca[idx]

                st.success(f"Selecionado: **{token_escolhido['simbolo']}** ({token_escolhido['rede']})")

                st.markdown("**3. Confirme os dados e o preço de compra:**")

                c1, c2, c3 = st.columns(3)
                c1.text_input("Símbolo", value=token_escolhido["simbolo"], disabled=True)
                c2.text_input("Rede", value=token_escolhido["rede"], disabled=True)
                c3.text_input("Contrato", value=token_escolhido["contrato"][:20] + "...", disabled=True)

                preco_sugerido = token_escolhido["preco"]
                preco_compra = st.number_input(
                    "Preço de compra (USD)",
                    min_value=0.0,
                    value=float(preco_sugerido),
                    format="%.10f",
                    help="Pode alterar se o preço que você comprou for diferente do atual"
                )
                quantidade = st.number_input("Quantidade (opcional)", min_value=0.0, value=0.0)
                observacao = st.text_input("Observação (opcional)")

                if st.button("💾 Salvar posição", type="primary"):
                    gc.adicionar_posicao(
                        simbolo=token_escolhido["simbolo"],
                        contrato=token_escolhido["contrato"],
                        rede=token_escolhido["rede"],
                        preco_compra=preco_compra,
                        quantidade=quantidade,
                        observacao=observacao
                    )
                    st.success(f"Posição {token_escolhido['simbolo']} cadastrada com sucesso!")
                    if "resultados_busca" in st.session_state:
                        del st.session_state["resultados_busca"]
                    st.cache_data.clear()
                    st.rerun()

        elif botao_buscar and nome_busca.strip():
            st.warning("Nenhum token encontrado. Tente outro nome ou símbolo.")

    st.divider()

    # ----- Botão de atualizar manual + feedback de e-mail -----
    if st.button("🔄 Atualizar preços e gerar alertas agora", type="primary"):
        with st.spinner("Consultando DexScreener e analisando posições..."):
            retorno = gc.gerar_e_enviar_alertas()
            st.session_state["ultima_analise"] = retorno["resultados"]
            st.session_state["email_status"] = retorno["email_status"]
            st.cache_data.clear()
        st.rerun()

    email_status = st.session_state.get("email_status")
    if email_status:
        tipo = email_status.get("tipo")
        msg = email_status.get("mensagem", "")

        if tipo == "enviado":
            st.success(f"✅ {msg}")
        elif tipo == "sem_alerta":
            st.info(f"ℹ️ {msg}")
        elif tipo == "erro":
            st.error(f"❌ {msg}")

    # ----- Lista de posições + alertas -----
    resultados = st.session_state.get("ultima_analise")
    if resultados is None:
        resultados = gc.monitorar_carteira()

    if not resultados:
        st.info("Nenhuma posição cadastrada ainda. Use o formulário acima.")
    else:
        st.subheader("Suas Posições e Alertas")

        for r in resultados:
            if not r.get("ok"):
                st.warning(f"Erro em uma posição: {r.get('erro')}")
                continue

            pos = r["posicao"]
            alerta = r["alerta"]
            cor_alerta = {
                "VENDER": "#dc2626",
                "RECOMPRAR": "#2563eb",
                "MANTER": "#16a34a"
            }.get(alerta, "#64748b")

            with st.container():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 2])
                c1.markdown(f"### {pos['simbolo']}")
                c1.caption(f"{pos['rede']} • {pos['contrato'][:10]}...")
                c2.metric("Preço Compra", f"${pos['preco_compra']:.8f}")
                c3.metric("Preço Atual", f"${r['preco_atual']:.8f}", f"{r['variacao_pct']:+.1f}%")
                c4.markdown(f"<h3 style='color:{cor_alerta}'>{alerta}</h3>", unsafe_allow_html=True)
                c4.caption(r["acao"])

                st.markdown(f"**Motivos:** {r['motivos']}")
                st.markdown(f"**Análise:** {r['analise']}")

                if r["info"].get("url"):
                    st.link_button("Ver no DexScreener →", r["info"]["url"])

                if st.button(f"Remover {pos['simbolo']}", key=f"del_{pos['id']}"):
                    gc.remover_posicao(pos["id"])
                    st.cache_data.clear()
                    st.rerun()

                st.divider()

    # ----- Gestão de e-mails -----
    with st.expander("📧 E-mails que recebem alertas"):
        emails = gc.carregar_emails()
        st.write("E-mails atuais:", emails)

        novo_email = st.text_input("Adicionar novo e-mail")
        if st.button("Adicionar e-mail") and novo_email:
            if novo_email not in emails:
                emails.append(novo_email)
                gc.salvar_emails(emails)
                st.success("E-mail adicionado!")
                st.cache_data.clear()
                st.rerun()

        if st.button("Remover último e-mail") and len(emails) > 1:
            emails.pop()
            gc.salvar_emails(emails)
            st.cache_data.clear()
            st.rerun()
