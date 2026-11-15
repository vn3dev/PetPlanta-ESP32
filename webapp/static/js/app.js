(function () {
  const canvas = document.getElementById("pet-canvas");
  const moodLabel = document.getElementById("mood-label");
  const badgeConexao = document.getElementById("badge-conexao");
  const badgeSim = document.getElementById("badge-sim");
  const lastUpdateEl = document.getElementById("last-update");
  const modeSwitch = document.getElementById("mode-switch");

  const valLuz = document.getElementById("val-luz");
  const valSolo = document.getElementById("val-solo");
  const valTemp = document.getElementById("val-temp");

  const barLuz = document.getElementById("bar-luz");
  const barSolo = document.getElementById("bar-solo");
  const barTemp = document.getElementById("bar-temp");

  const countdownLuz = document.getElementById("countdown-luz");
  const countdownSolo = document.getElementById("countdown-solo");
  const ultimaRegaEl = document.getElementById("ultima-rega");

  const btnSim = document.getElementById("btn-sim");
  const btnAudio = document.getElementById("btn-audio");
  const isMobileDevice = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
  const clientId = (window.crypto && crypto.randomUUID)
    ? crypto.randomUUID()
    : `petplanta-${Date.now()}-${Math.random().toString(16).slice(2)}`;

  const SOUND_FILES = {
    feliz: "feliz.wav",
    seca: "seco.wav",
    doente: "critico.wav",
    frio: "frio.wav",
    dormindo: "dormindo.mp3",
    oculos: "sol.wav",
    festa: "Festa.mp3",
  };
  const VIBRATION_PATTERNS = {
    feliz: 90,
    seca: [140, 80, 140],
    doente: [300, 100, 300, 100, 500],
    frio: [180, 80, 180],
    dormindo: 60,
    oculos: [80, 70, 80],
    festa: [100, 70, 100, 70, 100],
  };

  // Escalas usadas so para desenhar a barra de progresso de cada sensor
  // (nao tem relacao com os thresholds de mood em config.py).
  const BAR_MAX = { luz: 1023, solo: 600, temp: 40 };

  // Cores fixas usadas nas barras (verde/amarelo/vermelho do projeto).
  const BAR_COLOR_GREEN = "#4fa861";
  const BAR_COLOR_YELLOW = "#e0a23b";
  const BAR_COLOR_RED = "#d9534f";
  // Azul clarinho da barra de temperatura quando "com frio" - usa a MESMA
  // cor configurada em config.MOOD_BG["frio"] (exposta via window.MOOD_BG),
  // entao se a paleta mudar la, a barra acompanha sem precisar editar JS.
  const BAR_COLOR_FRIO = (window.MOOD_BG && window.MOOD_BG.frio) || "rgb(213, 238, 250)";
  // Limiar amarelo/verde da barra de solo - independente da escala visual
  // (BAR_MAX.solo), pra mudar o tamanho da barra sem mudar quando ela fica
  // amarela ou verde.
  const SOLO_AMARELO_MAX = 300;

  function numOr(value, fallback) {
    return value === null || value === undefined ? fallback : value;
  }

  // Cor da barra de luz: vermelho se estiver no limiar de "dormindo" (sem
  // luz), senao amarelo até 40% da escala da barra, verde dali pra cima.
  function colorForLuz(value, data) {
    if (value === null || value === undefined) return BAR_COLOR_GREEN;
    const luzEscuroMax = numOr(data.luz_escuro_max, 400);
    if (value <= luzEscuroMax) return BAR_COLOR_RED;
    const pct = value / BAR_MAX.luz;
    return pct <= 0.4 ? BAR_COLOR_YELLOW : BAR_COLOR_GREEN;
  }

  // Cor da barra de solo: vermelho se estiver no limiar de "seca", amarelo
  // se estiver até SOLO_AMARELO_MAX, verde acima disso.
  function colorForSolo(value, data) {
    if (value === null || value === undefined) return BAR_COLOR_GREEN;
    const soloSecoMax = numOr(data.solo_seco_max, 250);
    if (value < soloSecoMax) return BAR_COLOR_RED;
    return value <= SOLO_AMARELO_MAX ? BAR_COLOR_YELLOW : BAR_COLOR_GREEN;
  }

  // Cor da barra de temperatura: azul claro (frio), vermelho (calor extremo
  // / doente), verde no meio.
  function colorForTemp(value, data) {
    if (value === null || value === undefined) return BAR_COLOR_GREEN;
    const tempFrioMax = numOr(data.temp_frio_max, 15);
    const tempDoenteMin = numOr(data.temp_doente_min, 40);
    if (value <= tempFrioMax) return BAR_COLOR_FRIO;
    if (value >= tempDoenteMin) return BAR_COLOR_RED;
    return BAR_COLOR_GREEN;
  }

  let petPlayer = null;
  let playerReady = false;
  let latestMood = null;
  let hasReceivedMood = false;
  let soundEnabled = false;
  let moodAudio = null;
  let audioToggleBusy = false;
  let audioGeneration = 0;
  let pollInFlight = false;
  let modeChangeInFlight = false;
  let modeGeneration = 0;

  function updateAudioButton() {
    if (!btnAudio) return;
    btnAudio.textContent = soundEnabled ? "🔊" : "🔇";
    btnAudio.title = soundEnabled
      ? (isMobileDevice ? "Desativar sons e vibração" : "Desativar áudio do notebook")
      : (isMobileDevice ? "Ativar sons e vibração" : "Ativar áudio do notebook");
    btnAudio.setAttribute("aria-label", btnAudio.title);
    btnAudio.setAttribute("aria-pressed", String(soundEnabled));
    btnAudio.classList.toggle("active", soundEnabled);
  }

  function soundUrl(mood) {
    const file = SOUND_FILES[mood];
    return file ? `/static/audio/${file}` : null;
  }

  function vibrateForMood(mood) {
    if (!soundEnabled || !isMobileDevice || !navigator.vibrate) return;
    navigator.vibrate(VIBRATION_PATTERNS[mood] || 100);
  }

  function playMoodSound(mood) {
    // No notebook, o áudio é reproduzido exclusivamente pelo Python/MCI.
    // Isso evita que o MP3 toque duas vezes na mesma máquina.
    if (!soundEnabled || !isMobileDevice) return;
    const url = soundUrl(mood);
    if (!url) return;

    stopBrowserAudio();
    if (!moodAudio) moodAudio = new Audio();
    if (petPlayer && typeof petPlayer.syncAudio === "function") {
      petPlayer.syncAudio(moodAudio);
    }
    moodAudio.src = `${url}?v=${audioGeneration}`;
    moodAudio.currentTime = 0;
    moodAudio.loop = mood === "festa";
    // Efeitos curtos ficam abaixo da música principal para não assustar o
    // visitante nem mascarar o áudio ambiente.
    moodAudio.volume = 0.22;
    moodAudio.play().catch(() => {
      // O navegador pode bloquear o áudio se a ativação não tiver vindo de
      // uma interação recente do usuário. O botão de sons permite liberar isso.
    });
    vibrateForMood(mood);
  }

  function stopBrowserAudio() {
    audioGeneration += 1;
    if (moodAudio) {
      moodAudio.pause();
      moodAudio.currentTime = 0;
      moodAudio.removeAttribute("src");
      moodAudio.load();
    }
  }

  function silenceBrowserAudio() {
    stopBrowserAudio();
    if (navigator.vibrate) navigator.vibrate(0);
  }

  async function toggleAudio() {
    if (audioToggleBusy) return;
    audioToggleBusy = true;
    const previousEnabled = soundEnabled;
    const nextEnabled = !soundEnabled;

    try {
      if (!isMobileDevice) {
        soundEnabled = nextEnabled;
        updateAudioButton();
        const res = await fetch("/api/audio", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: nextEnabled }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Nao foi possivel alterar o audio.");
        soundEnabled = data.enabled;
        updateAudioButton();
        return;
      }

      soundEnabled = nextEnabled;
      updateAudioButton();

      if (soundEnabled) {
        // Essa chamada acontece dentro do clique e libera o audio em browsers
        // moveis que bloqueiam autoplay.
        playMoodSound(latestMood || "feliz");
      } else if (moodAudio) {
        stopBrowserAudio();
        if (navigator.vibrate) navigator.vibrate(0);
      }
    } catch (err) {
      soundEnabled = previousEnabled;
      updateAudioButton();
      console.error(err);
    } finally {
      audioToggleBusy = false;
    }
  }

  async function syncAudioPreference() {
    if (isMobileDevice) {
      updateAudioButton();
      return;
    }
    try {
      const res = await fetch("/api/audio", { cache: "no-store" });
      const data = await res.json();
      soundEnabled = Boolean(data.enabled);
    } catch (err) {
      soundEnabled = false;
    }
    updateAudioButton();
  }

  function sendHeartbeat(active = true) {
    if (isMobileDevice) return;
    const payload = JSON.stringify({ client_id: clientId, desktop: true, active });
    if (!active && navigator.sendBeacon) {
      navigator.sendBeacon(
        "/api/heartbeat",
        new Blob([payload], { type: "application/json" })
      );
      return;
    }
    fetch("/api/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: payload,
      cache: "no-store",
    }).catch(() => {});
  }

  // O player novo desenha a planta e o cenário no mesmo canvas. Ele mantém a
  // transição corrente, enfileira apenas o último pedido e anima partículas
  // sem depender do timing de GIF do navegador.
  async function initPetPlayer() {
    if (!canvas || !window.PetPlanta) return;
    try {
      petPlayer = await new PetPlanta(canvas, {
        base: "/static/pet-planta/sprites/",
        scene: true,
        ditherMs: 360,
      }).load();
      petPlayer.start("happy");
      playerReady = true;
      petPlayer.setMood((window.PET_MOOD_MAP && window.PET_MOOD_MAP[latestMood]) || "happy");
    } catch (err) {
      console.error("Nao foi possivel carregar os assets da PetPlanta", err);
    }
  }

  function applyMood(newMood) {
    const previousMood = latestMood;
    latestMood = newMood;
    const label = (window.MOOD_LABELS && window.MOOD_LABELS[newMood]) || newMood;
    moodLabel.textContent = label;
    const visualMood = (window.PET_MOOD_MAP && window.PET_MOOD_MAP[newMood]) || "happy";
    if (playerReady) petPlayer.setMood(visualMood);

    if (hasReceivedMood && previousMood !== newMood) {
      playMoodSound(newMood);
    }
    hasReceivedMood = true;
  }

  function fmt(value, suffix, digits) {
    if (value === null || value === undefined) return "--";
    if (typeof digits === "number") return value.toFixed(digits) + suffix;
    return value + suffix;
  }

  function setBar(el, value, max) {
    if (value === null || value === undefined) {
      el.style.width = "0%";
      return;
    }
    const pct = Math.max(0, Math.min(100, (value / max) * 100));
    el.style.width = pct + "%";
  }

  function setBarColor(el, color) {
    el.style.backgroundColor = color;
  }

  // Mostra "Critico em Xh Ym Zs" enquanto a condicao (seca/dormindo) estiver
  // ativa; quando o tempo zera, mostra que ja virou critico. Esconde o
  // contador quando a condicao nao esta mais ativa (valor null).
  function setCountdown(el, secondsRemaining) {
    if (secondsRemaining === null || secondsRemaining === undefined) {
      el.classList.add("hidden");
      el.classList.remove("critico");
      return;
    }

    el.classList.remove("hidden");

    if (secondsRemaining <= 0) {
      el.textContent = "Critico!";
      el.classList.add("critico");
      return;
    }

    el.classList.remove("critico");
    const total = Math.floor(secondsRemaining);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const s = total % 60;
    el.textContent = `Critico em ${h}h ${m}m ${s}s`;
  }

  // Mostra "Ultima rega Xh Ym atras" desde a ultima vez que o solo cruzou
  // REGA_DETECTADA_MIN subindo (ver serial_reader.py). Fica visivel e so
  // cresce até a proxima rega ser detectada - nao some so porque o solo
  // secou de novo. secondsAgo null = nenhuma rega detectada ainda.
  function setUltimaRega(el, secondsAgo) {
    if (secondsAgo === null || secondsAgo === undefined) {
      el.classList.add("hidden");
      return;
    }

    el.classList.remove("hidden");
    const total = Math.floor(secondsAgo);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);

    if (h > 0) {
      el.textContent = `Última rega ${h}h ${m}m atrás`;
    } else if (m > 0) {
      el.textContent = `Última rega ${m}m atrás`;
    } else {
      el.textContent = "Última rega agora";
    }
  }

  async function poll() {
    if (pollInFlight || modeChangeInFlight) return;
    pollInFlight = true;
    const requestGeneration = modeGeneration;
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      const data = await res.json();
      if (requestGeneration !== modeGeneration || modeChangeInFlight) return;

      valLuz.textContent = fmt(data.luz, "");
      valSolo.textContent = fmt(data.solo, "");
      valTemp.textContent = fmt(data.temperatura, " °C", 1);

      setBar(barLuz, data.luz, BAR_MAX.luz);
      setBar(barSolo, data.solo, BAR_MAX.solo);
      setBar(barTemp, data.temperatura, BAR_MAX.temp);

      setBarColor(barLuz, colorForLuz(data.luz, data));
      setBarColor(barSolo, colorForSolo(data.solo, data));
      setBarColor(barTemp, colorForTemp(data.temperatura, data));

      setCountdown(countdownLuz, data.dormindo_restante_s);
      setCountdown(countdownSolo, data.seca_restante_s);
      setUltimaRega(ultimaRegaEl, data.ultima_rega_s_atras);

      const simulationMode = data.run_mode === "simulation";
      if (modeSwitch) {
        modeSwitch.checked = simulationMode;
        modeSwitch.setAttribute("aria-checked", String(simulationMode));
        modeSwitch.classList.remove("error");
      }
      syncSimPanelFromState(data);

      if (data.last_update) {
        const d = new Date(data.last_update * 1000);
        lastUpdateEl.textContent = d.toLocaleTimeString();
      }

      applyMood(data.mood);
    } catch (err) {
      if (modeSwitch) modeSwitch.classList.add("error");
      console.error("Falha ao atualizar o estado da PetPlanta", err);
    } finally {
      pollInFlight = false;
    }
  }

  async function changeRunMode() {
    if (!modeSwitch) return;
    const mode = modeSwitch.checked ? "simulation" : "live";
    const previousMode = mode === "simulation" ? "live" : "simulation";
    modeGeneration += 1;
    modeChangeInFlight = true;
    modeSwitch.disabled = true;
    // A troca de fonte corta imediatamente qualquer audio da fonte anterior.
    silenceBrowserAudio();
    try {
      const res = await fetch("/api/mode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Nao foi possivel alterar o modo.");
      modeSwitch.checked = data.mode === "simulation";
      modeSwitch.setAttribute("aria-checked", String(modeSwitch.checked));
      await poll();
    } catch (err) {
      modeSwitch.checked = previousMode === "simulation";
      modeSwitch.setAttribute("aria-checked", String(modeSwitch.checked));
      console.error(err);
    } finally {
      modeChangeInFlight = false;
      modeSwitch.disabled = false;
    }
  }

  if (modeSwitch) modeSwitch.addEventListener("change", changeRunMode);

  if (btnAudio) btnAudio.addEventListener("click", toggleAudio);
  syncAudioPreference();

  // --- Tela de configuracoes (limiares editaveis) ---
  const btnConfig = document.getElementById("btn-config");
  const btnConfigClose = document.getElementById("btn-config-close");
  const btnConfigCancel = document.getElementById("btn-config-cancel");
  const overlay = document.getElementById("config-overlay");
  const configForm = document.getElementById("config-form");
  const configError = document.getElementById("config-error");
  const btnConfigSave = document.getElementById("btn-config-save");

  function showConfigError(msg) {
    configError.textContent = msg;
    configError.classList.remove("hidden");
  }

  function hideConfigError() {
    configError.classList.add("hidden");
  }

  function fillConfigForm(data) {
    Object.keys(data).forEach((key) => {
      const input = configForm.elements.namedItem(key);
      if (input) input.value = data[key];
    });
  }

  async function openConfigModal() {
    hideConfigError();
    overlay.classList.remove("hidden");
    try {
      const res = await fetch("/api/config", { cache: "no-store" });
      if (!res.ok) throw new Error("Nao foi possivel carregar as configuracoes atuais.");
      const data = await res.json();
      fillConfigForm(data);
    } catch (err) {
      showConfigError(err.message || "Erro ao carregar configuracoes.");
    }
  }

  function closeConfigModal() {
    overlay.classList.add("hidden");
    hideConfigError();
  }

  function readConfigForm() {
    const formData = new FormData(configForm);
    const values = {};
    formData.forEach((value, key) => {
      values[key] = value;
    });
    return values;
  }

  async function saveConfig(ev) {
    ev.preventDefault();
    hideConfigError();
    btnConfigSave.disabled = true;
    btnConfigSave.textContent = "Salvando...";
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(readConfigForm()),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Nao foi possivel salvar as configuracoes.");
      }
      fillConfigForm(data);
      closeConfigModal();
    } catch (err) {
      showConfigError(err.message || "Erro ao salvar configuracoes.");
    } finally {
      btnConfigSave.disabled = false;
      btnConfigSave.textContent = "Salvar";
    }
  }

  if (btnConfig) btnConfig.addEventListener("click", openConfigModal);
  if (btnConfigClose) btnConfigClose.addEventListener("click", closeConfigModal);
  if (btnConfigCancel) btnConfigCancel.addEventListener("click", closeConfigModal);
  if (overlay) {
    overlay.addEventListener("click", (ev) => {
      if (ev.target === overlay) closeConfigModal();
    });
  }
  if (configForm) configForm.addEventListener("submit", saveConfig);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !overlay.classList.contains("hidden")) closeConfigModal();
  });

  // --- Tela de simulacao (modo aleatorio/manual + valores de luz/solo/temp) ---
  const btnSimClose = document.getElementById("btn-sim-close");
  const btnSimCancel = document.getElementById("btn-sim-cancel");
  const simOverlay = document.getElementById("sim-overlay");
  const simForm = document.getElementById("sim-form");
  const simError = document.getElementById("sim-error");
  const btnSimSave = document.getElementById("btn-sim-save");
  const simModeRandom = document.getElementById("sim-mode-random");
  const simModeManual = document.getElementById("sim-mode-manual");
  const simLuz = document.getElementById("sim-luz");
  const simSolo = document.getElementById("sim-solo");
  const simTemp = document.getElementById("sim-temp");

  // So preenche os campos com o que vem do /api/state na PRIMEIRA vez que o
  // painel aparece (ou depois de fechado/reaberto) - assim nao fica
  // sobrescrevendo o que o usuario esta digitando a cada poll de 2s.
  let simSyncedOnce = false;

  function updateSimFieldsDisabled() {
    const manual = simModeManual.checked;
    simLuz.disabled = !manual;
    simSolo.disabled = !manual;
    simTemp.disabled = !manual;
  }

  function syncSimPanelFromState(data) {
    if (!data.simulated) {
      simSyncedOnce = false;
      return;
    }
    if (simSyncedOnce) return;
    simSyncedOnce = true;
    (data.sim_mode === "manual" ? simModeManual : simModeRandom).checked = true;
    if (data.sim_manual) {
      simLuz.value = data.sim_manual.luz;
      simSolo.value = data.sim_manual.solo;
      simTemp.value = data.sim_manual.temperatura;
    }
    updateSimFieldsDisabled();
  }

  function showSimError(msg) {
    simError.textContent = msg;
    simError.classList.remove("hidden");
  }

  function hideSimError() {
    simError.classList.add("hidden");
  }

  function openSimModal() {
    hideSimError();
    simOverlay.classList.remove("hidden");
  }

  function closeSimModal() {
    simOverlay.classList.add("hidden");
    hideSimError();
  }

  async function saveSim(ev) {
    ev.preventDefault();
    hideSimError();
    btnSimSave.disabled = true;
    btnSimSave.textContent = "Aplicando...";
    try {
      const body = { sim_mode: simModeManual.checked ? "manual" : "random" };
      if (body.sim_mode === "manual") {
        body.luz = simLuz.value;
        body.solo = simSolo.value;
        body.temperatura = simTemp.value;
      }
      const res = await fetch("/api/simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Nao foi possivel aplicar a simulacao.");
      }
      closeSimModal();
    } catch (err) {
      showSimError(err.message || "Erro ao aplicar simulacao.");
    } finally {
      btnSimSave.disabled = false;
      btnSimSave.textContent = "Aplicar";
    }
  }

  if (btnSim) btnSim.addEventListener("click", openSimModal);
  if (btnSimClose) btnSimClose.addEventListener("click", closeSimModal);
  if (btnSimCancel) btnSimCancel.addEventListener("click", closeSimModal);
  if (simOverlay) {
    simOverlay.addEventListener("click", (ev) => {
      if (ev.target === simOverlay) closeSimModal();
    });
  }
  if (simForm) simForm.addEventListener("submit", saveSim);
  if (simModeRandom) simModeRandom.addEventListener("change", updateSimFieldsDisabled);
  if (simModeManual) simModeManual.addEventListener("change", updateSimFieldsDisabled);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !simOverlay.classList.contains("hidden")) closeSimModal();
  });

  initPetPlayer();
  sendHeartbeat();
  setInterval(() => sendHeartbeat(), 2000);
  window.addEventListener("pagehide", () => sendHeartbeat(false));
  poll();
  setInterval(poll, 2000);
})();
