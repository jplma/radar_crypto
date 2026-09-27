# gestao_carteira.py
import json
import os
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Any, Optional

PASTA = PASTA = os.path.join(os.path.dirname(__file__), "dados")
ARQUIVO_PORTFOLIO = os.path.join(PASTA, "portfolio.json")
ARQUIVO_EMAILS = os.path.join(PASTA, "emails_alerta.json")
ARQUIVO_STATUS = os.path.join(PASTA, "monitor_status.json")

# ================= CONFIGURAÇÕES DE ALERTA =================
TAKE_PROFIT_PCT = 40.0
STOP_LOSS_PCT = -25.0
REBUY_DIP_PCT = -15.0
TRAILING_ATIVACAO_PCT = 25.0
TRAILING_DISTANCIA_PCT = 12.0

# ================= EMAIL (Gmail) =================
# IMPORTANTE: use "Senha de App" do Google (não a senha normal)
EMAIL_REMETENTE = "jplimasuporte@gmail.com"
SENHA_APP = "Jpl@105277"   # <-- COLOQUE A SENHA DE APP AQUI
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587


def garantir_pasta():
    if not os.path.exists(PASTA):
        os.makedirs(PASTA)


def carregar_portfolio() -> List[Dict]:
    garantir_pasta()
    if not os.path.exists(ARQUIVO_PORTFOLIO):
        return []
    with open(ARQUIVO_PORTFOLIO, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_portfolio(dados: List[Dict]):
    garantir_pasta()
    with open(ARQUIVO_PORTFOLIO, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def carregar_emails() -> List[str]:
    garantir_pasta()
    if not os.path.exists(ARQUIVO_EMAILS):
        return ["jplimasuporte@gmail.com"]
    with open(ARQUIVO_EMAILS, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_emails(lista: List[str]):
    garantir_pasta()
    with open(ARQUIVO_EMAILS, "w", encoding="utf-8") as f:
        json.dump(lista, f, indent=2)


def carregar_status() -> dict:
    garantir_pasta()
    if not os.path.exists(ARQUIVO_STATUS):
        status = {"ativo": False, "ultima_execucao": None}
        salvar_status(status)
        return status
    with open(ARQUIVO_STATUS, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_status(status: dict):
    garantir_pasta()
    with open(ARQUIVO_STATUS, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def adicionar_posicao(simbolo: str, contrato: str, rede: str, preco_compra: float,
                     quantidade: float = 0, observacao: str = "") -> Dict:
    portfolio = carregar_portfolio()
    nova = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "simbolo": simbolo.upper(),
        "contrato": contrato,
        "rede": rede.lower(),
        "preco_compra": float(preco_compra),
        "quantidade": float(quantidade),
        "data_compra": datetime.now().isoformat(),
        "observacao": observacao,
        "ativo": True,
        "maximo_atingido": float(preco_compra),
    }
    portfolio.append(nova)
    salvar_portfolio(portfolio)
    return nova


def remover_posicao(id_posicao: str):
    portfolio = carregar_portfolio()
    portfolio = [p for p in portfolio if p["id"] != id_posicao]
    salvar_portfolio(portfolio)


def buscar_token_por_nome(nome: str) -> list:
    """Busca tokens no DexScreener pelo nome ou símbolo"""
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={nome}"
        r = requests.get(url, timeout=12)
        data = r.json()
        pairs = data.get("pairs") or []

        resultados = []
        vistos = set()

        for p in pairs[:20]:
            base = p.get("baseToken", {})
            simbolo = base.get("symbol", "?")
            contrato = base.get("address", "")
            rede = p.get("chainId", "?")
            preco = float(p.get("priceUsd") or 0)
            liquidez = float(p.get("liquidity", {}).get("usd") or 0)
            chave = f"{rede}_{contrato}"

            if chave in vistos or not contrato or preco <= 0:
                continue
            vistos.add(chave)

            resultados.append({
                "simbolo": simbolo,
                "nome": base.get("name", ""),
                "contrato": contrato,
                "rede": rede,
                "preco": preco,
                "liquidez": liquidez,
                "url": p.get("url", ""),
            })

        resultados.sort(key=lambda x: x["liquidez"], reverse=True)
        return resultados

    except Exception as e:
        print(f"Erro na busca: {e}")
        return []


def buscar_preco_atual(contrato: str, rede: str) -> Optional[Dict[str, Any]]:
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{contrato}"
        r = requests.get(url, timeout=12)
        data = r.json()
        pairs = data.get("pairs") or []
        if not pairs:
            return None

        pares_rede = [p for p in pairs if p.get("chainId", "").lower() == rede.lower()]
        principal = max(pares_rede or pairs, key=lambda x: float(x.get("liquidity", {}).get("usd") or 0))

        preco = float(principal.get("priceUsd") or 0)
        liquidez = float(principal.get("liquidity", {}).get("usd") or 0)
        volume_24h = float(principal.get("volume", {}).get("h24") or 0)
        var_1h = float(principal.get("priceChange", {}).get("h1") or 0)
        var_6h = float(principal.get("priceChange", {}).get("h6") or 0)
        var_24h = float(principal.get("priceChange", {}).get("h24") or 0)
        url_dex = principal.get("url") or f"https://dexscreener.com/{rede}/{contrato}"

        return {
            "preco": preco,
            "liquidez": liquidez,
            "volume_24h": volume_24h,
            "var_1h": var_1h,
            "var_6h": var_6h,
            "var_24h": var_24h,
            "url": url_dex,
            "simbolo": principal.get("baseToken", {}).get("symbol", "?"),
        }
    except Exception as e:
        print(f"Erro ao buscar preço: {e}")
        return None


def analisar_posicao(pos: Dict) -> Dict[str, Any]:
    info = buscar_preco_atual(pos["contrato"], pos["rede"])
    if not info or info["preco"] <= 0:
        return {
            "ok": False,
            "erro": "Não foi possível obter preço atual",
            "alerta": "ERRO",
            "acao": "Verificar manualmente",
            "analise": "Falha na consulta ao DexScreener"
        }

    preco_atual = info["preco"]
    preco_compra = pos["preco_compra"]
    variacao_pct = ((preco_atual - preco_compra) / preco_compra) * 100

    maximo = max(pos.get("maximo_atingido", preco_compra), preco_atual)
    pos["maximo_atingido"] = maximo

    alerta = "MANTER"
    acao = "Aguardar"
    motivos = []

    if variacao_pct <= STOP_LOSS_PCT:
        alerta = "VENDER"
        acao = "Stop Loss atingido"
        motivos.append(f"Queda de {variacao_pct:.1f}% (stop em {STOP_LOSS_PCT}%)")

    elif variacao_pct >= TAKE_PROFIT_PCT:
        alerta = "VENDER"
        acao = "Take Profit atingido"
        motivos.append(f"Lucro de {variacao_pct:.1f}% (meta {TAKE_PROFIT_PCT}%)")

    elif variacao_pct >= TRAILING_ATIVACAO_PCT:
        queda_do_topo = ((preco_atual - maximo) / maximo) * 100
        if queda_do_topo <= -TRAILING_DISTANCIA_PCT:
            alerta = "VENDER"
            acao = "Trailing Stop"
            motivos.append(f"Caiu {abs(queda_do_topo):.1f}% do topo (trailing {TRAILING_DISTANCIA_PCT}%)")

    if variacao_pct <= REBUY_DIP_PCT and alerta == "MANTER":
        alerta = "RECOMPRAR"
        acao = "Possível zona de recompra"
        motivos.append(f"Queda de {variacao_pct:.1f}% – possível oportunidade de reforço")

    analise_partes = []
    analise_partes.append(f"Variação desde a compra: {variacao_pct:+.1f}%")
    analise_partes.append(f"Var 1h: {info['var_1h']:+.1f}% | Var 6h: {info['var_6h']:+.1f}% | Var 24h: {info['var_24h']:+.1f}%")
    analise_partes.append(f"Liquidez atual: ${info['liquidez']:,.0f}")
    analise_partes.append(f"Volume 24h: ${info['volume_24h']:,.0f}")

    if info["var_1h"] > 15:
        analise_partes.append("Momentum forte de alta no curto prazo.")
    elif info["var_1h"] < -15:
        analise_partes.append("Pressão vendedora forte na última hora.")

    if info["liquidez"] < 10000:
        analise_partes.append("⚠ Liquidez baixa – cuidado com slippage.")

    return {
        "ok": True,
        "preco_atual": preco_atual,
        "variacao_pct": variacao_pct,
        "maximo_atingido": maximo,
        "alerta": alerta,
        "acao": acao,
        "motivos": " | ".join(motivos) if motivos else "Nenhum gatilho forte",
        "analise": " • ".join(analise_partes),
        "info": info,
        "posicao": pos
    }


def monitorar_carteira() -> List[Dict]:
    portfolio = carregar_portfolio()
    resultados = []
    atualizados = []

    for pos in portfolio:
        if not pos.get("ativo", True):
            continue
        analise = analisar_posicao(pos)
        resultados.append(analise)
        if analise.get("ok"):
            pos["maximo_atingido"] = analise["maximo_atingido"]
        atualizados.append(pos)

    salvar_portfolio(atualizados)
    return resultados


def enviar_email_alerta(assunto: str, corpo_html: str, destinatarios: List[str] = None) -> dict:
    if destinatarios is None:
        destinatarios = carregar_emails()

    if not SENHA_APP or SENHA_APP == "COLOQUE_AQUI_SUA_SENHA_DE_APP":
        return {
            "ok": False,
            "mensagem": "Senha de App não configurada no gestao_carteira.py"
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"] = EMAIL_REMETENTE
        msg["To"] = ", ".join(destinatarios)

        msg.attach(MIMEText(corpo_html, "html"))

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(EMAIL_REMETENTE, SENHA_APP)
            server.sendmail(EMAIL_REMETENTE, destinatarios, msg.as_string())

        return {
            "ok": True,
            "mensagem": f"E-mail enviado para: {', '.join(destinatarios)}"
        }
    except Exception as e:
        return {
            "ok": False,
            "mensagem": f"Falha ao enviar e-mail: {str(e)}"
        }


def gerar_e_enviar_alertas() -> dict:
    resultados = monitorar_carteira()
    alertas_fortes = [r for r in resultados if r.get("ok") and r["alerta"] in ("VENDER", "RECOMPRAR")]

    if not alertas_fortes:
        return {
            "resultados": resultados,
            "email_status": {
                "ok": True,
                "tipo": "sem_alerta",
                "mensagem": "Nenhum alerta forte (VENDER/RECOMPRAR). E-mail não necessário."
            }
        }

    linhas = []
    for r in alertas_fortes:
        pos = r["posicao"]
        linhas.append(f"""
        <tr>
            <td><b>{pos['simbolo']}</b></td>
            <td style="color:{'#dc2626' if r['alerta']=='VENDER' else '#2563eb'}">{r['alerta']}</td>
            <td>{r['acao']}</td>
            <td>{r['variacao_pct']:+.1f}%</td>
            <td>${r['preco_atual']:.8f}</td>
            <td>{r['motivos']}</td>
        </tr>
        """)

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif">
        <h2>Crypto Radar – Alertas de Carteira</h2>
        <p>Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse">
            <tr style="background:#f1f5f9">
                <th>Token</th><th>Alerta</th><th>Ação</th><th>Variação</th><th>Preço Atual</th><th>Motivo</th>
            </tr>
            {''.join(linhas)}
        </table>
        <p style="margin-top:20px;color:#64748b">Sistema automático – Crypto Radar</p>
    </body>
    </html>
    """

    envio = enviar_email_alerta(
        assunto=f"[Crypto Radar] {len(alertas_fortes)} alerta(s) de carteira",
        corpo_html=html
    )

    return {
        "resultados": resultados,
        "email_status": {
            "ok": envio["ok"],
            "tipo": "enviado" if envio["ok"] else "erro",
            "mensagem": envio["mensagem"]
        }
    }
