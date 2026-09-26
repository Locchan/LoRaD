(function (global) {
  const TIMES_KEY = "ENABLED_PROGRAMS/NewsSmall/start_times";
  const PREP_KEY = "ENABLED_PROGRAMS/NewsSmall/preparation_needed_mins";
  const BACKGROUND_FEATURE_OFF_KEY = "lorad_immich_backgrounds_off";
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
    trackTitle: "",
    trackArtist: "",
    canSkip: false,
    canSwitch: true,
    liked: null,
    looping: null,
    coverReady: false,
    coverUrl: "",
    coverTrackKey: "",
    coverLoading: false,
    searchTimer: null,
    searchSeq: 0,
    playSearchInFlight: false,
    queueSearchInFlight: false,
    selectedSearchTrackId: "",
    customPlaying: false,
    customQueue: [],
    skipInFlight: false,
    likeInFlight: false,
    loopInFlight: false,
    loading: true,
    switchingPlayer: false,
    socket: null,
    reconnectTimer: null,
    bufferTimer: null,
    positionTimer: null,
    length: null,
    position: null,
    positionKey: "",
    backgroundUrl: "",
    backgroundLoaded: false,
    backgroundFeatureOff: sessionStorage.getItem(BACKGROUND_FEATURE_OFF_KEY) === "1",
    backgroundNatural: null,
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
    if (tech === "user:likes") return "Понравившееся";
    return readable || tech;
  }

  function syncStation() {
    const select = $("station");
    if (!state.stationTech) return;
    const option = Array.from(select.options).find((item) => item.value === state.stationTech);
    if (option) {
      // the list already carries readable names; only the Yandex wave needs its own label
      if (state.stationTech === "user:onyourwave") option.textContent = "Моя волна";
      if (state.stationTech === "user:likes") option.textContent = "Понравившееся";
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
    const pct = state.length > 0 ? Math.min(100, (state.position / state.length) * 100) : 0;
    $("track-progress-fill").style.width = `${pct}%`;
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

  function clearCover() {
    if (state.coverUrl && state.coverUrl.startsWith("blob:")) {
      URL.revokeObjectURL(state.coverUrl);
    }
    state.coverUrl = "";
    state.coverTrackKey = "";
    state.coverReady = false;
    const img = $("track-cover");
    img.removeAttribute("src");
    setHidden(img, true);
    setHidden($("track-cover-placeholder"), false);
  }

  async function loadCover(force) {
    const key = state.track || state.trackTitle || "";
    if (!state.coverReady) {
      if (state.coverUrl && state.coverUrl.startsWith("blob:")) {
        URL.revokeObjectURL(state.coverUrl);
      }
      state.coverUrl = "";
      state.coverTrackKey = "";
      setHidden($("track-cover"), true);
      setHidden($("track-cover-placeholder"), false);
      return;
    }
    if (!force && state.coverTrackKey === key && state.coverUrl) {
      setHidden($("track-cover"), false);
      setHidden($("track-cover-placeholder"), true);
      return;
    }
    if (state.coverLoading) return;
    state.coverLoading = true;
    try {
      const blob = await api.getYandexCover();
      if (!blob) {
        setHidden($("track-cover"), true);
        setHidden($("track-cover-placeholder"), false);
        return;
      }
      if (state.coverUrl && state.coverUrl.startsWith("blob:")) {
        URL.revokeObjectURL(state.coverUrl);
      }
      state.coverUrl = URL.createObjectURL(blob);
      state.coverTrackKey = key;
      const img = $("track-cover");
      img.src = state.coverUrl;
      setHidden(img, false);
      setHidden($("track-cover-placeholder"), true);
    } catch (error) {
      console.error("Failed to load track cover:", error);
      setHidden($("track-cover"), true);
      setHidden($("track-cover-placeholder"), false);
    } finally {
      state.coverLoading = false;
    }
  }

  function syncPlayerBarHeight() {
    const bar = $("audio-player-section");
    const height = bar && !bar.hidden ? bar.offsetHeight : 0;
    document.documentElement.style.setProperty(
      "--player-bar-height",
      height > 0 ? `${height}px` : "5.5rem"
    );
    positionBackgroundDate();
  }

  function renderPlayer() {
    const playing = Boolean(state.audio && !state.audio.paused);
    const locked = !state.canSwitch;
    const authed = api.isAuthenticated() && route() !== "/login";
    setHidden($("player-init-loading"), !state.loading);
    setHidden($("player-loading"), !state.switchingPlayer);
    setHidden($("audio-player-section"), !authed || state.loading);
    setHidden($("refresh-btn"), !authed);
    $("player").disabled = locked || state.switchingPlayer;
    $("station").disabled = locked || state.loading || state.switchingPlayer;
    const showSearch = !isRadio() && !state.loading;
    setHidden($("yandex-search-field"), !showSearch);
    $("yandex-search").disabled =
      locked || state.switchingPlayer || state.playSearchInFlight || state.queueSearchInFlight;
    syncSearchActions();
    if (!showSearch) closeSearchResults();
    $("track-title").textContent = state.trackTitle || state.track || "Нет информации о треке";
    $("track-artist").textContent = state.trackArtist || "";
    $("play-pause-icon").className = playing ? "fas fa-pause" : "fas fa-play";
    $("play-pause-btn").classList.toggle("playing", playing);
    $("play-pause-btn").disabled = locked || !(state.track || state.trackTitle);
    $("refresh-btn").disabled = locked;
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
    const canLoop = typeof state.looping === "boolean";
    setHidden($("loop-track-btn"), !canLoop);
    $("loop-track-btn").disabled = locked || state.loopInFlight;
    $("loop-track-btn").classList.toggle("looping", state.looping === true);
    $("loop-track-icon").className = state.loopInFlight ? "fas fa-spinner fa-spin" : "fas fa-repeat";
    setHidden($("queue-view-btn"), !authed || state.loading);
    $("queue-view-btn").disabled = state.loading;
    if ($("queue-popup") && !$("queue-popup").hidden) syncQueueSection();
    loadCover(false);
    // After layout (stacked portrait bar is taller than the desktop fallback).
    requestAnimationFrame(syncPlayerBarHeight);
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
    const nextTrack = data.playing || "";
    const nextReady = Boolean(data.cover_ready);
    const trackChanged = nextTrack !== state.track;
    const coverBecameReady = nextReady && !state.coverReady;
    state.track = nextTrack;
    state.trackTitle = data.track_title || nextTrack;
    state.trackArtist = data.track_artist || "";
    state.canSkip = Boolean(data.can_skip);
    // The server locks switching during programs and right after a switch.
    state.canSwitch = data.can_switch !== false;
    state.liked = typeof data.liked === "boolean" ? data.liked : null;
    state.looping = typeof data.looping === "boolean" ? data.looping : null;
    state.customPlaying = Boolean(data.custom_playing);
    state.customQueue = Array.isArray(data.custom_queue) ? data.custom_queue : [];
    if ($("queue-popup") && !$("queue-popup").hidden) syncQueueSection();
    state.coverReady = nextReady;
    if (trackChanged) {
      if (state.coverUrl && state.coverUrl.startsWith("blob:")) {
        URL.revokeObjectURL(state.coverUrl);
      }
      state.coverUrl = "";
      state.coverTrackKey = "";
    }
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
    if (coverBecameReady || (nextReady && trackChanged)) {
      loadCover(true);
    }
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

  function syncQueueSection() {
    const section = $("queue-section");
    const showQueue = Boolean(state.customPlaying);
    setHidden(section, !showQueue);
    if (showQueue) renderQueuePopupList();
  }

  function renderQueuePopupList() {
    const list = $("queue-popup-list");
    const empty = $("queue-popup-empty");
    list.innerHTML = "";
    const queue = state.customQueue || [];
    setHidden(empty, queue.length > 0);
    setHidden(list, queue.length === 0);
    let upcomingNumber = 2;
    queue.forEach((item, index) => {
      const li = document.createElement("li");
      const marker = document.createElement("span");
      marker.className = "queue-popup-index";
      const text = document.createElement("span");
      text.className = "queue-popup-text";
      const artist = item.artist || "";
      const title = item.title || "";
      text.textContent = artist ? `${artist} - ${title}` : title;
      if (item.playing) {
        marker.classList.add("playing");
        marker.textContent = "▶";
      } else {
        marker.textContent = `${upcomingNumber}.`;
        upcomingNumber += 1;
      }
      li.append(marker, text);
      if (!item.playing) {
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "queue-popup-remove";
        remove.title = "Убрать из очереди";
        remove.dataset.queueIndex = String(index);
        remove.textContent = "✕";
        li.appendChild(remove);
      }
      list.appendChild(li);
    });
  }

  async function removeQueueTrack(index) {
    if (!state.customPlaying || state.canSwitch === false) return;
    try {
      const data = await api.removeYandexQueueTrack(index);
      state.customQueue = Array.isArray(data.custom_queue) ? data.custom_queue : [];
      syncQueueSection();
    } catch (error) {
      console.error("Failed to remove queue track:", error);
    }
  }

  function openQueuePopup() {
    syncQueueSection();
    setHidden($("queue-popup"), false);
  }

  function closeQueuePopup() {
    const popup = $("queue-popup");
    if (popup) setHidden(popup, true);
    closeSearchResults();
  }

  function closeSearchResults() {
    const panel = $("yandex-search-panel");
    const list = $("yandex-search-results");
    list.innerHTML = "";
    state.selectedSearchTrackId = "";
    setHidden(panel, true);
    setHidden($("yandex-search-actions"), true);
    syncSearchActions();
  }

  function syncSearchActions() {
    const actions = $("yandex-search-actions");
    const playBtn = $("search-play-btn");
    const queueBtn = $("search-queue-btn");
    const hasSelection = Boolean(state.selectedSearchTrackId);
    const panelOpen = !$("yandex-search-panel").hidden;
    const locked =
      !state.canSwitch ||
      state.switchingPlayer ||
      state.playSearchInFlight ||
      state.queueSearchInFlight;
    setHidden(actions, !panelOpen || !hasSelection);
    setHidden(queueBtn, !state.customPlaying);
    playBtn.disabled = locked || !hasSelection;
    queueBtn.disabled = locked || !hasSelection || !state.customPlaying;
  }

  function selectSearchTrack(trackId) {
    state.selectedSearchTrackId = trackId || "";
    $("yandex-search-results").querySelectorAll(".search-result").forEach((btn) => {
      btn.classList.toggle("selected", btn.dataset.trackId === state.selectedSearchTrackId);
    });
    syncSearchActions();
  }

  function renderSearchResults(tracks) {
    const panel = $("yandex-search-panel");
    const list = $("yandex-search-results");
    list.innerHTML = "";
    state.selectedSearchTrackId = "";
    if (!tracks || !tracks.length) {
      const empty = document.createElement("li");
      empty.className = "search-results-empty";
      empty.textContent = "Ничего не найдено";
      list.appendChild(empty);
      setHidden(panel, false);
      setHidden($("yandex-search-actions"), true);
      syncSearchActions();
      return;
    }
    tracks.forEach((track) => {
      const item = document.createElement("li");
      const button = document.createElement("button");
      button.type = "button";
      button.className = "search-result";
      button.dataset.trackId = track.id;
      const title = document.createElement("span");
      title.className = "search-result-title";
      title.textContent = track.title || track.id;
      const artist = document.createElement("span");
      artist.className = "search-result-artist";
      artist.textContent = track.artist || "";
      button.append(title, artist);
      item.appendChild(button);
      list.appendChild(item);
    });
    setHidden(panel, false);
    syncSearchActions();
  }

  async function runYandexSearch(query) {
    const q = query.trim();
    if (!q || isRadio()) {
      closeSearchResults();
      return;
    }
    const seq = ++state.searchSeq;
    try {
      const data = await api.searchYandexTracks(q);
      if (seq !== state.searchSeq) return;
      renderSearchResults(data.tracks || []);
    } catch (error) {
      if (seq !== state.searchSeq) return;
      console.error("Yandex search failed:", error);
      closeSearchResults();
    }
  }

  function scheduleYandexSearch() {
    clearTimeout(state.searchTimer);
    const q = $("yandex-search").value.trim();
    if (!q) {
      state.searchSeq += 1;
      closeSearchResults();
      return;
    }
    state.searchTimer = setTimeout(() => runYandexSearch(q), 300);
  }

  async function confirmPlaySearchTrack() {
    const trackId = state.selectedSearchTrackId;
    if (!trackId || !state.canSwitch || state.playSearchInFlight || isRadio()) return;
    state.playSearchInFlight = true;
    renderPlayer();
    try {
      await api.playYandexTrack(trackId);
      state.searchSeq += 1;
      $("yandex-search").value = "";
      closeSearchResults();
    } catch (error) {
      console.error("Failed to play Yandex track:", error);
    } finally {
      state.playSearchInFlight = false;
      renderPlayer();
    }
  }

  async function enqueueSearchTrack() {
    const trackId = state.selectedSearchTrackId;
    if (
      !trackId ||
      !state.customPlaying ||
      !state.canSwitch ||
      state.queueSearchInFlight ||
      isRadio()
    ) {
      return;
    }
    state.queueSearchInFlight = true;
    renderPlayer();
    try {
      await api.enqueueYandexTrack(trackId);
      state.searchSeq += 1;
      $("yandex-search").value = "";
      closeSearchResults();
    } catch (error) {
      console.error("Failed to enqueue Yandex track:", error);
    } finally {
      state.queueSearchInFlight = false;
      renderPlayer();
    }
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
    clearCover();
    setHidden($("audio-player-section"), true);
    setHidden($("refresh-btn"), true);
    closeQueuePopup();
    syncPlayerBarHeight();
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

  async function toggleLoop() {
    if (!state.canSwitch || typeof state.looping !== "boolean" || state.loopInFlight) return;
    state.loopInFlight = true;
    renderPlayer();
    try {
      await api.setYandexTrackLoop(!state.looping);
    } catch (error) {
      console.error("Failed to change Yandex loop status:", error);
    } finally {
      state.loopInFlight = false;
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
      clearBackground();
      showView("view-login");
      updateLoginValidation(false);
      return;
    }

    if (path === "/schedule") {
      // the player keeps running in the background: the views are only hidden, not torn down
      showView("view-schedule");
      loadBackground();
      if (state.audio) renderPlayer();
      if (schedule.loaded || schedule.loading) {
        renderSchedule();
      } else {
        await loadSchedule();
      }
      return;
    }

    showView("view-player");
    loadBackground();
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
    $("loop-track-btn").addEventListener("click", toggleLoop);
    $("queue-view-btn").addEventListener("click", openQueuePopup);
    $("queue-popup-close").addEventListener("click", closeQueuePopup);
    $("queue-popup-list").addEventListener("click", (event) => {
      const button = event.target.closest("[data-queue-index]");
      if (!button) return;
      const index = Number(button.dataset.queueIndex);
      if (!Number.isInteger(index)) return;
      removeQueueTrack(index);
    });
    $("queue-popup").addEventListener("click", (event) => {
      if (event.target === $("queue-popup")) closeQueuePopup();
    });
    $("refresh-btn").addEventListener("click", () => {
      if (state.canSwitch) refreshStream();
    });
    $("yandex-search").addEventListener("input", scheduleYandexSearch);
    $("yandex-search").addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeSearchResults();
    });
    $("yandex-search-results").addEventListener("click", (event) => {
      const button = event.target.closest("[data-track-id]");
      if (!button) return;
      selectSearchTrack(button.dataset.trackId);
    });
    $("search-play-btn").addEventListener("click", confirmPlaySearchTrack);
    $("search-queue-btn").addEventListener("click", enqueueSearchTrack);
    document.addEventListener("click", (event) => {
      const field = $("yandex-search-field");
      if (!field || field.hidden) return;
      if (field.contains(event.target)) return;
      closeSearchResults();
    });
    // Volume is a local audio-element setting, so it stays usable even while the backend is locked.
    $("volume-slider").addEventListener("input", (event) => {
      state.volume = parseInt(event.target.value, 10);
      if (state.audio) state.audio.volume = state.volume / 100;
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
        clearBackground();
        schedule.loaded = false;
        navigate("/login");
      });
    });

    global.addEventListener("resize", () => {
      syncPlayerBarHeight();
    });
    global.addEventListener("hashchange", render);
    global.addEventListener("lorad:unauthorized", () => {
      stopPlayer();
      clearBackground();
      navigate("/login");
    });
  }

  function clearBackground() {
    if (state.backgroundUrl && state.backgroundUrl.startsWith("blob:")) {
      URL.revokeObjectURL(state.backgroundUrl);
    }
    state.backgroundUrl = "";
    state.backgroundLoaded = false;
    ["view-player", "view-schedule"].forEach((id) => {
      $(id).style.removeProperty("--bg-image");
      $(id).style.backgroundColor = "";
    });
    state.backgroundNatural = null;
    showBackgroundDate(null);
  }

  // Only Immich backgrounds carry a date, and only when Immich has one for that photo
  function showBackgroundDate(isoDate) {
    const label = $("background-date");
    if (!label) return;
    const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate || "");
    if (!parts) {
      label.textContent = "";
      setHidden(label, true);
      return;
    }
    label.textContent = `${parts[3]}.${parts[2]}.${parts[1]}`;
    setHidden(label, false);
    positionBackgroundDate();
  }

  function measureImage(url) {
    return new Promise((resolve) => {
      const probe = new Image();
      probe.onload = () => resolve({ width: probe.naturalWidth, height: probe.naturalHeight });
      probe.onerror = () => resolve(null);
      probe.src = url;
    });
  }

  // The photo is painted with background-size: contain against the viewport, so its own
  // bottom-right sits inside the page by however much the aspect ratios differ. Keep it
  // above the player bar.
  function positionBackgroundDate() {
    const label = $("background-date");
    if (!label || label.hidden) return;
    const natural = state.backgroundNatural;
    const viewWidth = document.documentElement.clientWidth;
    const viewHeight = document.documentElement.clientHeight;
    const bar = $("audio-player-section");
    const barHeight = bar && !bar.hidden ? bar.offsetHeight : 0;
    const clearBottom = barHeight + 12;
    if (!natural || !natural.width || !natural.height) {
      label.style.left = "auto";
      label.style.top = "auto";
      label.style.right = "20px";
      label.style.bottom = `${clearBottom}px`;
      return;
    }
    const scale = Math.min(viewWidth / natural.width, viewHeight / natural.height);
    const insetX = Math.round((viewWidth - natural.width * scale) / 2);
    const insetY = Math.round((viewHeight - natural.height * scale) / 2);
    label.style.left = "auto";
    label.style.top = "auto";
    label.style.right = `${insetX + 14}px`;
    label.style.bottom = `${Math.max(insetY + 12, clearBottom)}px`;
  }

  function applyBackground(url) {
    if (!api.isAuthenticated() || route() === "/login") return;
    // url() inside a custom property resolves against styles.css, not the page, so absolutise it
    const absolute = new URL(url, location.href).href;
    ["view-player", "view-schedule"].forEach((id) => {
      $(id).style.setProperty("--bg-image", `url('${absolute}')`);
    });
  }

  function applyBackgroundColor() {
    if (!api.isAuthenticated() || route() === "/login") return;
    ["view-player", "view-schedule"].forEach((id) => {
      $(id).style.setProperty("--bg-image", "none");
      $(id).style.backgroundColor = "#59636f";
    });
  }

  async function loadLocalBackground() {
    const candidates = [...BACKGROUNDS].sort(() => Math.random() - 0.5);
    for (const filename of candidates) {
      const url = `randomBackground/${filename}`;
      const loaded = await new Promise((resolve) => {
        const probe = new Image();
        probe.onload = () => resolve(true);
        probe.onerror = () => resolve(false);
        probe.src = url;
      });
      if (loaded) {
        applyBackground(url);
        state.backgroundNatural = null;
        showBackgroundDate(null);
        return;
      }
    }
    applyBackgroundColor();
    state.backgroundNatural = null;
    showBackgroundDate(null);
  }

  async function loadBackground() {
    if (state.backgroundLoaded) return;
    state.backgroundLoaded = true;
    applyBackgroundColor();
    if (state.backgroundFeatureOff) {
      await loadLocalBackground();
      return;
    }
    try {
      const picked = await api.getBackground();
      const blob = picked && picked.blob;
      if (!blob || !blob.size || (blob.type && !blob.type.startsWith("image/"))) {
        await loadLocalBackground();
        return;
      }
      if (state.backgroundUrl && state.backgroundUrl.startsWith("blob:")) {
        URL.revokeObjectURL(state.backgroundUrl);
      }
      state.backgroundUrl = URL.createObjectURL(blob);
      applyBackground(state.backgroundUrl);
      state.backgroundNatural = await measureImage(state.backgroundUrl);
      showBackgroundDate(picked.date);
    } catch (error) {
      if (error.status === 501) {
        state.backgroundFeatureOff = true;
        sessionStorage.setItem(BACKGROUND_FEATURE_OFF_KEY, "1");
      }
      if (error.status !== 401) await loadLocalBackground();
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    if (location.hash) {
      render();
    } else {
      location.hash = api.isAuthenticated() ? "/" : "/login";
    }
  });
})(window);
