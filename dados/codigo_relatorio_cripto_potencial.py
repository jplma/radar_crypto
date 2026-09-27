# codigo_relatorio_cripto_potencial.py
import requests
import pandas as pd
import time
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# ================= CONFIGURAÇÕES =================
PASTA_RESULTADO = os.path.join(os.path.dirname(__file__), "dados")
MAX_TOKENS_ANALISAR = 30
SLEEP_ENTRE_REQUESTS = 1.1

LIQUIDEZ_MIN = 8000
LIQUIDEZ_MAX = 180000
VOLUME_24H_MIN = 3000
IDADE_MIN_HORAS = 2
# =================================================

def safe_float(value, default=0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def calcular_idade_horas(pair_created_at) -> Optional[float]:
    try:
        if not pair_created_at:
            return None
        if isinstance(pair_created_at, (int, float)):
            created = datetime.fromtimestamp(pair_created_at / 1000, tz=timezone.utc)
        else:
            return None
        agora = datetime.now(timezone.utc)
        return (agora - created).total_seconds() / 3600
    except Exception:
        return None


def classificar_risco(par: Dict[str, Any], info: Dict[str, Any]) -> Dict[str, Any]:
    motivos = []
    liquidez = info["liquidez"]
    volume_24h = info["volume_24h"]
    var_1h = info["var_1h"]
    idade_h = info["idade_h"]
    buys_1h = info["buys_1h"]
    sells_1h = info["sells_1h"]
    mcap = info["mcap"]
    preco = info["preco"]

    if idade_h is not None and idade_h < 2:
        motivos.append(f"Muito novo ({idade_h:.1f}h)")

    if liquidez < 5000:
        motivos.append(f"Liquidez muito baixa (${liquidez:,.0f})")

    if var_1h > 120:
        motivos.append(f"Pump extremo 1h ({var_1h:.0f}%)")

    if var_1h < -40:
        motivos.append(f"Queda forte 1h ({var_1h:.0f}%)")

    if (buys_1h + sells_1h) < 5 and volume_24h < 8000:
        motivos.append("Poucas transações")

    if mcap <= 0 and liquidez < 15000:
        motivos.append("Sem MCap + liquidez baixa")

    if preco <= 0:
        motivos.append("Preço inválido")

    risco = len(motivos) >= 1
    if len(motivos) >= 2:
        risco = True

    return {
        "risco": risco,
        "motivos_risco": " | ".join(motivos) if motivos else "Nenhum"
    }


def calcular_score(par: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    detalhes = []

    liquidez = safe_float(par.get("liquidity", {}).get("usd"))
    volume_24h = safe_float(par.get("volume", {}).get("h24"))
    volume_1h = safe_float(par.get("volume", {}).get("h1"))
    var_1h = safe_float(par.get("priceChange", {}).get("h1"))
    var_6h = safe_float(par.get("priceChange", {}).get("h6"))
    preco = safe_float(par.get("priceUsd"))
    mcap = safe_float(par.get("marketCap") or par.get("fdv"))
    txns_h1 = par.get("txns", {}).get("h1", {})
    buys_1h = safe_float(txns_h1.get("buys"))
    sells_1h = safe_float(txns_h1.get("sells"))
    idade_h = calcular_idade_horas(par.get("pairCreatedAt"))

    if LIQUIDEZ_MIN <= liquidez <= LIQUIDEZ_MAX:
        score += 25
        detalhes.append("Liquidez sweet spot (+25)")
    elif liquidez > LIQUIDEZ_MAX:
        score -= 10
    elif 3000 <= liquidez < LIQUIDEZ_MIN:
        score += 8

    if liquidez > 0:
        ratio_24h = volume_24h / liquidez
        if ratio_24h >= 3:
            score += 30
            detalhes.append(f"Alta atividade (x{ratio_24h:.1f}) (+30)")
        elif ratio_24h >= 1.2:
            score += 18
        elif ratio_24h >= 0.4:
            score += 8

        if volume_1h / liquidez >= 0.8:
            score += 12

    if 3 <= var_1h <= 45:
        score += 20
        detalhes.append(f"Momentum saudável ({var_1h:.1f}%) (+20)")
    elif 0 < var_1h < 3:
        score += 8
    elif var_1h > 80:
        score -= 15
    elif var_1h < -15:
        score -= 10

    if var_6h > 10 and var_1h > 0:
        score += 8

    if idade_h is not None:
        if IDADE_MIN_HORAS <= idade_h <= 48:
            score += 15
            detalhes.append(f"Idade boa ({idade_h:.1f}h) (+15)")
        elif idade_h < IDADE_MIN_HORAS:
            score -= 20
        elif idade_h > 24 * 7:
            score -= 5

    if buys_1h + sells_1h > 0:
        buy_ratio = buys_1h / (buys_1h + sells_1h)
        if buy_ratio >= 0.62:
            score += 12
        elif buy_ratio <= 0.40:
            score -= 8

    if 0 < preco < 0.001:
        score += 8
    elif 0 < preco < 0.01:
        score += 4

    if 0 < mcap < 300_000:
        score += 15
    elif 300_000 <= mcap < 1_000_000:
        score += 7
    elif mcap > 5_000_000:
        score -= 10

    return {
        "score": max(score, 0),
        "detalhes": " | ".join(detalhes),
        "liquidez": liquidez,
        "volume_24h": volume_24h,
        "var_1h": var_1h,
        "var_6h": var_6h,
        "preco": preco,
        "mcap": mcap,
        "idade_h": idade_h,
        "buys_1h": buys_1h,
        "sells_1h": sells_1h,
    }


def buscar_e_analisar():
    if not os.path.exists(PASTA_RESULTADO):
        os.makedirs(PASTA_RESULTADO)

    print("Iniciando análise de criptos + classificação de risco...\n")

    try:
        url_latest = "https://api.dexscreener.com/token-profiles/latest/v1"
        tokens = requests.get(url_latest, timeout=15).json()
    except Exception as e:
        print(f"Erro ao buscar tokens: {e}")
        return None

    analise_final = []

    for i, t in enumerate(tokens[:MAX_TOKENS_ANALISAR], 1):
        addr = t.get("tokenAddress")
        if not addr:
            continue

        try:
            url_detalhes = f"https://api.dexscreener.com/latest/dex/tokens/{addr}"
            det = requests.get(url_detalhes, timeout=15).json()
            pairs = det.get("pairs") or []

            if not pairs:
                time.sleep(SLEEP_ENTRE_REQUESTS)
                continue

            principal = max(pairs, key=lambda x: safe_float(x.get("liquidity", {}).get("usd")))
            info = calcular_score(principal)
            risco_info = classificar_risco(principal, info)

            liquidez = info["liquidez"]
            volume_24h = info["volume_24h"]

            if liquidez < 2500 or volume_24h < VOLUME_24H_MIN:
                print(f"[{i}] Descartado (liquidez/volume baixo)")
                time.sleep(SLEEP_ENTRE_REQUESTS)
                continue

            simbolo = principal.get("baseToken", {}).get("symbol", "???")
            rede = principal.get("chainId", "?")
            url_dex = principal.get("url") or f"https://dexscreener.com/{rede}/{addr}"

            status_risco = "RISCO" if risco_info["risco"] else "OK"

            analise_final.append({
                "SCORE": info["score"],
                "Risco": status_risco,
                "Motivos_Risco": risco_info["motivos_risco"],
                "Simbolo": simbolo,
                "Rede": rede,
                "Preco_USD": info["preco"],
                "Liquidez_USD": liquidez,
                "Volume_24h": volume_24h,
                "Var_1h_%": info["var_1h"],
                "Var_6h_%": info["var_6h"],
                "MCap_USD": info["mcap"],
                "Idade_horas": round(info["idade_h"], 1) if info["idade_h"] is not None else None,
                "Buys_1h": info["buys_1h"],
                "Sells_1h": info["sells_1h"],
                "Contrato": addr,
                "DexScreener": url_dex,
                "Motivos_Score": info["detalhes"],
            })

            print(f"[{i}] {simbolo:10} | Score: {info['score']:3} | {status_risco:6} | Liq: ${liquidez:,.0f}")

        except Exception as e:
            print(f"[{i}] Erro: {e}")

        time.sleep(SLEEP_ENTRE_REQUESTS)

    if not analise_final:
        print("Nenhum token passou nos filtros.")
        return None

    df = pd.DataFrame(analise_final)
    df = df.sort_values(by="SCORE", ascending=False).reset_index(drop=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    caminho_csv = os.path.join(PASTA_RESULTADO, f"ranking_potencial_{timestamp}.csv")
    caminho_txt = os.path.join(PASTA_RESULTADO, f"ranking_potencial_{timestamp}.txt")

    df.to_csv(caminho_csv, index=False, encoding="utf-8-sig")

    with open(caminho_txt, "w", encoding="utf-8") as f:
        f.write(f"RELATÓRIO CRIPTO + RISCO - {datetime.now()}\n")
        f.write("=" * 90 + "\n\n")
        for idx, row in df.iterrows():
            f.write(f"#{idx+1} {row['Simbolo']} | SCORE: {row['SCORE']} | RISCO: {row['Risco']}\n")
            f.write(f"   Motivos Risco: {row['Motivos_Risco']}\n")
            f.write(f"   Preço: ${row['Preco_USD']:.8f} | Liquidez: ${row['Liquidez_USD']:,.0f}\n")
            f.write(f"   Link: {row['DexScreener']}\n")
            f.write("-" * 90 + "\n")

    print(f"\nCSV salvo em: {caminho_csv}")
    print(f"Tokens OK: {len(df[df['Risco']=='OK'])} | Tokens RISCO: {len(df[df['Risco']=='RISCO'])}")
    return df


if __name__ == "__main__":
    buscar_e_analisar()
