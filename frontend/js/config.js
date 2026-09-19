window.LORAD_CONFIG = (function () {
  const domain = "radio.locchan.dev";
  const scheme = "https";
  const apiPath = "/lorad/api";
  const radioPath = "/lorad/live";
  return {
    domain,
    scheme,
    apiPath,
    radioPath,
    apiUrl: scheme + "://" + domain + apiPath,
    radioUrl: scheme + "://" + domain + radioPath,
    autoplay: false,
    radioTitle: "ЙОПТЫМОПТЫ",
  };
})();
