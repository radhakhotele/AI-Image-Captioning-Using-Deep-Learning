---
name: Replit Preview forwarding
description: Replit custom-workflow webview port mapping and external-route verification.
---

For this mixed-service workspace, the Streamlit frontend listens on port 5000 and Replit Preview must route external port 80 to it. The Flask API on port 8000 is server-to-server from Streamlit and should remain internal. If any `.replit` port mappings are used, preserve mappings for every registered artifact service as well.

**Why:** Both servers and the workflow-reported ports were healthy while the Replit dev domain returned “Backend Not Configured”; the proxied route began returning the Streamlit page only after its port mapping was present.

**How to apply:** Verify the actual Replit dev-domain root and Streamlit health route, not only localhost or workflow `openPorts`. Use the validated `.replit` configuration flow for port mappings and check Replit Networking if the public route still has no upstream.