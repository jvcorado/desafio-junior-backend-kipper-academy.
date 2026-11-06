package br.com.kipper.triagem.agent;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;

/** Provider port: the harness, rather than the provider, executes tools. */
public interface AiModel {
    JsonNode complete(List<JsonNode> messages, JsonNode tools);
    String name();
}
