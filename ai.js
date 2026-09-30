// static/ai.js - Eyewall AI Panel Integration
const API_BASE = (window.EYEWALL_API_BASE || "");

function getElement(id) {
  return document.getElementById(id);
}

function updateElement(id, text) {
  const el = getElement(id);
  if (!el) return;
  if ("value" in el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
    el.value = text;
  } else {
    el.textContent = text;
  }
}

async function updateHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/health`);
    if (!res.ok) {
      updateElement("ai-error", `Health check failed: HTTP ${res.status}`);
      return;
    }
    const data = await res.json();
    if (data.gemini) {
      if (data.gemini.configured && data.gemini.model) {
        updateElement("ai-status", `Configured (${data.gemini.model})`);
      } else {
        updateElement("ai-status", `Not Configured (${data.gemini.error || "No API key"})`);
      }
      if (data.gemini.remaining_today !== undefined) {
        updateElement("ai-quota", `${data.gemini.remaining_today} calls remaining today`);
      }
    }
  } catch (err) {
    updateElement("ai-error", `Health check request failed: ${err.message}`);
  }
}

async function updateQuota() {
  try {
    const res = await fetch(`${API_BASE}/api/quota`);
    if (!res.ok) {
      updateElement("ai-error", `Quota check failed: HTTP ${res.status}`);
      return;
    }
    const data = await res.json();
    if (data.remaining_today !== undefined && data.daily_budget !== undefined) {
      updateElement("ai-quota", `${data.remaining_today} / ${data.daily_budget} calls remaining today`);
    }
  } catch (err) {
    updateElement("ai-error", `Quota request failed: ${err.message}`);
  }
}

async function readRisk(exposure, surge) {
  updateElement("ai-error", "");
  try {
    const res = await fetch(`${API_BASE}/api/risk/read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ exposure, surge }),
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      updateElement("ai-error", errData.detail || errData.note || `Risk check failed: HTTP ${res.status}`);
      return null;
    }
    const data = await res.json();
    if (!data.ok) {
      updateElement("ai-error", data.note || "Risk assessment failed");
      if (data.guardrail && data.guardrail.ok === false) {
        updateElement("ai-error", `Risk guardrail rejected: ${data.note || "unverified numbers"}`);
      }
      return data;
    }

    const risk = data.risk || {};
    let text = `Headline: ${risk.headline || "N/A"}\n`;
    text += `Score: ${risk.score || "N/A"} / 5\n`;
    text += `Confidence: ${risk.confidence || "N/A"}\n`;
    if (Array.isArray(risk.reasons) && risk.reasons.length > 0) {
      text += `Reasons:\n - ` + risk.reasons.join("\n - ") + "\n";
    }
    if (Array.isArray(risk.caveats) && risk.caveats.length > 0) {
      text += `Caveats:\n - ` + risk.caveats.join("\n - ");
    }
    updateElement("ai-risk", text);
    return data;
  } catch (err) {
    updateElement("ai-error", `Risk request failed: ${err.message}`);
    return null;
  }
}

async function draftAdvisory(exposure, surge, lang = "en", includeGrounding = false) {
  updateElement("ai-error", "");
  updateElement("ai-advisory", "");
  updateElement("ai-aimode", "Drafting...");

  try {
    const res = await fetch(`${API_BASE}/api/advisory/draft`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ surge, lang, exposure, include_grounding: includeGrounding }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      updateElement("ai-error", errData.detail || errData.note || `Advisory draft failed: HTTP ${res.status}`);
      updateElement("ai-aimode", "Failed");
      return null;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    let accumulatedText = "";
    let doneMetadata = null;

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let currentEvent = null;
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          currentEvent = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          const rawData = line.slice(6).trim();
          try {
            const parsed = JSON.parse(rawData);
            if (currentEvent === "done") {
              doneMetadata = parsed;
            } else if (parsed.text) {
              accumulatedText += parsed.text;
              updateElement("ai-advisory", accumulatedText);
            }
          } catch (e) {
            // ignore JSON parse errors on partial chunks
          }
          currentEvent = null;
        }
      }
    }

    if (doneMetadata) {
      if (doneMetadata.mode === "gemini") {
        updateElement("ai-aimode", `Gemini (${doneMetadata.model || "Unknown Model"})`);
      } else if (doneMetadata.mode === "template") {
        updateElement("ai-aimode", "Template");
      } else {
        updateElement("ai-aimode", doneMetadata.mode || "Unknown");
      }

      if (doneMetadata.guardrail && doneMetadata.guardrail.ok === false) {
        updateElement(
          "ai-error",
          `Model draft was rejected: ${doneMetadata.note || "Guardrail validation failed"}`
        );
      } else if (doneMetadata.note && doneMetadata.mode === "template") {
        updateElement("ai-error", `Notice: ${doneMetadata.note}`);
      }
    }

    updateQuota();
    return doneMetadata;
  } catch (err) {
    updateElement("ai-error", `Advisory request failed: ${err.message}`);
    updateElement("ai-aimode", "Failed");
    return null;
  }
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    updateHealth();
    updateQuota();
  });
}

if (typeof window !== "undefined") {
  window.EyewallAI = {
    updateHealth,
    updateQuota,
    readRisk,
    draftAdvisory,
  };
}
