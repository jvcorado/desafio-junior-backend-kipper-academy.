package br.com.kipper.triagem.delivery;

import br.com.kipper.triagem.domain.Models.Ticket;
import br.com.kipper.triagem.persistence.Store;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

/** Confirmed handoff to the project's own Kanban, with a durable idempotent receipt. */
@Component
@ConditionalOnProperty(name="triagem.delivery-mode",havingValue="panel")
public class PanelIssueGateway implements IssueGateway {
    private final Store store;
    public PanelIssueGateway(Store store) { this.store=store; }
    public String name() { return "panel"; }
    public Result create(Ticket ticket) {
        if(ticket.team()==null || ticket.category()==null || ticket.priority()==null)
            return new Result(Outcome.REJECTED,null,null,"Triagem incompleta para o Kanban");
        try {
            store.jdbc().update("INSERT INTO kanban_handoffs VALUES (?,?,?,?,?,?)",Store.id(),ticket.id(),
                ticket.team().name(),ticket.category().name(),ticket.priority().name(),Store.now());
        } catch(DuplicateKeyException repeated) {
            // The unique ticket receipt arbitrates concurrent/repeated dispatches.
        }
        return find(ticket);
    }
    public Result find(Ticket ticket) {
        var ids=store.jdbc().queryForList("SELECT id FROM kanban_handoffs WHERE ticket_id=?",String.class,ticket.id());
        return ids.isEmpty()?Result.unknown("Confirmação do Kanban ainda não localizada"):
            new Result(Outcome.CONFIRMED,ids.getFirst(),"/?ticket="+ticket.id(),"Encaminhamento registrado no Kanban interno");
    }
}
