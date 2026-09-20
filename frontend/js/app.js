(function (global) {
  const CONFIG_KEY = "ENABLED_PROGRAMS/NewsSmall/start_times";
  const PREP_KEY = "ENABLED_PROGRAMS/NewsSmall/preparation_needed_mins";
  const BACKGROUND_IMAGES = [
    "1VuZTnscmraqYUZHZ1EQbecdrVfPm_l244Nl7PF1FkChpTa4adEpJMsKskpKRJXqryRvomDp.jpeg",
    "20160308_preview.jpeg",
    "3nKXMUBrk6P9d1hoN_4inCDZvSVkFQ_vkrA3YyqWggi6_F2aDFU7gJYF9CjD7v3MybVD8eGQ.jpeg",
    "IMG_1556_preview.jpeg",
    "IMG_5239_preview.jpeg",
    "IMG_6271_preview.jpeg",
    "ldTUiHwSCDrpbn_6FoA8x0jWqOayj8i54Vtw_WoLHPiBQ3eBBD4I3MiiVRiQ9LAl4CsJfS80.jpeg",
    "NKhd8U97D677IGE_3yYeNKT7Ii7nOjrV_8mItpXRK8HgfJmiYHb9A4OsbSQCCvapT6x16z4W.jpeg",
  ];

  const api = global.LoradApi;
  const config = global.LORAD_CONFIG;

  const playerState = {
    currentTrack: "",
    currentStation: "",
    availablePlayers: {},
    currentPlayer: "",
    selectedPlayer: "",
    availableStations: {},
    selectedStation: "",
    audio: null,
    volume: 100,
    isLoading: true,
    isPlayerLoading: false,
    whatsPlayingSocket: null,
    whatsPlayingReconnectTimer: null,
    bufferTimer: null,
    skipInFlight: false,
    canSkip: false,
    canSwitch: true,
    liked: null,
    likeInFlight: false,
    stationTech: "",
    stationReadable: "",
    trackPosition: null,
    trackLength: null,
    positionTrack: "",
    positionTimer: null,
  };

  // whatsplaying only corrects the playhead every few seconds, so the UI counts on its own
  // and snaps to the server when the two disagree by more than this.
  const POSITION_RESYNC_S = 2;

  const scheduleState = {
    times: [],
    originalTimes: [],
    preparationNeededMins: null,
    isLoading: false,
    loaded: false,
    successTimer: null,
  };

  const backgroundImage = `randomBackground/${BACKGROUND_IMAGES[Math.floor(Math.random() * BACKGROUND_IMAGES.length)]}`;

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function setHidden(el, hidden) {
    if (!el) return;
    el.hidden = hidden;
  }

  function publicBase() {
    const base = document.querySelector("base");
    return base ? base.getAttribute("href") || "/" : "/";
  }

  function currentRoute() {
    const hash = location.hash.replace(/^#/, "");
    if (!hash || hash === "/") return "/";
    return hash.startsWith("/") ? hash : `/${hash}`;
  }

  function navigate(path) {
    location.hash = path === "/" ? "/" : path;
  }

  function normalizeLegacyPath() {
    const path = location.pathname
      .replace(/\/ui\/?/, "/")
      .replace(/index\.html$/, "")
      .replace(/\/$/, "") || "/";
    if (path === "/login" || path === "/schedule") {
      history.replaceState(null, "", `${publicBase()}#${path}`);
    }
  }

  function requireAuth(route) {
    if (route !== "/login" && !api.isAuthenticated()) {
      navigate("/login");
      return false;
    }
    return true;
  }

  function fillTitles() {
    document.title = config.radioTitle;
    document.querySelectorAll("[data-bind='radio-title']").forEach((el) => {
      el.textContent = config.radioTitle;
    });
  }

  function fillUsernames() {
    const username = api.getUsername() || "";
    document.querySelectorAll("[data-bind='username']").forEach((el) => {
      el.textContent = username;
    });
  }

  function setBackgrounds() {
    $("view-player").style.backgroundImage = `url('${backgroundImage}')`;
    $("view-schedule").style.backgroundImage = `url('${backgroundImage}')`;
  }

  function showView(id) {
    ["view-login", "view-player", "view-schedule"].forEach((viewId) => {
      setHidden($(viewId), viewId !== id);
    });
  }

  function fillSelect(select, items, selected) {
    const current = selected || "";
    select.innerHTML = '<option value="">' + select.options[0].textContent + "</option>";
    Object.keys(items).forEach((key) => {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = select.id === "player" ? (items[key] || key) : key;
      select.appendChild(option);
    });
    select.value = current;
  }

  function isPlaying() {
    return Boolean(playerState.audio && !playerState.audio.paused);
  }

  // Option values are readable station names, while the API talks in technical ids.
  function stationKeyFor(techId, readableName) {
    const stations = playerState.availableStations || {};
    const byTech = Object.keys(stations).find((key) => stations[key] === techId);
    if (byTech) return byTech;
    if (readableName && Object.prototype.hasOwnProperty.call(stations, readableName)) {
      return readableName;
    }
    return "";
  }

  function syncStationSelect() {
    if (!playerState.stationTech && !playerState.stationReadable) return;
    const select = $("station");
    let key = stationKeyFor(playerState.stationTech, playerState.stationReadable);
    if (!key && playerState.stationReadable) {
      // the backend plays something that is not in the list (e.g. "Моя волна"): show it anyway
      key = playerState.stationReadable;
      playerState.availableStations[key] = playerState.stationTech;
      const option = document.createElement("option");
      option.value = key;
      option.textContent = key;
      select.appendChild(option);
    }
    if (!key) return;
    playerState.currentStation = key;
    playerState.selectedStation = key;
    select.value = key;
  }

  function formatClock(seconds) {
    const total = Math.max(0, Math.floor(seconds));
    return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
  }

  function renderTrackProgress() {
    const known = playerState.trackLength != null && playerState.trackPosition != null;
    setHidden($("track-progress"), !known);
    if (!known) return;
    $("track-position").textContent = formatClock(playerState.trackPosition);
    $("track-length").textContent = formatClock(playerState.trackLength);
  }

  function startPositionTicker() {
    if (playerState.positionTimer) return;
    playerState.positionTimer = setInterval(() => {
      if (playerState.trackPosition == null || playerState.trackLength == null) return;
      if (playerState.trackPosition >= playerState.trackLength) return;
      playerState.trackPosition = Math.min(playerState.trackPosition + 1, playerState.trackLength);
      renderTrackProgress();
    }, 1000);
  }

  function applyTrackProgress(response) {
    const length = Number(response.length_s);
    const position = Number(response.position_s);
    if (!Number.isFinite(length) || !Number.isFinite(position)) {
      playerState.trackLength = null;
      playerState.trackPosition = null;
      playerState.positionTrack = "";
      renderTrackProgress();
      return;
    }

    const track = `${response.playing || ""}|${length}`;
    const isNewTrack = track !== playerState.positionTrack;
    const drifted =
      playerState.trackPosition == null ||
      Math.abs(position - playerState.trackPosition) > POSITION_RESYNC_S;

    playerState.trackLength = length;
    if (isNewTrack || drifted) {
      playerState.trackPosition = position;
      playerState.positionTrack = track;
    }
    renderTrackProgress();
    startPositionTicker();
  }

  function updatePlaybackUi() {
    const playing = isPlaying();
    $("play-pause-icon").className = playing ? "fas fa-pause" : "fas fa-play";
    $("play-pause-btn").classList.toggle("playing", playing);
    $("status-dot").classList.toggle("active", playing);
    $("status-text").textContent = playing ? "Воспроизводится" : "Остановлено";
    $("fallback-status").textContent = playing ? "Воспроизводится" : "Остановлено";
    $("play-pause-btn").disabled = !playerState.currentTrack;
  }

  function updatePlayerSections() {
    setHidden($("player-init-loading"), !playerState.isLoading);
    setHidden($("player-loading"), !playerState.isPlayerLoading);
    $("player").disabled = playerState.isPlayerLoading || !playerState.canSwitch;
    $("station").disabled = playerState.isLoading || playerState.isPlayerLoading || !playerState.canSwitch;
    setHidden($("audio-player-section"), !(playerState.currentTrack && !playerState.isLoading));
    setHidden($("track-fallback"), !(!playerState.currentTrack && playerState.selectedStation && !playerState.isLoading));
    $("track-title").textContent = playerState.currentTrack || "Нет информации о треке";
    $("fallback-station").textContent = `Станция: ${playerState.selectedStation}`;
    setHidden($("next-track-btn"), !playerState.canSkip);
    $("next-track-btn").disabled = playerState.skipInFlight || !playerState.canSkip;
    $("next-track-icon").className = playerState.skipInFlight ? "fas fa-spinner fa-spin" : "fas fa-forward-step";
    const canLike = typeof playerState.liked === "boolean";
    setHidden($("like-track-btn"), !canLike);
    $("like-track-btn").disabled = playerState.likeInFlight || !canLike;
    $("like-track-btn").classList.toggle("liked", playerState.liked === true);
    $("like-track-btn").title = playerState.liked ? "Убрать отметку «Нравится»" : "Нравится";
    $("like-track-icon").className = playerState.likeInFlight
      ? "fas fa-spinner fa-spin"
      : playerState.liked
        ? "fas fa-heart"
        : "far fa-heart";
    updatePlaybackUi();
  }

  function stopPlayer() {
    if (playerState.whatsPlayingReconnectTimer) {
      clearTimeout(playerState.whatsPlayingReconnectTimer);
      playerState.whatsPlayingReconnectTimer = null;
    }
    if (playerState.whatsPlayingSocket) {
      const socket = playerState.whatsPlayingSocket;
      playerState.whatsPlayingSocket = null;
      socket.close();
    }
    if (playerState.bufferTimer) {
      clearInterval(playerState.bufferTimer);
      playerState.bufferTimer = null;
    }
    if (playerState.positionTimer) {
      clearInterval(playerState.positionTimer);
      playerState.positionTimer = null;
    }
    playerState.trackPosition = null;
    playerState.trackLength = null;
    playerState.positionTrack = "";
    renderTrackProgress();
    if (playerState.audio) {
      playerState.audio.pause();
      playerState.audio = null;
    }
  }

  function bindAudioEvents(audio) {
    ["play", "pause", "ended"].forEach((eventName) => {
      audio.addEventListener(eventName, updatePlaybackUi);
    });
  }

  function freshStreamUrl() {
    const separator = config.radioUrl.includes("?") ? "&" : "?";
    return `${config.radioUrl}${separator}t=${Date.now()}`;
  }

  function maxBufferSeconds() {
    const kb = Number(config.maxBufferKb) || 128;
    const bitrate = Number(config.streamBitrateKbps) || 128;
    return (kb * 8) / bitrate;
  }

  function bufferedAheadSeconds(audio) {
    if (!audio || !audio.buffered || audio.buffered.length === 0) return 0;
    return audio.buffered.end(audio.buffered.length - 1) - audio.currentTime;
  }

  function trimBuffer() {
    const audio = playerState.audio;
    if (!audio || audio.paused) return;
    const limit = maxBufferSeconds();
    if (bufferedAheadSeconds(audio) <= limit) return;
    const target = audio.buffered.end(audio.buffered.length - 1) - limit / 2;
    if (audio.seekable.length && target <= audio.seekable.end(audio.seekable.length - 1)) {
      audio.currentTime = target;
      return;
    }
    // live stream is not seekable: reconnecting is the only way to drop what the browser holds
    refreshStream();
  }

  function startBufferWatchdog() {
    if (playerState.bufferTimer) {
      clearInterval(playerState.bufferTimer);
    }
    playerState.bufferTimer = setInterval(trimBuffer, 2000);
  }

  async function loadStationsForCurrentPlayer() {
    try {
      playerState.availableStations =
        playerState.currentPlayer === "player_radio"
          ? await api.getRadioStations()
          : await api.getYandexStations();
      fillSelect($("station"), playerState.availableStations, playerState.selectedStation);
      syncStationSelect();
    } catch (error) {
      console.error(`Failed to load ${playerState.currentPlayer} stations:`, error);
    }
    await loadCurrentStationAndPlay();
  }

  async function loadCurrentStationAndPlay() {
    try {
      const response =
        playerState.currentPlayer === "player_radio"
          ? await api.getRadioCurrentStation()
          : await api.getCurrentStation();
      const station = response.station || "";
      if (station !== playerState.stationTech) {
        // this endpoint only knows technical ids, so a name from whatsplaying is stale now
        playerState.stationReadable = "";
      }
      playerState.stationTech = station;
      syncStationSelect();
    } catch (error) {
      console.error(`Failed to get current station for ${playerState.currentPlayer}:`, error);
    }
    finalizeInitializationAndPlay();
  }

  function finalizeInitializationAndPlay() {
    playerState.isLoading = false;
    playerState.isPlayerLoading = false;
    updatePlayerSections();
    startWhatsPlayingUpdates();
    autoStartMusic();
  }

  function autoStartMusic() {
    if (!config.autoplay) {
      return;
    }
    if (playerState.audio && playerState.selectedStation) {
      setTimeout(() => {
        playerState.audio.play().catch(() => {
          refreshStream();
          setTimeout(() => {
            playerState.audio.play().catch((error) => {
              console.error("Failed to auto-start music after refresh:", error);
            });
          }, 1000);
        });
      }, 1000);
    }
  }

  function applyWhatsPlaying(response) {
    if (!response) return;
    playerState.currentTrack = response.playing || "Нет информации о треке";
    playerState.canSkip = Boolean(response.can_skip);
    // The server locks switching during programs and right after a switch.
    playerState.canSwitch = Object.prototype.hasOwnProperty.call(response, "can_switch")
      ? Boolean(response.can_switch)
      : true;
    playerState.liked = Object.prototype.hasOwnProperty.call(response, "liked")
      ? response.liked
      : null;
    const showPanorama = Boolean(response.playing && String(response.playing).startsWith("Panorama"));
    setHidden($("panorama-popup"), !showPanorama);
    if (showPanorama) {
      setTimeout(forceVideoPlay, 100);
    }

    if (response.player_tech && response.player_tech !== playerState.currentPlayer) {
      playerState.currentPlayer = response.player_tech;
      playerState.selectedPlayer = response.player_tech;
      $("player").value = response.player_tech;
    }

    if (response.station_tech) {
      playerState.stationTech = response.station_tech;
      playerState.stationReadable = response.station_readable || "";
      syncStationSelect();
    }

    applyTrackProgress(response);
    updateDropdownsFromReadableValues(response);
    updatePlayerSections();
  }

  function startWhatsPlayingUpdates() {
    if (playerState.whatsPlayingSocket) return;
    const socket = api.openWhatsPlaying(applyWhatsPlaying, (closedSocket) => {
      if (playerState.whatsPlayingSocket !== closedSocket) return;
      playerState.whatsPlayingSocket = null;
      if (currentRoute() === "/login" || !api.isAuthenticated()) return;
      playerState.whatsPlayingReconnectTimer = setTimeout(() => {
        playerState.whatsPlayingReconnectTimer = null;
        startWhatsPlayingUpdates();
      }, 2000);
    });
    playerState.whatsPlayingSocket = socket;
  }

  function updateDropdownsFromReadableValues(response) {
    if (response.player_readable) {
      const currentName = playerState.availablePlayers[playerState.selectedPlayer] || playerState.selectedPlayer;
      if (response.player_readable !== currentName) {
        const matching = Object.keys(playerState.availablePlayers).find(
          (key) => playerState.availablePlayers[key] === response.player_readable
        );
        if (matching && matching !== playerState.selectedPlayer) {
          playerState.selectedPlayer = matching;
          playerState.currentPlayer = matching;
          $("player").value = matching;
        }
      }
    }

  }

  async function initializePlayer() {
    playerState.isLoading = true;
    playerState.volume = api.loadVolume();
    $("volume-slider").value = String(playerState.volume);
    $("volume-value").textContent = `${playerState.volume}%`;
    updatePlayerSections();

    playerState.audio = new Audio(freshStreamUrl());
    playerState.audio.preload = "none";
    playerState.audio.volume = playerState.volume / 100;
    bindAudioEvents(playerState.audio);
    startBufferWatchdog();
    setupVideoAutoplayWorkaround();

    try {
      const who = await api.whoami();
      fillUsernames();
      if (who && who.username) {
        document.querySelectorAll("[data-bind='username']").forEach((el) => {
          el.textContent = who.username;
        });
      }
    } catch (error) {
      console.error("Failed to get current user:", error);
    }

    try {
      playerState.availablePlayers = await api.getAvailablePlayers();
    } catch (error) {
      console.error("Failed to load available players:", error);
      playerState.availablePlayers = {
        player_radio: "Radio Player",
        player_streaming: "Streaming Player",
      };
    }
    fillSelect($("player"), playerState.availablePlayers, playerState.selectedPlayer);

    try {
      const currentPlayer = await api.getCurrentPlayer();
      playerState.currentPlayer = currentPlayer.player;
      playerState.selectedPlayer = currentPlayer.player;
      $("player").value = currentPlayer.player || "";
    } catch (error) {
      console.error("Failed to get current player:", error);
      const defaultPlayer = Object.keys(playerState.availablePlayers)[0];
      if (defaultPlayer) {
        playerState.currentPlayer = defaultPlayer;
        playerState.selectedPlayer = defaultPlayer;
        $("player").value = defaultPlayer;
      } else {
        playerState.isLoading = false;
        updatePlayerSections();
        return;
      }
    }

    await loadStationsForCurrentPlayer();
  }

  async function switchToPlayer(player) {
    playerState.isPlayerLoading = true;
    updatePlayerSections();
    try {
      await api.switchPlayer(player);
      playerState.currentPlayer = player;
      playerState.selectedPlayer = player;
      playerState.stationTech = "";
      playerState.stationReadable = "";
      playerState.availableStations = player === "player_radio"
        ? await api.getRadioStations()
        : await api.getYandexStations();
      fillSelect($("station"), playerState.availableStations, "");
      await loadCurrentStationAndPlay();
    } catch (error) {
      console.error("Failed to switch player:", error);
      playerState.isPlayerLoading = false;
      updatePlayerSections();
    }
  }

  async function onStationChange(stationKey) {
    if (!stationKey || stationKey === playerState.currentStation) {
      return;
    }
    const stationValue = playerState.availableStations[stationKey];
    if (!stationValue) {
      console.error("Station value not found for key:", stationKey);
      return;
    }
    try {
      if (playerState.currentPlayer === "player_radio") {
        await api.switchRadioStation(stationValue);
      } else {
        await api.switchYandexStation(stationValue);
      }
      playerState.currentStation = stationKey;
      playerState.selectedStation = stationKey;
    } catch (error) {
      console.error("Failed to switch station:", error);
    }
  }

  function playPause() {
    if (!playerState.audio) return;
    if (playerState.audio.paused) {
      playerState.audio.play();
    } else {
      playerState.audio.pause();
    }
  }

  function refreshStream() {
    if (!playerState.audio) return;
    const wasPlaying = !playerState.audio.paused;
    playerState.audio.src = freshStreamUrl();
    playerState.audio.load();
    if (wasPlaying) {
      playerState.audio.play();
    }
  }

  async function skipToNextTrack() {
    if (!playerState.canSkip || playerState.skipInFlight) {
      return;
    }
    playerState.skipInFlight = true;
    updatePlayerSections();
    try {
      const result = await api.nextYandexTrack();
      if (result && result.playing) {
        playerState.currentTrack = result.playing;
      }
    } catch (error) {
      if (error.status !== 409) {
        console.error("Failed to skip track:", error);
      }
    } finally {
      playerState.skipInFlight = false;
      updatePlayerSections();
    }
  }

  async function setYandexTrackLiked() {
    if (typeof playerState.liked !== "boolean" || playerState.likeInFlight) {
      return;
    }
    playerState.likeInFlight = true;
    updatePlayerSections();
    try {
      await api.setYandexTrackLiked(!playerState.liked);
      // The WebSocket state change updates the heart for every connected client.
    } catch (error) {
      console.error("Failed to change Yandex like status:", error);
    } finally {
      playerState.likeInFlight = false;
      updatePlayerSections();
    }
  }

  function createSilentAudioContext() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const audioContext = new AudioCtx();
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      gainNode.gain.setValueAtTime(0, audioContext.currentTime);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.1);
    } catch (error) {
      console.log("Could not create audio context:", error);
    }
  }

  function attemptVideoPlay(video) {
    video.play().then(() => undefined).catch(() => {
      video.currentTime = 0;
      video.play().catch(() => {
        video.load();
        setTimeout(() => {
          video.play().catch((error) => {
            console.log("All video play attempts failed:", error);
          });
        }, 100);
      });
    });
  }

  function forceVideoPlay() {
    const video = $("news-video");
    if (video) {
      attemptVideoPlay(video);
    }
  }

  function setupVideoAutoplayWorkaround() {
    createSilentAudioContext();
    document.addEventListener("click", forceVideoPlay, { once: true });
    document.addEventListener("keydown", forceVideoPlay, { once: true });
    document.addEventListener("touchstart", forceVideoPlay, { once: true });
    $("news-video").addEventListener("loadeddata", (event) => attemptVideoPlay(event.target));
  }

  function minutesWordRu(count) {
    const n = Math.abs(Number(count)) % 100;
    const last = n % 10;
    if (n > 10 && n < 20) {
      return "минут";
    }
    if (last === 1) {
      return "минута";
    }
    if (last >= 2 && last <= 4) {
      return "минуты";
    }
    return "минут";
  }

  function hasScheduleChanges() {
    const original = scheduleState.originalTimes.slice().sort();
    const current = scheduleState.times.slice().sort();
    return JSON.stringify(original) !== JSON.stringify(current);
  }

  function renderScheduleTimes() {
    const grid = $("times-grid");
    grid.innerHTML = "";
    scheduleState.times.forEach((time) => {
      const item = document.createElement("div");
      item.className = "time-item";
      item.innerHTML = `
        <div class="time-display">
          <i class="fas fa-clock"></i>
          <span class="time-text">${escapeHtml(time)}</span>
        </div>
        <div class="time-actions">
          <button type="button" class="remove-btn" data-time="${escapeHtml(time)}" ${scheduleState.isLoading ? "disabled" : ""}>
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;
      grid.appendChild(item);
    });

    const empty = scheduleState.times.length === 0 && !scheduleState.isLoading;
    setHidden($("times-list"), scheduleState.times.length === 0);
    setHidden($("schedule-empty"), !empty);
    $("save-schedule-btn").disabled = scheduleState.isLoading || !hasScheduleChanges();
    $("newTime").disabled = scheduleState.isLoading;
    $("add-time-btn").disabled = !$("newTime").value || scheduleState.isLoading;
    setHidden($("schedule-loading"), !scheduleState.isLoading);

    const prepMins = Number(scheduleState.preparationNeededMins);
    const prepNote = $("schedule-prep-note");
    if (Number.isFinite(prepMins)) {
      $("schedule-prep-mins").textContent = `${prepMins} ${minutesWordRu(prepMins)}`;
      setHidden(prepNote, false);
    } else {
      setHidden(prepNote, true);
    }
  }

  function showSuccess(message) {
    $("success-message-text").textContent = message;
    setHidden($("success-message"), false);
    if (scheduleState.successTimer) {
      clearTimeout(scheduleState.successTimer);
    }
    scheduleState.successTimer = setTimeout(() => {
      setHidden($("success-message"), true);
    }, 3000);
  }

  async function loadSchedule() {
    scheduleState.isLoading = true;
    $("schedule-loading-message").textContent = "Загрузка расписания...";
    renderScheduleTimes();
    try {
      const [timesResponse, prepResponse] = await Promise.all([
        api.getConfig(CONFIG_KEY),
        api.getConfig(PREP_KEY),
      ]);
      const times = timesResponse[CONFIG_KEY] || [];
      scheduleState.times = times.slice();
      scheduleState.originalTimes = times.slice();
      scheduleState.preparationNeededMins = prepResponse[PREP_KEY];
      scheduleState.loaded = true;
    } catch (error) {
      console.error("Error loading schedule:", error);
      alert("Ошибка загрузки расписания");
    } finally {
      scheduleState.isLoading = false;
      renderScheduleTimes();
    }
  }

  async function saveSchedule() {
    if (!hasScheduleChanges()) return;
    scheduleState.isLoading = true;
    $("schedule-loading-message").textContent = "Сохранение расписания...";
    renderScheduleTimes();
    try {
      await api.setConfig(CONFIG_KEY, scheduleState.times);
      scheduleState.originalTimes = scheduleState.times.slice();
      showSuccess("Расписание успешно сохранено");
    } catch (error) {
      console.error("Error saving schedule:", error);
      alert("Ошибка сохранения расписания");
    } finally {
      scheduleState.isLoading = false;
      renderScheduleTimes();
    }
  }

  function addTime() {
    const value = $("newTime").value;
    if (!value) return;
    if (scheduleState.times.includes(value)) {
      alert("Время уже существует");
      return;
    }
    scheduleState.times = [...scheduleState.times, value].sort((a, b) => a.localeCompare(b));
    $("newTime").value = "";
    renderScheduleTimes();
  }

  function removeTime(time) {
    scheduleState.times = scheduleState.times.filter((item) => item !== time);
    renderScheduleTimes();
  }

  function loginValid() {
    const username = $("username").value;
    const password = $("password").value;
    return username.length >= 3 && password.length >= 8;
  }

  function updateLoginValidation(showTouched) {
    const username = $("username");
    const password = $("password");
    if (showTouched || username.classList.contains("touched")) {
      username.classList.toggle("is-invalid", username.value.length < 3);
      setHidden($("username-error"), username.value.length >= 3);
    }
    if (showTouched || password.classList.contains("touched")) {
      password.classList.toggle("is-invalid", password.value.length < 8);
      setHidden($("password-error"), password.value.length >= 8);
    }
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
        error.status === 401 ? "Invalid username or password" : "An error occurred. Please try again.";
      setHidden($("login-error"), false);
    } finally {
      setLoginLoading(false);
    }
  }

  function onLogout() {
    api.logout();
    stopPlayer();
    scheduleState.loaded = false;
    navigate("/login");
  }

  async function render() {
    normalizeLegacyPath();
    const route = currentRoute();
    if (!requireAuth(route)) {
      return;
    }

    fillTitles();
    fillUsernames();

    if (route === "/login") {
      stopPlayer();
      showView("view-login");
      updateLoginValidation(false);
      return;
    }

    if (route === "/schedule") {
      // the player keeps running in the background: the views are only hidden, not torn down
      showView("view-schedule");
      if (!scheduleState.loaded && !scheduleState.isLoading) {
        await loadSchedule();
      } else {
        renderScheduleTimes();
      }
      return;
    }

    showView("view-player");
    if (!playerState.audio) {
      await initializePlayer();
    }
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
      const player = event.target.value;
      if (player && player !== playerState.currentPlayer) {
        switchToPlayer(player);
      }
    });
    $("station").addEventListener("change", (event) => onStationChange(event.target.value));
    $("play-pause-btn").addEventListener("click", playPause);
    $("next-track-btn").addEventListener("click", skipToNextTrack);
    $("like-track-btn").addEventListener("click", setYandexTrackLiked);
    $("refresh-btn").addEventListener("click", refreshStream);
    $("volume-slider").addEventListener("input", (event) => {
      playerState.volume = parseInt(event.target.value, 10);
      if (playerState.audio) {
        playerState.audio.volume = playerState.volume / 100;
      }
      $("volume-value").textContent = `${playerState.volume}%`;
      api.saveVolume(playerState.volume);
    });

    $("add-time-btn").addEventListener("click", addTime);
    $("newTime").addEventListener("input", () => {
      $("add-time-btn").disabled = !$("newTime").value || scheduleState.isLoading;
    });
    $("save-schedule-btn").addEventListener("click", saveSchedule);
    $("times-grid").addEventListener("click", (event) => {
      const button = event.target.closest("[data-time]");
      if (button) {
        removeTime(button.getAttribute("data-time"));
      }
    });
    $("success-close-btn").addEventListener("click", () => setHidden($("success-message"), true));

    document.querySelectorAll("[data-action='logout']").forEach((button) => {
      button.addEventListener("click", onLogout);
    });

    window.addEventListener("hashchange", render);
    window.addEventListener("lorad:unauthorized", () => {
      stopPlayer();
      navigate("/login");
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    fillTitles();
    setBackgrounds();
    bindEvents();
    if (!location.hash) {
      location.hash = api.isAuthenticated() ? "/" : "/login";
    } else {
      render();
    }
  });
})(window);
