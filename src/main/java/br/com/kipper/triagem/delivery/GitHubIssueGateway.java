package br.com.kipper.triagem.delivery;

import br.com.kipper.triagem.domain.Models.Ticket;
import com.fasterxml.jackson.databind.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import java.util.*;

@Component
@ConditionalOnProperty(name="triagem.delivery-mode",havingValue="github")
public class GitHubIssueGateway implements IssueGateway {
    private final HttpClient client=HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build();
    private final ObjectMapper json;
    private final String base,repository,token;
    public GitHubIssueGateway(ObjectMapper json,@Value("${triagem.github-url}") String base,
        @Value("${triagem.github-repository}") String repository,@Value("${triagem.github-token}") String token) {
        this.json=json; this.base=base.replaceAll("/+$",""); this.repository=repository; this.token=token;
        if(!repository.matches("[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+") || token.isBlank()) throw new IllegalArgumentException("Configure repositório e token do GitHub");
        URI uri=URI.create(base);
        if(!uri.getScheme().equals("https") && !Set.of("localhost","127.0.0.1").contains(uri.getHost())) throw new IllegalArgumentException("GitHub exige HTTPS ou loopback");
    }
    public String name() { return "github"; }
    public static String marker(Ticket t) { return "<!-- triagem-ticket:"+t.id()+" -->"; }
    private HttpRequest.Builder request(String suffix) {
        return HttpRequest.newBuilder(URI.create(base+"/repos/"+repository+"/issues"+suffix)).timeout(Duration.ofSeconds(30))
            .header("Authorization","Bearer "+token).header("Accept","application/vnd.github+json")
            .header("X-GitHub-Api-Version","2022-11-28");
    }
    public Result create(Ticket t) {
        try {
            // Client contact details remain local. Use fictional messages in any public test repository.
            String body=marker(t)+"\n## Triagem de suporte\nEquipe: "+t.team()+"\nCategoria: "+t.category()+"\nPrioridade: "+t.priority()
                +"\n\nJustificativa: "+t.explanation()+"\n\nMensagem de teste:\n```text\n"+t.message().replace("```","''' ")+"\n```\n\nEncaminhamento não significa resolução.";
            var req=request("").header("Content-Type","application/json").POST(HttpRequest.BodyPublishers.ofString(
                json.writeValueAsString(Map.of("title","["+t.team()+"]["+t.priority()+"] Suporte "+t.id(),"body",body)))).build();
            var r=client.send(req,HttpResponse.BodyHandlers.ofString());
            if(r.statusCode()==201) return confirmed(json.readTree(r.body()));
            if(r.statusCode()>=400 && r.statusCode()<500 && r.statusCode()!=408)
                return new Result(Outcome.REJECTED,null,null,"GitHub rejeitou a criação (HTTP "+r.statusCode()+")");
            return Result.unknown("Resposta inconclusiva do GitHub (HTTP "+r.statusCode()+"); reconciliar antes de qualquer reenvio");
        } catch(InterruptedException e) { Thread.currentThread().interrupt(); return Result.unknown("Envio interrompido; criação pode ter ocorrido"); }
        catch(Exception e) { return Result.unknown("Sem confirmação válida do GitHub; criação pode ter ocorrido"); }
    }
    public Result find(Ticket t) {
        try {
            for(int page=1;page<=20;page++) {
                var r=client.send(request("?state=all&per_page=100&page="+page).GET().build(),HttpResponse.BodyHandlers.ofString());
                if(r.statusCode()!=200) return Result.unknown("Não foi possível consultar o GitHub para reconciliar");
                var issues=json.readTree(r.body());
                if(!issues.isArray()) return Result.unknown("Resposta inválida na reconciliação");
                List<JsonNode> found=new ArrayList<>();
                for(var issue:issues) if(!issue.has("pull_request") && issue.path("body").asText().startsWith(marker(t)+"\n")) found.add(issue);
                if(found.size()>1) return Result.unknown("Múltiplas issues correlacionadas; revisão manual necessária");
                if(found.size()==1) return confirmed(found.getFirst());
                if(issues.size()<100) break;
            }
            // Absence in a bounded list does not prove the original request failed.
            return Result.unknown("Registro ainda não localizado; mantido sem reenvio para evitar duplicação");
        } catch(InterruptedException e) { Thread.currentThread().interrupt(); return Result.unknown("Consulta interrompida"); }
        catch(Exception e) { return Result.unknown("Falha ao reconciliar; não reenviar"); }
    }
    private Result confirmed(JsonNode issue) {
        long number=issue.path("number").asLong(0);
        String url=issue.path("html_url").asText();
        if(number<1 || !url.equals("https://github.com/"+repository+"/issues/"+number)) return Result.unknown("Confirmação do GitHub sem ID e link válidos");
        return new Result(Outcome.CONFIRMED,Long.toString(number),url,"Criação confirmada pelo GitHub");
    }
}
