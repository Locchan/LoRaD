(function (global) {
  const CONFIG_KEY = "ENABLED_PROGRAMS/NewsSmall/start_times";
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
    trackTimer: null,
  };

  const scheduleState = {
    times: [],
    originalTimes: [],
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
    $("player").disabled = playerState.isPlayerLoading;
    $("station").disabled = playerState.isLoading || playerState.isPlayerLoading;
    setHidden($("audio-player-section"), !(playerState.currentTrack && !playerState.isLoading));
    setHidden($("track-fallback"), !(!playerState.currentTrack && playerState.selectedStation && !playerState.isLoading));
    $("track-title").textContent = playerState.currentTrack || "Нет информации о треке";
    $("fallback-station").textContent = `Станция: ${playerState.selectedStation}`;
    updatePlaybackUi();
  }

  function stopPlayer() {
    if (playerState.trackTimer) {
      clearInterval(playerState.trackTimer);
      playerState.trackTimer = null;
    }
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

  async function loadStationsForCurrentPlayer() {
    try {
      playerState.availableStations =
        playerState.currentPlayer === "player_radio"
          ? await api.getRadioStations()
          : await api.getYandexStations();
      fillSelect($("station"), playerState.availableStations, playerState.selectedStation);
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
      playerState.currentStation = response.station;
      playerState.selectedStation = response.station;
      $("station").value = response.station || "";
    } catch (error) {
      console.error(`Failed to get current station for ${playerState.currentPlayer}:`, error);
    }
    finalizeInitializationAndPlay();
  }

  function finalizeInitializationAndPlay() {
    playerState.isLoading = false;
    playerState.isPlayerLoading = false;
    updatePlayerSections();
    startTrackUpdates();
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

  function startTrackUpdates() {
    if (playerState.trackTimer) {
      clearInterval(playerState.trackTimer);
    }
    playerState.trackTimer = setInterval(async () => {
      try {
        const response = await api.getWhatsPlaying();
        if (!response) {
          playerState.currentTrack = "Нет информации о треке";
          setHidden($("panorama-popup"), true);
          updatePlayerSections();
          return;
        }

        playerState.currentTrack = response.playing || "Нет информации о треке";
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

        if (response.station_tech && response.station_tech !== playerState.currentStation) {
          playerState.currentStation = response.station_tech;
          playerState.selectedStation = response.station_tech;
          $("station").value = response.station_tech;
        }

        updateDropdownsFromReadableValues(response);
        updatePlayerSections();
      } catch (error) {
        console.error("Failed to get current track:", error);
        playerState.currentTrack = "Ошибка загрузки трека";
        updatePlayerSections();
      }
    }, 2000);
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

    if (response.station_readable && response.station_readable !== playerState.selectedStation) {
      const matching = Object.keys(playerState.availableStations).find(
        (key) => key === response.station_readable
      );
      if (matching && matching !== playerState.selectedStation) {
        playerState.selectedStation = matching;
        playerState.currentStation = matching;
        $("station").value = matching;
      }
    }
  }

  async function initializePlayer() {
    playerState.isLoading = true;
    playerState.volume = api.loadVolume();
    $("volume-slider").value = String(playerState.volume);
    $("volume-value").textContent = `${playerState.volume}%`;
    updatePlayerSections();

    playerState.audio = new Audio(config.radioUrl);
    playerState.audio.volume = playerState.volume / 100;
    bindAudioEvents(playerState.audio);
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
    playerState.audio.load();
    if (!playerState.audio.paused) {
      playerState.audio.play();
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
      const response = await api.getConfig(CONFIG_KEY);
      const times = response[CONFIG_KEY] || [];
      scheduleState.times = times.slice();
      scheduleState.originalTimes = times.slice();
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
      stopPlayer();
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
