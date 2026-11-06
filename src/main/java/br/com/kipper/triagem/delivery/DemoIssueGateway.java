package br.com.kipper.triagem.delivery;

import br.com.kipper.triagem.domain.Models.Ticket;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name="triagem.delivery-mode",havingValue="demo")
public class DemoIssueGateway implements IssueGateway {
    public String name() { return "demo"; }
    public Result create(Ticket t) { return new Result(Outcome.CONFIRMED,"demo-"+t.id(),"/demo.html?id="+t.id(),"Registro simulado; nenhuma issue criada no GitHub"); }
    public Result find(Ticket t) { return Result.unknown("O adaptador de demonstração não consulta o GitHub"); }
}
