"""Fixed, unprivileged Hermes inference worker. Credentials stay in Hermes."""
import json
import sys


def complete(request):
    from agent.auxiliary_client import resolve_provider_client
    client, model = resolve_provider_client("openai-codex", model="gpt-6.1-sol")
    if client is None:
        raise RuntimeError("Provider unavailable")
    reply = client.chat.completions.create(
        model=model, messages=request["messages"], tools=request["tools"],
        tool_choice="auto", timeout=48,
    ).choices[0].message
    message = {"role": "assistant", "content": reply.content}
    calls = getattr(reply, "tool_calls", None)
    if calls:
        message["tool_calls"] = [{"id": c.id, "type": "function", "function": {
            "name": c.function.name, "arguments": c.function.arguments}} for c in calls]
    return {"choices": [{"message": message}]}


if __name__ == "__main__":
    try:
        request = json.loads(sys.stdin.read(100_001))
        assert len(json.dumps(request)) <= 100_000
        assert len(request["tools"]) == 1
        assert request["tools"][0]["function"]["name"] == "consult_policy"
        print(json.dumps(complete(request)))
    except Exception:
        print(json.dumps({"error": "Hermes inference unavailable"}))
        sys.exit(1)
