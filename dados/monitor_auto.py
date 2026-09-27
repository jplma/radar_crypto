# monitor_auto.py
import time
import json
import os
from datetime import datetime
import gestao_carteira as gc

PASTA = PASTA = os.path.join(os.path.dirname(__file__), "dados")
ARQUIVO_STATUS = os.path.join(PASTA, "monitor_status.json")
INTERVALO_MINUTOS = 15

def main():
    print("=" * 60)
    print("  MONITOR AUTOMÁTICO DE CARTEIRA - Crypto Radar")
    print(f"  Intervalo: {INTERVALO_MINUTOS} minutos")
    print("=" * 60)
    print("Deixe este script rodando. Use o dashboard para Ativar/Desativar.\n")

    while True:
        status = gc.carregar_status()

        if status.get("ativo", False):
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            print(f"[{agora}] Monitor ATIVO → verificando carteira...")

            try:
                # 1. Obtém o dicionário completo retornado pela função
                retorno = gc.gerar_e_enviar_alertas()
                
                # 2. Extrai a lista de posições analisadas de dentro da chave "resultados"
                resultados_lista = retorno.get("resultados", [])

                # 3. Filtra os alertas fortes da lista
                alertas = [r for r in resultados_lista if isinstance(r, dict) and r.get("ok") and r.get("alerta") in ("VENDER", "RECOMPRAR")]

                if alertas:
                    print(f"   → {len(alertas)} alerta(s) de ação detectado(s).")
                else:
                    print("   → Nenhum alerta forte no momento.")

                # Exibe o status do envio de e-mail no console
                email_status = retorno.get("email_status", {})
                if email_status.get("mensagem"):
                    print(f"   [E-mail]: {email_status['mensagem']}")

                status["ultima_execucao"] = agora
                gc.salvar_status(status)

            except Exception as e:
                print(f"   Erro na verificação: {e}")
        else:
            agora = datetime.now().strftime("%H:%M:%S")
            print(f"[{agora}] Monitor DESATIVADO (aguardando...)")

        time.sleep(INTERVALO_MINUTOS * 60)

if __name__ == "__main__":
    main()
