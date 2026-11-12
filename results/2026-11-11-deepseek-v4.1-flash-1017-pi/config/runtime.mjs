export default function benchmarkRuntime(pi) {
  pi.on("before_provider_request", (event) => {
    const payload = { ...event.payload, max_tokens: 1048576 };
    delete payload.max_completion_tokens;
    delete payload.max_output_tokens;
    payload.thinking = { type: "enabled" };
    console.error("WCB_REQUEST_CONFIG " + JSON.stringify({
      model: payload.model,
      max_tokens: payload.max_tokens,
      context_window: 1048576,
      thinking: payload.thinking,
      policy: "Model context ceiling; provider bounds remaining generation; no smaller client output cap",
    }));
    return payload;
  });
  pi.on("tool_call", (event) => {
    if (event.toolName === "bash") {
      const requested = event.input.timeout;
      event.input.timeout = Math.min(requested > 0 ? requested : 120, 120);
    }
  });
}
