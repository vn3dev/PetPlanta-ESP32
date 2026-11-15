# -*- coding: utf-8 -*-
"""Controlador de audio do PetPlanta.

No Windows, os efeitos e a musica sao reproduzidos pelo MCI. O frontend usa a
API Audio apenas no celular. Uma unica fonte de verdade evita audio duplicado
e garante que a musica seja encerrada ao sair do modo festa.
"""

import ctypes
import os
import threading
import time
from pathlib import Path


_LOCK = threading.RLock()
_ABERTO = False
_TOCANDO = False
_HABILITADO = False
_HUMOR_ATUAL = None
_MODO_ATUAL = "live"
_CONTEXTO_ATUAL = 0
_CLIENTES_DESKTOP = {}
_CLIENTE_TIMEOUT_S = 5.0
_ALIAS = "petplanta_audio"
_ALIASES_ANTIGOS = ("petplanta_festa",)
_PASTA_AUDIO = Path(__file__).resolve().parent / "static" / "audio"
_ARQUIVOS = {
    "feliz": "feliz.wav",
    "seca": "seco.wav",
    "doente": "critico.wav",
    "frio": "frio.wav",
    "dormindo": "dormindo.mp3",
    "oculos": "sol.wav",
    "festa": "Festa.mp3",
}


def _comando(texto):
    return ctypes.windll.winmm.mciSendStringW(texto, None, 0, None)


def _parar_windows():
    global _ABERTO, _TOCANDO
    # O projeto possui um unico player MCI. Limpa tambem dispositivos/aliases
    # que possam ter ficado de uma versao anterior do servidor.
    _comando("stop all")
    _comando("close all")
    _comando(f"stop {_ALIAS}")
    _comando(f"close {_ALIAS}")
    # Versoes anteriores usavam este alias. Se o servidor foi atualizado sem
    # encerrar o processo antigo, ele tambem precisa ser desligado.
    for alias in _ALIASES_ANTIGOS:
        _comando(f"stop {alias}")
        _comando(f"close {alias}")
    _ABERTO = False
    _TOCANDO = False


def _tem_cliente_desktop_locked():
    agora = time.monotonic()
    expirados = [
        cliente for cliente, ultima_vez in _CLIENTES_DESKTOP.items()
        if agora - ultima_vez > _CLIENTE_TIMEOUT_S
    ]
    for cliente in expirados:
        del _CLIENTES_DESKTOP[cliente]
    return bool(_CLIENTES_DESKTOP)


def _reproduzir_windows(humor):
    global _ABERTO, _TOCANDO
    if not _HABILITADO or not _tem_cliente_desktop_locked() or humor not in _ARQUIVOS:
        return
    arquivo = _PASTA_AUDIO / _ARQUIVOS[humor]
    if not arquivo.is_file():
        print(f"[PetPlanta] Audio nao encontrado: {arquivo}")
        return

    # Sempre fecha o audio anterior antes de abrir o proximo.
    _parar_windows()
    caminho = str(arquivo).replace('"', '')
    tipo = "waveaudio" if arquivo.suffix.lower() == ".wav" else "mpegvideo"
    resultado = _comando(f'open "{caminho}" type {tipo} alias {_ALIAS}')
    if resultado != 0:
        print(f"[PetPlanta] Nao foi possivel abrir {arquivo.name} (codigo {resultado}).")
        return

    _ABERTO = True
    # MCI usa escala de 0 a 1000: efeitos ficam mais baixos que a musica.
    _comando(f"setaudio {_ALIAS} volume to {1000 if humor == 'festa' else 220}")
    comando_play = f"play {_ALIAS} repeat" if humor == "festa" else f"play {_ALIAS}"
    resultado = _comando(comando_play)
    if resultado != 0:
        print(f"[PetPlanta] Nao foi possivel reproduzir {arquivo.name} (codigo {resultado}).")
        _parar_windows()
    else:
        _TOCANDO = True
        print(f"[PetPlanta] Audio iniciado: {arquivo.name}")


def set_enabled(enabled):
    """Habilita ou desabilita o audio do notebook."""
    global _HABILITADO
    with _LOCK:
        _HABILITADO = bool(enabled)
        if os.name != "nt":
            return
        if not _HABILITADO:
            _parar_windows()
            print("[PetPlanta] Audio do notebook desabilitado.")
        elif _HUMOR_ATUAL == "festa":
            # A musica volta ao reativar; efeitos curtos nao sao repetidos.
            _reproduzir_windows(_HUMOR_ATUAL)


