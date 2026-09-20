(function (global) {
  const TOKEN_KEY = "authToken";
  const USER_KEY = "username";
  const VOLUME_KEY = "lorad_volume";

  function config() {
    return global.LORAD_CONFIG;
  }

  function getToken() {
    return localStorage.getItem(TOKEN_KEY);
  }

  function getUsername() {
    return localStorage.getItem(USER_KEY);
  }

  function isAuthenticated() {
    return Boolean(getToken() && getUsername());
  }

  function authHeader() {
    const token = getToken();
    const username = getUsername();
    if (!token || !username) {
      throw new Error("Not authenticated");
    }
    return `${username}, ${token}`;
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function saveVolume(volume) {
    localStorage.setItem(VOLUME_KEY, String(volume));
  }

  function loadVolume() {
    const saved = localStorage.getItem(VOLUME_KEY);
    return saved ? parseInt(saved, 10) : 100;
  }

  async function request(path, options = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
    if (options.auth !== false) {
      headers.Authorization = authHeader();
    }

    const response = await fetch(`${config().apiUrl}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });

    if (response.status === 401 && options.auth !== false) {
      logout();
      global.dispatchEvent(new CustomEvent("lorad:unauthorized"));
      const error = new Error("Unauthorized");
      error.status = 401;
      throw error;
    }

    if (!response.ok) {
      const error = new Error(`Request failed: ${response.status}`);
      error.status = response.status;
      throw error;
    }

    const text = await response.text();
    return text ? JSON.parse(text) : {};
  }

  async function login(username, password) {
    const data = await request("/user/auth", {
      method: "POST",
      auth: false,
      body: { username, password },
    });
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, username);
    return data;
  }

  function openWhatsPlaying(onMessage, onClose) {
    const wsUrl = `${config().wsUrl.replace(/\/$/, "")}/whatsplaying`;
    const socket = new WebSocket(wsUrl);
    socket.addEventListener("open", () => {
      socket.send(JSON.stringify({ username: getUsername(), token: getToken() }));
    });
    socket.addEventListener("message", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.error === "Unauthorized") {
          logout();
          global.dispatchEvent(new CustomEvent("lorad:unauthorized"));
          socket.close();
          return;
        }
        onMessage(data);
      } catch (error) {
        console.error("Invalid whatsplaying WebSocket message:", error);
      }
    });
    socket.addEventListener("close", () => onClose(socket));
    socket.addEventListener("error", () => socket.close());
    return socket;
  }

  global.LoradApi = {
    isAuthenticated,
    getUsername,
    logout,
    saveVolume,
    loadVolume,
    login,
    whoami: () => request("/user/whoami"),
    getYandexStations: () => request("/yandex/available_stations"),
    getCurrentStation: () => request("/yandex/current_station"),
    openWhatsPlaying,
    switchYandexStation: (newStation) =>
      request("/yandex/switch_station", { method: "POST", body: { new_station: newStation } }),
    nextYandexTrack: () => request("/yandex/next_track", { method: "POST", body: {} }),
    setYandexTrackLiked: (liked) =>
      request("/yandex/like_track", { method: "POST", body: { liked } }),
    switchRadioStation: (newStation) =>
      request("/radio/switch_station", { method: "POST", body: { new_station: newStation } }),
    getAvailablePlayers: () => request("/available_players"),
    getRadioStations: () => request("/radio/available_stations"),
    getCurrentPlayer: () => request("/current_player"),
    switchPlayer: (newPlayer) =>
      request("/switch_player", { method: "POST", body: { new_player: newPlayer } }),
    getRadioCurrentStation: () => request("/radio/current_station"),
    getConfig: (key) =>
      request(`/admin/get_config?key=${encodeURIComponent(key)}`),
    setConfig: (key, value) => request("/admin/set_config", { method: "POST", body: { key, value } }),
  };
})(window);
