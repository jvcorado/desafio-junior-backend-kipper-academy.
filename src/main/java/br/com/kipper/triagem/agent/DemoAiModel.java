package br.com.kipper.triagem.agent;

import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.persistence.Store;
import com.fasterxml.jackson.databind.*;
import java.util.*;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/** Scripted local demonstration only. Does not count as evidence of a real AI call. */
@Component
@ConditionalOnProperty(name="triagem.ai-mode",havingValue="demo")
public class DemoAiModel implements AiModel {
    private final ObjectMapper json;
    private final Store store;
    public DemoAiModel(ObjectMapper json,Store store) { this.json=json; this.store=store; }
    public String name() { return "demo"; }
    public JsonNode complete(List<JsonNode> messages,JsonNode tools) {
        String original=store.read(messages.get(1).path("content").asText(),JsonNode.class).path("customerMessage").asText();
        String text=original.toLowerCase(Locale.ROOT);
        boolean billing=text.contains("cobrado duas vezes") || text.contains("cobrança duplicada");
        boolean blocked=text.contains("produto está indisponível") || text.contains("não consigo usar o produto");
        boolean minor=text.contains("consigo usar o produto") && !text.contains("não consigo usar o produto");
        Category category=billing?Category.BILLING:blocked||minor?Category.TECHNICAL:Category.OTHER;
        if(messages.stream().noneMatch(x -> "tool".equals(x.path("role").asText()))) {
            return json.valueToTree(Map.of("role","assistant","tool_calls",List.of(Map.of("id","demo-policy","type","function","function",Map.of("name","consult_policy","arguments",store.json(Map.of("category",category)))))));
        }
        var policy=store.read(messages.getLast().path("content").asText(),Policy.class);
        boolean complete=category!=Category.OTHER;
        Proposal p=new Proposal(category,complete?(blocked&&!billing?Priority.HIGH:Priority.NORMAL):null,policy.team(),
            complete?"Demonstração: mensagem corresponde ao cenário de teste do catálogo.":"Informação insuficiente ou fora do catálogo; revisão humana necessária.",
            complete,complete?blocked&&!billing:null,complete?original:null,policy.id(),policy.version());
        return json.valueToTree(Map.of("role","assistant","content",store.json(p)));
    }
}
