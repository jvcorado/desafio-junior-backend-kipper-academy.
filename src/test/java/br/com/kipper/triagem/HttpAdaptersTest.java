package br.com.kipper.triagem;

import br.com.kipper.triagem.agent.HttpAiModel;
import br.com.kipper.triagem.delivery.*;
import br.com.kipper.triagem.domain.Models.*;
import com.fasterxml.jackson.databind.*;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.*;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.atomic.*;
import static org.assertj.core.api.Assertions.*;

class HttpAdaptersTest {
    HttpServer server;
    ObjectMapper json=new ObjectMapper();
    AtomicInteger status=new AtomicInteger(201),posts=new AtomicInteger();
    AtomicReference<String> response=new AtomicReference<>(),requestBody=new AtomicReference<>();
    String base;
    Ticket ticket=new Ticket("test-uuid","test","ticket-test","customer","Fictício","+5511999999999","Fui cobrado duas vezes","2026-11-05T00:00:00Z","","",Status.READY,Category.BILLING,Priority.NORMAL,Team.FINANCE,"Cobrança duplicada",null,null,null);
    @BeforeEach void start() throws Exception {
        server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
        server.createContext("/",exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(),StandardCharsets.UTF_8));
            if(exchange.getRequestMethod().equals("POST")) posts.incrementAndGet();
            byte[] bytes=response.get().getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type","application/json");
            exchange.sendResponseHeaders(status.get(),bytes.length);exchange.getResponseBody().write(bytes);exchange.close();
        });
        server.start();base="http://127.0.0.1:"+server.getAddress().getPort();
        response.set("{\"number\":10,\"html_url\":\"https://github.com/test/repo/issues/10\"}");
    }
    @AfterEach void stop() { server.stop(0); }
    GitHubIssueGateway github() { return new GitHubIssueGateway(json,base,"test/repo","fake-test-token"); }
    @Test void validGithubConfirmationAndBodyCorrelation() throws Exception {
        var result=github().create(ticket);
        assertThat(result.outcome()).isEqualTo(IssueGateway.Outcome.CONFIRMED);assertThat(result.externalId()).isEqualTo("10");
        var body=json.readTree(requestBody.get());assertThat(body.path("title").asText()).contains("FINANCE","NORMAL");
        assertThat(body.path("body").asText()).startsWith(GitHubIssueGateway.marker(ticket));
        assertThat(requestBody.get()).doesNotContain(ticket.whatsapp(),ticket.customerName());
    }
    @Test void explicitRejectionIsNotForwardedAndServerFailureIsUnknown() {
        status.set(422);response.set("{}");assertThat(github().create(ticket).outcome()).isEqualTo(IssueGateway.Outcome.REJECTED);
        status.set(500);assertThat(github().create(ticket).outcome()).isEqualTo(IssueGateway.Outcome.UNKNOWN);
        status.set(408);assertThat(github().create(ticket).outcome()).isEqualTo(IssueGateway.Outcome.UNKNOWN);
    }
    @Test void malformedConfirmationAndWrongDestinationRemainUnknown() {
        response.set("{}");assertThat(github().create(ticket).outcome()).isEqualTo(IssueGateway.Outcome.UNKNOWN);
        response.set("{\"number\":10,\"html_url\":\"https://attacker.example/issues/10\"}");
        assertThat(github().create(ticket).outcome()).isEqualTo(IssueGateway.Outcome.UNKNOWN);
    }
    @Test void reconciliationUsesExactMarkerAndNeverPosts() {
        status.set(200);response.set("[{\"number\":10,\"html_url\":\"https://github.com/test/repo/issues/10\",\"body\":\"<!-- triagem-ticket:test-uuid -->\\nContent\"}]");
        assertThat(github().find(ticket).outcome()).isEqualTo(IssueGateway.Outcome.CONFIRMED);assertThat(posts).hasValue(0);
        response.set("[]");assertThat(github().find(ticket).outcome()).isEqualTo(IssueGateway.Outcome.UNKNOWN);assertThat(posts).hasValue(0);
    }
    @Test void aiAdapterSendsStructuredToolsAndReturnsToolCalls() throws Exception {
        status.set(200);response.set("{\"choices\":[{\"message\":{\"role\":\"assistant\",\"tool_calls\":[{\"id\":\"one\",\"type\":\"function\",\"function\":{\"name\":\"consult_policy\",\"arguments\":\"{\\\"category\\\":\\\"BILLING\\\"}\"}}]}}]}");
        var ai=new HttpAiModel(json,base+"/v1/chat/completions","fake-token","test-model");
        var tools=json.readTree("[{\"type\":\"function\",\"function\":{\"name\":\"consult_policy\"}}]");
        var result=ai.complete(List.of(json.valueToTree(Map.of("role","user","content","test"))),tools);
        assertThat(result.path("tool_calls").get(0).path("function").path("name").asText()).isEqualTo("consult_policy");
        assertThat(json.readTree(requestBody.get()).path("tools")).isEqualTo(tools);
    }
}
