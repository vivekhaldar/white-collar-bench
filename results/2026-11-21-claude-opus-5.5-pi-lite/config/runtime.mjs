// Bash calls get at most 120 s so the agent can recover from hanging scripts (as in the DeepSeek run).
export default function benchmarkRuntime(pi) {
  pi.on("tool_call", (event) => {
    if (event.toolName === "bash") {
      const requested = event.input.timeout;
      event.input.timeout = Math.min(requested > 0 ? requested : 120, 120);
    }
  });
}
