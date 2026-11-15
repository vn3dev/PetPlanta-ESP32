# -*- coding: utf-8 -*-
"""PetPlanta Flask -- mesma interface do projeto original, agora via Wi-Fi."""
from flask import Flask, jsonify, render_template, request

import config
import audio_player
from wifi_reader import start_background_reader

app = Flask(__name__)
state = start_background_reader()


@app.route("/")
def index():
    return render_template(
        "index.html",
        moods=config.MOODS,
        mood_labels=config.MOOD_LABELS,
        mood_bg=config.MOOD_BG,
        transition_ms=config.TRANSITION_DURATION_MS,
        transition_frames=config.TRANSITION_FRAMES,
        frame_ms=config.TRANSITION_FRAME_MS,
    )


@app.route("/api/state")
def api_state():
    return jsonify(state.to_dict())


@app.route("/api/mode", methods=["GET"])
def api_mode_get():
    return jsonify({"mode": state.get_run_mode()})


@app.route("/api/mode", methods=["POST"])
def api_mode_post():
    body = request.get_json(silent=True)
    mode = body.get("mode") if isinstance(body, dict) else None
    if mode not in ("live", "simulation"):
        return jsonify({"error": "'mode' precisa ser 'live' ou 'simulation'."}), 400

    if mode in ("live", "simulation"):
        # A próxima leitura real assume novamente o controle do humor e dos
        # sensores; não deixamos uma música de demonstração presa no fundo.
        audio_player.set_run_mode(mode)
        state.set_festa(False)
        state.set_run_mode(mode)
    return jsonify({"mode": state.get_run_mode()})


@app.route("/api/audio", methods=["GET"])
def api_audio_get():
    return jsonify({"enabled": audio_player.is_enabled()})


@app.route("/api/audio", methods=["POST"])
def api_audio_post():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get("enabled"), bool):
        return jsonify({"error": "'enabled' precisa ser booleano."}), 400
    audio_player.set_enabled(body["enabled"])
    return jsonify({"enabled": audio_player.is_enabled()})


@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Corpo da requisicao invalido."}), 400
    client_id = body.get("client_id")
    if not isinstance(client_id, str) or not client_id.strip():
        return jsonify({"error": "'client_id' e obrigatorio."}), 400
    # Somente o navegador do notebook controla o audio MCI. Celulares mantem
    # seus proprios elementos Audio no frontend e nao prolongam a sessao local.
    if body.get("desktop") is True:
        audio_player.set_client_presence(client_id, body.get("active", True) is not False)
    return jsonify({"ok": True})


@app.route("/api/config", methods=["GET"])
def api_config_get():
    return jsonify(config.get_editable_config())


@app.route("/api/config", methods=["POST"])
def api_config_post():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Corpo da requisicao invalido (esperado JSON)."}), 400
    try:
        novo = config.update_editable_config(body)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(novo)


@app.route("/api/simulation", methods=["GET"])
def api_simulation_get():
    return jsonify({"sim_mode": state.sim_mode, "sim_manual": dict(state.sim_manual)})


@app.route("/api/simulation", methods=["POST"])
def api_simulation_post():
    """Guarda as configuracoes de simulacao para compatibilidade com a interface.
    No modo Wi-Fi, sem o ESP32, o app nao inventa leituras.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Corpo da requisicao invalido (esperado JSON)."}), 400
    mode = body.get("sim_mode")
    if mode not in ("random", "manual"):
        return jsonify({"error": "'sim_mode' precisa ser 'random' ou 'manual'."}), 400
    manual_values = {}
    bounds = {
        "luz": ("Luz", 0, 1023),
        "solo": ("Solo", 0, 1023),
        "temperatura": ("Temperatura", -40, 100),
    }
    for key, (label, lo, hi) in bounds.items():
        if key in body and body[key] not in (None, ""):
            try:
                v = float(body[key])
            except (TypeError, ValueError):
                return jsonify({"error": f"Valor invalido em '{label}': precisa ser um numero"}), 400
            if not (lo <= v <= hi):
                return jsonify({"error": f"'{label}' precisa estar entre {lo} e {hi}"}), 400
            manual_values[key] = v
    state.set_sim_mode(mode)
    if manual_values:
        state.set_sim_manual_values(**manual_values)
    return jsonify({"sim_mode": state.sim_mode, "sim_manual": dict(state.sim_manual)})

if __name__ == "__main__":
    print("PetPlanta iniciado!")
    app.run(
        host="0.0.0.0",
        port=80,
        debug=False,    
        use_reloader=False
    )
