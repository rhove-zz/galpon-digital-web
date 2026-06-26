const $ = (id) => document.getElementById(id);

    function text(value) {
      if (value === null || value === undefined || value === "") return "-";
      return String(value).replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }[char]));
    }

    function badge(value) {
      const normalized = String(value ?? "").toLowerCase();
      const className = normalized === "true" || normalized === "active" || normalized === "completed"
        ? "ok"
        : normalized === "false" || normalized === "failed" || normalized === "rejected"
          ? "fail"
          : "warn";
      return `<span class="badge ${className}">${text(value)}</span>`;
    }

    function hitlStatusBadge(status) {
      const normalized = String(status || "pending").toLowerCase();
      const labels = {
        pending: "pending",
        approved: "approved",
        executed: "executed",
        failed: "failed",
        rejected: "rejected",
        resumed: "resumed"
      };
      return `<span class="badge hitl-status hitl-${text(normalized)}">${text(labels[normalized] || normalized)}</span>`;
    }

    function formatUnixTime(value) {
      const timestamp = Number(value || 0);
      if (!timestamp) return "-";
      return new Date(timestamp * 1000).toLocaleString();
    }

    function hitlActions(row) {
      const status = String(row.status || "").toLowerCase();
      if (status === "pending") {
        return `
          <div class="hitl-actions">
            <button class="compact" type="button" onclick="approveTool('${text(row.id)}')">Aprobar</button>
            <button class="danger compact" type="button" onclick="rejectTool('${text(row.id)}')">Rechazar</button>
          </div>
        `;
      }
      if (status === "executed" || status === "failed") {
        return `
          <div class="hitl-actions">
            <button class="secondary compact" type="button" onclick="resumeTool('${text(row.id)}')">Reanudar</button>
          </div>
        `;
      }
      return `<span class="muted-text">Sin accion</span>`;
    }

    function hitlOutcome(row) {
      const status = String(row.status || "").toLowerCase();
      if (status === "rejected") {
        return `<div class="hitl-outcome">Rechazada por operador.</div>`;
      }
      if (status === "resumed") {
        return `<div class="hitl-outcome">Conversacion reanudada.</div>`;
      }
      if (row.result) {
        const result = row.result.result ?? row.result.error ?? row.result;
        return `<details class="hitl-outcome"><summary>Resultado</summary><pre>${jsonText(result)}</pre></details>`;
      }
      return "";
    }

    function appendHitlSystemTurn(toolId, status, message) {
      const panel = $("chatPanel");
      clearEmptyChat(panel);
      panel.insertAdjacentHTML("afterbegin", `
        <div class="turn hitl-turn">
          <div class="meta">HITL ${text(toolId).substring(0, 8)} - ${text(status)} - ${new Date().toLocaleTimeString()}</div>
          <p>${text(message)}</p>
        </div>
      `);
    }

    function jsonText(value) {
      return text(JSON.stringify(value, null, 2));
    }

    async function copyText(value) {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return;
      }
      const input = document.createElement("textarea");
      input.value = value;
      input.setAttribute("readonly", "");
      input.style.position = "absolute";
      input.style.left = "-9999px";
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
    }

    function clearEmptyChat(panel) {
      if (panel.querySelector(".empty")) {
        panel.innerHTML = "";
      }
    }

    function toolDetails(toolCalls) {
      if (!toolCalls.length) {
        return `<p><strong>Herramientas:</strong> -</p>`;
      }
      return `
        <details class="tool-details">
          <summary>Herramientas (${toolCalls.length})</summary>
          ${toolCalls.map((tool) => `
            <div class="tool-call">
              <div class="meta">${text(tool.tool)} - ${text(tool.success ? "ok" : "error")} - ${text(tool.execution_time_ms)} ms</div>
              <pre>${jsonText(tool.result ?? tool.error ?? {})}</pre>
            </div>
          `).join("")}
        </details>
      `;
    }

    function appendChatTurn(panel, message, data) {
      const toolCalls = data.tool_calls || [];
      clearEmptyChat(panel);
      panel.insertAdjacentHTML("afterbegin", `
        <div class="turn">
          <div class="meta">session ${text(data.session_id)} - iter ${text(data.iterations)} - ${new Date().toLocaleTimeString()}</div>
          <p><strong>Usuario:</strong> ${text(message)}</p>
          <p><strong>Agente:</strong> ${text(data.response)}</p>
          ${toolDetails(toolCalls)}
        </div>
      `);
    }

    function appendChatError(panel, message, error) {
      clearEmptyChat(panel);
      panel.insertAdjacentHTML("afterbegin", `
        <div class="turn">
          <div class="meta">${new Date().toLocaleTimeString()}</div>
          <p><strong>Usuario:</strong> ${text(message)}</p>
          <p class="error-text"><strong>Error:</strong> ${text(error.message)}</p>
        </div>
      `);
    }

    function detailText(detail) {
      if (Array.isArray(detail)) {
        return detail.map((item) => item.msg || item.message || JSON.stringify(item)).join("; ");
      }
      if (detail && typeof detail === "object") {
        return detail.detail || detail.message || JSON.stringify(detail);
      }
      return detail ? String(detail) : "";
    }

    async function responseMessage(response) {
      let detail = "";
      try {
        const payload = await response.json();
        detail = detailText(payload.detail || payload);
      } catch (error) {
        detail = "";
      }

      if (response.status === 401) {
        return detail || "API key requerida o invalida. Guarda una clave valida en el campo API key.";
      }
      if (response.status === 403) {
        return detail || "Rol insuficiente. Usa una clave con permisos para esta seccion.";
      }
      if (response.status === 413) {
        return detail || "Payload demasiado grande. Reduce el contenido enviado.";
      }
      if (response.status === 429) {
        const retryAfter = response.headers.get("Retry-After");
        return retryAfter
          ? `Rate limit excedido. Intenta nuevamente en ${retryAfter} segundos.`
          : "Rate limit excedido. Intenta nuevamente mas tarde.";
      }
      if (response.status === 422) {
        return detail || "Datos invalidos. Revisa el formulario.";
      }
      return detail || `${response.status} ${response.statusText}`;
    }

    async function fetchJson(url) {
      return requestJson(url);
    }

    async function requestJson(url, options = {}) {
      const headers = {};
      const apiKey = localStorage.getItem("acu_api_key") || "";
      if (apiKey) {
        headers["X-ACU-API-Key"] = apiKey;
      }
      if (options.body) {
        headers["Content-Type"] = "application/json";
      }
      const response = await fetch(url, { ...options, headers: { ...headers, ...(options.headers || {}) } });
      if (!response.ok) {
        throw new Error(await responseMessage(response));
      }
      return response.json();
    }

    function params(values) {
      const query = new URLSearchParams();
      Object.entries(values).forEach(([key, value]) => {
        if (value !== null && value !== undefined && value !== "") {
          query.set(key, value);
        }
      });
      const encoded = query.toString();
      return encoded ? `?${encoded}` : "";
    }

    async function loadHealth() {
      try {
        const data = await fetchJson("/health");
        $("serviceStatus").textContent = data.status;
        $("serviceVersion").textContent = `${data.service} ${data.version}`;
      } catch (error) {
        $("serviceStatus").textContent = "error";
        $("serviceVersion").textContent = error.message;
      }
    }

    async function approveTool(toolId) {
      try {
        const approval = await fetchJson(`/tools/pending/${toolId}/approve`, { method: "POST" });
        if (approval.success) {
          await resumeTool(toolId);
        }
        await loadPendingTools();
      } catch (error) {
        alert("Error al aprobar herramienta: " + error.message);
      }
    }

    async function rejectTool(toolId) {
      try {
        await fetchJson(`/tools/pending/${toolId}/reject`, { method: "POST" });
        appendHitlSystemTurn(toolId, "rejected", "Herramienta rechazada por operador.");
        await loadPendingTools();
      } catch (error) {
        alert("Error al rechazar herramienta: " + error.message);
      }
    }

    async function resumeTool(toolId) {
      const resumed = await fetchJson(`/tools/pending/${toolId}/resume`, { method: "POST" });
      appendHitlSystemTurn(
        toolId,
        resumed.status || "resumed",
        `Agente: ${resumed.response}`
      );
      return resumed;
    }

    window.approveTool = approveTool;
    window.rejectTool = rejectTool;
    window.resumeTool = resumeTool;

    async function loadPendingTools() {
      const section = $("pendingApprovalsSection");
      const body = $("pendingToolsBody");
      try {
        const tools = await fetchJson("/tools/pending");
        const rows = [...tools].sort((a, b) => Number(b.timestamp || 0) - Number(a.timestamp || 0));
        const pendingTools = rows.filter(t => t.status === "pending");
        if (rows.length > 0) {
          section.style.display = "flex";
          body.innerHTML = rows.map((row) => `
            <tr class="hitl-row hitl-row-${text(row.status || "pending")}">
              <td><span title="${text(row.id)}">${text(row.id).substring(0, 8)}...</span></td>
              <td>${hitlStatusBadge(row.status)}</td>
              <td><strong>${text(row.tool)}</strong><pre class="hitl-params">${jsonText(row.parameters)}</pre>${hitlOutcome(row)}</td>
              <td>${formatUnixTime(row.timestamp)}</td>
              <td>${hitlActions(row)}</td>
            </tr>
          `).join("");
          
          const pendingIds = new Set(pendingTools.map(row => String(row.id)));
          document.querySelectorAll('.auth-card').forEach(card => {
            if (!pendingIds.has(card.dataset.toolId)) {
              card.remove();
            }
          });

          // Inyectar en el chat si hay uno activo
          const activeToolsContainer = document.querySelector('.chat-msg.assistant:last-child .tools-container');
          if (activeToolsContainer) {
            pendingTools.forEach(row => {
              // Avoid duplicates in chat
              if (!document.getElementById('chat-auth-' + row.id)) {
                const card = document.createElement('div');
                card.id = 'chat-auth-' + row.id;
                card.dataset.toolId = String(row.id);
                card.className = 'tool-call pending auth-card';
                card.innerHTML = `
                  <div style="color: #fbbf24; font-weight: bold; margin-bottom: 8px;">⚠️ Autorización Requerida</div>
                  <div>La herramienta <strong>${text(row.tool)}</strong> requiere aprobación.</div>
                  <pre style="background: rgba(0,0,0,0.4); padding: 8px; border-radius: 4px; margin: 8px 0; font-size: 11px; white-space: pre-wrap;">${jsonText(row.parameters)}</pre>
                  <div style="display: flex; gap: 8px; margin-top: 12px;">
                    <button type="button" onclick="approveTool('${row.id}')" style="background: var(--ok); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; flex: 1;">✅ Aprobar</button>
                    <button type="button" onclick="rejectTool('${row.id}')" style="background: var(--danger); color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; flex: 1;">❌ Rechazar</button>
                  </div>
                `;
                card.innerHTML = `
                  <div class="auth-title">Autorizacion requerida</div>
                  <div>La herramienta <strong>${text(row.tool)}</strong> requiere aprobacion.</div>
                  <pre class="hitl-params">${jsonText(row.parameters)}</pre>
                  <div class="hitl-actions">
                    <button type="button" class="compact" onclick="approveTool('${row.id}')">Aprobar</button>
                    <button type="button" class="danger compact" onclick="rejectTool('${row.id}')">Rechazar</button>
                  </div>
                `;
                activeToolsContainer.appendChild(card);
                
                // Scroll al fondo para asegurar que se vea la tarjeta
                const panel = $("chatPanel");
                panel.scrollTop = panel.scrollHeight;
              }
            });
          }
        } else {
          section.style.display = "none";
          // Limpiar auth cards del chat activo que ya hayan sido resueltas
          document.querySelectorAll('.auth-card').forEach(card => card.remove());
        }
      } catch (error) {
        if(section.style.display !== "none") {
          body.innerHTML = `<tr><td colspan="5" class="error">${text(error.message)}</td></tr>`;
        }
      }
    }

    async function loadSessions() {
      const query = params({
        domain: $("domainFilter").value.trim(),
        status: $("statusFilter").value,
        limit: $("sessionLimit").value
      });
      const body = $("sessionsBody");
      body.innerHTML = `<tr><td colspan="5">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson(`/sessions${query}`);
        $("sessionCount").textContent = rows.length;
        $("sessionHint").textContent = new Date().toLocaleTimeString();
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr class="selectable" data-session="${text(row.session_id)}">
            <td>${text(row.session_id)}</td>
            <td>${text(row.domain)}</td>
            <td>${badge(row.status)}</td>
            <td>${text(row.total_iterations)}</td>
            <td>${text(row.started_at)}</td>
          </tr>
        `).join("") : `<tr><td colspan="5">Sin sesiones.</td></tr>`;
        body.querySelectorAll("tr[data-session]").forEach((row) => {
          row.addEventListener("click", () => {
            $("selectedSession").value = row.dataset.session;
            loadContext();
          });
        });
      } catch (error) {
        body.innerHTML = `<tr><td colspan="5" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function loadContext() {
      const sessionId = $("selectedSession").value.trim();
      const panel = $("contextPanel");
      if (!sessionId) {
        panel.innerHTML = `<div class="turn"><div class="empty">Selecciona una sesion para ver el contexto.</div></div>`;
        return;
      }
      panel.innerHTML = `<div class="turn"><div class="empty">Cargando...</div></div>`;
      try {
        const rows = await fetchJson(`/sessions/${encodeURIComponent(sessionId)}/context?limit=50`);
        panel.innerHTML = rows.length ? rows.map((row) => `
          <div class="turn">
            <div class="meta">${text(row.timestamp)} - pasos ${text(row.steps_used)}</div>
            <p><strong>Usuario:</strong> ${text(row.user_query)}</p>
            <p><strong>Agente:</strong> ${text(row.agent_response)}</p>
          </div>
        `).join("") : `<div class="turn"><div class="empty">Sin contexto para esta sesion.</div></div>`;
      } catch (error) {
        panel.innerHTML = `<div class="error">${text(error.message)}</div>`;
      }
    }

    async function sendChat() {
      const message = $("chatMessage").value.trim();
      const panel = $("chatPanel");
      if (!message) {
        $("chatStatus").textContent = "Mensaje requerido";
        return;
      }
      $("sendChat").disabled = true;
      $("chatStatus").textContent = "Conectando stream...";
      
      const domain = $("chatDomain").value.trim() || "generic";
      const persona = $("chatPersona") ? $("chatPersona").value : "default";
      
      // Creamos el contenedor del turno de chat usando el nuevo formato
      clearEmptyChat(panel);
      const turnId = 'turn-' + Date.now();
      
      // Append User message
      panel.insertAdjacentHTML("beforeend", `
        <div class="chat-msg user" id="${turnId}-user">
          <p>${text(message)}</p>
          <div class="meta" style="color: rgba(255,255,255,0.7); align-self: flex-end; margin-top: 4px;">Tú</div>
        </div>
      `);
      
      // Append Assistant message container
      panel.insertAdjacentHTML("beforeend", `
        <div class="chat-msg assistant" id="${turnId}-assistant">
          <div class="meta" style="margin-bottom: 8px;">Agente [${text(persona)}]</div>
          <div class="thought-container" style="display: none; background: rgba(0,0,0,0.3); padding: 8px; border-radius: 6px; margin-bottom: 12px; font-size: 12px; color: var(--muted);">
            <strong>🧠 Razonamiento:</strong>
            <pre class="thought-text blink-cursor" style="white-space: pre-wrap; margin-top: 4px; background: transparent; border: none; padding: 0;"></pre>
          </div>
          <div class="tools-container" style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px;"></div>
          <div class="final-answer-container" style="display: none;">
            <div class="response-text blink-cursor"></div>
          </div>
          <div class="status-indicator" style="font-size: 11px; color: var(--muted); margin-top: 8px;">Iniciando...</div>
        </div>
      `);
      
      panel.scrollTop = panel.scrollHeight;
      
      const assistantEl = document.getElementById(`${turnId}-assistant`);
      const responseTextEl = assistantEl.querySelector('.response-text');
      const thoughtContainer = assistantEl.querySelector('.thought-container');
      const thoughtTextEl = assistantEl.querySelector('.thought-text');
      const finalAnswerContainer = assistantEl.querySelector('.final-answer-container');
      const statusEl = assistantEl.querySelector('.status-indicator');
      const toolsEl = assistantEl.querySelector('.tools-container');
      
      let fullResponse = "";
      let fullThought = "";
      let toolCalls = [];

      try {
        const headers = { "Content-Type": "application/json" };
        const apiKey = localStorage.getItem("acu_api_key");
        if (apiKey) headers["X-ACU-API-Key"] = apiKey;

        const response = await fetch("/chat/stream", {
          method: "POST",
          headers,
          body: JSON.stringify({ message, domain, persona })
        });

        if (!response.ok) {
          throw new Error(await responseMessage(response));
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          
          buffer += decoder.decode(value, { stream: true });
          const parts = buffer.split("\n\n");
          buffer = parts.pop();
          
          for (const part of parts) {
            if (part.startsWith("data: ")) {
              const jsonStr = part.slice(6);
              try {
                const event = JSON.parse(jsonStr);
                
                if (event.type === 'status') {
                  statusEl.textContent = event.content;
                } else if (event.type === 'thought_token') {
                  thoughtContainer.style.display = 'block';
                  statusEl.textContent = "Razonando...";
                  fullThought += event.content;
                  thoughtTextEl.textContent = fullThought;
                } else if (event.type === 'answer_token') {
                  thoughtTextEl.classList.remove('blink-cursor');
                  finalAnswerContainer.style.display = 'block';
                  statusEl.textContent = "Respondiendo...";
                  fullResponse += event.content;
                  // Streaming simple text first, markdown formatting at the end
                  responseTextEl.textContent = fullResponse;
                } else if (event.type === 'tool_call') {
                  statusEl.textContent = `Preparando herramienta: ${event.tool}`;
                  const toolDiv = document.createElement('div');
                  toolDiv.className = 'tool-call pending';
                  toolDiv.style = "background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 4px; padding: 6px; font-size: 11px;";
                  toolDiv.innerHTML = `<strong>⚙️ ${text(event.tool)}</strong>`;
                  toolsEl.appendChild(toolDiv);
                  toolCalls.push({ element: toolDiv, tool: event.tool });
                } else if (event.type === 'tool_result') {
                  statusEl.textContent = "Analizando resultado...";
                  const lastTool = toolCalls[toolCalls.length - 1];
                  if (lastTool && lastTool.element) {
                    lastTool.element.className = 'tool-call completed';
                    lastTool.element.style.borderColor = event.success ? "rgba(16, 185, 129, 0.3)" : "rgba(239, 68, 68, 0.3)";
                    lastTool.element.innerHTML = `<strong>⚙️ ${text(lastTool.tool)}</strong> <span style="color: ${event.success ? 'var(--ok)' : 'var(--danger)'}">[${event.success ? 'OK' : 'Error'}]</span>`;
                  }
                } else if (event.type === 'error') {
                  statusEl.innerHTML = `<span style="color: var(--danger)">${text(event.content)}</span>`;
                } else if (event.type === 'done') {
                  responseTextEl.classList.remove('blink-cursor');
                  statusEl.style.display = 'none';
                  
                  // Aplicar Markdown si marked está disponible
                  if (window.marked && fullResponse) {
                    responseTextEl.innerHTML = marked.parse(fullResponse);
                    // Aplicar syntax highlighting
                    if (window.hljs) {
                      responseTextEl.querySelectorAll('pre code').forEach((block) => {
                        hljs.highlightElement(block);
                      });
                    }
                  }
                }
                panel.scrollTop = panel.scrollHeight;
              } catch (e) {
                console.warn("Error parseando SSE chunk", e);
              }
            }
          }
        }
        
        $("chatMessage").value = "";
        $("chatStatus").textContent = "Respuesta recibida";
        await loadSessions();
        await loadTools();
      } catch (error) {
        turnEl.remove();
        appendChatError(panel, message, error);
        $("chatStatus").textContent = error.message;
      } finally {
        $("sendChat").disabled = false;
      }
    }

    async function loadTools() {
      const query = params({
        tool_name: $("toolFilter").value.trim(),
        success: $("toolSuccessFilter").value,
        limit: $("toolLimit").value
      });
      const body = $("toolsBody");
      body.innerHTML = `<tr><td colspan="4">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson(`/tools/executions${query}`);
        $("toolCount").textContent = rows.length;
        $("toolHint").textContent = new Date().toLocaleTimeString();
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr>
            <td>${text(row.tool_name)}</td>
            <td>${badge(row.success)}</td>
            <td>${text(row.execution_time_ms)}</td>
            <td>${text(row.executed_at)}</td>
          </tr>
        `).join("") : `<tr><td colspan="4">Sin auditoria.</td></tr>`;
      } catch (error) {
        body.innerHTML = `<tr><td colspan="4" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function loadDecisions() {
      const query = params({
        search: $("decisionSearch").value.trim(),
        domain: $("decisionDomain").value.trim(),
        limit: $("decisionLimit").value
      });
      const body = $("decisionsBody");
      body.innerHTML = `<tr><td colspan="3">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson(`/braincore/decisions${query}`);
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr>
            <td title="${text(row.decision)}">${text(row.title)}</td>
            <td>${text(row.domain)}</td>
            <td>${badge(row.status)}</td>
          </tr>
        `).join("") : `<tr><td colspan="3">Sin decisiones.</td></tr>`;
      } catch (error) {
        body.innerHTML = `<tr><td colspan="3" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function loadSources() {
      const query = params({
        domain: $("sourceDomain").value.trim(),
        source_type: $("sourceType").value.trim(),
        status: $("sourceStatus").value,
        limit: $("sourceLimit").value
      });
      const body = $("sourcesBody");
      body.innerHTML = `<tr><td colspan="5">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson(`/braincore/sources${query}`);
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr>
            <td title="${text(row.source_path)}">${text(row.source_path)}</td>
            <td>${text(row.source_type)}</td>
            <td>${text(row.chunks_count)}</td>
            <td>${badge(row.status)}</td>
            <td><button class="danger compact" type="button" data-delete-source="${text(row.id)}">Eliminar</button></td>
          </tr>
        `).join("") : `<tr><td colspan="5">Sin fuentes indexadas.</td></tr>`;
        body.querySelectorAll("button[data-delete-source]").forEach((button) => {
          button.addEventListener("click", () => deleteSource(button));
        });
      } catch (error) {
        body.innerHTML = `<tr><td colspan="5" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function loadBrainMetrics() {
      try {
        const data = await fetchJson("/braincore/metrics");
        $("decisionCount").textContent = data.decisions_count ?? 0;
        $("decisionHint").textContent = data.last_updated_at || "Metricas BrainCore";
        $("sourceCount").textContent = data.sources_count ?? 0;
        $("sourceHint").textContent = data.last_indexed_at || "Fuentes indexadas";
        $("chunkCount").textContent = data.chunks_count ?? 0;
        const mainType = (data.source_types || [])[0];
        $("chunkHint").textContent = mainType
          ? `${mainType.name}: ${mainType.chunks_count}`
          : "Contexto ingerido";
        $("domainCount").textContent = data.domains_count ?? 0;
        const mainDomain = (data.domains || [])[0];
        $("domainHint").textContent = mainDomain
          ? `${mainDomain.name}: ${mainDomain.sources_count}`
          : "Dominios indexados";
      } catch (error) {
        $("chunkHint").textContent = error.message;
        $("domainHint").textContent = error.message;
      }
    }

    async function loadSystemMetrics() {
      try {
        const data = await fetchJson("/system/metrics");
        const vector = data.vector_store || {};
        const hitl = data.pending_tools || {};
        const scheduler = data.scheduler || {};
        const redis = data.redis || {};
        const webhooks = data.webhooks || {};
        const webhookTotal = webhooks.total || {};
        $("vectorStatus").textContent = vector.status || "unknown";
        $("vectorHint").textContent = vector.enabled
          ? `${vector.engine || "vector"} - ${vector.records_count ?? 0} registros`
          : "Vector store deshabilitado";
        $("hitlStatus").textContent = hitl.pending ?? 0;
        $("hitlHint").textContent = `${hitl.total ?? 0} total - ${hitl.executed ?? 0} ejecutadas - ${hitl.resumed ?? 0} reanudadas`;
        $("schedulerStatus").textContent = scheduler.running ? "activo" : scheduler.mode || "disabled";
        $("schedulerHint").textContent = `${scheduler.jobs_count ?? 0} jobs - ${redis.backend || "local"}`;
        $("webhookStatusMetric").textContent = webhookTotal.received ?? 0;
        $("webhookHint").textContent = `${webhookTotal.accepted ?? 0} aceptados - ${webhookTotal.rejected ?? 0} rechazados`;
        const policies = [];
        if (data.api_auth_required) policies.push("auth");
        if (data.rate_limit_enabled) policies.push("rate");
        if (data.payload_limit_enabled) policies.push("payload");
        if (data.cors_enabled) policies.push("cors");
        $("securityStatus").textContent = policies.length ? "activo" : "basico";
        $("securityHint").textContent = policies.length
          ? policies.join(", ")
          : "Sin politicas adicionales";
      } catch (error) {
        $("vectorStatus").textContent = "error";
        $("vectorHint").textContent = error.message;
        $("hitlStatus").textContent = "error";
        $("hitlHint").textContent = error.message;
        $("schedulerStatus").textContent = "error";
        $("schedulerHint").textContent = error.message;
        $("webhookStatusMetric").textContent = "error";
        $("webhookHint").textContent = error.message;
        $("securityStatus").textContent = "error";
        $("securityHint").textContent = error.message;
      }
    }

    async function ingestSource() {
      const path = $("ingestPath").value.trim();
      if (!path) {
        $("ingestStatus").textContent = "Ruta requerida";
        return;
      }
      const button = $("ingestSource");
      button.disabled = true;
      $("ingestStatus").textContent = "Ingestando...";
      try {
        const result = await requestJson("/braincore/ingest", {
          method: "POST",
          body: JSON.stringify({
            path,
            domain: $("ingestDomain").value.trim() || "generic",
            source_type: $("ingestSourceType").value || "auto"
          })
        });
        $("ingestStatus").textContent = `${result.sources_indexed} fuentes, ${result.chunks_indexed} chunks`;
        await loadBrainMetrics();
        await loadSystemMetrics();
        await loadSources();
      } catch (error) {
        $("ingestStatus").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    }

    async function searchBrainCore() {
      const query = $("brainSearchQuery").value.trim();
      const panel = $("brainSearchResults");
      if (!query) {
        panel.innerHTML = `<div class="result"><div class="empty">Consulta requerida.</div></div>`;
        return;
      }
      $("runBrainSearch").disabled = true;
      panel.innerHTML = `<div class="result"><div class="empty">Buscando...</div></div>`;
      try {
        const data = await requestJson("/braincore/search", {
          method: "POST",
          body: JSON.stringify({
            query,
            domain: $("brainSearchDomain").value.trim() || null,
            source_type: $("brainSearchType").value.trim() || null,
            top_k: Number($("brainSearchTopK").value || 5)
          })
        });
        const rows = data.results || [];
        panel.innerHTML = rows.length ? rows.map((row) => `
          <div class="result">
            <div class="meta">${text(row.source_path)} - ${text(row.source_type)} - score ${text(row.similarity)}</div>
            <p><strong>${text(row.title)}</strong></p>
            <p>${text(row.content)}</p>
          </div>
        `).join("") : `<div class="result"><div class="empty">Sin resultados.</div></div>`;
      } catch (error) {
        panel.innerHTML = `<div class="error">${text(error.message)}</div>`;
      } finally {
        $("runBrainSearch").disabled = false;
      }
    }

    async function deleteSource(button) {
      const sourceId = button.dataset.deleteSource;
      if (!sourceId) return;
      if (!window.confirm(`Eliminar fuente BrainCore ${sourceId}?`)) return;
      button.disabled = true;
      button.textContent = "Eliminando";
      try {
        await requestJson(`/braincore/sources/${encodeURIComponent(sourceId)}`, { method: "DELETE" });
        await loadBrainMetrics();
        await loadSystemMetrics();
        await loadSources();
      } catch (error) {
        button.disabled = false;
        button.textContent = "Eliminar";
        $("sourceHint").textContent = error.message;
      }
    }

    async function loadAccessLog() {
      const query = params({
        path: $("accessPathFilter").value.trim(),
        authorized: $("accessAuthorizedFilter").value,
        limit: $("accessLimit").value
      });
      const body = $("accessBody");
      body.innerHTML = `<tr><td colspan="5">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson(`/api/access-log${query}`);
        $("accessCount").textContent = rows.length;
        $("accessHint").textContent = new Date().toLocaleTimeString();
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr>
            <td>${text(row.method)}</td>
            <td>${text(row.path)}</td>
            <td>${badge(row.status_code)}</td>
            <td>${text((row.roles || []).join(","))}</td>
            <td>${text(row.accessed_at)}</td>
          </tr>
        `).join("") : `<tr><td colspan="5">Sin accesos.</td></tr>`;
      } catch (error) {
        body.innerHTML = `<tr><td colspan="5" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function loadApiKeys() {
      const body = $("apiKeysBody");
      body.innerHTML = `<tr><td colspan="5">Cargando...</td></tr>`;
      try {
        const rows = await fetchJson("/api/keys?limit=50");
        body.innerHTML = rows.length ? rows.map((row) => `
          <tr>
            <td>${text(row.name)}</td>
            <td>${text((row.roles || []).join(","))}</td>
            <td>${badge(row.status)}</td>
            <td>${text(row.key_fingerprint)}</td>
            <td><button class="danger compact" type="button" data-revoke-key="${text(row.id)}" ${row.status === "revoked" ? "disabled" : ""}>Revocar</button></td>
          </tr>
        `).join("") : `<tr><td colspan="5">Sin claves gestionadas.</td></tr>`;
        body.querySelectorAll("button[data-revoke-key]").forEach((button) => {
          button.addEventListener("click", () => revokeApiKey(button));
        });
      } catch (error) {
        body.innerHTML = `<tr><td colspan="5" class="error">${text(error.message)}</td></tr>`;
      }
    }

    async function createApiKey() {
      const name = $("apiKeyName").value.trim();
      const roles = $("apiKeyRoles").value.split(",").map((role) => role.trim()).filter(Boolean);
      if (!name || !roles.length) {
        $("apiKeyCreateStatus").textContent = "Nombre y roles requeridos";
        return;
      }
      const button = $("createApiKey");
      button.disabled = true;
      $("apiKeyCreateStatus").textContent = "Creando...";
      try {
        const payload = { name, roles };
        const expiresAt = $("apiKeyExpires").value.trim();
        if (expiresAt) {
          payload.expires_at = expiresAt;
        }
        const result = await requestJson("/api/keys", {
          method: "POST",
          body: JSON.stringify(payload)
        });
        $("apiKeyCreateStatus").innerHTML = `
          <span>Clave creada: <code>${text(result.api_key)}</code></span>
          <button id="copyCreatedApiKey" class="secondary compact" type="button">Copiar</button>
        `;
        $("copyCreatedApiKey").addEventListener("click", async () => {
          await copyText(result.api_key);
          $("copyCreatedApiKey").textContent = "Copiada";
        });
        $("apiKeyName").value = "";
        $("apiKeyRoles").value = "";
        $("apiKeyExpires").value = "";
        await loadApiKeys();
      } catch (error) {
        $("apiKeyCreateStatus").textContent = error.message;
      } finally {
        button.disabled = false;
      }
    }

    async function revokeApiKey(button) {
      const keyId = button.dataset.revokeKey;
      if (!keyId) return;
      if (!window.confirm(`Revocar clave API ${keyId}?`)) return;
      button.disabled = true;
      button.textContent = "Revocando";
      try {
        await requestJson(`/api/keys/${encodeURIComponent(keyId)}/revoke`, { method: "POST" });
        await loadApiKeys();
      } catch (error) {
        button.disabled = false;
        button.textContent = "Revocar";
        $("apiKeyCreateStatus").textContent = error.message;
      }
    }

    function refreshAll() {
      loadHealth();
      loadPendingTools();
      loadSessions();
      loadTools();
      loadDecisions();
      loadSources();
      loadBrainMetrics();
      loadSystemMetrics();
      loadAccessLog();
      loadApiKeys();
      loadContext();
    }

    $("refreshAll").addEventListener("click", refreshAll);
    if ($("refreshPendingTools")) {
      $("refreshPendingTools").addEventListener("click", loadPendingTools);
    }
    
    // Polling for pending tools
    setInterval(loadPendingTools, 3000);
    $("sendChat").addEventListener("click", sendChat);
    $("chatMessage").addEventListener("keydown", (event) => {
      if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        sendChat();
      }
    });
    $("refreshSessions").addEventListener("click", loadSessions);
    $("refreshTools").addEventListener("click", loadTools);
    $("refreshContext").addEventListener("click", loadContext);
    $("refreshDecisions").addEventListener("click", loadDecisions);
    $("refreshSources").addEventListener("click", loadSources);
    $("ingestSource").addEventListener("click", ingestSource);
    $("runBrainSearch").addEventListener("click", searchBrainCore);
    $("brainSearchQuery").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        searchBrainCore();
      }
    });
    $("refreshAccess").addEventListener("click", loadAccessLog);
    $("refreshApiKeys").addEventListener("click", loadApiKeys);
    $("createApiKey").addEventListener("click", createApiKey);
    $("openDocs").addEventListener("click", () => { window.location.href = "/docs"; });
    $("saveApiKey").addEventListener("click", () => {
      const apiKey = $("apiKeyInput").value.trim();
      if (apiKey) {
        localStorage.setItem("acu_api_key", apiKey);
      } else {
        localStorage.removeItem("acu_api_key");
      }
      refreshAll();
    });
    ["domainFilter", "statusFilter", "sessionLimit"].forEach((id) => $(id).addEventListener("change", loadSessions));
    ["toolFilter", "toolSuccessFilter", "toolLimit"].forEach((id) => $(id).addEventListener("change", loadTools));
    ["decisionSearch", "decisionDomain", "decisionLimit"].forEach((id) => $(id).addEventListener("change", loadDecisions));
    ["sourceDomain", "sourceType", "sourceStatus", "sourceLimit"].forEach((id) => $(id).addEventListener("change", loadSources));
    ["accessPathFilter", "accessAuthorizedFilter", "accessLimit"].forEach((id) => $(id).addEventListener("change", loadAccessLog));
    $("selectedSession").addEventListener("change", loadContext);
    $("apiKeyInput").value = localStorage.getItem("acu_api_key") || "";
    refreshAll();
