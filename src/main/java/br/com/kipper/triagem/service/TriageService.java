package br.com.kipper.triagem.service;

import br.com.kipper.triagem.agent.AgentHarness;
import br.com.kipper.triagem.delivery.IssueGateway;
import br.com.kipper.triagem.domain.Models.*;
import br.com.kipper.triagem.domain.DomainException;
import br.com.kipper.triagem.persistence.Store;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class TriageService {
    private final Store store;
    private final AgentHarness agent;
    private final IssueGateway gateway;
    private final TransactionTemplate tx;
    public TriageService(Store store,AgentHarness agent,IssueGateway gateway,TransactionTemplate tx) { this.store=store; this.agent=agent; this.gateway=gateway; this.tx=tx; }
    public Ticket process(String id) {
        store.ticket(id);
        if(!store.claim(id,Status.RECEIVED,Status.PROCESSING)) throw new DomainException(409,"Chamado já processado ou em processamento");
        var analysis=agent.analyze(store.ticket(id));
        boolean ready=tx.execute(s -> {
            store.jdbc().queryForList("SELECT id FROM tickets WHERE id=? FOR UPDATE",id);
            if(store.ticket(id).status()!=Status.PROCESSING) return false;
            store.jdbc().update("INSERT INTO analyses VALUES (?,?,?,?,?,?,?,?,?)",Store.id(),id,Store.now(),analysis.adapter(),
                analysis.proposal()==null?null:store.json(analysis.proposal()),store.json(analysis.policies()),store.json(analysis.trace()),analysis.valid(),analysis.reason());
            Proposal p=analysis.proposal();
            if(!analysis.valid() || p==null || !Boolean.TRUE.equals(p.sufficientInformation()) || p.team()==Team.REVIEW) {
                store.review(id,analysis.valid()?p.explanation():analysis.reason());
                return false;
            }
            store.jdbc().update("UPDATE tickets SET status='READY',category=?,priority=?,team=?,explanation=?,updated_at=? WHERE id=? AND status='PROCESSING'",
                p.category().name(),p.priority().name(),p.team().name(),p.explanation(),Store.now(),id);
            return true;
        });
        if(ready) send(id,Status.READY);
        return store.ticket(id);
    }
    private void send(String id,Status expected) {
        String attempt=Store.id();
        tx.executeWithoutResult(s -> {
            if(!store.claim(id,expected,Status.SENDING)) throw new DomainException(409,"Estado não permite envio");
            store.jdbc().update("UPDATE tickets SET delivery_adapter=? WHERE id=?",gateway.name(),id);
            store.jdbc().update("INSERT INTO delivery_attempts VALUES (?,?,?,?,?,?,NULL,NULL)",attempt,id,Store.now(),gateway.name(),"STARTED","Envio iniciado; sem confirmação ainda");
        });
        IssueGateway.Result result;
        try { result=gateway.create(store.ticket(id)); }
        catch(Exception e) { result=IssueGateway.Result.unknown("Adaptador interrompido; resultado desconhecido"); }
        finish(id,attempt,result);
    }
    private void finish(String id,String attempt,IssueGateway.Result result) {
        tx.executeWithoutResult(s -> {
            var outcome=result.outcome();
            if(outcome==IssueGateway.Outcome.CONFIRMED && (result.externalId()==null || result.url()==null))
                throw new IllegalStateException("Confirmação incompleta do adaptador");
            Status status=switch(outcome) { case CONFIRMED -> Status.FORWARDED; case REJECTED -> Status.DELIVERY_FAILED; case UNKNOWN -> Status.DELIVERY_UNKNOWN; };
            store.jdbc().update("UPDATE delivery_attempts SET outcome=?,detail=?,external_id=?,external_url=? WHERE id=?",
                outcome.name(),result.detail(),result.externalId(),result.url(),attempt);
            store.jdbc().update("UPDATE tickets SET status=?,external_id=?,external_url=?,updated_at=? WHERE id=? AND status='SENDING'",
                status.name(),result.externalId(),result.url(),Store.now(),id);
        });
    }
    public Ticket retry(String id) {
        var t=store.ticket(id);
        if(t.status()!=Status.DELIVERY_FAILED || !gateway.name().equals(t.deliveryAdapter())) throw new DomainException(409,"Somente rejeição explícita pelo mesmo adaptador permite nova tentativa");
        send(id,Status.DELIVERY_FAILED);
        return store.ticket(id);
    }
    public Ticket reconcile(String id) {
        var t=store.ticket(id);
        if(t.status()!=Status.DELIVERY_UNKNOWN && t.status()!=Status.SENDING) throw new DomainException(409,"Chamado não tem envio inconclusivo");
        if(!gateway.name().equals(t.deliveryAdapter())) throw new DomainException(409,"Reative o adaptador original para reconciliar");
        var result=gateway.find(t);
        tx.executeWithoutResult(s -> {
            // Row lock serializes concurrent reconciliations; reconciliation never creates an issue.
            store.jdbc().queryForList("SELECT id FROM tickets WHERE id=? FOR UPDATE",id);
            var current=store.ticket(id);
            if(current.status()!=Status.SENDING && current.status()!=Status.DELIVERY_UNKNOWN) return;
            store.jdbc().update("INSERT INTO delivery_attempts VALUES (?,?,?,?,?,?,?,?)",Store.id(),id,Store.now(),gateway.name(),result.outcome().name(),result.detail(),result.externalId(),result.url());
            if(result.outcome()==IssueGateway.Outcome.CONFIRMED && result.externalId()!=null && result.url()!=null)
                store.jdbc().update("UPDATE tickets SET status='FORWARDED',external_id=?,external_url=?,updated_at=? WHERE id=?",result.externalId(),result.url(),Store.now(),id);
            else store.jdbc().update("UPDATE tickets SET status='DELIVERY_UNKNOWN',updated_at=? WHERE id=?",Store.now(),id);
        });
        return store.ticket(id);
    }
    public Ticket reanalyze(String id,String note) {
        tx.executeWithoutResult(s -> {
            if(!store.claim(id,Status.REVIEW,Status.RECEIVED)) throw new DomainException(409,"Somente revisão humana permite reanálise");
            audit(id,"REANALYZE",note);
        });
        return process(id);
    }
    public Ticket close(String id,String note) {
        tx.executeWithoutResult(s -> {
            if(!store.claim(id,Status.FORWARDED,Status.CLOSED)) throw new DomainException(409,"Só um encaminhamento confirmado permite encerramento humano");
            audit(id,"CLOSE",note);
        });
        return store.ticket(id);
    }
    public Ticket recover(String id,String note) {
        var ticket=store.ticket(id);
        if(java.time.Instant.parse(ticket.updatedAt()).isAfter(java.time.Instant.now().minusSeconds(900)))
            throw new DomainException(409,"Aguarde 15 minutos antes de recuperar uma análise potencialmente ativa");
        tx.executeWithoutResult(s -> {
            if(!store.claim(id,Status.PROCESSING,Status.REVIEW)) throw new DomainException(409,"Recuperação disponível somente para análise interrompida");
            store.review(id,"Análise interrompida; aguardando revisão humana");
            audit(id,"RECOVER",note);
        });
        return store.ticket(id);
    }
    private void audit(String id,String action,String note) {
        store.jdbc().update("INSERT INTO ticket_actions VALUES (?,?,?,?,?)",Store.id(),id,action,note,Store.now());
    }
}
