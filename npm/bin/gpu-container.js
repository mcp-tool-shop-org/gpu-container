#!/usr/bin/env node
"use strict";

// Thin npm wrapper for the gpu-container CLI. Pure JSON config — @mcptoolshop/npm-launcher derives
// the release-asset names from convention, downloads the platform binary from the gpu-container
// GitHub Release, verifies its SHA256 against checksums-<version>.txt, caches it, and runs it with
// full arg passthrough.
//   binary:    gpu-container-0.1.1-linux-x64
//   checksums: checksums-0.1.1.txt
process.env.MCPTOOLSHOP_LAUNCH_CONFIG = JSON.stringify({
  toolName: "gpu-container",
  owner: "mcp-tool-shop-org",
  repo: "gpu-container",
  version: "0.1.1",
  tag: "v0.1.1",
});

require("@mcptoolshop/npm-launcher/bin/mcptoolshop-launch.js");
