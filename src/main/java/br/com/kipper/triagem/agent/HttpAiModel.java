package br.com.kipper.triagem.agent;

import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;

@Component
@ConditionalOnProperty(name="triagem.ai-mode",havingValue="http")
public class HttpAiModel implements AiModel {
    private final ObjectMapper json;
    private final URI url;
    private final String key,model;
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    public HttpAiModel(ObjectMapper json,@Value("${triagem.ai-url}") String url,@Value("${triagem.ai-key}") String key,@Value("${triagem.ai-model}") String model) {
        this.json=json; this.url=URI.create(url); this.key=key; this.model=model;
        if(key.isBlank() || model.isBlank()) throw new IllegalArgumentException("AI_API_KEY e AI_MODEL obrigatórios no modo http");
        if(!this.url.getScheme().equals("https") && !Set.of("127.0.0.1","localhost").contains(this.url.getHost()))
            throw new IllegalArgumentException("IA exige HTTPS ou loopback");
    }
    public String name() { return "http"; }
    public JsonNode complete(List<JsonNode> messages,JsonNode tools) {
        try {
            String body=json.writeValueAsString(Map.of("model",model,"messages",messages,"tools",tools,"tool_choice","auto"));
            var request=HttpRequest.newBuilder(url).timeout(Duration.ofSeconds(60)).header("Authorization","Bearer "+key)
                .header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(body)).build();
            var response=client.send(request,HttpResponse.BodyHandlers.ofString());
            if(response.statusCode()!=200 || response.body().length()>100_000) throw new IllegalStateException("Provedor de IA indisponível");
            return json.readTree(response.body()).path("choices").path(0).path("message");
        } catch(InterruptedException e) { Thread.currentThread().interrupt(); throw new IllegalStateException("IA interrompida"); }
        catch(Exception e) { throw new IllegalStateException("Falha no provedor de IA"); }
    }
}