def set_client_presence(client_id, present=True):
    """Registra a página desktop e corta o audio quando ela desaparece."""
    global _HUMOR_ATUAL, _CONTEXTO_ATUAL
    client_id = str(client_id or "").strip()
    if not client_id:
        return
    with _LOCK:
        if present:
            havia_clientes = _tem_cliente_desktop_locked()
            _CLIENTES_DESKTOP[client_id] = time.monotonic()
            # Se a festa estava ativa enquanto a pagina estava fechada, ela
            # pode voltar a tocar assim que o notebook for reaberto.
            if not havia_clientes and _HABILITADO and _HUMOR_ATUAL == "festa":
                _reproduzir_windows(_HUMOR_ATUAL)
        else:
            _CLIENTES_DESKTOP.pop(client_id, None)
            if not _tem_cliente_desktop_locked():
                _HUMOR_ATUAL = None
                _CONTEXTO_ATUAL += 1
                if os.name == "nt":
                    _parar_windows()


def _presence_watchdog():
    global _HUMOR_ATUAL, _CONTEXTO_ATUAL
    while True:
        time.sleep(1.0)
        with _LOCK:
            havia_clientes = bool(_CLIENTES_DESKTOP)
            tem_clientes = _tem_cliente_desktop_locked()
            if havia_clientes and not tem_clientes:
                _HUMOR_ATUAL = None
                # A ausencia do navegador invalida leituras de audio antigas.
                _CONTEXTO_ATUAL += 1
                if os.name == "nt":
                    _parar_windows()


def is_enabled():
    with _LOCK:
        return _HABILITADO


def set_mood(humor, *, mode=None, context_id=None):
    """Reproduz o audio associado a uma nova transicao de humor.

    ``mode`` identifica a thread que gerou a leitura. Isso impede que uma
    leitura antiga, concluida depois de uma troca de switch, ressuscite audio.
    """
    global _HUMOR_ATUAL
    humor = str(humor or "").lower()
    if humor not in _ARQUIVOS:
        return
    with _LOCK:
        if mode is not None and mode != _MODO_ATUAL:
            return
        if context_id is not None and context_id != _CONTEXTO_ATUAL:
            return
        if humor == _HUMOR_ATUAL:
            return
        _HUMOR_ATUAL = humor
        if os.name == "nt" and _HABILITADO:
            _reproduzir_windows(humor)


def set_run_mode(mode):
    """Troca o contexto do audio e cancela imediatamente o player atual.

    A troca interrompe o audio atual e limpa o humor anterior. O proximo
    estado da nova fonte inicia um audio novo normalmente, desde que o botao
    de audio esteja habilitado.
    """
    global _MODO_ATUAL, _HUMOR_ATUAL, _CONTEXTO_ATUAL
    if mode not in ("live", "simulation"):
        raise ValueError("Modo de audio invalido")
    with _LOCK:
        _MODO_ATUAL = mode
        _CONTEXTO_ATUAL += 1
        _HUMOR_ATUAL = None
        if os.name == "nt":
            _parar_windows()


def get_context():
    """Retorna o modo e a geracao atuais para uma leitura em andamento."""
    with _LOCK:
        return _MODO_ATUAL, _CONTEXTO_ATUAL


def set_festa(ativo):
    """Compatibilidade com chamadas antigas; prefira usar set_mood()."""
    global _HUMOR_ATUAL
    if ativo:
        set_mood("festa")
    else:
        with _LOCK:
            if _HUMOR_ATUAL == "festa":
                _HUMOR_ATUAL = None
                if os.name != "nt":
                    return
                _parar_windows()


def stop():
    """Interrompe o audio, usado quando o ESP32 desconecta."""
    global _HUMOR_ATUAL, _CONTEXTO_ATUAL
    with _LOCK:
        _HUMOR_ATUAL = None
        _CONTEXTO_ATUAL += 1
        if os.name == "nt":
            _parar_windows()


# Limpa qualquer alias do PetPlanta deixado por uma execucao anterior antes
# de iniciar o watchdog e aceitar novas leituras.
if os.name == "nt":
    _parar_windows()

threading.Thread(target=_presence_watchdog, daemon=True, name="petplanta-audio-watchdog").start()
