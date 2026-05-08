/**
 * Smart BI Embed SDK
 * Usage:
 *   <script src="https://your-smartbi.com/embed.js"><\/script>
 *   <div id="my-chart"></div>
 *   <script>
 *     SmartBI.embed({ token: "xxx", target: "#my-chart", height: "400px" });
 *   <\/script>
 */
(function (global) {
  "use strict";

  function embed(options) {
    var token = options.token;
    var target = options.target;
    var height = options.height || "400px";
    var width = options.width || "100%";
    var noHeader = options.noHeader ? "?no_header=1" : "";

    if (!token) {
      console.error("[SmartBI] embed token is required");
      return;
    }

    var el = typeof target === "string" ? document.querySelector(target) : target;
    if (!el) {
      console.error("[SmartBI] target element not found:", target);
      return;
    }

    var origin = options.origin || (
      document.currentScript
        ? new URL(document.currentScript.src).origin
        : window.location.origin
    );

    var iframe = document.createElement("iframe");
    iframe.src = origin + "/embed/" + token + noHeader;
    iframe.style.width = width;
    iframe.style.height = height;
    iframe.style.border = "none";
    iframe.style.borderRadius = options.borderRadius || "8px";
    iframe.allowFullscreen = true;
    iframe.setAttribute("loading", "lazy");

    el.innerHTML = "";
    el.appendChild(iframe);

    return iframe;
  }

  global.SmartBI = { embed: embed };
})(window);
