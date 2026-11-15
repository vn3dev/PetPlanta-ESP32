# -*- coding: utf-8 -*-
"""Le os sensores do ESP32 por Wi-Fi e reutiliza a logica original do PetPlanta.

O notebook deve estar conectado ao Wi-Fi PetPlanta-ESP32.
Este arquivo substitui APENAS o transporte serial; os GIFs, as regras de humor,
as configuracoes e o historico de rega continuam no projeto original.
"""

import json
import os
import random
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from serial_reader import state  # reutiliza SharedState original, sem iniciar a serial
import audio_player

ESP32_URL = os.environ.get("PETPLANTA_ESP32_URL", "http://192.168.4.1").rstrip("/")


class FilaComandosWiFi:
    """Recebe comandos da logica original e guarda o mais recente por tipo.

    SharedState chama write() dentro de um lock; por isso aqui apenas
    enfileiramos. A comunicacao HTTP acontece fora do lock do SharedState.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._pendentes = {}

    def write(self, dados):
        texto = dados.decode("ascii", errors="ignore")
        with self._lock:
            for linha in texto.splitlines():
                linha = linha.strip()
                if linha.startswith("CRITICO:"):
                    self._pendentes["CRITICO"] = linha
                elif linha.startswith("MOOD:"):
                    self._pendentes["MOOD"] = linha
        return len(dados)

    def pendentes(self):
        with self._lock:
            return list(self._pendentes.items())

    def confirmar(self, tipo, comando):
        with self._lock:
            if self._pendentes.get(tipo) == comando:
                del self._pendentes[tipo]


def _buscar_leituras():
    with urlopen(ESP32_URL + "/dados", timeout=2) as resposta:
        dados = json.load(resposta)
    # A API do ESP32 envia luz/solo ja no intervalo 0..1023.
    luz = int(dados["luz"])
    solo = int(dados["solo"])
    temp = dados.get("temperatura")
    temp = float(temp) if temp is not None else None
    festa = bool(dados.get("festa", False))
    if not (0 <= luz <= 1023 and 0 <= solo <= 1023):
        raise ValueError("Leitura de luz ou solo fora de 0..1023")
    if temp is not None and not (-40 <= temp <= 100):
        raise ValueError("Temperatura fora da faixa esperada")
    return {"luz": luz, "solo": solo, "temperatura": temp, "festa": festa}


def _enviar_comando(comando):
    corpo = urlencode({"comando": comando}).encode("ascii")
    pedido = Request(
        ESP32_URL + "/comando",
        data=corpo,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(pedido, timeout=2) as resposta:
        resposta.read()


def _loop_wifi():
    fila = FilaComandosWiFi()
    conectado = False
    print(f"[PetPlanta] Conectando ao ESP32 por Wi-Fi: {ESP32_URL}/dados")

    while True:
        if state.get_run_mode() != "live":
            conectado = False
            time.sleep(0.25)
            continue
        _, audio_context = audio_player.get_context()
        try:
            valores = _buscar_leituras()
            if not conectado:
                # O firmware pode ter reiniciado: envia de novo o ultimo
                # humor e o ultimo estado critico, assim que a rede volta.
                state.serial_conn = fila
                state.resync_arduino()
                print("[PetPlanta] ESP32 conectado via Wi-Fi!")
                conectado = True

            state.update(
                luz=valores["luz"],
                solo=valores["solo"],
                temperatura=valores["temperatura"],
                simulated=False,
                raw_line=f"Wi-Fi: {valores}",
            )
            state.set_festa(valores["festa"])
            # O audio acompanha o humor completo: efeitos de transicao e a
            # musica de festa passam pelo mesmo controlador, sem duplicacao.
            audio_player.set_mood(
                state.mood, mode="live", context_id=audio_context
            )
            print("[PetPlanta] Wi-Fi: Luz={luz} Solo={solo} Temp={temperatura} | "
                  "humor={humor}".format(**valores, humor=state.mood))

            # HTTP de saida: fora do lock de estado
            for tipo, comando in fila.pendentes():
                try:
                    _enviar_comando(comando)
                    fila.confirmar(tipo, comando)
                except Exception as exc:
                    print(f"[PetPlanta] Falha enviando {comando}: {exc}")

        except Exception as exc:
            if conectado:
                print(f"[PetPlanta] ESP32 desconectado: {exc}")
            else:
                print(f"[PetPlanta] Aguardando ESP32 ({exc})")
            conectado = False
            state.serial_conn = None
            state.set_festa(False)
            audio_player.stop()
            with state._lock:
                state.connected = False
                state.simulated = False

        time.sleep(1)


_SIMULATION_STATES = [
    "feliz",
    "seca",
    "doente",
    "frio",
    "dormindo",
    "oculos",
    "festa",
]

_SIMULATION_VALUES = {
    "feliz": (650, 500, 24.0),
    "seca": (650, 150, 24.0),
    "doente": (650, 500, 45.0),
    "frio": (650, 500, 8.0),
    "dormindo": (100, 500, 24.0),
    "oculos": (950, 500, 24.0),
    "festa": (650, 500, 24.0),
}


def _loop_simulation():
    """Percorre todos os humores uma vez por ciclo, sem repetir estado."""
    ordem = []
    proxima_troca = 0.0

    while True:
        if state.get_run_mode() != "simulation":
            ordem = []
            proxima_troca = 0.0
            time.sleep(0.25)
            continue

        agora = time.time()
        if agora >= proxima_troca:
            _, audio_context = audio_player.get_context()
            if not ordem:
                ordem = list(_SIMULATION_STATES)
                random.shuffle(ordem)

            mood = ordem.pop(0)
            luz, solo, temperatura = _SIMULATION_VALUES[mood]
            state.update_simulated(
                mood=mood,
                luz=luz,
                solo=solo,
                temperatura=temperatura,
            )
            audio_player.set_mood(
                mood, mode="simulation", context_id=audio_context
            )
            print(f"[PetPlanta] Simulacao: estado={mood}; "
                  f"proximo em 5 segundos ({len(ordem)} restantes no ciclo)")
            proxima_troca = agora + 5.0

        time.sleep(0.1)


def start_background_reader():
    wifi_thread = threading.Thread(target=_loop_wifi, daemon=True)
    simulation_thread = threading.Thread(target=_loop_simulation, daemon=True)
    wifi_thread.start()
    simulation_thread.start()
    return state
