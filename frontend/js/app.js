(function (global) {
  const TIMES_KEY = "ENABLED_PROGRAMS/NewsSmall/start_times";
  const PREP_KEY = "ENABLED_PROGRAMS/NewsSmall/preparation_needed_mins";
  const BACKGROUNDS = [
    "1VuZTnscmraqYUZHZ1EQbecdrVfPm_l244Nl7PF1FkChpTa4adEpJMsKskpKRJXqryRvomDp.jpeg",
    "20160308_preview.jpeg",
    "3nKXMUBrk6P9d1hoN_4inCDZvSVkFQ_vkrA3YyqWggi6_F2aDFU7gJYF9CjD7v3MybVD8eGQ.jpeg",
    "IMG_1556_preview.jpeg",
    "IMG_5239_preview.jpeg",
    "IMG_6271_preview.jpeg",
    "ldTUiHwSCDrpbn_6FoA8x0jWqOayj8i54Vtw_WoLHPiBQ3eBBD4I3MiiVRiQ9LAl4CsJfS80.jpeg",
    "NKhd8U97D677IGE_3yYeNKT7Ii7nOjrV_8mItpXRK8HgfJmiYHb9A4OsbSQCCvapT6x16z4W.jpeg",
  ];
  // whatsplaying corrects the playhead every few seconds; the UI counts on its own
  // and snaps to the server when the two disagree by more than this.
  const RESYNC_S = 2;

  const api = global.LoradApi;
  const config = global.LORAD_CONFIG;

  const state = {
    audio: null,
    volume: 100,
    players: {},
    currentPlayer: "",
    stations: {},
    stationTech: "",
    stationName: "",
    track: "",
    canSkip: false,
    canSwitch: true,
    liked: null,
    skipInFlight: false,
    likeInFlight: false,
    loading: true,
    switchingPlayer: false,
    socket: null,
    reconnectTimer: null,
    bufferTimer: null,
    positionTimer: null,
    length: null,
    position: null,
    positionKey: "",
  };

  const schedule = {
    times: [],
    saved: [],
    prepMins: null,
    loading: false,
    loaded: false,
    toastTimer: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function setHidden(el, hidden) {
    el.hidden = hidden;
  }

  function route() {
    const hash = location.hash.replace(/^#/, "");
    return hash.startsWith("/") ? hash : "/";
  }

  function navigate(path) {
    location.hash = path;
  }

  function showView(id) {
    ["view-login", "view-player", "view-schedule"].forEach((viewId) => {
      setHidden($(viewId), viewId !== id);
    });
  }

  function fillSelect(select, entries, value) {
    const placeholder = select.options[0].textContent;
    select.innerHTML = "";
    select.appendChild(new Option(placeholder, ""));
    entries.forEach(([optionValue, label]) => select.appendChild(new Option(label, optionValue)));
    select.value = value || "";
  }

  function stationLabel(tech, readable) {
    if (tech === "user:onyourwave") return "Моя волна";
    return readable || tech;
  }

  function syncStation() {
    const select = $("station");
    if (!state.stationTech) return;
    const option = Array.from(select.options).find((item) => item.value === state.stationTech);
    if (option) {
      // the list already carries readable names; only the Yandex wave needs its own label
      if (state.stationTech === "user:onyourwave") option.textContent = "Моя волна";
    } else {
      // the backend plays something outside the list: show it anyway
      select.appendChild(new Option(stationLabel(state.stationTech, state.stationName), state.stationTech));
    }
    select.value = state.stationTech;
  }

  function clock(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function renderProgress() {
    const known = state.length != null && state.position != null;
    setHidden($("track-progress"), !known);
    if (!known) return;
    $("track-position").textContent = clock(state.position);
    $("track-length").textContent = clock(state.length);
  }

  function applyProgress(data) {
    const length = Number(data.length_s);
    const position = Number(data.position_s);
    if (!Number.isFinite(length) || !Number.isFinite(position)) {
      state.length = null;
      state.position = null;
      state.positionKey = "";
      renderProgress();
      return;
    }
    const key = `${data.playing || ""}|${length}`;
    if (key !== state.positionKey || state.position == null || Math.abs(position - state.position) > RESYNC_S) {
      state.position = position;
      state.positionKey = key;
    }
    state.length = length;
    renderProgress();
    if (!state.positionTimer) {
      state.positionTimer = setInterval(() => {
        if (state.position == null || state.length == null || state.position >= state.length) return;
        state.position = Math.min(state.position + 1, state.length);
        renderProgress();
      }, 1000);
    }
  }

  function renderPlayer() {
    const playing = Boolean(state.audio && !state.audio.paused);
    const locked = !state.canSwitch;
    setHidden($("player-init-loading"), !state.loading);
    setHidden($("player-loading"), !state.switchingPlayer);
    setHidden($("audio-player-section"), state.loading);
    $("player").disabled = locked || state.switchingPlayer;
    $("station").disabled = locked || state.loading || state.switchingPlayer;
    $("track-title").textContent = state.track || "Нет информации о треке";
    $("play-pause-icon").className = playing ? "fas fa-pause" : "fas fa-play";
    $("play-pause-btn").classList.toggle("playing", playing);
    $("play-pause-btn").disabled = locked || !state.track;
    $("refresh-btn").disabled = locked;
    $("status-dot").classList.toggle("active", playing);
    $("status-text").textContent = playing ? "Воспроизводится" : "Остановлено";
    setHidden($("next-track-btn"), !state.canSkip);
    $("next-track-btn").disabled = locked || state.skipInFlight;
    $("next-track-icon").className = state.skipInFlight ? "fas fa-spinner fa-spin" : "fas fa-forward-step";
    const canLike = typeof state.liked === "boolean";
    setHidden($("like-track-btn"), !canLike);
    $("like-track-btn").disabled = locked || state.likeInFlight;
    $("like-track-btn").classList.toggle("liked", state.liked === true);
    $("like-track-icon").className = state.likeInFlight
      ? "fas fa-spinner fa-spin"
      : state.liked
        ? "fas fa-heart"
        : "far fa-heart";
  }

  function streamUrl() {
    return `${config.radioUrl}${config.radioUrl.includes("?") ? "&" : "?"}t=${Date.now()}`;
  }

  function refreshStream() {
    if (!state.audio) return;
    const wasPlaying = !state.audio.paused;
    state.audio.src = streamUrl();
    state.audio.load();
    if (wasPlaying) state.audio.play();
  }

  // The browser keeps buffering the live stream and drifts behind; jump back to the edge.
  function trimBuffer() {
    const audio = state.audio;
    if (!audio || audio.paused || !audio.buffered.length) return;
    const edge = audio.buffered.end(audio.buffered.length - 1);
    const limit = ((Number(config.maxBufferKb) || 128) * 8) / (Number(config.streamBitrateKbps) || 128);
    if (edge - audio.currentTime <= limit) return;
    const target = edge - limit / 2;
    if (audio.seekable.length && target <= audio.seekable.end(audio.seekable.length - 1)) {
      audio.currentTime = target;
    } else {
      // a live stream is not seekable: reconnecting is the only way to drop what the browser holds
      refreshStream();
    }
  }

  function applyWhatsPlaying(data) {
    if (!data) return;
    state.track = data.playing || "";
    state.canSkip = Boolean(data.can_skip);
    // The server locks switching during programs and right after a switch.
    state.canSwitch = data.can_switch !== false;
    state.liked = typeof data.liked === "boolean" ? data.liked : null;
    if (data.player_tech && data.player_tech !== state.currentPlayer) {
      state.currentPlayer = data.player_tech;
      $("player").value = data.player_tech;
    }
    if (data.station_tech) {
      state.stationTech = data.station_tech;
      state.stationName = data.station_readable || "";
      syncStation();
    }
    applyProgress(data);
    renderPlayer();
  }

  function connectSocket() {
    if (state.socket) return;
    state.socket = api.openWhatsPlaying(applyWhatsPlaying, (closed) => {
      if (state.socket !== closed) return;
      state.socket = null;
      if (route() === "/login" || !api.isAuthenticated()) return;
      state.reconnectTimer = setTimeout(() => {
        state.reconnectTimer = null;
        connectSocket();
      }, 2000);
    });
  }

  function isRadio() {
    return state.currentPlayer === "player_radio";
  }

  async function loadStations() {
    try {
      state.stations = isRadio() ? await api.getRadioStations() : await api.getYandexStations();
    } catch (error) {
      console.error("Failed to load stations:", error);
      state.stations = {};
    }
    // The API maps a readable name to a technical id; the option value is the id.
    fillSelect(
      $("station"),
      Object.keys(state.stations).map((name) => {
        const tech = state.stations[name];
        return [tech, stationLabel(tech, name)];
      }),
      state.stationTech
    );
    try {
      const response = isRadio() ? await api.getRadioCurrentStation() : await api.getCurrentStation();
      state.stationTech = response.station || "";
      state.stationName = "";
    } catch (error) {
      console.error("Failed to get the current station:", error);
    }
    syncStation();
    state.loading = false;
    state.switchingPlayer = false;
    renderPlayer();
    connectSocket();
    if (config.autoplay && state.audio) {
      state.audio.play().catch((error) => console.error("Failed to auto-start music:", error));
    }
  }

  async function initPlayer() {
    state.loading = true;
    state.volume = api.loadVolume();
    $("volume-slider").value = String(state.volume);
    $("volume-value").textContent = `${state.volume}%`;
    renderPlayer();

    state.audio = new Audio(streamUrl());
    state.audio.preload = "none";
    state.audio.volume = state.volume / 100;
    ["play", "pause", "ended"].forEach((event) => state.audio.addEventListener(event, renderPlayer));
    state.bufferTimer = setInterval(trimBuffer, 2000);

    try {
      state.players = await api.getAvailablePlayers();
    } catch (error) {
      console.error("Failed to load available players:", error);
      state.players = {};
    }
    try {
      state.currentPlayer = (await api.getCurrentPlayer()).player || "";
    } catch (error) {
      console.error("Failed to get the current player:", error);
      state.currentPlayer = Object.keys(state.players)[0] || "";
    }
    fillSelect(
      $("player"),
      Object.keys(state.players).map((tech) => [tech, state.players[tech]]),
      state.currentPlayer
    );
    await loadStations();
  }

  function stopPlayer() {
    clearTimeout(state.reconnectTimer);
    clearInterval(state.bufferTimer);
    clearInterval(state.positionTimer);
    state.reconnectTimer = null;
    state.bufferTimer = null;
    state.positionTimer = null;
    if (state.socket) {
      const socket = state.socket;
      state.socket = null;
      socket.close();
    }
    if (state.audio) {
      state.audio.pause();
      state.audio = null;
    }
    state.length = null;
    state.position = null;
    state.positionKey = "";
    renderProgress();
  }

  async function switchToPlayer(player) {
    state.switchingPlayer = true;
    renderPlayer();
    try {
      await api.switchPlayer(player);
      state.currentPlayer = player;
      state.stationTech = "";
      state.stationName = "";
      await loadStations();
    } catch (error) {
      console.error("Failed to switch player:", error);
      state.switchingPlayer = false;
      renderPlayer();
    }
  }

  async function switchStation(station) {
    if (!station || station === state.stationTech) return;
    try {
      if (isRadio()) {
        await api.switchRadioStation(station);
      } else {
        await api.switchYandexStation(station);
      }
      state.stationTech = station;
    } catch (error) {
      console.error("Failed to switch station:", error);
      syncStation();
    }
  }

  async function skipTrack() {
    if (!state.canSwitch || !state.canSkip || state.skipInFlight) return;
    state.skipInFlight = true;
    renderPlayer();
    try {
      await api.nextYandexTrack();
    } catch (error) {
      console.error("Failed to skip track:", error);
    } finally {
      state.skipInFlight = false;
      renderPlayer();
    }
  }

  async function toggleLike() {
    if (!state.canSwitch || typeof state.liked !== "boolean" || state.likeInFlight) return;
    state.likeInFlight = true;
    renderPlayer();
    try {
      // The WebSocket state change updates the heart for every connected client.
      await api.setYandexTrackLiked(!state.liked);
    } catch (error) {
      console.error("Failed to change Yandex like status:", error);
    } finally {
      state.likeInFlight = false;
      renderPlayer();
    }
  }

  function scheduleChanged() {
    return schedule.times.join() !== schedule.saved.join();
  }

  function renderSchedule() {
    const grid = $("times-grid");
    grid.innerHTML = "";
    schedule.times.forEach((time) => {
      const item = document.createElement("div");
      item.className = "time-item card";
      const text = document.createElement("span");
      text.className = "time-text";
      text.textContent = time;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "remove-btn";
      remove.dataset.time = time;
      remove.disabled = schedule.loading;
      remove.innerHTML = '<i class="fas fa-trash"></i>';
      item.append(text, remove);
      grid.appendChild(item);
    });

    setHidden($("times-list"), schedule.times.length === 0);
    setHidden($("schedule-empty"), schedule.times.length > 0 || schedule.loading);
    setHidden($("schedule-loading"), !schedule.loading);
    $("save-schedule-btn").disabled = schedule.loading || !scheduleChanged();
    $("newTime").disabled = schedule.loading;
    $("add-time-btn").disabled = !$("newTime").value || schedule.loading;

    const prep = Number(schedule.prepMins);
    setHidden($("schedule-prep-note"), !Number.isFinite(prep));
    if (Number.isFinite(prep)) {
      $("schedule-prep-mins").textContent = `${prep} мин.`;
    }
  }

  function showSuccess(message) {
    $("success-message-text").textContent = message;
    setHidden($("success-message"), false);
    clearTimeout(schedule.toastTimer);
    schedule.toastTimer = setTimeout(() => setHidden($("success-message"), true), 3000);
  }

  async function loadSchedule() {
    schedule.loading = true;
    $("schedule-loading-message").textContent = "Загрузка расписания...";
    renderSchedule();
    try {
      const [times, prep] = await Promise.all([api.getConfig(TIMES_KEY), api.getConfig(PREP_KEY)]);
      schedule.times = (times[TIMES_KEY] || []).slice();
      schedule.saved = schedule.times.slice();
      schedule.prepMins = prep[PREP_KEY];
      schedule.loaded = true;
    } catch (error) {
      console.error("Error loading schedule:", error);
      alert("Ошибка загрузки расписания");
    } finally {
      schedule.loading = false;
      renderSchedule();
    }
  }

  async function saveSchedule() {
    if (!scheduleChanged()) return;
    schedule.loading = true;
    $("schedule-loading-message").textContent = "Сохранение расписания...";
    renderSchedule();
    try {
      await api.setConfig(TIMES_KEY, schedule.times);
      schedule.saved = schedule.times.slice();
      showSuccess("Расписание успешно сохранено");
    } catch (error) {
      console.error("Error saving schedule:", error);
      alert("Ошибка сохранения расписания");
    } finally {
      schedule.loading = false;
      renderSchedule();
    }
  }

  function addTime() {
    const value = $("newTime").value;
    if (!value) return;
    if (schedule.times.includes(value)) {
      alert("Время уже существует");
      return;
    }
    schedule.times = [...schedule.times, value].sort();
    $("newTime").value = "";
    renderSchedule();
  }

  function loginValid() {
    return $("username").value.length >= 3 && $("password").value.length >= 8;
  }

  function updateLoginValidation(showTouched) {
    [["username", 3], ["password", 8]].forEach(([id, min]) => {
      const input = $(id);
      if (!showTouched && !input.classList.contains("touched")) return;
      input.classList.toggle("is-invalid", input.value.length < min);
      setHidden($(`${id}-error`), input.value.length >= min);
    });
    $("login-button").disabled = !loginValid() || $("login-button").dataset.loading === "1";
  }

  function setLoginLoading(loading) {
    $("login-button").dataset.loading = loading ? "1" : "0";
    $("login-button").disabled = loading || !loginValid();
    $("login-button-icon").className = loading ? "fas fa-spinner fa-spin" : "fas fa-sign-in-alt";
    $("login-button-text").textContent = loading ? "Вход..." : "Войти";
  }

  async function onLoginSubmit(event) {
    event.preventDefault();
    if ($("login-button").disabled) return;
    setLoginLoading(true);
    setHidden($("login-error"), true);
    try {
      await api.login($("username").value, $("password").value);
      navigate("/");
    } catch (error) {
      $("login-error-text").textContent =
        error.status === 401 ? "Неверное имя пользователя или пароль" : "Ошибка. Попробуйте ещё раз.";
      setHidden($("login-error"), false);
    } finally {
      setLoginLoading(false);
    }
  }

  async function render() {
    const path = route();
    if (path !== "/login" && !api.isAuthenticated()) {
      navigate("/login");
      return;
    }

    document.title = config.radioTitle;
    document.querySelectorAll("[data-bind='username']").forEach((el) => {
      el.textContent = api.getUsername() || "";
    });

    if (path === "/login") {
      stopPlayer();
      showView("view-login");
      updateLoginValidation(false);
      return;
    }

    if (path === "/schedule") {
      // the player keeps running in the background: the views are only hidden, not torn down
      showView("view-schedule");
      if (schedule.loaded || schedule.loading) {
        renderSchedule();
      } else {
        await loadSchedule();
      }
      return;
    }

    showView("view-player");
    if (!state.audio) await initPlayer();
  }

  function bindEvents() {
    $("login-form").addEventListener("submit", onLoginSubmit);
    ["username", "password"].forEach((id) => {
      $(id).addEventListener("input", () => updateLoginValidation(false));
      $(id).addEventListener("blur", (event) => {
        event.target.classList.add("touched");
        updateLoginValidation(true);
      });
    });

    $("player").addEventListener("change", (event) => {
      if (state.canSwitch && event.target.value && event.target.value !== state.currentPlayer) {
        switchToPlayer(event.target.value);
      }
    });
    $("station").addEventListener("change", (event) => {
      if (state.canSwitch) switchStation(event.target.value);
    });
    $("play-pause-btn").addEventListener("click", () => {
      if (!state.canSwitch || !state.audio) return;
      if (state.audio.paused) state.audio.play();
      else state.audio.pause();
    });
    $("next-track-btn").addEventListener("click", skipTrack);
    $("like-track-btn").addEventListener("click", toggleLike);
    $("refresh-btn").addEventListener("click", () => {
      if (state.canSwitch) refreshStream();
    });
    // Volume is a local audio-element setting, so it stays usable even while the backend is locked.
    $("volume-slider").addEventListener("input", (event) => {
      state.volume = parseInt(event.target.value, 10);
      if (state.audio) state.audio.volume = state.volume / 100;
      $("volume-value").textContent = `${state.volume}%`;
      api.saveVolume(state.volume);
    });

    $("add-time-btn").addEventListener("click", addTime);
    $("newTime").addEventListener("input", () => {
      $("add-time-btn").disabled = !$("newTime").value || schedule.loading;
    });
    $("save-schedule-btn").addEventListener("click", saveSchedule);
    $("times-grid").addEventListener("click", (event) => {
      const button = event.target.closest("[data-time]");
      if (!button) return;
      schedule.times = schedule.times.filter((time) => time !== button.dataset.time);
      renderSchedule();
    });
    $("success-close-btn").addEventListener("click", () => setHidden($("success-message"), true));

    document.querySelectorAll("[data-action='logout']").forEach((button) => {
      button.addEventListener("click", () => {
        api.logout();
        stopPlayer();
        schedule.loaded = false;
        navigate("/login");
      });
    });

    global.addEventListener("hashchange", render);
    global.addEventListener("lorad:unauthorized", () => {
      stopPlayer();
      navigate("/login");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const background = `randomBackground/${BACKGROUNDS[Math.floor(Math.random() * BACKGROUNDS.length)]}`;
    $("view-player").style.backgroundImage = `url('${background}')`;
    $("view-schedule").style.backgroundImage = `url('${background}')`;
    bindEvents();
    if (location.hash) {
      render();
    } else {
      location.hash = api.isAuthenticated() ? "/" : "/login";
    }
  });
})(window);
