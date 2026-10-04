"""Busca resultados só das ligas com sinais já jogados e ainda sem resultado
(cada consulta de resultados custa 2 créditos; assim gasta pouco)."""
import csv, os
from datetime import datetime, timedelta, timezone
import requests
import config as C

def main():
    cam_s, cam_r = os.path.join(C.PASTA, "sinais.csv"), os.path.join(C.PASTA, "resultados.csv")
    if not os.path.exists(cam_s):
        return print("sem sinais")
    feitos = set()
    if os.path.exists(cam_r):
        with open(cam_r) as f:
            feitos = {r["jogo_id"] for r in csv.DictReader(f)}
    agora = datetime.now(timezone.utc)
    ligas = set()
    with open(cam_s) as f:
        for s in csv.DictReader(f):
            ini = datetime.fromisoformat(s["inicio"].replace("Z", "+00:00"))
            if s["jogo_id"] not in feitos and agora - timedelta(days=3) < ini < agora - timedelta(hours=3):
                ligas.add(s["liga"])
    novos = []
    for liga in sorted(ligas):
        r = requests.get(f"{C.API}/sports/{liga}/scores/", timeout=30,
                         params={"apiKey": C.chave(), "daysFrom": 3})
        r.raise_for_status()
        for e in r.json():
            if e.get("completed") and e["id"] not in feitos and e.get("scores"):
                g = {x["name"]: int(x["score"]) for x in e["scores"]}
                novos.append({"jogo_id": e["id"], "liga": liga, "casa_time": e["home_team"], "fora_time": e["away_team"],
                              "gols_casa": g.get(e["home_team"]), "gols_fora": g.get(e["away_team"])})
                feitos.add(e["id"])
    if novos:
        novo_arq = not os.path.exists(cam_r)
        with open(cam_r, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(novos[0]))
            if novo_arq:
                w.writeheader()
            w.writerows(novos)
    print(f"ligas consultadas: {len(ligas)} | resultados novos: {len(novos)}")

if __name__ == "__main__":
    main()
