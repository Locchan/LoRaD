window.LORAD_CONFIG = (function () {
  const domain = "radio.locchan.dev";
  const scheme = "https";
  const apiPath = "/lorad/api";
  const radioPath = "/lorad/live";
  const wsPath = "/lorad/ws";
  const apiUrlOverride = "";
  const radioUrlOverride = "";
  const wsUrlOverride = "";
  const apiUrl = apiUrlOverride || (scheme + "://" + domain + apiPath);
  const radioUrl = radioUrlOverride || (scheme + "://" + domain + radioPath);
  const wsScheme = scheme === "https" ? "wss" : "ws";
  const wsUrl = wsUrlOverride || (wsScheme + "://" + domain + wsPath);
  return {
    domain,
    scheme,
    apiPath,
    radioPath,
    wsPath,
    apiUrl,
    radioUrl,
    wsUrl,
    autoplay: false,
    radioTitle: "ДедоРадио",
    // how much of the live stream the browser is allowed to sit on before we drop back to the edge
    maxBufferKb: 128,
    streamBitrateKbps: 128,
  };
})();
